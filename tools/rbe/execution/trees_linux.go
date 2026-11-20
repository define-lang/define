package execution

import (
	"bufio"
	"bytes"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"

	"golang.org/x/sys/unix"

	"github.com/define-lang/define/tools/processtree"
)

const cgroupMount = "/sys/fs/cgroup"

// actionOOMScoreAdjustment is the OOM score adjustment that systemd gives the
// developer's programs. When the machine runs out of memory, the kernel then
// chooses between an action and the developer's programs by how much memory
// each uses.
const actionOOMScoreAdjustment = "300"

// actionTrees starts each action in a cgroup of its own under the service's
// cgroup, which systemd delegates to the service. The cgroup limits the
// memory of every process in the action. Without a memory limit, actions run
// in process groups.
type actionTrees struct {
	// cgroup is the service's cgroup directory, which holds every action's
	// cgroup. It is empty when actions have no memory limit.
	cgroup      string
	memoryLimit int64
}

var takeOverCgroup = sync.OnceValues(moveIntoLeafCgroup)

func newActionTrees(memoryLimit int64) (*actionTrees, error) {
	if memoryLimit == 0 {
		return &actionTrees{}, nil
	}
	cgroup, err := takeOverCgroup()
	if err != nil {
		return nil, fmt.Errorf("setting up cgroups for action memory limits: %w", err)
	}
	return &actionTrees{cgroup: cgroup, memoryLimit: memoryLimit}, nil
}

// moveIntoLeafCgroup moves this process's cgroup's processes into a child
// cgroup and lets the cgroup's other children limit memory. A cgroup that
// limits its children's memory can't hold processes itself. It returns the
// cgroup.
func moveIntoLeafCgroup() (string, error) {
	contents, err := os.ReadFile("/proc/self/cgroup")
	if err != nil {
		return "", err
	}
	path, found := strings.CutPrefix(strings.TrimSpace(string(contents)), "0::")
	if !found {
		return "", fmt.Errorf("/proc/self/cgroup has no cgroup v2 entry: %q", contents)
	}
	cgroup := filepath.Join(cgroupMount, path)
	leaf, err := os.MkdirTemp(cgroup, "service-")
	if err != nil {
		return "", err
	}
	processes, err := os.ReadFile(filepath.Join(cgroup, "cgroup.procs"))
	if err != nil {
		return "", err
	}
	for process := range strings.FieldsSeq(string(processes)) {
		if err := writeCgroupFile(leaf, "cgroup.procs", process); err != nil {
			return "", err
		}
	}
	if err := writeCgroupFile(cgroup, "cgroup.subtree_control", "+memory"); err != nil {
		return "", err
	}
	return cgroup, nil
}

func writeCgroupFile(cgroup string, name string, value string) error {
	return os.WriteFile(filepath.Join(cgroup, name), []byte(value), 0)
}

// start starts process in a tree of its own.
func (trees *actionTrees) start(process *exec.Cmd) (actionTree, error) {
	if trees.cgroup == "" {
		tree, err := processtree.Start(process)
		if err != nil {
			return nil, err
		}
		if err := matchDeveloperOOMScore(process); err != nil {
			tree.End()
			return nil, err
		}
		return unlimitedTree{tree}, nil
	}
	cgroup, err := os.MkdirTemp(trees.cgroup, "action-")
	if err != nil {
		return nil, err
	}
	tree := &cgroupTree{cgroup: cgroup}
	if err := tree.limitMemory(trees.memoryLimit); err != nil {
		tree.End()
		return nil, err
	}
	directory, err := os.Open(cgroup)
	if err != nil {
		tree.End()
		return nil, err
	}
	defer directory.Close()
	process.SysProcAttr = &syscall.SysProcAttr{UseCgroupFD: true, CgroupFD: int(directory.Fd())}
	if err := process.Start(); err != nil {
		tree.End()
		return nil, err
	}
	if err := matchDeveloperOOMScore(process); err != nil {
		tree.End()
		return nil, err
	}
	return tree, nil
}

