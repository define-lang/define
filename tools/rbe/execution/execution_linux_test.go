package execution

import (
	"context"
	"testing"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"

	"github.com/define-lang/define/tools/rbe/testprogram"
)

func TestActionsHaveTheDevelopersOOMScoreAdjustment(t *testing.T) {
	for _, memoryLimit := range []int64{0, 256 << 20} {
		executor, store := newExecutor(t)
		if memoryLimit != 0 {
			executor, store = newLimitedExecutor(t, memoryLimit)
		}
		root := putDirectory(t, store, &repb.Directory{})
		command := testprogram.Command(t, "copy", "/proc/self/oom_score_adj", "score.txt")
		command.OutputPaths = []string{"score.txt"}
		result, err := executor.Execute(context.Background(), &repb.Action{InputRootDigest: root}, command)
		if err != nil {
			t.Fatal(err)
		}
		if score := readBlob(t, store, result.OutputFiles[0].Digest); score != "300\n" {
			t.Errorf("with a memory limit of %d, the action's OOM score adjustment is %q", memoryLimit, score)
		}
	}
}
