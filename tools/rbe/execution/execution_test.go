package execution

import (
	"context"
	"crypto/sha256"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"testing"
	"time"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"google.golang.org/protobuf/types/known/durationpb"

	"github.com/define-lang/define/tools/rbe/cas"
	"github.com/define-lang/define/tools/rbe/testprogram"
)

func TestMain(m *testing.M) {
	testprogram.Main(m)
}

func newExecutor(t *testing.T) (*Executor, *cas.Store) {
	t.Helper()
	return newReusingExecutor(t, 0)
}

func put(t *testing.T, store *cas.Store, contents string) *repb.Digest {
	t.Helper()
	key := cas.Key{Hash: sha256.Sum256([]byte(contents)), Size: int64(len(contents))}
	if err := store.Put(key, []byte(contents)); err != nil {
		t.Fatal(err)
	}
	return key.Digest()
}

func putDirectory(t *testing.T, store *cas.Store, directory *repb.Directory) *repb.Digest {
	t.Helper()
	key, err := store.PutMessage(directory)
	if err != nil {
		t.Fatal(err)
	}
	return key.Digest()
}

func readBlob(t *testing.T, store *cas.Store, digest *repb.Digest) string {
	t.Helper()
	key, err := cas.KeyFromDigest(digest)
	if err != nil {
		t.Fatal(err)
	}
	contents, err := store.Read(key)
	if err != nil {
		t.Fatal(err)
	}
	return string(contents)
}

func TestRunsCommandOnStagedInputsAndCollectsOutputs(t *testing.T) {
	executor, store := newExecutor(t)
	source := putDirectory(t, store, &repb.Directory{
		Files: []*repb.FileNode{{Name: "input.txt", Digest: put(t, store, "hello")}},
	})
	root := putDirectory(t, store, &repb.Directory{
		Directories: []*repb.DirectoryNode{{Name: "src", Digest: source}},
	})
	command := testprogram.Command(t,
		"copy", "src/input.txt", "out/file.txt",
		"write", "out/dir/sub/nested.txt", "nested\n",
		"stderr", "said\n",
	)
	command.OutputPaths = []string{"out/file.txt", "out/dir", "out/absent"}

	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, command)
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 0 {
		t.Fatalf("exit code %d, stderr %q", result.ExitCode, readBlob(t, store, result.StderrDigest))
	}
	if len(result.OutputFiles) != 1 || result.OutputFiles[0].Path != "out/file.txt" {
		t.Fatalf("output files %v", result.OutputFiles)
	}
	if contents := readBlob(t, store, result.OutputFiles[0].Digest); contents != "hello" {
		t.Fatalf("output file contains %q", contents)
	}
	if len(result.OutputDirectories) != 1 || result.OutputDirectories[0].Path != "out/dir" {
		t.Fatalf("output directories %v", result.OutputDirectories)
	}
	treeKey, err := cas.KeyFromDigest(result.OutputDirectories[0].TreeDigest)
	if err != nil {
		t.Fatal(err)
	}
	tree := &repb.Tree{}
	if err := store.ReadMessage(treeKey, tree); err != nil {
		t.Fatal(err)
	}
	if len(tree.Root.Directories) != 1 || tree.Root.Directories[0].Name != "sub" || len(tree.Children) != 1 {
		t.Fatalf("tree %v", tree)
	}
	if contents := readBlob(t, store, tree.Children[0].Files[0].Digest); contents != "nested\n" {
		t.Fatalf("nested output contains %q", contents)
	}
	if stderr := readBlob(t, store, result.StderrDigest); stderr != "said\n" {
		t.Fatalf("stderr %q", stderr)
	}
	metadata := result.ExecutionMetadata
	if metadata.ExecutionCompletedTimestamp.AsTime().Before(metadata.ExecutionStartTimestamp.AsTime()) {
		t.Fatalf("metadata %v", metadata)
	}
}

