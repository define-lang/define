package main_test

import (
	"errors"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/bazelbuild/rules_go/go/runfiles"
)

// Runfiles paths set at link time.
var (
	dprintConfigRlocationPath string
	formatRlocationPath       string
)

func TestMain(m *testing.M) {
	// Each test isolates HOME, which would give dprint an empty cache and make
	// it compile its plugins again in every test. That made the tests slow
	// enough to time out on loaded CI machines.
	cacheDirectory, err := os.MkdirTemp("", "dprint-cache")
	if err != nil {
		log.Fatal(err)
	}
	if err := os.Setenv("DPRINT_CACHE_DIR", cacheDirectory); err != nil {
		log.Fatal(err)
	}
	exitCode := m.Run()
	if err := os.RemoveAll(cacheDirectory); err != nil {
		log.Fatal(err)
	}
	os.Exit(exitCode)
}

func newRepository(t *testing.T, files map[string]string) string {
	t.Helper()
	// Isolate git from the user's and the system's configuration.
	t.Setenv("HOME", t.TempDir())
	t.Setenv("GIT_CONFIG_NOSYSTEM", "1")
	repository := t.TempDir()
	writeFiles(t, repository, files)
	// The workspace's dprint configuration gives each file type only one of
	// the dprint plugins that can format it.
	dprintConfig, err := os.ReadFile(rlocation(t, dprintConfigRlocationPath))
	if err != nil {
		t.Fatal(err)
	}
	writeFiles(t, repository, map[string]string{"dprint.jsonc": string(dprintConfig)})
	git(t, repository, "init", "--quiet")
	git(t, repository, "add", ".")
	git(t, repository, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "--allow-empty", "--message=Initial")
	return repository
}

