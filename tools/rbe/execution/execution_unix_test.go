//go:build unix

package execution

import (
	"context"
	"testing"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"

	"github.com/define-lang/define/tools/rbe/testprogram"
)

func TestReportsSignal(t *testing.T) {
	executor, store := newExecutor(t)
	root := putDirectory(t, store, &repb.Directory{})
	result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, testprogram.Command(t, "terminate"))
	if err != nil {
		t.Fatal(err)
	}
	if result.ExitCode != 128+15 {
		t.Errorf("exited with %d", result.ExitCode)
	}
}
