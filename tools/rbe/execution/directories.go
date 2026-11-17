package execution

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"

	"github.com/define-lang/define/tools/rbe/cas"
)

// Creating and deleting the directories of an action's input tree contends
// for the file system's inode allocation locks with every other action doing
// the same. An action that runs the same command as an earlier one, such as
// the same test after a small change, has nearly the same input tree at the
// same paths, so it reuses the earlier action's directory and changes only
// what differs.
type directoryPool struct {
	mutex sync.Mutex
	// Oldest first.
	idle    []idleDirectory
	maxIdle int
	created uint64
}

type idleDirectory struct {
	command string
	path    string
}

// commandIdentity is the same for the actions that would stage their inputs at
// the same paths. Environment variables are left out, since they differ
// between shards of a test.
func commandIdentity(command *repb.Command) string {
	parts := []string{command.WorkingDirectory}
	parts = append(parts, command.Arguments...)
	parts = append(parts, "")
	parts = append(parts, outputPaths(command)...)
	return strings.Join(parts, "\x00")
}

// take returns an idle directory that ran the same command, or a new path and
// false.
func (pool *directoryPool) take(workRoot string, command string) (string, bool) {
	pool.mutex.Lock()
	defer pool.mutex.Unlock()
	for index := len(pool.idle) - 1; index >= 0; index-- {
		if pool.idle[index].command == command {
			path := pool.idle[index].path
			pool.idle = append(pool.idle[:index], pool.idle[index+1:]...)
			return path, true
		}
	}
	pool.created++
	return filepath.Join(workRoot, strconv.FormatUint(pool.created, 10)), false
}

// put makes a finished action's directory idle, and returns the directories
// that no longer fit and must be deleted. Idle directories keep their inputs'
// blobs on disk even after the store evicts them, so maxIdle also bounds that
// space.
func (pool *directoryPool) put(command string, path string) []string {
	pool.mutex.Lock()
	defer pool.mutex.Unlock()
	pool.idle = append(pool.idle, idleDirectory{command: command, path: path})
	var evicted []string
	for len(pool.idle) > pool.maxIdle {
		evicted = append(evicted, pool.idle[0].path)
		pool.idle = pool.idle[1:]
	}
	return evicted
}

// prepareReused readies an earlier action's directory for a new action.
func prepareReused(actionDirectory string, tempDirectory string) error {
	// The store took the earlier action's stdout and stderr files as blobs by
	// linking them, so writing to them would change those blobs.
	for _, name := range []string{"stdout", "stderr"} {
		if err := os.Remove(filepath.Join(actionDirectory, name)); err != nil && !errors.Is(err, fs.ErrNotExist) {
			return err
		}
	}
	if err := cas.RemoveTree(tempDirectory); err != nil {
		return err
	}
	return os.Mkdir(tempDirectory, 0o755)
}

// restage makes an existing tree at path match the input tree rootKey,
// keeping what already matches. Outputs and other files that an earlier
// action left there are deleted, the same way as inputs that changed, since
// the store may hold them as blobs.
func (executor *Executor) restage(rootKey cas.Key, path string) error {
	missing := &cas.MissingBlobsError{}
	var symlinks []symlink
	if err := executor.restageDirectory(rootKey, path, missing, &symlinks); err != nil {
		return err
	}
	if len(missing.Keys) > 0 {
		return missing
	}
	return createSymlinks(symlinks)
}

func (executor *Executor) restageDirectory(key cas.Key, path string, missing *cas.MissingBlobsError, symlinks *[]symlink) error {
	directory, err := executor.store.Directory(key)
	var missingErr *cas.MissingBlobsError
	if errors.As(err, &missingErr) {
		missing.Keys = append(missing.Keys, missingErr.Keys...)
		return nil
	}
	if err != nil {
		return err
	}
	// An earlier action may have made the directory read-only, which would
	// keep its entries from being deleted.
	if err := os.Chmod(path, 0o755); err != nil {
		return err
	}
	files := map[string]*repb.FileNode{}
	for _, file := range directory.Files {
		files[file.Name] = file
	}
	directories := map[string]*repb.DirectoryNode{}
	for _, child := range directory.Directories {
		directories[child.Name] = child
	}
	links := map[string]*repb.SymlinkNode{}
	for _, link := range directory.Symlinks {
		links[link.Name] = link
	}
	entries, err := os.ReadDir(path)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		name := entry.Name()
		entryPath := filepath.Join(path, name)
		keep, err := executor.reuseEntry(entry, entryPath, files[name], directories[name], links[name], missing, symlinks)
		if err != nil {
			return err
		}
		if keep {
			delete(files, name)
			delete(directories, name)
			delete(links, name)
			continue
		}
		if entry.IsDir() {
			err = cas.RemoveTree(entryPath)
		} else {
			err = os.Remove(entryPath)
		}
		if err != nil {
			return err
		}
	}
	remaining := &repb.Directory{}
	for _, file := range directory.Files {
		if files[file.Name] != nil {
			remaining.Files = append(remaining.Files, file)
		}
	}
	for _, child := range directory.Directories {
		if directories[child.Name] != nil {
			remaining.Directories = append(remaining.Directories, child)
		}
	}
	for _, link := range directory.Symlinks {
		if links[link.Name] != nil {
			remaining.Symlinks = append(remaining.Symlinks, link)
		}
	}
	return executor.stageEntries(remaining, path, missing, symlinks)
}

// reuseEntry reports whether an existing entry already is the input that the
// directory should have under its name, restaging it if it is a directory.
func (executor *Executor) reuseEntry(entry fs.DirEntry, path string, file *repb.FileNode, child *repb.DirectoryNode, link *repb.SymlinkNode, missing *cas.MissingBlobsError, symlinks *[]symlink) (bool, error) {
	switch {
	case file != nil:
		fileKey, err := cas.KeyFromDigest(file.Digest)
		if err != nil {
			return false, err
		}
		info, err := entry.Info()
		if err != nil {
			return false, err
		}
		return executor.store.IsLink(fileKey, info)
	case child != nil && entry.IsDir():
		childKey, err := cas.KeyFromDigest(child.Digest)
		if err != nil {
			return false, err
		}
		return true, executor.restageDirectory(childKey, path, missing, symlinks)
	case link != nil && entry.Type()&fs.ModeSymlink != 0:
		target, err := os.Readlink(path)
		if err != nil {
			return false, err
		}
		return target == link.Target, nil
	default:
		return false, nil
	}
}
