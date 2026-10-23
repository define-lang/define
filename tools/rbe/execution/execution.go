// Package execution runs REAPI actions in directories built from a local
// content-addressed store.
package execution

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"google.golang.org/protobuf/types/known/timestamppb"

	"github.com/define-lang/define/tools/rbe/cas"
)

// An action that sets no timeout of its own gets this one.
const defaultTimeout = 15 * time.Minute

// TimeoutError reports an action that ran out of time. Its partial result is
// still returned with it.
type TimeoutError struct {
	Timeout time.Duration
}

func (err *TimeoutError) Error() string {
	return fmt.Sprintf("action exceeded its timeout of %s", err.Timeout)
}

// Executor runs actions. At most `slots` actions are staged or running at
// once.
type Executor struct {
	store      *cas.Store
	workRoot   string
	workerName string
	slots      chan struct{}
	deletions  chan string
	count      atomic.Uint64
}

// New creates an executor that builds action directories under workRoot,
// which must be on the same filesystem as the store, and deletes any left
// there.
func New(store *cas.Store, workRoot string, slots int, deleters int) (*Executor, error) {
	if err := os.RemoveAll(workRoot); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(workRoot, 0o755); err != nil {
		return nil, err
	}
	hostname, err := os.Hostname()
	if err != nil {
		return nil, err
	}
	executor := &Executor{
		store:      store,
		workRoot:   workRoot,
		workerName: hostname,
		slots:      make(chan struct{}, slots),
		deletions:  make(chan string, 4096),
	}
	for range deleters {
		go executor.delete()
	}
	return executor, nil
}

// delete removes finished action directories. Deleting them after the result
// is sent keeps it off every action's critical path.
func (executor *Executor) delete() {
	for directory := range executor.deletions {
		if err := os.RemoveAll(directory); err != nil {
			// Read-only directories that an action left behind cannot be
			// emptied until they are writable again.
			makeWritable(directory)
			if err := os.RemoveAll(directory); err != nil {
				panic(fmt.Sprintf("deleting action directory %s: %v", directory, err))
			}
		}
	}
}

func makeWritable(root string) {
	_ = filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err == nil && entry.IsDir() {
			_ = os.Chmod(path, 0o755)
		}
		return nil
	})
}

// Execute runs an action and returns its result. A *cas.MissingBlobsError
// reports inputs that the store does not hold, and a *TimeoutError comes with
// the partial result of an action that ran out of time.
func (executor *Executor) Execute(ctx context.Context, action *repb.Action, command *repb.Command) (*repb.ActionResult, error) {
	metadata := &repb.ExecutedActionMetadata{Worker: executor.workerName, QueuedTimestamp: timestamppb.Now()}
	select {
	case executor.slots <- struct{}{}:
	case <-ctx.Done():
		return nil, ctx.Err()
	}
	defer func() { <-executor.slots }()

	metadata.WorkerStartTimestamp = timestamppb.Now()
	actionDirectory := filepath.Join(executor.workRoot, strconv.FormatUint(executor.count.Add(1), 10))
	defer func() { executor.deletions <- actionDirectory }()
	inputRoot := filepath.Join(actionDirectory, "root")
	tempDirectory := filepath.Join(actionDirectory, "tmp")
	for _, directory := range []string{inputRoot, tempDirectory} {
		if err := os.MkdirAll(directory, 0o755); err != nil {
			return nil, err
		}
	}

	metadata.InputFetchStartTimestamp = timestamppb.Now()
	inputRootKey, err := cas.KeyFromDigest(action.InputRootDigest)
	if err != nil {
		return nil, err
	}
	if err := executor.stage(inputRootKey, inputRoot); err != nil {
		return nil, err
	}
	workingDirectory, err := resolveRelative(inputRoot, command.WorkingDirectory)
	if err != nil {
		return nil, err
	}
	outputPaths := outputPaths(command)
	for _, outputPath := range outputPaths {
		path, err := resolveRelative(workingDirectory, outputPath)
		if err != nil {
			return nil, err
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return nil, err
		}
	}
	metadata.InputFetchCompletedTimestamp = timestamppb.Now()

	timeout := defaultTimeout
	if action.Timeout != nil && action.Timeout.AsDuration() > 0 {
		timeout = action.Timeout.AsDuration()
	}
	metadata.ExecutionStartTimestamp = timestamppb.Now()
	exitCode, runErr := run(ctx, command, workingDirectory, actionDirectory, tempDirectory, timeout)
	metadata.ExecutionCompletedTimestamp = timestamppb.Now()
	var timeoutErr *TimeoutError
	if runErr != nil && !errors.As(runErr, &timeoutErr) {
		return nil, runErr
	}

	metadata.OutputUploadStartTimestamp = timestamppb.Now()
	result, err := executor.collect(workingDirectory, outputPaths)
	if err != nil {
		return nil, err
	}
	result.ExitCode = exitCode
	for _, stream := range []struct {
		name   string
		digest **repb.Digest
	}{{"stdout", &result.StdoutDigest}, {"stderr", &result.StderrDigest}} {
		key, err := executor.store.AddFile(filepath.Join(actionDirectory, stream.name))
		if err != nil {
			return nil, err
		}
		*stream.digest = key.Digest()
	}
	metadata.OutputUploadCompletedTimestamp = timestamppb.Now()
	metadata.WorkerCompletedTimestamp = timestamppb.Now()
	result.ExecutionMetadata = metadata
	return result, runErr
}

