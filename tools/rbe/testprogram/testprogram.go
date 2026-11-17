// Package testprogram lets tests run actions without a shell. A test's action
// runs the test binary itself, which does the steps it is given and exits.
package testprogram

import (
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

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
//	sleep SECONDS      sleeps
//	spawn PATH         starts a process that writes PATH a second later
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
		case "sleep":
			var seconds float64
			if seconds, err = strconv.ParseFloat(arguments[1], 64); err == nil {
				time.Sleep(time.Duration(seconds * float64(time.Second)))
			}
			arguments = arguments[2:]
		case "spawn":
			err = exec.Command(os.Args[0], "sleep", "1", "write", arguments[1], "survived").Start()
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
				time.Sleep(time.Minute)
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
