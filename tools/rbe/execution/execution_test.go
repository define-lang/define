package execution

import (
	"context"
	"crypto/sha256"
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
	"time"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"google.golang.org/protobuf/types/known/durationpb"

	"github.com/define-lang/define/tools/rbe/cas"
)

func newExecutor(t *testing.T) (*Executor, *cas.Store) {
	t.Helper()
	root := t.TempDir()
	store, err := cas.Open(filepath.Join(root, "cas"), 1<<30, 100)
	if err != nil {
		t.Fatal(err)
	}
	executor, err := New(store, filepath.Join(root, "work"), 4, 1)
	if err != nil {
		t.Fatal(err)
	}
	return executor, store
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

func shellCommand(script string, outputPaths ...string) *repb.Command {
	return &repb.Command{
		Arguments:            []string{"sh", "-c", script},
		EnvironmentVariables: []*repb.Command_EnvironmentVariable{{Name: "PATH", Value: "/usr/bin:/bin"}},
		OutputPaths:          outputPaths,
	}
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
	command := shellCommand(
		"cat src/input.txt > out/file.txt && mkdir -p out/dir/sub && echo nested > out/dir/sub/nested.txt && echo said >&2",
		"out/file.txt", "out/dir", "out/absent",
	)

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
	command := shellCommand(`basename "$PWD" > where && test -d "$TMPDIR" && test "$TMPDIR" != /tmp`, "where")
	command.WorkingDirectory = "pkg"

	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, command)
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 0 {
		t.Fatalf("exit code %d", result.ExitCode)
	}
	if contents := readBlob(t, store, result.OutputFiles[0].Digest); contents != "pkg\n" {
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

	_, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, shellCommand("true"))
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

	result, err := executor.Execute(context.Background(), action, shellCommand("echo started; exec sleep 60"))
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
		shellCommand("(sleep 1; touch "+marker+") &"))
	if err != nil || result.ExitCode != 0 {
		t.Fatalf("result %v, %v", result, err)
	}
	time.Sleep(1500 * time.Millisecond)
	if _, err := os.Stat(marker); !errors.Is(err, os.ErrNotExist) {
		t.Fatal("a background process kept running after its action finished")
	}
}

func TestReportsExitCodeAndSignal(t *testing.T) {
	executor, store := newExecutor(t)
	root := putDirectory(t, store, &repb.Directory{})
	for script, expected := range map[string]int32{"exit 3": 3, "kill -TERM $$": 128 + 15} {
		result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, shellCommand(script))
		if err != nil {
			t.Fatal(err)
		}
		if result.ExitCode != expected {
			t.Errorf("%s exited with %d", script, result.ExitCode)
		}
	}
}

func TestFindsProgramInCommandPath(t *testing.T) {
	directory := t.TempDir()
	program := filepath.Join(directory, "tool")
	if err := os.WriteFile(program, []byte("#!/bin/sh\n"), 0o755); err != nil {
		t.Fatal(err)
	}
	found, err := findProgram("tool", t.TempDir(), "/nonexistent:"+directory)
	if err != nil || found != program {
		t.Fatalf("found %q, %v", found, err)
	}
	if _, err := findProgram("tool", t.TempDir(), "/nonexistent"); err == nil || !strings.Contains(err.Error(), "tool") {
		t.Fatalf("found a program that is not in PATH: %v", err)
	}
	relative, err := findProgram("bin/tool", "/work", "")
	if err != nil || relative != "/work/bin/tool" {
		t.Fatalf("resolved %q, %v", relative, err)
	}
}

func TestRejectsPathsThatLeaveTheActionDirectory(t *testing.T) {
	for _, path := range []string{"../escape", "/absolute"} {
		if _, err := resolveRelative("/work", path); err == nil {
			t.Errorf("accepted %q", path)
		}
	}
	for path, expected := range map[string]string{"": "/work", ".": "/work", "a/b": "/work/a/b"} {
		resolved, err := resolveRelative("/work", path)
		if err != nil || resolved != expected {
			t.Errorf("resolved %q to %q, %v", path, resolved, err)
		}
	}
}
