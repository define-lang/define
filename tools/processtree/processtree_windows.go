package processtree

import (
	"fmt"
	"os/exec"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

var procNtResumeProcess = windows.NewLazySystemDLL("ntdll.dll").NewProc("NtResumeProcess")

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

// End kills what is left in the job and waits for it to exit. Terminating a
// job doesn't wait, and a process that is still exiting keeps its working
// directory and files in use, so they couldn't be deleted.
func (tree *Tree) End() {
	tree.Kill()
	var accounting jobAccounting
	for windows.QueryInformationJobObject(tree.job, windows.JobObjectBasicAccountingInformation,
		uintptr(unsafe.Pointer(&accounting)), uint32(unsafe.Sizeof(accounting)), nil) == nil &&
		accounting.ActiveProcesses > 0 {
		time.Sleep(10 * time.Millisecond)
	}
	_ = windows.CloseHandle(tree.job)
}
