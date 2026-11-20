// Package testprogram lets tests run actions without a shell. A test's action
// runs the test binary itself, which does the steps it is given and exits.
package testprogram

import (
	"bufio"
	"fmt"
	"io"
	"io/fs"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"testing"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
)

// The test binary does steps instead of running tests when this is set.
const stepsVariable = "RBE_TEST_PROGRAM"

// Main runs the tests, or the steps when the test binary was started as an
// action's program.
func Main(m *testing.M) {
	if os.Getenv(stepsVariable) != "" {
		if err := run(os.Args[1:]); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(100)
		}
		os.Exit(0)
	}
	os.Exit(m.Run())
}

// Command returns a command that does the steps, in order:
//
//	write PATH TEXT    writes TEXT to PATH, creating its directory
//	copy FROM TO       copies a file
//	stdout TEXT        writes TEXT to standard output
//	stderr TEXT        writes TEXT to standard error
//	where PATH         writes the working directory's name to PATH
//	checktemp OUTSIDE  fails unless each temporary directory variable names a
//	                   directory other than OUTSIDE
//	block              waits until it is killed
//	connect ADDRESS    connects to the TCP listener at ADDRESS, waits for
//	                   the listener to send a byte, writes "connected" to
//	                   standard output, and waits until the listener closes
//	                   the connection
//	spawn ADDRESS      starts a process that connects to ADDRESS, and waits
//	                   until that process has connected
//	allocate BYTES     allocates BYTES bytes of memory and writes to all of
//	                   them, so that the system must give the process that
//	                   memory
//	exit CODE          exits with CODE
//	terminate          sends itself SIGTERM
func Command(t *testing.T, steps ...string) *repb.Command {
	t.Helper()
	program, err := os.Executable()
	if err != nil {
		t.Fatal(err)
	}
	return &repb.Command{
		Arguments:            append([]string{program}, steps...),
		EnvironmentVariables: []*repb.Command_EnvironmentVariable{{Name: stepsVariable, Value: "1"}},
	}
}

func tempVariables() []string {
	if runtime.GOOS == "windows" {
		return []string{"TEMP", "TMP"}
	}
	return []string{"TMPDIR"}
}

func run(arguments []string) error {
	for len(arguments) > 0 {
		step := arguments[0]
		var err error
		switch step {
		case "write":
			if err = os.MkdirAll(filepath.Dir(arguments[1]), 0o755); err == nil {
				err = os.WriteFile(arguments[1], []byte(arguments[2]), 0o644)
			}
			arguments = arguments[3:]
		case "copy":
			var contents []byte
			if contents, err = os.ReadFile(arguments[1]); err == nil {
				err = os.WriteFile(arguments[2], contents, 0o644)
			}
			arguments = arguments[3:]
		case "script":
			// Steps from an input file let actions that run the same command
			// do different things.
			var contents []byte
			if contents, err = os.ReadFile(arguments[1]); err == nil {
				err = run(strings.Fields(string(contents)))
			}
			arguments = arguments[2:]
		case "tree":
			err = writeTree(arguments[1], arguments[2])
			arguments = arguments[3:]
		case "tempwrite":
			err = os.WriteFile(filepath.Join(os.Getenv(tempVariables()[0]), arguments[1]), nil, 0o644)
			arguments = arguments[2:]
		case "temptree":
			err = writeTree(os.Getenv(tempVariables()[0]), arguments[1])
			arguments = arguments[2:]
		case "readonly":
			err = os.Chmod(arguments[1], 0o555)
			arguments = arguments[2:]
		case "writable":
			err = os.Chmod(arguments[1], 0o644)
			arguments = arguments[2:]
		case "remove":
			err = os.RemoveAll(arguments[1])
			arguments = arguments[2:]
		case "mkdir":
			err = os.Mkdir(arguments[1], 0o755)
			arguments = arguments[2:]
		case "symlink":
			err = os.Symlink(arguments[1], arguments[2])
			arguments = arguments[3:]
		case "stdout":
			_, err = os.Stdout.WriteString(arguments[1])
			arguments = arguments[2:]
		case "stderr":
			_, err = os.Stderr.WriteString(arguments[1])
			arguments = arguments[2:]
		case "where":
			var directory string
			if directory, err = os.Getwd(); err == nil {
				err = os.WriteFile(arguments[1], []byte(filepath.Base(directory)), 0o644)
			}
			arguments = arguments[2:]
		case "checktemp":
			err = checkTemp(arguments[1])
			arguments = arguments[2:]
		case "block":
			waitForever()
		case "connect":
			err = connect(arguments[1])
			arguments = arguments[2:]
		case "spawn":
			err = spawn(arguments[1])
			arguments = arguments[2:]
		case "allocate":
			var size int
			if size, err = strconv.Atoi(arguments[1]); err == nil {
				allocate(size)
			}
			arguments = arguments[2:]
		case "exit":
			var code int
			if code, err = strconv.Atoi(arguments[1]); err == nil {
				os.Exit(code)
			}
			arguments = arguments[2:]
		case "terminate":
			var process *os.Process
			if process, err = os.FindProcess(os.Getpid()); err == nil {
				err = process.Signal(syscall.SIGTERM)
				// The signal ends the process.
				waitForever()
			}
			arguments = arguments[1:]
		default:
			return fmt.Errorf("unknown step %q", step)
		}
		if err != nil {
			return fmt.Errorf("%s: %w", step, err)
		}
	}
	return nil
}

