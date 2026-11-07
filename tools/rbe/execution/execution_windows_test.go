package execution

import (
	"context"
	"testing"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"

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