// resolveRelative joins a path from an action to a directory, refusing paths
// that leave it.
func resolveRelative(base string, relative string) (string, error) {
	if relative != "" && !filepath.IsLocal(relative) {
		return "", fmt.Errorf("path %q is not relative to the action's directory", relative)
	}
	return filepath.Join(base, relative), nil
}

func outputPaths(command *repb.Command) []string {
	if len(command.OutputPaths) > 0 {
		return command.OutputPaths
	}
	return append(slices.Clone(command.OutputFiles), command.OutputDirectories...)
}

// stage builds an input tree by hardlinking its files from the store.
func (executor *Executor) stage(rootKey cas.Key, path string) error {
	missing := &cas.MissingBlobsError{}
	if err := executor.stageDirectory(rootKey, path, missing); err != nil {
		return err
	}
	if len(missing.Keys) > 0 {
		return missing
	}
	return nil
}

func (executor *Executor) stageDirectory(key cas.Key, path string, missing *cas.MissingBlobsError) error {
	directory, err := executor.store.Directory(key)
	var missingErr *cas.MissingBlobsError
	if errors.As(err, &missingErr) {
		missing.Keys = append(missing.Keys, missingErr.Keys...)
		return nil
	}
	if err != nil {
		return err
	}
	for _, file := range directory.Files {
		fileKey, err := cas.KeyFromDigest(file.Digest)
		if err != nil {
			return err
		}
		err = executor.store.Link(fileKey, filepath.Join(path, file.Name))
		if errors.As(err, &missingErr) {
			missing.Keys = append(missing.Keys, missingErr.Keys...)
			continue
		}
		if err != nil {
			return err
		}
	}
	for _, symlink := range directory.Symlinks {
		if err := os.Symlink(symlink.Target, filepath.Join(path, symlink.Name)); err != nil {
			return err
		}
	}
	for _, child := range directory.Directories {
		childKey, err := cas.KeyFromDigest(child.Digest)
		if err != nil {
			return err
		}
		childPath := filepath.Join(path, child.Name)
		if err := os.Mkdir(childPath, 0o755); err != nil {
			return err
		}
		if err := executor.stageDirectory(childKey, childPath, missing); err != nil {
			return err
		}
	}
	return nil
}

// run runs a command in its own process group and kills the whole group when
// the command ends, so that no process it started outlives the action.
func run(ctx context.Context, command *repb.Command, workingDirectory string, actionDirectory string, tempDirectory string, timeout time.Duration) (int32, error) {
	if len(command.Arguments) == 0 {
		return 0, errors.New("command has no arguments")
	}
	environment := make([]string, 0, len(command.EnvironmentVariables)+1)
	searchPath := ""
	hasTempDirectory := false
	for _, variable := range command.EnvironmentVariables {
		environment = append(environment, variable.Name+"="+variable.Value)
		switch variable.Name {
		case "PATH":
			searchPath = variable.Value
		case "TMPDIR":
			hasTempDirectory = true
		}
	}
	// Actions that share /tmp collide on fixed file names there.
	if !hasTempDirectory {
		environment = append(environment, "TMPDIR="+tempDirectory)
	}
	program, err := findProgram(command.Arguments[0], workingDirectory, searchPath)
	if err != nil {
		return 0, err
	}
	stdout, err := os.Create(filepath.Join(actionDirectory, "stdout"))
	if err != nil {
		return 0, err
	}
	defer stdout.Close()
	stderr, err := os.Create(filepath.Join(actionDirectory, "stderr"))
	if err != nil {
		return 0, err
	}
	defer stderr.Close()

	process := &exec.Cmd{
		Path:        program,
		Args:        command.Arguments,
		Env:         environment,
		Dir:         workingDirectory,
		Stdout:      stdout,
		Stderr:      stderr,
		SysProcAttr: &syscall.SysProcAttr{Setpgid: true},
	}
	if err := process.Start(); err != nil {
		return 0, fmt.Errorf("starting %s: %w", command.Arguments[0], err)
	}
	processGroup := process.Process.Pid
	waited := make(chan error, 1)
	go func() { waited <- process.Wait() }()
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	var waitErr error
	var runErr error
	select {
	case waitErr = <-waited:
	case <-timer.C:
		_ = syscall.Kill(-processGroup, syscall.SIGKILL)
		waitErr = <-waited
		runErr = &TimeoutError{Timeout: timeout}
	case <-ctx.Done():
		_ = syscall.Kill(-processGroup, syscall.SIGKILL)
		<-waited
		return 0, ctx.Err()
	}
	_ = syscall.Kill(-processGroup, syscall.SIGKILL)
	var exitErr *exec.ExitError
	if errors.As(waitErr, &exitErr) {
		if status, ok := exitErr.Sys().(syscall.WaitStatus); ok && status.Signaled() {
			return 128 + int32(status.Signal()), runErr
		}
		return int32(exitErr.ExitCode()), runErr
	}
	return 0, errors.Join(waitErr, runErr)
}

