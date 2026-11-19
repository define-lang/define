package main

import (
	"io"
	"os"
	"os/exec"
	"os/signal"
	"strings"
	"testing"
)

// helperVariable makes this test binary act as the command that the tests
// run, as each of its values says.
const helperVariable = "RUN_WITH_TIMEOUT_TEST_HELPER"

func TestMain(m *testing.M) {
	switch os.Getenv(helperVariable) {
	case "exit 3":
		os.Exit(3)
	case "wait with a grandchild":
		// The grandchild inherits standard output, as this process does.
		grandchild := exec.Command(os.Args[0])
		grandchild.Env = append(os.Environ(), helperVariable+"=wait")
		grandchild.Stdout = os.Stdout
		if err := grandchild.Start(); err != nil {
			panic(err)
		}
		waitForever()
	case "wait":
		os.Stdout.WriteString("started\n")
		waitForever()
	}
	os.Exit(m.Run())
}

func TestReturnsTheCommandsExitCode(t *testing.T) {
	t.Setenv(helperVariable, "exit 3")
	if code := run([]string{"60", os.Args[0]}, io.Discard, io.Discard); code != 3 {
		t.Errorf("run returned %d, want 3", code)
	}
}

func TestKillsACommandThatRunsTooLongWithItsChildren(t *testing.T) {
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	var stderr strings.Builder
	t.Setenv(helperVariable, "wait with a grandchild")
	code := run([]string{"1", os.Args[0]}, writer, &stderr)
	writer.Close()
	if code != failedExitCode {
		t.Errorf("run returned %d, want %d", code, failedExitCode)
	}
	if !strings.HasSuffix(stderr.String(), "ran out of its 1 s time limit.\n") {
		t.Errorf("standard error is %q", stderr.String())
	}
	// The output ends only once no process holds it, so a surviving
	// grandchild makes the test time out here.
	read, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	if string(read) != "started\n" {
		t.Errorf("output is %q, want %q", read, "started\n")
	}
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
