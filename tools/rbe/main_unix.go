//go:build unix

package main

import (
	"errors"
	"net"
	"os"
	"strconv"

	"google.golang.org/grpc"
)

func setUpLogging() error {
	return nil
}

// listen returns the one socket that systemd passed to this process. systemd
// holds the socket while the service restarts, so clients that connect during
// a deploy wait instead of failing.
func listen() (net.Listener, error) {
	if os.Getenv("LISTEN_PID") != strconv.Itoa(os.Getpid()) || os.Getenv("LISTEN_FDS") != "1" {
		return nil, errors.New("expected exactly one socket from systemd socket activation")
	}
	// systemd passes its sockets starting at file descriptor 3.
	file := os.NewFile(3, "systemd socket")
	defer file.Close()
	return net.FileListener(file)
}

func serve(server *grpc.Server, listener net.Listener) error {
	return serveUntilSignal(server, listener)
}