// findProgram resolves a command's program the way REAPI specifies: a path
// with a separator is relative to the working directory, and a bare name is
// searched for in the command's own PATH.
func findProgram(name string, workingDirectory string, searchPath string) (string, error) {
	if strings.Contains(name, "/") {
		if filepath.IsAbs(name) {
			return name, nil
		}
		return filepath.Join(workingDirectory, name), nil
	}
	for _, directory := range filepath.SplitList(searchPath) {
		if !filepath.IsAbs(directory) {
			directory = filepath.Join(workingDirectory, directory)
		}
		candidate := filepath.Join(directory, name)
		if info, err := os.Stat(candidate); err == nil && info.Mode().IsRegular() && info.Mode()&0o111 != 0 {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("program %q is not in PATH %q", name, searchPath)
}

// collect adds an action's outputs to the store and describes them.
func (executor *Executor) collect(workingDirectory string, outputPaths []string) (*repb.ActionResult, error) {
	result := &repb.ActionResult{}
	for _, outputPath := range outputPaths {
		path := filepath.Join(workingDirectory, outputPath)
		info, err := os.Lstat(path)
		if errors.Is(err, fs.ErrNotExist) {
			continue
		}
		if err != nil {
			return nil, err
		}
		switch {
		case info.Mode()&fs.ModeSymlink != 0:
			target, err := os.Readlink(path)
			if err != nil {
				return nil, err
			}
			result.OutputSymlinks = append(result.OutputSymlinks, &repb.OutputSymlink{Path: outputPath, Target: target})
		case info.IsDir():
			tree := &repb.Tree{}
			root, err := executor.collectDirectory(path, tree)
			if err != nil {
				return nil, err
			}
			tree.Root = root
			treeKey, err := executor.store.PutMessage(tree)
			if err != nil {
				return nil, err
			}
			result.OutputDirectories = append(result.OutputDirectories, &repb.OutputDirectory{
				Path:       outputPath,
				TreeDigest: treeKey.Digest(),
			})
		default:
			key, err := executor.store.AddFile(path)
			if err != nil {
				return nil, err
			}
			result.OutputFiles = append(result.OutputFiles, &repb.OutputFile{
				Path:         outputPath,
				Digest:       key.Digest(),
				IsExecutable: info.Mode()&0o111 != 0,
			})
		}
	}
	return result, nil
}

// collectDirectory adds an output directory's files to the store and returns
// its Directory message, appending its subdirectories' messages to the tree.
func (executor *Executor) collectDirectory(path string, tree *repb.Tree) (*repb.Directory, error) {
	entries, err := os.ReadDir(path)
	if err != nil {
		return nil, err
	}
	directory := &repb.Directory{}
	for _, entry := range entries {
		entryPath := filepath.Join(path, entry.Name())
		info, err := entry.Info()
		if err != nil {
			return nil, err
		}
		switch {
		case info.Mode()&fs.ModeSymlink != 0:
			target, err := os.Readlink(entryPath)
			if err != nil {
				return nil, err
			}
			directory.Symlinks = append(directory.Symlinks, &repb.SymlinkNode{Name: entry.Name(), Target: target})
		case info.IsDir():
			child, err := executor.collectDirectory(entryPath, tree)
			if err != nil {
				return nil, err
			}
			childKey, err := cas.KeyFromMessage(child)
			if err != nil {
				return nil, err
			}
			tree.Children = append(tree.Children, child)
			directory.Directories = append(directory.Directories, &repb.DirectoryNode{Name: entry.Name(), Digest: childKey.Digest()})
		default:
			key, err := executor.store.AddFile(entryPath)
			if err != nil {
				return nil, err
			}
			directory.Files = append(directory.Files, &repb.FileNode{
				Name:         entry.Name(),
				Digest:       key.Digest(),
				IsExecutable: info.Mode()&0o111 != 0,
			})
		}
	}
	return directory, nil
}