// matchDeveloperOOMScore raises the OOM score adjustment of an action's
// process. The
// processes that it starts inherit the adjustment. A program takes far longer
// to start up than this write, so the process starts no other process first.
func matchDeveloperOOMScore(process *exec.Cmd) error {
	path := fmt.Sprintf("/proc/%d/oom_score_adj", process.Process.Pid)
	return os.WriteFile(path, []byte(actionOOMScoreAdjustment), 0)
}

// cgroupTree is an action's cgroup, which holds its process and every process
// that process starts.
type cgroupTree struct {
	cgroup string
}

// limitMemory makes the kernel kill every process in the cgroup when they use
// more than limit bytes in all. Swap doesn't count toward the limit, so the
// cgroup gets none, so that an action that uses too much memory is killed
// rather than slowed.
func (tree *cgroupTree) limitMemory(limit int64) error {
	for _, setting := range []struct{ name, value string }{
		{"memory.max", strconv.FormatInt(limit, 10)},
		{"memory.swap.max", "0"},
		{"memory.oom.group", "1"},
	} {
		if err := writeCgroupFile(tree.cgroup, setting.name, setting.value); err != nil {
			return err
		}
	}
	return nil
}

// Kill kills every process in the cgroup.
func (tree *cgroupTree) Kill() {
	if err := writeCgroupFile(tree.cgroup, "cgroup.kill", "1"); err != nil {
		panic(fmt.Sprintf("killing the processes of %s: %v", tree.cgroup, err))
	}
}

// End kills what is left in the cgroup, waits for it to exit, and removes the
// cgroup. Killing doesn't wait, and the kernel can't remove a cgroup that has
// processes.
func (tree *cgroupTree) End() {
	tree.Kill()
	if err := tree.waitUntilEmpty(); err != nil {
		panic(fmt.Sprintf("waiting for the processes of %s to exit: %v", tree.cgroup, err))
	}
	if err := removeCgroup(tree.cgroup); err != nil {
		panic(fmt.Sprintf("removing %s: %v", tree.cgroup, err))
	}
}

// removeCgroup removes a cgroup that has no processes, and the cgroups under
// it. An action that runs this executor, such as this package's tests, makes
// cgroups under its own.
func removeCgroup(cgroup string) error {
	entries, err := os.ReadDir(cgroup)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if entry.IsDir() {
			if err := removeCgroup(filepath.Join(cgroup, entry.Name())); err != nil {
				return err
			}
		}
	}
	return os.Remove(cgroup)
}

// waitUntilEmpty waits until no process is left in the cgroup. The kernel
// changes cgroup.events when the cgroup's last process exits.
func (tree *cgroupTree) waitUntilEmpty() error {
	events := filepath.Join(tree.cgroup, "cgroup.events")
	watcher, err := unix.InotifyInit1(unix.IN_CLOEXEC)
	if err != nil {
		return err
	}
	defer unix.Close(watcher)
	if _, err := unix.InotifyAddWatch(watcher, events, unix.IN_MODIFY); err != nil {
		return err
	}
	buffer := make([]byte, unix.SizeofInotifyEvent+unix.PathMax+1)
	for {
		populated, err := readCgroupValue(events, "populated")
		if err != nil {
			return err
		}
		if populated == 0 {
			return nil
		}
		if _, err := unix.Read(watcher, buffer); err != nil && !errors.Is(err, unix.EINTR) {
			return err
		}
	}
}

// RanOutOfMemory reports whether the kernel killed processes in the cgroup
// because they used too much memory. It doesn't count processes in cgroups
// that the action makes under its own, which have limits of their own.
func (tree *cgroupTree) RanOutOfMemory() bool {
	kills, err := readCgroupValue(filepath.Join(tree.cgroup, "memory.events.local"), "oom_kill")
	if err != nil {
		panic(fmt.Sprintf("reading the memory events of %s: %v", tree.cgroup, err))
	}
	return kills > 0
}

// readCgroupValue reads the value of a key in a cgroup file of "key value"
// lines.
func readCgroupValue(path string, key string) (int64, error) {
	contents, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}
	scanner := bufio.NewScanner(bytes.NewReader(contents))
	for scanner.Scan() {
		name, value, found := strings.Cut(scanner.Text(), " ")
		if found && name == key {
			return strconv.ParseInt(value, 10, 64)
		}
	}
	return 0, fmt.Errorf("%s has no %s", path, key)
}
