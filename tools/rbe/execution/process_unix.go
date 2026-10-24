//go:build unix

package execution

import (
	"io/fs"
	"os"
	"os/exec"
	"syscall"
)

const pathSeparators = "/"

var tempVariables = []string{"TMPDIR"}

// processTree is a command's process group.
type processTree struct {
	group int
}

func startTree(process *exec.Cmd) (*processTree, error) {
	process.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	if err := process.Start(); err != nil {
		return nil, err
	}
	return &processTree{group: process.Process.Pid}, nil
}

func (tree *processTree) kill() {
	_ = syscall.Kill(-tree.group, syscall.SIGKILL)
}

func (tree *processTree) end() {
	tree.kill()
}

func exitCode(exitErr *exec.ExitError) int32 {
	if status, ok := exitErr.Sys().(syscall.WaitStatus); ok && status.Signaled() {
		return 128 + int32(status.Signal())
	}
	return int32(exitErr.ExitCode())
}

func startablePath(program string) string {
	return program
}

func makeInputDirectory(path string) error {
	return os.Mkdir(path, 0o755)
}

func createSymlinks(symlinks []symlink) error {
	for _, link := range symlinks {
		if err := os.Symlink(link.target, link.path); err != nil {
			return err
		}
	}
	return nil
}

func programCandidates(path string) []string {
	return []string{path}
}

func isExecutable(_ string, info fs.FileInfo) bool {
	return info.Mode()&0o111 != 0
}