func TestRunsInWorkingDirectoryWithItsOwnTempDirectory(t *testing.T) {
	executor, store := newExecutor(t)
	root := putDirectory(t, store, &repb.Directory{
		Directories: []*repb.DirectoryNode{{Name: "pkg", Digest: putDirectory(t, store, &repb.Directory{})}},
	})
	command := testprogram.Command(t, "where", "where", "checktemp", os.TempDir())
	command.OutputPaths = []string{"where"}
	command.WorkingDirectory = "pkg"

	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, command)
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 0 {
		t.Fatalf("exit code %d", result.ExitCode)
	}
	if contents := readBlob(t, store, result.OutputFiles[0].Digest); contents != "pkg" {
		t.Fatalf("ran in %q", contents)
	}
}

func TestReportsMissingInputs(t *testing.T) {
	executor, store := newExecutor(t)
	missingFile := cas.Key{Hash: sha256.Sum256([]byte("absent file")), Size: 11}
	missingDirectory := cas.Key{Hash: sha256.Sum256([]byte("absent directory")), Size: 16}
	root := putDirectory(t, store, &repb.Directory{
		Files:       []*repb.FileNode{{Name: "file", Digest: missingFile.Digest()}},
		Directories: []*repb.DirectoryNode{{Name: "dir", Digest: missingDirectory.Digest()}},
	})

	_, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, testprogram.Command(t))
	var missingErr *cas.MissingBlobsError
	if !errors.As(err, &missingErr) {
		t.Fatalf("returned %v", err)
	}
	if !slices.Equal(missingErr.Keys, []cas.Key{missingFile, missingDirectory}) {
		t.Fatalf("missing %v", missingErr.Keys)
	}
}

func TestTimeoutKillsTheActionAndKeepsItsOutput(t *testing.T) {
	executor, store := newExecutor(t)
	root := putDirectory(t, store, &repb.Directory{})
	action := &repb.Action{InputRootDigest: root, Timeout: durationpb.New(200 * time.Millisecond)}

	result, err := executor.Execute(context.Background(), action, testprogram.Command(t, "stdout", "started\n", "sleep", "60"))
	var timeoutErr *TimeoutError
	if !errors.As(err, &timeoutErr) {
		t.Fatalf("returned %v", err)
	}
	if stdout := readBlob(t, store, result.StdoutDigest); stdout != "started\n" {
		t.Fatalf("stdout %q", stdout)
	}
}

func TestNoProcessOutlivesItsAction(t *testing.T) {
	executor, store := newExecutor(t)
	root := putDirectory(t, store, &repb.Directory{})
	marker := filepath.Join(t.TempDir(), "survived")

	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root},
		testprogram.Command(t, "spawn", marker))
	if err != nil || result.ExitCode != 0 {
		t.Fatalf("result %v, %v", result, err)
	}
	time.Sleep(1500 * time.Millisecond)
	if _, err := os.Stat(marker); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("a background process kept running after its action finished")
	}
}

func TestReportsExitCode(t *testing.T) {
	executor, store := newExecutor(t)
	root := putDirectory(t, store, &repb.Directory{})
	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, testprogram.Command(t, "exit", "3"))
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 3 {
		t.Errorf("exited with %d", result.ExitCode)
	}
}

func TestFollowsSymlinksToDirectoriesThroughOtherSymlinks(t *testing.T) {
	executor, store := newExecutor(t)
	// A Directory lists its symlinks by name, so "a" comes before the "b" it
	// leads through.
	root := putDirectory(t, store, &repb.Directory{
		Directories: []*repb.DirectoryNode{{Name: "dir", Digest: putDirectory(t, store, &repb.Directory{
			Files: []*repb.FileNode{{Name: "file.txt", Digest: put(t, store, "through links")}},
		})}},
		Symlinks: []*repb.SymlinkNode{{Name: "a", Target: "b"}, {Name: "b", Target: "dir"}},
	})
	command := testprogram.Command(t, "copy", "a/file.txt", "out")
	command.OutputPaths = []string{"out"}

	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, command)
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 0 {
		t.Fatalf("exit code %d, stderr %q", result.ExitCode, readBlob(t, store, result.StderrDigest))
	}
	if contents := readBlob(t, store, result.OutputFiles[0].Digest); contents != "through links" {
		t.Fatalf("output file contains %q", contents)
	}
}

