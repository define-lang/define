package execution

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

const pathSeparators = `/\`

var tempVariables = []string{"TEMP", "TMP"}

// The extensions that Windows runs as programs, by default.
var programExtensions = []string{".com", ".exe", ".bat", ".cmd"}

var procNtResumeProcess = windows.NewLazySystemDLL("ntdll.dll").NewProc("NtResumeProcess")

// processTree is a Job Object that holds a command's process and every process
// it starts.
type processTree struct {
	job windows.Handle
}

func startTree(process *exec.Cmd) (*processTree, error) {
	job, err := windows.CreateJobObject(nil, nil)
	if err != nil {
		return nil, err
	}
	tree := &processTree{job: job}
	limits := windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION{
		BasicLimitInformation: windows.JOBOBJECT_BASIC_LIMIT_INFORMATION{
			LimitFlags: windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
		},
	}
	if _, err := windows.SetInformationJobObject(job, windows.JobObjectExtendedLimitInformation,
		uintptr(unsafe.Pointer(&limits)), uint32(unsafe.Sizeof(limits))); err != nil {
		tree.end()
		return nil, err
	}
	// The process starts suspended, so that it can't start another process
	// before it is in the job.
	process.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_SUSPENDED}
	if err := process.Start(); err != nil {
		tree.end()
		return nil, err
	}
	if err := tree.adopt(process.Process.Pid); err != nil {
		_ = process.Process.Kill()
		_ = process.Wait()
		tree.end()
		return nil, err
	}
	return tree, nil
}

// adopt puts a suspended process in the job and resumes it.
func (tree *processTree) adopt(pid int) error {
	process, err := windows.OpenProcess(
		windows.PROCESS_SET_QUOTA|windows.PROCESS_TERMINATE|windows.PROCESS_SUSPEND_RESUME, false, uint32(pid))
	if err != nil {
		return err
	}
	defer windows.CloseHandle(process)
	if err := windows.AssignProcessToJobObject(tree.job, process); err != nil {
		return err
	}
	if status, _, _ := procNtResumeProcess.Call(uintptr(process)); status != 0 {
		return fmt.Errorf("resuming the process: %w", windows.NTStatus(status))
	}
	return nil
}

func (tree *processTree) kill() {
	_ = windows.TerminateJobObject(tree.job, 1)
}

// jobAccounting is JOBOBJECT_BASIC_ACCOUNTING_INFORMATION, which
// golang.org/x/sys/windows doesn't define.
type jobAccounting struct {
	TotalUserTime             int64
	TotalKernelTime           int64
	ThisPeriodTotalUserTime   int64
	ThisPeriodTotalKernelTime int64
	TotalPageFaultCount       uint32
	TotalProcesses            uint32
	ActiveProcesses           uint32
	TotalTerminatedProcesses  uint32
}

// end kills what is left in the job and waits for it to exit. Terminating a
// job doesn't wait, and a process that is still exiting keeps its working
// directory and files in use, so the action directory couldn't be deleted.
func (tree *processTree) end() {
	tree.kill()
	var accounting jobAccounting
	for windows.QueryInformationJobObject(tree.job, windows.JobObjectBasicAccountingInformation,
		uintptr(unsafe.Pointer(&accounting)), uint32(unsafe.Sizeof(accounting)), nil) == nil &&
		accounting.ActiveProcesses > 0 {
		time.Sleep(10 * time.Millisecond)
	}
	_ = windows.CloseHandle(tree.job)
}

// Windows exit codes are 32-bit, such as 0xC0000135 for a missing DLL, and
// keep their bits as an int32.
func exitCode(exitErr *exec.ExitError) int32 {
	return int32(uint32(exitErr.ExitCode()))
}

// startablePath lets a program whose name has no extension start, such as one
// that Bazel on Linux built for Windows. os/exec refuses such a path, but
// Windows runs the file it names when given the path with a trailing dot,
// which it drops.
// TODO: Remove this once rules_py names its Windows launchers .exe:
// https://github.com/aspect-build/rules_py/pull/1644
func startablePath(program string) string {
	if filepath.Ext(program) == "" {
		return program + "."
	}
	return program
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
