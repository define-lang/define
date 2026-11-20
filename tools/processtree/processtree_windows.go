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

// jobMemoryLimitMessage is JOB_OBJECT_MSG_JOB_MEMORY_LIMIT, which a job posts
// to its completion port when a process in the job fails to commit memory
// beyond the job's limit. golang.org/x/sys/windows doesn't define it.
const jobMemoryLimitMessage = 10

// maxListedProcesses is how many process IDs one query of a job lists. End
// queries the job again until it has no processes left.
const maxListedProcesses = 256

// Tree is a Job Object that holds a command's process and every process it
// starts.
type Tree struct {
	job windows.Handle
	// port receives the job's messages when the job has a memory limit, and
	// is zero otherwise.
	port windows.Handle
}

// associateCompletionPort is JOBOBJECT_ASSOCIATE_COMPLETION_PORT, which
// golang.org/x/sys/windows doesn't define.
type associateCompletionPort struct {
	CompletionKey  uintptr
	CompletionPort windows.Handle
}

// Start starts process in a Job Object of its own.
func Start(process *exec.Cmd) (*Tree, error) {
	return StartWithMemoryLimit(process, 0)
}

// StartWithMemoryLimit starts process in a Job Object of its own that can
// commit at most memoryLimit bytes in all, or any amount when memoryLimit is
// zero. A process that commits more gets an allocation failure.
func StartWithMemoryLimit(process *exec.Cmd, memoryLimit uint64) (*Tree, error) {
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
	if memoryLimit > 0 {
		if err := tree.reportMemoryLimit(); err != nil {
			tree.End()
			return nil, err
		}
		limits.BasicLimitInformation.LimitFlags |= windows.JOB_OBJECT_LIMIT_JOB_MEMORY
		limits.JobMemoryLimit = uintptr(memoryLimit)
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

// reportMemoryLimit gives the job a completion port, where the job posts a
// message when a process in it reaches the job's memory limit.
func (tree *Tree) reportMemoryLimit() error {
	port, err := windows.CreateIoCompletionPort(windows.InvalidHandle, 0, 0, 1)
	if err != nil {
		return err
	}
	tree.port = port
	association := associateCompletionPort{CompletionPort: port}
	_, err = windows.SetInformationJobObject(tree.job, windows.JobObjectAssociateCompletionPortInformation,
		uintptr(unsafe.Pointer(&association)), uint32(unsafe.Sizeof(association)))
	return err
}

// RanOutOfMemory reports whether a process in the job has failed to commit
// memory beyond the job's memory limit. The job posts that message when the
// commit fails, so the message is there once the process has exited.
func (tree *Tree) RanOutOfMemory() bool {
	if tree.port == 0 {
		return false
	}
	ranOut := false
	for {
		var message uint32
		var key uintptr
		var overlapped *windows.Overlapped
		if err := windows.GetQueuedCompletionStatus(tree.port, &message, &key, &overlapped, 0); err != nil {
			return ranOut
		}
		if message == jobMemoryLimitMessage {
			ranOut = true
		}
	}
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
	if tree.port != 0 {
		_ = windows.CloseHandle(tree.port)
	}
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