func TestFindsProgramInCommandPath(t *testing.T) {
	directory := t.TempDir()
	fileName := "tool"
	if runtime.GOOS == "windows" {
		fileName = "tool.exe"
	}
	program := filepath.Join(directory, fileName)
	if err := os.WriteFile(program, nil, 0o755); err != nil {
		t.Fatal(err)
	}
	nonexistent := filepath.Join(t.TempDir(), "nonexistent")
	found, err := findProgram("tool", t.TempDir(), nonexistent+string(os.PathListSeparator)+directory)
	if err != nil || found != program {
		t.Fatalf("found %q, %v", found, err)
	}
	if _, err := findProgram("tool", t.TempDir(), nonexistent); err == nil || !strings.Contains(err.Error(), "tool") {
		t.Fatalf("found a program that is not in PATH: %v", err)
	}
	work := filepath.FromSlash("/work")
	relative, err := findProgram("bin/tool", work, "")
	if err != nil || relative != filepath.Join(work, "bin", "tool") {
		t.Fatalf("resolved %q, %v", relative, err)
	}
}

func TestRejectsPathsThatLeaveTheActionDirectory(t *testing.T) {
	work := filepath.FromSlash("/work")
	for _, path := range []string{"../escape", "/absolute"} {
		if _, err := resolveRelative(work, path); err == nil {
			t.Errorf("accepted %q", path)
		}
	}
	for path, expected := range map[string]string{"": work, ".": work, "a/b": filepath.Join(work, "a", "b")} {
		resolved, err := resolveRelative(work, path)
		if err != nil || resolved != expected {
			t.Errorf("resolved %q to %q, %v", path, resolved, err)
		}
	}
}

func newReusingExecutor(t *testing.T, idleDirectories int) (*Executor, *cas.Store) {
	t.Helper()
	root := t.TempDir()
	store, err := cas.Open(filepath.Join(root, "cas"), 1<<30, 100)
	if err != nil {
		t.Fatal(err)
	}
	executor, err := New(store, filepath.Join(root, "work"), 4, 1, idleDirectories)
	if err != nil {
		t.Fatal(err)
	}
	return executor, store
}

func TestReusedDirectoryHoldsExactlyTheNewInputs(t *testing.T) {
	executor, store := newReusingExecutor(t, 4)
	command := testprogram.Command(t, "script", "script")
	command.OutputPaths = []string{"out/tree.txt", "out/temp.txt"}
	first := putDirectory(t, store, &repb.Directory{
		Files: []*repb.FileNode{
			{Name: "change.txt", Digest: put(t, store, "old")},
			{Name: "gone.txt", Digest: put(t, store, "gone")},
			{Name: "keep.txt", Digest: put(t, store, "same")},
			{Name: "script", Digest: put(t, store, "write dir/extra.txt leftover\nreadonly dir\ntempwrite leftover\nwrite out/tree.txt first\nwrite out/temp.txt first\nstdout one")},
		},
		Directories: []*repb.DirectoryNode{
			{Name: "dir", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "inner.txt", Digest: put(t, store, "inner")}}})},
			{Name: "olddir", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "file", Digest: put(t, store, "old")}}})},
		},
		Symlinks: []*repb.SymlinkNode{{Name: "link", Target: "keep.txt"}, {Name: "relink", Target: "change.txt"}},
	})
	second := putDirectory(t, store, &repb.Directory{
		Files: []*repb.FileNode{
			{Name: "added.txt", Digest: put(t, store, "added")},
			{Name: "change.txt", Digest: put(t, store, "new")},
			{Name: "keep.txt", Digest: put(t, store, "same")},
			{Name: "script", Digest: put(t, store, "tree . out/tree.txt\ntemptree out/temp.txt\nstdout two")},
		},
		Directories: []*repb.DirectoryNode{
			{Name: "dir", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "inner.txt", Digest: put(t, store, "inner")}}})},
			{Name: "newdir", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "file", Digest: put(t, store, "new")}}})},
		},
		Symlinks: []*repb.SymlinkNode{{Name: "link", Target: "keep.txt"}, {Name: "relink", Target: "keep.txt"}},
	})

	firstResult, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: first}, command)
	if err != nil || firstResult.ExitCode != 0 {
		t.Fatalf("result %v, %v", firstResult, err)
	}
	secondResult, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: second}, command)
	if err != nil || secondResult.ExitCode != 0 {
		t.Fatalf("result %v, %v", secondResult, err)
	}

	if entries := workDirectoryEntries(t, executor); entries != 1 {
		t.Fatalf("%d action directories, so the second action did not reuse the first's", entries)
	}
	want := strings.Join([]string{
		"added.txt = added",
		"change.txt = new",
		"dir/",
		"dir/inner.txt = inner",
		"keep.txt = same",
		"link -> keep.txt",
		"newdir/",
		"newdir/file = new",
		"out/",
		"relink -> keep.txt",
		"script = tree . out/tree.txt\ntemptree out/temp.txt\nstdout two",
	}, "\n")
	if tree := readBlob(t, store, secondResult.OutputFiles[0].Digest); tree != want {
		t.Fatalf("the second action saw:\n%s\nwant:\n%s", tree, want)
	}
	if temp := readBlob(t, store, secondResult.OutputFiles[1].Digest); temp != "" {
		t.Fatalf("the second action's temporary directory holds:\n%s", temp)
	}
	// The store took the first action's outputs and stdout by linking them,
	// so the second action must not have written over them.
	for _, digest := range []*repb.Digest{firstResult.OutputFiles[0].Digest, firstResult.OutputFiles[1].Digest} {
		if contents := readBlob(t, store, digest); contents != "first" {
			t.Fatalf("the first action's output now holds %q", contents)
		}
	}
	if stdout := readBlob(t, store, firstResult.StdoutDigest); stdout != "one" {
		t.Fatalf("the first action's stdout now holds %q", stdout)
	}
	if stdout := readBlob(t, store, secondResult.StdoutDigest); stdout != "two" {
		t.Fatalf("the second action's stdout holds %q", stdout)
	}
}

