package execution

import (
	"errors"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
)

const pathSeparators = `/\`

var tempVariables = []string{"TEMP", "TMP"}

// The extensions that Windows runs as programs, by default.
var programExtensions = []string{".com", ".exe", ".bat", ".cmd"}

// Windows exit codes are 32-bit, such as 0xC0000135 for a missing DLL, and
// keep their bits as an int32.
func exitCode(exitErr *exec.ExitError) int32 {
	return int32(uint32(exitErr.ExitCode()))
}

// makeInputDirectory makes a directory of an input tree. NTFS ignores case, so
// two directories whose names differ only in case are the same directory, which
// gets the entries of both.
func makeInputDirectory(path string) error {
	if err := os.Mkdir(path, 0o755); err != nil && !errors.Is(err, fs.ErrExist) {
		return err
	}
	return nil
}

func (link symlink) targetExists() bool {
	target := link.target
	if !filepath.IsAbs(target) {
		target = filepath.Join(filepath.Dir(link.path), target)
	}
	_, err := os.Stat(target)
	return err == nil
}

// createSymlinks creates each symlink after its target, where it can, since
// Windows makes a link to a directory differently from a link to a file, and
// decides which by what is at the target.
func createSymlinks(symlinks []symlink) error {
	for len(symlinks) > 0 {
		var waiting []symlink
		for _, link := range symlinks {
			if !link.targetExists() {
				waiting = append(waiting, link)
				continue
			}
			if err := os.Symlink(link.target, link.path); err != nil {
				return err
			}
		}
		if len(waiting) == len(symlinks) {
			// The rest dangle, or lead only to one another.
			for _, link := range waiting {
				if err := os.Symlink(link.target, link.path); err != nil {
					return err
				}
			}
			return nil
		}
		symlinks = waiting
	}
	return nil
}

func programCandidates(path string) []string {
	if filepath.Ext(path) != "" {
		return []string{path}
	}
	candidates := make([]string, len(programExtensions))
	for index, extension := range programExtensions {
		candidates[index] = path + extension
	}
	return candidates
}

func isExecutable(path string, _ fs.FileInfo) bool {
	return slices.Contains(programExtensions, strings.ToLower(filepath.Ext(path)))
}
