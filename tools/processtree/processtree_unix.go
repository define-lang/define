//go:build unix

package processtree

import (
	"os/exec"
	"syscall"
)

// Tree is a command's process group.
type Tree struct {
	group int
}

// Start starts process in a process group of its own.
func Start(process *exec.Cmd) (*Tree, error) {
	process.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := process.Start(); err != nil {
		return nil, err
	}
	return &Tree{group: process.Process.Pid}, nil
}

// Kill kills every process in the tree.
func (tree *Tree) Kill() {
	_ = syscall.Kill(-tree.group, syscall.SIGKILL)
}

// End kills what is left of the tree.
func (tree *Tree) End() {
	tree.Kill()
}
