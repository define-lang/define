package execution

import (
	"os/exec"

	"github.com/define-lang/define/tools/processtree"
)

// actionTrees starts each action in a Job Object of its own, which limits the
// memory that the action's processes commit in all.
type actionTrees struct {
	memoryLimit uint64
}

func newActionTrees(memoryLimit int64) (*actionTrees, error) {
	return &actionTrees{memoryLimit: uint64(memoryLimit)}, nil
}

// start starts process in a tree of its own.
func (trees *actionTrees) start(process *exec.Cmd) (actionTree, error) {
	tree, err := processtree.StartWithMemoryLimit(process, trees.memoryLimit)
	if err != nil {
		return nil, err
	}
	return tree, nil
}