func writeFiles(t *testing.T, directory string, files map[string]string) {
	t.Helper()
	for path, content := range files {
		path = filepath.Join(directory, path)
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
}

func git(t *testing.T, repository string, arguments ...string) {
	t.Helper()
	command := exec.Command("git", arguments...)
	command.Dir = repository
	if output, err := command.CombinedOutput(); err != nil {
		t.Fatalf("git %s: %v\n%s", strings.Join(arguments, " "), err, output)
	}
}

func runFormat(t *testing.T, environment []string, arguments ...string) (string, int) {
	t.Helper()
	command := exec.Command(rlocation(t, formatRlocationPath), arguments...)
	command.Env = append(os.Environ(), environment...)
	// Coverage-instrumented binaries need a directory even when a test invokes
	// them only to check their behavior.
	command.Env = append(command.Env, "GOCOVERDIR="+t.TempDir())
	output, err := command.CombinedOutput()
	var exitError *exec.ExitError
	if errors.As(err, &exitError) {
		return string(output), exitError.ExitCode()
	}
	if err != nil {
		t.Fatal(err)
	}
	return string(output), 0
}

func rlocation(t *testing.T, rlocationPath string) string {
	t.Helper()
	path, err := runfiles.Rlocation(rlocationPath)
	if err != nil {
		t.Fatal(err)
	}
	return path
}

func runFormatIn(t *testing.T, workspace, workingDirectory string, arguments ...string) (string, int) {
	t.Helper()
	return runFormat(t, []string{
		"BUILD_WORKSPACE_DIRECTORY=" + workspace,
		"BUILD_WORKING_DIRECTORY=" + workingDirectory,
	}, arguments...)
}

func assertFiles(t *testing.T, directory string, expected map[string]string) {
	t.Helper()
	for path, content := range expected {
		actual, err := os.ReadFile(filepath.Join(directory, path))
		if err != nil {
			t.Fatal(err)
		}
		if string(actual) != content {
			t.Errorf("%s is %q, expected %q", path, actual, content)
		}
	}
}

func assertSucceeded(t *testing.T, output string, exitCode int) {
	t.Helper()
	if exitCode != 0 || output != "" {
		t.Fatalf("format exited with %d and output:\n%s", exitCode, output)
	}
}

func TestAllFormatsEveryLanguage(t *testing.T) {
	repository := newRepository(t, map[string]string{
		"BUILD.bazel": "filegroup(name=\"all\")\n",
		// gofmt keeps a blank line at the start of a function body, but
		// gofumpt removes it.
		"a.go":    "package a\n\nfunc f() {\n\n\tf()\n}\n",
		"a.json":  "{\"a\":1}\n",
		"a.json5": "{a:1}\n",
		"a.jsonc": "{\"a\":1 // b\n}\n",
		"a.md":    "*  a\n",
		"a.proto": "syntax = \"proto3\";\n\npackage   a;\n",
		"a.py":    "x  =  1\n",
		"a.rs":    "fn  main(){}\n",
		"a.sh":    "echo   a\n",
		"a.toml":  "a  =  1\n",
		"a.yaml":  "a:   1\n",
	})
	output, exitCode := runFormatIn(t, repository, repository, "--all")
	assertSucceeded(t, output, exitCode)
	assertFiles(t, repository, map[string]string{
		"BUILD.bazel": "filegroup(name = \"all\")\n",
		"a.go":        "package a\n\nfunc f() {\n\tf()\n}\n",
		"a.json":      "{ \"a\": 1 }\n",
		"a.json5":     "{ a: 1 }\n",
		"a.jsonc":     "{\n  \"a\": 1, // b\n}\n",
		"a.md":        "- a\n",
		"a.proto":     "syntax = \"proto3\";\n\npackage a;\n",
		"a.py":        "x = 1\n",
		"a.rs":        "fn main() {}\n",
		"a.sh":        "echo a\n",
		"a.toml":      "a = 1\n",
		"a.yaml":      "a: 1\n",
	})
}

func TestFormatsMarkdownAndItsPythonCodeBlocks(t *testing.T) {
	// prettier keeps setext headings, but dprint rewrites them as ATX
	// headings.
	repository := newRepository(t, map[string]string{
		"a.md": "A\n=\n\n*  a\n\n```python\nx  =  1\n```\n",
	})
	output, exitCode := runFormatIn(t, repository, repository, "--all")
	assertSucceeded(t, output, exitCode)
	assertFiles(t, repository, map[string]string{
		"a.md": "# A\n\n- a\n\n```python\nx = 1\n```\n",
	})
}

func TestDefaultFormatsOnlyChangedAndUntrackedFiles(t *testing.T) {
	repository := newRepository(t, map[string]string{
		".gitignore":   "ignored.py\n",
		"committed.py": "x  =  1\n",
		"deleted.py":   "x = 1\n",
		"modified.py":  "x = 1\n",
	})
	if err := os.Remove(filepath.Join(repository, "deleted.py")); err != nil {
		t.Fatal(err)
	}
	writeFiles(t, repository, map[string]string{
		"ignored.py":   "x  =  1\n",
		"modified.py":  "x  =  2\n",
		"untracked.py": "x  =  3\n",
	})
	output, exitCode := runFormatIn(t, repository, repository)
	assertSucceeded(t, output, exitCode)
	assertFiles(t, repository, map[string]string{
		"committed.py": "x  =  1\n",
		"ignored.py":   "x  =  1\n",
		"modified.py":  "x = 2\n",
		"untracked.py": "x = 3\n",
	})
}

func TestPathsFormatEveryFileUnderThem(t *testing.T) {
	repository := newRepository(t, map[string]string{
		"a.py":                 "x  =  1\n",
		"directory/a.py":       "x  =  2\n",
		"directory/child/a.py": "x  =  3\n",
		"directory/child/b.py": "x  =  4\n",
	})
	output, exitCode := runFormatIn(t, repository, filepath.Join(repository, "directory"), "child")
	assertSucceeded(t, output, exitCode)
	assertFiles(t, repository, map[string]string{
		"a.py":                 "x  =  1\n",
		"directory/a.py":       "x  =  2\n",
		"directory/child/a.py": "x = 3\n",
		"directory/child/b.py": "x = 4\n",
	})
}

func TestSkipsVendoredAndGeneratedFiles(t *testing.T) {
	repository := newRepository(t, map[string]string{
		".gitattributes": "vendored/** linguist-vendored\ngenerated.py linguist-generated\n",
		"generated.py":   "x  =  1\n",
		"vendored/a.py":  "x  =  2\n",
	})
	output, exitCode := runFormatIn(t, repository, repository, "--all")
	assertSucceeded(t, output, exitCode)
	assertFiles(t, repository, map[string]string{
		"generated.py":  "x  =  1\n",
		"vendored/a.py": "x  =  2\n",
	})
}

func TestSkipsSymbolicLinks(t *testing.T) {
	outside := t.TempDir()
	writeFiles(t, outside, map[string]string{"a.py": "x  =  1\n"})
	repository := newRepository(t, map[string]string{})
	if err := os.Symlink(filepath.Join(outside, "a.py"), filepath.Join(repository, "link.py")); err != nil {
		t.Fatal(err)
	}
	output, exitCode := runFormatIn(t, repository, repository)
	assertSucceeded(t, output, exitCode)
	assertFiles(t, outside, map[string]string{"a.py": "x  =  1\n"})
}

func TestFormatsFilesBeyondOneCommandLine(t *testing.T) {
	// Each file name and the space after it are 103 characters, so 300 of
	// them are longer than one command line.
	files := map[string]string{}
	expected := map[string]string{}
	for index := range 300 {
		path := fmt.Sprintf("%s%03d.py", strings.Repeat("a", 96), index)
		files[path] = "x  =  1\n"
		expected[path] = "x = 1\n"
	}
	repository := newRepository(t, files)
	output, exitCode := runFormatIn(t, repository, repository, "--all")
	assertSucceeded(t, output, exitCode)
	assertFiles(t, repository, expected)
}

func TestCheckSucceedsForFormattedFiles(t *testing.T) {
	repository := newRepository(t, map[string]string{
		"a.go": "package a\n",
		"a.py": "x = 1\n",
	})
	// dprint reports each plugin it compiles into an empty cache, and a check
	// runs at a log level that shows those reports, so this warms the cache.
	output, exitCode := runFormatIn(t, repository, repository, "--all")
	assertSucceeded(t, output, exitCode)
	output, exitCode = runFormatIn(t, repository, repository, "--check", "--all")
	assertSucceeded(t, output, exitCode)
}

func TestCheckReportsUnformattedFilesWithoutChangingThem(t *testing.T) {
	repository := newRepository(t, map[string]string{})
	writeFiles(t, repository, map[string]string{"a.py": "x  =  1\n"})
	output, exitCode := runFormatIn(t, repository, repository, "--check")
	if exitCode != 1 || !strings.HasSuffix(output, "Files are not formatted. Run `bazelisk run //:format` to format them.\n") {
		t.Errorf("format exited with %d and output:\n%s", exitCode, output)
	}
	assertFiles(t, repository, map[string]string{"a.py": "x  =  1\n"})
}

func TestCheckAllSuggestsFormattingAllFiles(t *testing.T) {
	repository := newRepository(t, map[string]string{"a.py": "x  =  1\n"})
	output, exitCode := runFormatIn(t, repository, repository, "--check", "--all")
	if exitCode != 1 || !strings.HasSuffix(output, "Files are not formatted. Run `bazelisk run //:format -- --all` to format them.\n") {
		t.Errorf("format exited with %d and output:\n%s", exitCode, output)
	}
}

func TestCheckReportsUnformattedGoFiles(t *testing.T) {
	repository := newRepository(t, map[string]string{"a.go": "package  a\n"})
	output, exitCode := runFormatIn(t, repository, repository, "--check", "--all")
	if exitCode != 1 || !strings.HasSuffix(output, "gofumpt: exit status 1\nFiles are not formatted. Run `bazelisk run //:format -- --all` to format them.\n") {
		t.Errorf("format exited with %d and output:\n%s", exitCode, output)
	}
	assertFiles(t, repository, map[string]string{"a.go": "package  a\n"})
}

func TestFormatReportsBuildifierWarningsThatItCannotFix(t *testing.T) {
	// buildifier checks the docstrings only of functions with at least five
	// statements.
	repository := newRepository(t, map[string]string{})
	writeFiles(t, repository, map[string]string{
		"a.bzl": "\"\"\"A.\"\"\"\n\ndef f(x):\n    \"\"\"F.\n\n    Args:\n        x: x\n    \"\"\"\n    a  =  x\n    b = a\n    c = b\n    d = c\n    return d\n",
	})
	output, exitCode := runFormatIn(t, repository, repository)
	expected := "a.bzl:4: function-docstring-return: Return value of \"f\" is not documented. (https://github.com/bazel-contrib/buildtools/blob/main/WARNINGS.md#function-docstring-return)\nbuildifier: exit status 4\n"
	if exitCode != 1 || output != expected {
		t.Errorf("format exited with %d and output:\n%s", exitCode, output)
	}
	assertFiles(t, repository, map[string]string{
		"a.bzl": "\"\"\"A.\"\"\"\n\ndef f(x):\n    \"\"\"F.\n\n    Args:\n        x: x\n    \"\"\"\n    a = x\n    b = a\n    c = b\n    d = c\n    return d\n",
	})
}

func TestFormatFailsWhenAFormatterFails(t *testing.T) {
	repository := newRepository(t, map[string]string{})
	writeFiles(t, repository, map[string]string{"a.py": "x = (\n"})
	output, exitCode := runFormatIn(t, repository, repository)
	if exitCode != 1 || !strings.HasSuffix(output, "ruff: exit status 2\n") {
		t.Errorf("format exited with %d and output:\n%s", exitCode, output)
	}
}

func TestRequiresBazelRun(t *testing.T) {
	output, exitCode := runFormat(t, nil)
	if exitCode != 1 || output != "format must be run with bazel run\n" {
		t.Errorf("format exited with %d and output:\n%s", exitCode, output)
	}
}
