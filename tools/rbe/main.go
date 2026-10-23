// Command rbe serves Bazel remote caching and execution for builds on the same
// machine. It serves on a socket that systemd passes to it; see README.md.
package main

import (
	"errors"
	"flag"
	"log"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strconv"
	"syscall"

	"google.golang.org/grpc"

	"github.com/define-lang/define/tools/rbe/cas"
	"github.com/define-lang/define/tools/rbe/execution"
	"github.com/define-lang/define/tools/rbe/service"
)

func main() {
	root := flag.String("root", "", "directory for the store and action directories; inputs are hardlinked, so both must be on one filesystem")
	maxCasBytes := flag.Int64("max_cas_bytes", 100<<30, "bytes of blobs to keep before evicting the least recently used")
	maxDirectories := flag.Int("max_cached_directories", 100_000, "decoded input directories to keep in memory")
	slots := flag.Int("slots", runtime.NumCPU(), "actions to stage or run at once")
	deleters := flag.Int("deleters", 8, "finished action directories to delete at once")
	flag.Parse()
	if *root == "" {
		log.Fatal("--root is required")
	}

	store, err := cas.Open(filepath.Join(*root, "cas"), *maxCasBytes, *maxDirectories)
	if err != nil {
		log.Fatalf("opening the store: %v", err)
	}
	executor, err := execution.New(store, filepath.Join(*root, "work"), *slots, *deleters)
	if err != nil {
		log.Fatalf("creating the executor: %v", err)
	}
	listener, err := systemdListener()
	if err != nil {
		log.Fatalf("getting the socket from systemd: %v", err)
	}
	server := grpc.NewServer(
		grpc.MaxRecvMsgSize(service.MaxMessageBytes),
		grpc.MaxSendMsgSize(service.MaxMessageBytes),
	)
	service.New(store, executor).Register(server)

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-signals
		server.Stop()
	}()
	log.Printf("serving on %s", listener.Addr())
	if err := server.Serve(listener); err != nil {
		log.Fatalf("serving: %v", err)
	}
}

// systemdListener returns the one socket that systemd passed to this process.
// systemd holds the socket while the service restarts, so clients that connect
// during a deploy wait instead of failing.
func systemdListener() (net.Listener, error) {
	if os.Getenv("LISTEN_PID") != strconv.Itoa(os.Getpid()) || os.Getenv("LISTEN_FDS") != "1" {
		return nil, errors.New("expected exactly one socket from systemd socket activation")
	}
	// systemd passes its sockets starting at file descriptor 3.
	file := os.NewFile(3, "systemd socket")
	defer file.Close()
	return net.FileListener(file)
}
