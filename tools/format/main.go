// Command format formats the workspace's source files with the formatter for
// each file's language, or checks that they are already formatted.
//
// Usage:
//
//	bazelisk run //:format -- [--check] [--all | path...]
//
// By default, it formats the files that differ from HEAD or are untracked.
// --all formats every file in the workspace, and paths format every file at or
// under those paths.
package main

import (
	"bytes"
	"errors"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"github.com/bazelbuild/rules_go/go/runfiles"
)

// Runfiles paths of the formatter binaries and plugins, set at link time.
// dprintPluginRlocationPaths separates its paths with spaces.
var (
	bufRlocationPath           string
	buildifierRlocationPath    string
	dprintPluginRlocationPaths string
	dprintRlocationPath        string
	gofumptRlocationPath       string
	ruffRlocationPath          string
	rustfmtRlocationPath       string
)

// Windows limits a command line to 32767 characters.
const maxBatchCharacters = 30000

// Files with these attributes in .gitattributes are not maintained in this
// repository, so they keep their upstream formatting.
var ignoredAttributes = []string{"linguist-generated", "linguist-vendored"}

type formatter struct {
	rlocationPath  string
	fixArguments   []string
	checkArguments []string
	// pathFlag precedes each file for a formatter that does not take files
	// as positional arguments.
	pathFlag string
	// pluginRlocationPaths are the runfiles paths of plugins that the
	// formatter takes after --plugins, followed by -- before the files.
	pluginRlocationPaths []string
}

var (
	buf = &formatter{
		rlocationPath:  bufRlocationPath,
		fixArguments:   []string{"format", "--write", "--disable-symlinks"},
		checkArguments: []string{"format", "--diff", "--exit-code", "--disable-symlinks"},
		pathFlag:       "--path",
	}
	buildifier = &formatter{
		rlocationPath:  buildifierRlocationPath,
		fixArguments:   []string{"-mode=fix", "-lint=fix"},
		checkArguments: []string{"-mode=check", "-lint=warn"},
	}
	// buildifier -lint=fix succeeds even when warnings that it cannot fix
	// remain, so formatting runs this afterward to report them. A check
	// already reports them through buildifier's own check.
	buildifierLint = &formatter{
		rlocationPath: buildifierRlocationPath,
		fixArguments:  []string{"-mode=check", "-lint=warn"},
	}
	dprint = &formatter{
		rlocationPath: dprintRlocationPath,
		// At the default log level, dprint reports every file it formats, and
		// at lower log levels its check reports no diffs.
		fixArguments:         []string{"fmt", "--log-level=warn"},
		checkArguments:       []string{"check"},
		pluginRlocationPaths: strings.Fields(dprintPluginRlocationPaths),
	}
	gofumpt = &formatter{
		rlocationPath: gofumptRlocationPath,
		fixArguments:  []string{"-w"},
		// -l exits successfully even when files are unformatted, but -d
		// does not.
		checkArguments: []string{"-d"},
	}
	ruff = &formatter{
		rlocationPath: ruffRlocationPath,
		// --force-exclude applies the configured exclusions to files named
		// on the command line.
		fixArguments:   []string{"format", "--force-exclude", "--quiet"},
		checkArguments: []string{"format", "--check", "--force-exclude", "--diff", "--quiet"},
	}
	rustfmt = &formatter{
		rlocationPath:  rustfmtRlocationPath,
		fixArguments:   []string{"--edition", "2024"},
		checkArguments: []string{"--edition", "2024", "--check"},
	}
)

// The formatters run in this order so that their output is deterministic.
var formatters = []*formatter{buf, buildifier, buildifierLint, dprint, gofumpt, ruff, rustfmt}

// Formatters rewrite whole files, so a file with several formatters is
// formatted by one of them at a time, in order.
var formattersByExtension = map[string][]*formatter{
	".bazel": {buildifier, buildifierLint},
	".bzl":   {buildifier, buildifierLint},
	".go":    {gofumpt},
	".json":  {dprint},
	".json5": {dprint},
	".jsonc": {dprint},
	// ruff formats the Python code blocks in Markdown files.
	".md":    {dprint, ruff},
	".proto": {buf},
	".py":    {ruff},
	".pyi":   {ruff},
	".rs":    {rustfmt},
	".sh":    {dprint},
	".toml":  {dprint},
	".yaml":  {dprint},
	".yml":   {dprint},
}

