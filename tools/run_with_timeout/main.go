// Command run_with_timeout runs a command, and fails if the command runs longer
// than a time limit. It then kills the command and every process the command
// started.
//
// Usage:
//
//	run_with_timeout SECONDS COMMAND [ARGUMENT]...
//
// It exits with the command's exit code, or with 1 if the command ran out of
// time or could not start.
package main

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/define-lang/define/tools/processtree"
)

const (
	failedExitCode = 1
	usageExitCode  = 2
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(arguments []string, stdout io.Writer, stderr io.Writer) int {
	if len(arguments) < 2 {
		fmt.Fprintln(stderr, "usage: run_with_timeout SECONDS COMMAND [ARGUMENT]...")
		return usageExitCode
	}
	seconds, err := strconv.ParseFloat(arguments[0], 64)
	if err != nil || seconds <= 0 {
		fmt.Fprintf(stderr, "run_with_timeout: %q is not a positive number of seconds\n", arguments[0])
		return usageExitCode
	}
	command := exec.Command(arguments[1], arguments[2:]...)
	command.Stdin = os.Stdin
	command.Stdout = stdout
	command.Stderr = stderr
	// A command such as `bash -c 'generate && format'` starts other
	// processes, which must not outlive it.
	tree, err := processtree.Start(command)
	if err != nil {
		fmt.Fprintf(stderr, "run_with_timeout: starting %s: %v\n", arguments[1], err)
		return failedExitCode
	}
	defer tree.End()
	waited := make(chan error, 1)
	go func() { waited <- command.Wait() }()
	timer := time.NewTimer(time.Duration(seconds * float64(time.Second)))
	defer timer.Stop()
	select {
	case err := <-waited:
		return exitCode(err)
	case <-timer.C:
		tree.Kill()
		<-waited
		fmt.Fprintf(stderr, "%s ran out of its %s s time limit.\n",
			strings.Join(arguments[1:], " "), arguments[0])
		return failedExitCode
	}
}

func exitCode(err error) int {
	if err == nil {
		return 0
	}
	var exitErr *exec.ExitError
	// A command that a signal killed has no exit code of its own.
	if errors.As(err, &exitErr) && exitErr.ExitCode() > 0 {
		return exitErr.ExitCode()
	}
	return failedExitCode
}
