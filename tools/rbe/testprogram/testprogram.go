// Package testprogram lets tests run actions without a shell. A test's action
// runs the test binary itself, which does the steps it is given and exits.
package testprogram

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
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
