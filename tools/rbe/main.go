// Command rbe serves Bazel remote caching and execution for builds on the same
// machine. On Linux, it serves on a socket that systemd passes to it; see
// README.md. On Windows, it runs as a Windows service; see
// tools/windows_vm/README.md.
package main

import (
	"flag"
	"log"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
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
	if err := setUpLogging(); err != nil {
		log.Fatalf("setting up logging: %v", err)
	}
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
	listener, err := listen()
	if err != nil {
		log.Fatalf("listening: %v", err)
	}
	server := grpc.NewServer(
		grpc.MaxRecvMsgSize(service.MaxMessageBytes),
		grpc.MaxSendMsgSize(service.MaxMessageBytes),
	)
	service.New(store, executor).Register(server)

	log.Printf("serving on %s", listener.Addr())
	if err := serve(server, listener); err != nil {
		log.Fatalf("serving: %v", err)
	}
}

// serveUntilSignal serves until the process is told to stop.
func serveUntilSignal(server *grpc.Server, listener net.Listener) error {
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-signals
		server.Stop()
	}()
	return server.Serve(listener)
}
