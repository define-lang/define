//go:build unix && !linux

package execution

import (
	"errors"
	"os/exec"

	"github.com/define-lang/define/tools/processtree"
)

// actionTrees starts each action in a process group. Only Linux and Windows
// can limit an action's memory.
type actionTrees struct{}

func newActionTrees(memoryLimit int64) (*actionTrees, error) {
	if memoryLimit != 0 {
		return nil, errors.New("action memory limits need Linux or Windows")
	}
	return &actionTrees{}, nil
}

// start starts process in a tree of its own.
func (*actionTrees) start(process *exec.Cmd) (actionTree, error) {
	tree, err := processtree.Start(process)
	if err != nil {
		return nil, err
	}
	return unlimitedTree{tree}, nil
}