// allocated holds the memory that the allocate step allocates, so that the
// compiler can't remove the allocation.
var allocated []byte

func allocate(size int) {
	allocated = make([]byte, size)
	const pageSize = 4096
	for index := 0; index < size; index += pageSize {
		allocated[index] = 1
	}
}

// writeTree writes a line for each entry under root: a directory's path with
// a trailing slash, a file's path and contents, and a symlink's path and
// target.
func writeTree(root string, output string) error {
	var lines []string
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil || path == root {
			return err
		}
		relative, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		relative = filepath.ToSlash(relative)
		switch {
		case entry.Type()&fs.ModeSymlink != 0:
			target, err := os.Readlink(path)
			if err != nil {
				return err
			}
			lines = append(lines, relative+" -> "+target)
		case entry.IsDir():
			lines = append(lines, relative+"/")
		default:
			contents, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			lines = append(lines, relative+" = "+string(contents))
		}
		return nil
	})
	if err != nil {
		return err
	}
	return os.WriteFile(output, []byte(strings.Join(lines, "\n")), 0o644)
}

func checkTemp(outside string) error {
	for _, name := range tempVariables() {
		directory := os.Getenv(name)
		info, err := os.Stat(directory)
		if err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
		if !info.IsDir() || filepath.Clean(directory) == filepath.Clean(outside) {
			return fmt.Errorf("%s is %q", name, directory)
		}
	}
	return nil
}

// connect connects to the TCP listener at address, and waits until the
// listener closes the connection. It writes "connected" to standard output
// once the listener has accepted the connection and sent a byte. Windows drops
// a connection whose process exits before the listener accepts it, so a
// listener must accept each connection while its process runs.
func connect(address string) error {
	connection, err := net.Dial("tcp", address)
	if err != nil {
		return err
	}
	defer connection.Close()
	if _, err := io.ReadFull(connection, make([]byte, 1)); err != nil {
		return err
	}
	if _, err := fmt.Println("connected"); err != nil {
		return err
	}
	_, err = io.Copy(io.Discard, connection)
	return err
}

// spawn starts a process that connects to address, and returns once that
// process has connected. The process keeps running after this one exits.
func spawn(address string) error {
	child := exec.Command(os.Args[0], "connect", address)
	output, err := child.StdoutPipe()
	if err != nil {
		return err
	}
	if err := child.Start(); err != nil {
		return err
	}
	line, err := bufio.NewReader(output).ReadString('\n')
	if err != nil {
		return err
	}
	if line != "connected\n" {
		return fmt.Errorf("the spawned process wrote %q", line)
	}
	return nil
}

// waitForever waits until the process is killed. A program whose goroutines
// all wait on channels, as in a bare select {}, ends with a deadlock error, so
// it waits for a signal that never comes instead.
func waitForever() {
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, os.Interrupt)
	for range signals {
	}
}