func TestDeletesTheOldestIdleDirectoryBeyondTheLimit(t *testing.T) {
	executor, store := newReusingExecutor(t, 1)
	root := putDirectory(t, store, &repb.Directory{})
	for _, steps := range [][]string{{"stdout", "first"}, {"stdout", "second"}} {
		if _, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, testprogram.Command(t, steps...)); err != nil {
			t.Fatal(err)
		}
	}
	waitUntil(t, func() bool { return workDirectoryEntries(t, executor) == 1 })
	if _, err := os.Stat(filepath.Join(executor.workRoot, "2")); err != nil {
		t.Fatalf("the newest idle directory is gone: %v", err)
	}
}

func workDirectoryEntries(t *testing.T, executor *Executor) int {
	t.Helper()
	entries, err := os.ReadDir(executor.workRoot)
	if err != nil {
		t.Fatal(err)
	}
	return len(entries)
}

func waitUntil(t *testing.T, condition func() bool) {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for !condition() {
		if time.Now().After(deadline) {
			t.Fatal("timed out")
		}
		time.Sleep(10 * time.Millisecond)
	}
}

// scriptCommand runs the steps in the input file "script", so that actions
// that run the same command, and so reuse each other's directories, can do
// different things.
func scriptCommand(t *testing.T) *repb.Command {
	t.Helper()
	command := testprogram.Command(t, "script", "script")
	command.OutputPaths = []string{"out/tree.txt"}
	return command
}

func withScript(t *testing.T, store *cas.Store, directory *repb.Directory, script string) *repb.Digest {
	t.Helper()
	withScript := &repb.Directory{
		Files:       append(slices.Clone(directory.Files), &repb.FileNode{Name: "script", Digest: put(t, store, script)}),
		Directories: directory.Directories,
		Symlinks:    directory.Symlinks,
	}
	return putDirectory(t, store, withScript)
}

// inputTree runs an action that lists its input tree in a directory that an
// earlier action with the same command left behind.
func inputTree(t *testing.T, executor *Executor, store *cas.Store, inputs *repb.Directory) string {
	t.Helper()
	root := withScript(t, store, inputs, "tree . out/tree.txt")
	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, scriptCommand(t))
	if err != nil || result.ExitCode != 0 {
		t.Fatalf("result %v, %v", result, err)
	}
	if entries := workDirectoryEntries(t, executor); entries != 1 {
		t.Fatalf("%d action directories, so the action did not reuse the earlier one's", entries)
	}
	return readBlob(t, store, result.OutputFiles[0].Digest)
}

