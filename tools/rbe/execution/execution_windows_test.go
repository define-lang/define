package execution

import (
	"context"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"testing"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"golang.org/x/sys/windows"

	"github.com/define-lang/define/tools/rbe/cas"
	"github.com/define-lang/define/tools/rbe/testprogram"
)

func TestReportsWindowsStatusCodeExitCode(t *testing.T) {
	executor, store := newExecutor(t)
	root := putDirectory(t, store, &repb.Directory{})
	// STATUS_DLL_NOT_FOUND, which a program that is missing a DLL exits with.
	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, testprogram.Command(t, "exit", "-1073741515"))
	if err != nil {
		t.Fatal(err)
	}
	if uint32(result.ExitCode) != 0xC0000135 {
		t.Errorf("exited with %#x", uint32(result.ExitCode))
	}
}

func TestStagesNamesThatDifferOnlyInCase(t *testing.T) {
	executor, store := newExecutor(t)
	header := put(t, store, "header")
	include := putDirectory(t, store, &repb.Directory{
		Files: []*repb.FileNode{{Name: "Header.h", Digest: header}, {Name: "header.h", Digest: header}},
	})
	root := putDirectory(t, store, &repb.Directory{
		Directories: []*repb.DirectoryNode{{Name: "Include", Digest: include}, {Name: "include", Digest: include}},
	})
	command := testprogram.Command(t, "copy", "include/header.h", "out")
	command.OutputPaths = []string{"out"}

	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, command)
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 0 {
		t.Fatalf("exit code %d, stderr %q", result.ExitCode, readBlob(t, store, result.StderrDigest))
	}
	if contents := readBlob(t, store, result.OutputFiles[0].Digest); contents != "header" {
		t.Fatalf("output file contains %q", contents)
	}
}

// holdOpen opens path the way antivirus software scans a new file: without
// sharing deletion, so that deleting the file fails until the handle closes.
func holdOpen(t *testing.T, path string) windows.Handle {
	t.Helper()
	name, err := windows.UTF16PtrFromString(path)
	if err != nil {
		t.Fatal(err)
	}
	handle, err := windows.CreateFile(name, windows.GENERIC_READ,
		windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, 0, 0)
	if err != nil {
		t.Fatal(err)
	}
	return handle
}

func TestRemoveDirectoriesReturnsTheDirectoriesThatAreInUse(t *testing.T) {
	root := t.TempDir()
	held := filepath.Join(root, "held")
	free := filepath.Join(root, "free")
	for _, directory := range []string{held, free} {
		if err := os.MkdirAll(directory, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(directory, "file"), []byte("contents"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	handle := holdOpen(t, filepath.Join(held, "file"))

	inUse := removeDirectories([]string{held, free})
	if !slices.Equal(inUse, []string{held}) {
		t.Fatalf("in use: %v", inUse)
	}
	if _, err := os.Stat(free); !errors.Is(err, fs.ErrNotExist) {
		t.Fatalf("the free directory is still there: %v", err)
	}

	if err := windows.CloseHandle(handle); err != nil {
		t.Fatal(err)
	}
	if inUse := removeDirectories(inUse); len(inUse) != 0 {
		t.Fatalf("still in use: %v", inUse)
	}
	if _, err := os.Stat(held); !errors.Is(err, fs.ErrNotExist) {
		t.Fatalf("the held directory is still there: %v", err)
	}
}

func TestActionStagesANewDirectoryWhenTheIdleOneIsInUse(t *testing.T) {
	root := t.TempDir()
	store, err := cas.Open(filepath.Join(root, "cas"), 1<<30, 100)
	if err != nil {
		t.Fatal(err)
	}
	// With no deleters, the test receives each deletion itself.
	executor, err := New(store, filepath.Join(root, "work"), 4, 0, 4, 0)
	if err != nil {
		t.Fatal(err)
	}
	inputRoot := putDirectory(t, store, &repb.Directory{})
	command := testprogram.Command(t, "tempwrite", "held")
	if _, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: inputRoot}, command); err != nil {
		t.Fatal(err)
	}
	first := filepath.Join(executor.workRoot, "1")
	handle := holdOpen(t, filepath.Join(first, "tmp", "held"))
	defer windows.CloseHandle(handle)

	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: inputRoot}, command)
	if err != nil || result.ExitCode != 0 {
		t.Fatalf("result %v, %v", result, err)
	}
	if deleted := <-executor.deletions; deleted != first {
		t.Fatalf("deleted %s", deleted)
	}
	if _, err := os.Stat(filepath.Join(executor.workRoot, "2")); err != nil {
		t.Fatalf("the action did not stage a new directory: %v", err)
	}
}

func TestDeletingLeftoversKeepsBlobsReadOnly(t *testing.T) {
	root := t.TempDir()
	store, err := cas.Open(filepath.Join(root, "cas"), 1<<30, 100)
	if err != nil {
		t.Fatal(err)
	}
	workRoot := filepath.Join(root, "work")
	executor, err := New(store, workRoot, 4, 0, 4, 0)
	if err != nil {
		t.Fatal(err)
	}
	inputRoot := putDirectory(t, store, &repb.Directory{
		Files: []*repb.FileNode{{Name: "input.txt", Digest: put(t, store, "input")}},
	})
	if _, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: inputRoot}, testprogram.Command(t, "exit", "0")); err != nil {
		t.Fatal(err)
	}
	// Windows keeps the read-only attribute per file, so another link to the
	// staged input shows the blob's attribute.
	probe := filepath.Join(root, "probe")
	if err := os.Link(filepath.Join(workRoot, "1", "root", "input.txt"), probe); err != nil {
		t.Fatal(err)
	}

	restarted, err := New(store, workRoot, 4, 0, 0, 0)
	if err != nil {
		t.Fatal(err)
	}
	leftovers := make([]string, len(restarted.deletions))
	for index := range leftovers {
		leftovers[index] = <-restarted.deletions
	}
	if inUse := removeDirectories(leftovers); len(inUse) != 0 {
		t.Fatalf("in use: %v", inUse)
	}
	info, err := os.Stat(probe)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm()&0o200 != 0 {
		t.Fatal("deleting a leftover link made its blob writable")
	}
}
