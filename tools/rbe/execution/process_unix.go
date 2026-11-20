//go:build unix

package execution

import (
	"io/fs"
	"os"
	"os/exec"
	"syscall"

	"github.com/define-lang/define/tools/processtree"
)

const pathSeparators = "/"

var tempVariables = []string{"TMPDIR"}

func exitCode(exitErr *exec.ExitError) int32 {
	if status, ok := exitErr.Sys().(syscall.WaitStatus); ok && status.Signaled() {
		return 128 + int32(status.Signal())
	}
	return int32(exitErr.ExitCode())
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

// unlimitedTree is an action's process group, which has no memory limit.
type unlimitedTree struct {
	*processtree.Tree
}

func (unlimitedTree) RanOutOfMemory() bool {
	return false
}