func TestReuseRestoresInputsThatAnActionChanged(t *testing.T) {
	executor, store := newReusingExecutor(t, 4)
	inputs := &repb.Directory{
		Files: []*repb.FileNode{
			{Name: "empty", Digest: cas.EmptyKey.Digest()},
			{Name: "file_to_directory", Digest: put(t, store, "file")},
			{Name: "same.txt", Digest: put(t, store, "same")},
		},
		Directories: []*repb.DirectoryNode{
			{Name: "deleted", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "x", Digest: put(t, store, "x")}}})},
			{Name: "directory_to_file", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "y", Digest: put(t, store, "y")}}})},
		},
		Symlinks: []*repb.SymlinkNode{{Name: "symlink_to_file", Target: "same.txt"}},
	}
	changes := strings.Join([]string{
		"remove same.txt write same.txt replaced",
		"remove deleted",
		"remove file_to_directory mkdir file_to_directory",
		"remove directory_to_file write directory_to_file file",
		"remove symlink_to_file write symlink_to_file file",
		"writable empty write empty filled",
		"write out/tree.txt first",
	}, "\n")
	root := withScript(t, store, inputs, changes)
	if result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, scriptCommand(t)); err != nil || result.ExitCode != 0 {
		t.Fatalf("result %v, %v", result, err)
	}

	want := strings.Join([]string{
		"deleted/",
		"deleted/x = x",
		"directory_to_file/",
		"directory_to_file/y = y",
		"empty = ",
		"file_to_directory = file",
		"out/",
		"same.txt = same",
		"script = tree . out/tree.txt",
		"symlink_to_file -> same.txt",
	}, "\n")
	if tree := inputTree(t, executor, store, inputs); tree != want {
		t.Fatalf("the second action saw:\n%s\nwant:\n%s", tree, want)
	}
}

func TestReuseDeletesSymlinksOutOfTheTreeWithoutFollowingThem(t *testing.T) {
	executor, store := newReusingExecutor(t, 4)
	outside := t.TempDir()
	if err := os.WriteFile(filepath.Join(outside, "outside.txt"), []byte("untouched"), 0o644); err != nil {
		t.Fatal(err)
	}
	inputs := &repb.Directory{
		Files:       []*repb.FileNode{{Name: "keep.txt", Digest: put(t, store, "keep")}},
		Directories: []*repb.DirectoryNode{{Name: "dir", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "inner.txt", Digest: put(t, store, "inner")}}})}},
	}
	changes := strings.Join([]string{
		"remove dir symlink " + outside + " dir",
		"remove keep.txt symlink " + filepath.Join(outside, "outside.txt") + " keep.txt",
		"write out/tree.txt first",
	}, "\n")
	root := withScript(t, store, inputs, changes)
	if result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, scriptCommand(t)); err != nil || result.ExitCode != 0 {
		t.Fatalf("result %v, %v", result, err)
	}

	want := strings.Join([]string{
		"dir/",
		"dir/inner.txt = inner",
		"keep.txt = keep",
		"out/",
		"script = tree . out/tree.txt",
	}, "\n")
	if tree := inputTree(t, executor, store, inputs); tree != want {
		t.Fatalf("the second action saw:\n%s\nwant:\n%s", tree, want)
	}
	entries, err := os.ReadDir(outside)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0].Name() != "outside.txt" {
		t.Fatalf("the directory outside the tree now holds %v", entries)
	}
	if contents, err := os.ReadFile(filepath.Join(outside, "outside.txt")); err != nil || string(contents) != "untouched" {
		t.Fatalf("the file outside the tree now holds %q, %v", contents, err)
	}
}

func TestReusesTheDirectoryOfAnActionThatTimedOut(t *testing.T) {
	executor, store := newReusingExecutor(t, 4)
	inputs := &repb.Directory{Files: []*repb.FileNode{{Name: "input.txt", Digest: put(t, store, "input")}}}
	root := withScript(t, store, inputs, "remove input.txt write junk.txt junk sleep 60")
	action := &repb.Action{InputRootDigest: root, Timeout: durationpb.New(500 * time.Millisecond)}
	var timeoutErr *TimeoutError
	if _, err := executor.Execute(context.Background(), action, scriptCommand(t)); !errors.As(err, &timeoutErr) {
		t.Fatalf("returned %v", err)
	}

	want := "input.txt = input\nout/\nscript = tree . out/tree.txt"
	if tree := inputTree(t, executor, store, inputs); tree != want {
		t.Fatalf("the second action saw:\n%s\nwant:\n%s", tree, want)
	}
}