func formattersFor(path string) []*formatter {
	name := filepath.Base(path)
	if name == "BUILD" {
		return []*formatter{buildifier, buildifierLint}
	}
	return formattersByExtension[filepath.Ext(name)]
}

func main() {
	log.SetFlags(0)
	check := flag.Bool("check", false, "report unformatted files instead of formatting them")
	all := flag.Bool("all", false, "format every file instead of only the files that differ from HEAD or are untracked")
	flag.Parse()

	workspace := os.Getenv("BUILD_WORKSPACE_DIRECTORY")
	if workspace == "" {
		log.Fatal("format must be run with bazel run")
	}
	pathspecs, err := workspacePathspecs(workspace, os.Getenv("BUILD_WORKING_DIRECTORY"), flag.Args())
	if err != nil {
		log.Fatal(err)
	}
	stages := formattableFiles(workspace, listFiles(workspace, *all || len(pathspecs) > 0, pathspecs))

	allRunfiles, err := runfiles.New()
	if err != nil {
		log.Fatal(err)
	}
	succeeded := true
	for _, files := range stages {
		succeeded = runAll(formatterCommands(allRunfiles, workspace, *check, files)) && succeeded
	}
	if !succeeded {
		if *check && *all {
			log.Fatal("Files are not formatted. Run `bazelisk run //:format -- --all` to format them.")
		}
		if *check {
			log.Fatal("Files are not formatted. Run `bazelisk run //:format` to format them.")
		}
		os.Exit(1)
	}
}

// formatterCommands returns the formatter runs that format the files, which
// are grouped by formatter.
func formatterCommands(allRunfiles *runfiles.Runfiles, workspace string, check bool, files map[*formatter][]string) []*exec.Cmd {
	var result []*exec.Cmd
	for _, formatter := range formatters {
		arguments := formatter.fixArguments
		if check {
			arguments = formatter.checkArguments
		}
		if len(files[formatter]) == 0 || arguments == nil {
			continue
		}
		tool, err := allRunfiles.Rlocation(formatter.rlocationPath)
		if err != nil {
			log.Fatal(err)
		}
		if len(formatter.pluginRlocationPaths) > 0 {
			arguments = append(append([]string{}, arguments...), "--plugins")
			for _, pluginRlocationPath := range formatter.pluginRlocationPaths {
				plugin, err := allRunfiles.Rlocation(pluginRlocationPath)
				if err != nil {
					log.Fatal(err)
				}
				arguments = append(arguments, plugin)
			}
			arguments = append(arguments, "--")
		}
		for _, batch := range batches(formatter.pathFlag, files[formatter]) {
			command := exec.Command(tool, append(append([]string{}, arguments...), batch...)...)
			command.Dir = workspace
			command.Env = append(os.Environ(), allRunfiles.Env()...)
			result = append(result, command)
		}
	}
	return result
}

// workspacePathspecs converts paths relative to the directory where the user
// ran bazel into git pathspecs relative to the workspace.
func workspacePathspecs(workspace, workingDirectory string, paths []string) ([]string, error) {
	var pathspecs []string
	for _, path := range paths {
		if !filepath.IsAbs(path) {
			path = filepath.Join(workingDirectory, path)
		}
		relative, err := filepath.Rel(workspace, path)
		if err != nil {
			return nil, err
		}
		pathspecs = append(pathspecs, filepath.ToSlash(relative))
	}
	return pathspecs, nil
}

func listFiles(workspace string, allTracked bool, pathspecs []string) []string {
	untracked := git(workspace, nil, append([]string{"ls-files", "-z", "--others", "--exclude-standard", "--"}, pathspecs...)...)
	var tracked []byte
	if allTracked {
		tracked = git(workspace, nil, append([]string{"ls-files", "-z", "--cached", "--"}, pathspecs...)...)
	} else {
		tracked = git(workspace, nil, append([]string{"diff", "-z", "--name-only", "--no-renames", "HEAD", "--"}, pathspecs...)...)
	}
	return append(splitNul(tracked), splitNul(untracked)...)
}

