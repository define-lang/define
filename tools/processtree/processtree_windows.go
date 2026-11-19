package processtree

import (
	"errors"
	"fmt"
	"os/exec"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

var (
	procNtResumeProcess = windows.NewLazySystemDLL("ntdll.dll").NewProc("NtResumeProcess")
	procIsProcessInJob  = windows.NewLazySystemDLL("kernel32.dll").NewProc("IsProcessInJob")
)

// maxListedProcesses is how many process IDs one query of a job lists. End
// queries the job again until it has no processes left.
const maxListedProcesses = 256

// Tree is a Job Object that holds a command's process and every process it
// starts.
type Tree struct {
	job windows.Handle
}

// Start starts process in a Job Object of its own.
func Start(process *exec.Cmd) (*Tree, error) {
	job, err := windows.CreateJobObject(nil, nil)
	if err != nil {
		return nil, err
	}
	tree := &Tree{job: job}
	limits := windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION{
		BasicLimitInformation: windows.JOBOBJECT_BASIC_LIMIT_INFORMATION{
			LimitFlags: windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
		},
	}
	if _, err := windows.SetInformationJobObject(job, windows.JobObjectExtendedLimitInformation,
		uintptr(unsafe.Pointer(&limits)), uint32(unsafe.Sizeof(limits))); err != nil {
		tree.End()
		return nil, err
	}
	// The process starts suspended, so that it can't start another process
	// before it is in the job.
	process.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_SUSPENDED}
	if err := process.Start(); err != nil {
		tree.End()
		return nil, err
	}
	if err := tree.adopt(process.Process.Pid); err != nil {
		_ = process.Process.Kill()
		_ = process.Wait()
		tree.End()
		return nil, err
	}
	return tree, nil
}

// adopt puts a suspended process in the job and resumes it.
func (tree *Tree) adopt(pid int) error {
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

// Kill kills every process in the job.
func (tree *Tree) Kill() {
	_ = windows.TerminateJobObject(tree.job, 1)
}

// processIDList is JOBOBJECT_BASIC_PROCESS_ID_LIST, which
// golang.org/x/sys/windows doesn't define.
type processIDList struct {
	NumberOfAssignedProcesses uint32
	NumberOfProcessIdsInList  uint32
	ProcessIDList             [maxListedProcesses]uintptr
}

// End kills what is left in the job and waits for it to exit. Terminating a
// job doesn't wait, and a process that is still exiting keeps its working
// directory and files in use, so they couldn't be deleted.
func (tree *Tree) End() {
	tree.Kill()
	for tree.waitForListedProcesses() {
	}
	_ = windows.CloseHandle(tree.job)
}

// waitForListedProcesses waits for each process that the job lists to exit,
// and reports whether it waited for any.
func (tree *Tree) waitForListedProcesses() bool {
	var list processIDList
	if err := windows.QueryInformationJobObject(tree.job, windows.JobObjectBasicProcessIdList,
		uintptr(unsafe.Pointer(&list)), uint32(unsafe.Sizeof(list)), nil); err != nil &&
		!errors.Is(err, windows.ERROR_MORE_DATA) {
		return false
	}
	waited := false
	for _, id := range list.ProcessIDList[:list.NumberOfProcessIdsInList] {
		if tree.waitForProcess(uint32(id)) {
			waited = true
		}
	}
	return waited
}

// waitForProcess waits for a process in the job to exit. It reports false for
// a process that has already exited, and for an ID that a process outside the
// job now has.
func (tree *Tree) waitForProcess(id uint32) bool {
	process, err := windows.OpenProcess(windows.SYNCHRONIZE|windows.PROCESS_QUERY_LIMITED_INFORMATION, false, id)
	if err != nil {
		return false
	}
	defer windows.CloseHandle(process)
	var inJob int32
	if ok, _, _ := procIsProcessInJob.Call(uintptr(process), uintptr(tree.job), uintptr(unsafe.Pointer(&inJob))); ok == 0 || inJob == 0 {
		return false
	}
	_, _ = windows.WaitForSingleObject(process, windows.INFINITE)
	return true
}