func TestReusesTheDirectoryOfAnActionWithMissingInputs(t *testing.T) {
	executor, store := newReusingExecutor(t, 4)
	present := &repb.Directory{Files: []*repb.FileNode{{Name: "present.txt", Digest: put(t, store, "present")}}}
	missingFile := cas.Key{Hash: sha256.Sum256([]byte("later")), Size: 5}
	partial := &repb.Directory{
		Directories: []*repb.DirectoryNode{
			{Name: "a", Digest: putDirectory(t, store, present)},
			{Name: "b", Digest: putDirectory(t, store, &repb.Directory{Files: []*repb.FileNode{{Name: "later.txt", Digest: missingFile.Digest()}}})},
		},
	}
	root := withScript(t, store, partial, "write out/tree.txt first")
	var missingErr *cas.MissingBlobsError
	if _, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, scriptCommand(t)); !errors.As(err, &missingErr) {
		t.Fatalf("returned %v", err)
	}

	put(t, store, "later")
	want := "a/\na/present.txt = present\nb/\nb/later.txt = later\nout/\nscript = tree . out/tree.txt"
	if tree := inputTree(t, executor, store, partial); tree != want {
		t.Fatalf("the second action saw:\n%s\nwant:\n%s", tree, want)
	}
}

func TestConcurrentActionsWithTheSameCommandGetTheirOwnDirectories(t *testing.T) {
	executor, store := newReusingExecutor(t, 4)
	root := withScript(t, store, &repb.Directory{}, "write out/tree.txt first")
	if _, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, scriptCommand(t)); err != nil {
		t.Fatal(err)
	}

	slow := withScript(t, store, &repb.Directory{}, "sleep 1 tree . out/tree.txt")
	command := scriptCommand(t)
	trees := make(chan string, 2)
	errs := make(chan error, 2)
	for range 2 {
		go func() {
			result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: slow}, command)
			if err != nil {
				errs <- err
				return
			}
			key, err := cas.KeyFromDigest(result.OutputFiles[0].Digest)
			if err != nil {
				errs <- err
				return
			}
			contents, err := store.Read(key)
			errs <- err
			trees <- string(contents)
		}()
	}
	for range 2 {
		if err := <-errs; err != nil {
			t.Fatal(err)
		}
	}
	for range 2 {
		if tree := <-trees; tree != "out/\nscript = sleep 1 tree . out/tree.txt" {
			t.Fatalf("an action saw:\n%s", tree)
		}
	}
	if entries := workDirectoryEntries(t, executor); entries != 2 {
		t.Fatalf("%d action directories for two actions at once", entries)
	}
}

func TestReportsMissingInputsOfAReusedDirectory(t *testing.T) {
	executor, store := newReusingExecutor(t, 4)
	root := withScript(t, store, &repb.Directory{
		Directories: []*repb.DirectoryNode{{Name: "dir", Digest: putDirectory(t, store, &repb.Directory{})}},
	}, "write out/tree.txt first")
	if _, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, scriptCommand(t)); err != nil {
		t.Fatal(err)
	}

	missingFile := cas.Key{Hash: sha256.Sum256([]byte("absent file")), Size: 11}
	missingDirectory := cas.Key{Hash: sha256.Sum256([]byte("absent directory")), Size: 16}
	root = withScript(t, store, &repb.Directory{
		Files:       []*repb.FileNode{{Name: "file", Digest: missingFile.Digest()}},
		Directories: []*repb.DirectoryNode{{Name: "dir", Digest: missingDirectory.Digest()}},
	}, "tree . out/tree.txt")
	_, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, scriptCommand(t))
	var missingErr *cas.MissingBlobsError
	if !errors.As(err, &missingErr) {
		t.Fatalf("returned %v", err)
	}
	if !slices.Equal(missingErr.Keys, []cas.Key{missingDirectory, missingFile}) {
		t.Fatalf("missing %v", missingErr.Keys)
	}
	if entries := workDirectoryEntries(t, executor); entries != 1 {
		t.Fatalf("%d action directories, so the action did not reuse the earlier one's", entries)
	}
}
