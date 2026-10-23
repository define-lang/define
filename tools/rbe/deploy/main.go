// Command deploy installs the rbe binary it was built with and restarts the rbe
// service on this machine. Run it with bazelisk run //tools/rbe/deploy after
// setup.sh has set up the service; see ../README.md.
package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

const (
	installedBinary = "/usr/local/libexec/rbe/rbe"
	socket          = "/run/rbe/rbe.sock"
)

func main() {
	if len(os.Args) != 2 {
		log.Fatal("usage: bazelisk run //tools/rbe/deploy")
	}
	// bazel run starts programs in the main repository's directory of their
	// runfiles, and the argument is the rbe binary's path in the runfiles.
	if err := install(filepath.Join("..", os.Args[1])); err != nil {
		log.Fatalf("installing %s: %v", installedBinary, err)
	}
	// setup.sh lets the developer run exactly this command without a password.
	restart := exec.Command("sudo", "--non-interactive", "systemctl", "restart", "rbe.service")
	restart.Stdout = os.Stdout
	restart.Stderr = os.Stderr
	if err := restart.Run(); err != nil {
		log.Fatalf("restarting rbe.service: %v", err)
	}
	if err := checkServing(); err != nil {
		log.Fatalf("rbe.service did not start serving; see journalctl -u rbe.service: %v", err)
	}
	fmt.Println("Deployed rbe.")
}

// install replaces the installed binary by renaming over it, so the running
// service keeps its old binary until it restarts.
func install(binary string) error {
	source, err := os.Open(binary)
	if err != nil {
		return err
	}
	defer source.Close()
	temporary, err := os.CreateTemp(filepath.Dir(installedBinary), ".rbe-")
	if err != nil {
		return err
	}
	defer os.Remove(temporary.Name())
	if _, err := io.Copy(temporary, source); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Chmod(0o755); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(temporary.Name(), installedBinary)
}

func checkServing() error {
	connection, err := grpc.NewClient("unix://"+socket, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return err
	}
	defer connection.Close()
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	_, err = repb.NewCapabilitiesClient(connection).GetCapabilities(ctx, &repb.GetCapabilitiesRequest{}, grpc.WaitForReady(true))
	return err
}