// formattableFiles groups the regular files that have formatters into stages,
// where stage N holds each file's Nth formatter, and groups each stage's files
// by formatter. Symbolic links are skipped because their targets are formatted
// under their own paths.
func formattableFiles(workspace string, paths []string) []map[*formatter][]string {
	var candidates []string
	for _, path := range paths {
		if formattersFor(path) == nil {
			continue
		}
		info, err := os.Lstat(filepath.Join(workspace, path))
		// Files deleted from the working tree are still listed in the index.
		if errors.Is(err, fs.ErrNotExist) {
			continue
		}
		if err != nil {
			log.Fatal(err)
		}
		if info.Mode().IsRegular() {
			candidates = append(candidates, path)
		}
	}
	if len(candidates) == 0 {
		return nil
	}
	attributeArguments := append([]string{"check-attr", "-z", "--stdin"}, ignoredAttributes...)
	ignored := ignoredFiles(git(workspace, []byte(strings.Join(candidates, "\x00")), attributeArguments...))
	var stages []map[*formatter][]string
	for _, path := range candidates {
		if ignored[path] {
			continue
		}
		for stage, stageFormatter := range formattersFor(path) {
			if stage == len(stages) {
				stages = append(stages, map[*formatter][]string{})
			}
			stages[stage][stageFormatter] = append(stages[stage][stageFormatter], path)
		}
	}
	return stages
}

// ignoredFiles reads the output of `git check-attr -z`, which is a sequence
// of path, attribute, and value fields.
func ignoredFiles(checkAttrOutput []byte) map[string]bool {
	fields := splitNul(checkAttrOutput)
	ignored := map[string]bool{}
	for index := 0; index+2 < len(fields); index += 3 {
		value := fields[index+2]
		if value == "set" || value == "true" {
			ignored[fields[index]] = true
		}
	}
	return ignored
}

// batches splits files into argument lists that fit on one command line.
func batches(pathFlag string, files []string) [][]string {
	var result [][]string
	var batch []string
	characters := 0
	for _, file := range files {
		arguments := []string{file}
		if pathFlag != "" {
			arguments = []string{pathFlag, file}
		}
		// Each argument is followed by a space.
		length := len(strings.Join(arguments, " ")) + 1
		if len(batch) > 0 && characters+length > maxBatchCharacters {
			result = append(result, batch)
			batch = nil
			characters = 0
		}
		batch = append(batch, arguments...)
		characters += length
	}
	if len(batch) > 0 {
		result = append(result, batch)
	}
	return result
}

// runAll runs the commands concurrently and prints their output in order once
// they have all finished. It reports whether every command succeeded.
func runAll(commands []*exec.Cmd) bool {
	outputs := make([]bytes.Buffer, len(commands))
	failures := make([]error, len(commands))
	var group sync.WaitGroup
	for index, command := range commands {
		command.Stdout = &outputs[index]
		command.Stderr = &outputs[index]
		group.Go(func() {
			failures[index] = command.Run()
		})
	}
	group.Wait()
	succeeded := true
	for index, command := range commands {
		os.Stderr.Write(outputs[index].Bytes())
		if failures[index] != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", filepath.Base(command.Path), failures[index])
			succeeded = false
		}
	}
	return succeeded
}

func git(workspace string, stdin []byte, arguments ...string) []byte {
	command := exec.Command("git", arguments...)
	command.Dir = workspace
	command.Stdin = bytes.NewReader(stdin)
	command.Stderr = os.Stderr
	output, err := command.Output()
	if err != nil {
		log.Fatalf("git %s: %v", arguments[0], err)
	}
	return output
}

func splitNul(output []byte) []string {
	if len(output) == 0 {
		return nil
	}
	return strings.Split(strings.TrimSuffix(string(output), "\x00"), "\x00")
}
