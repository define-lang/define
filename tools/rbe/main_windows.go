package main

import (
	"errors"
	"flag"
	"log"
	"net"

	"golang.org/x/sys/windows/svc"
	"golang.org/x/sys/windows/svc/eventlog"
	"google.golang.org/grpc"
)

// serviceName names the Windows service and its event log source, which
// tools/windows_vm:deploy_rbe creates.
const serviceName = "rbe"

var listenAddress = flag.String("listen", "", "TCP address to serve on, such as :8980")

// eventLogWriter sends the log to the Windows event log, since a service has
// no console.
type eventLogWriter struct {
	log *eventlog.Log
}

func (writer eventLogWriter) Write(message []byte) (int, error) {
	if err := writer.log.Info(1, string(message)); err != nil {
		return 0, err
	}
	return len(message), nil
}

func setUpLogging() error {
	isService, err := svc.IsWindowsService()
	if err != nil || !isService {
		return err
	}
	eventLog, err := eventlog.Open(serviceName)
	if err != nil {
		return err
	}
	// The event log records the time itself.
	log.SetFlags(0)
	log.SetOutput(eventLogWriter{log: eventLog})
	return nil
}

func listen() (net.Listener, error) {
	if *listenAddress == "" {
		return nil, errors.New("--listen is required")
	}
	return net.Listen("tcp", *listenAddress)
}

func serve(server *grpc.Server, listener net.Listener) error {
	isService, err := svc.IsWindowsService()
	if err != nil {
		return err
	}
	if !isService {
		return serveUntilSignal(server, listener)
	}
	return svc.Run(serviceName, &windowsService{server: server, listener: listener})
}

// windowsService serves until the service control manager stops it.
type windowsService struct {
	server   *grpc.Server
	listener net.Listener
}

func (service *windowsService) Execute(_ []string, requests <-chan svc.ChangeRequest, statuses chan<- svc.Status) (bool, uint32) {
	served := make(chan error, 1)
	go func() { served <- service.server.Serve(service.listener) }()
	statuses <- svc.Status{State: svc.Running, Accepts: svc.AcceptStop | svc.AcceptShutdown}
	for {
		select {
		case err := <-served:
			// A nonzero exit code counts as a failure, so the service control
			// manager's recovery actions restart the service.
			log.Printf("serving: %v", err)
			return false, 1
		case request := <-requests:
			switch request.Cmd {
			case svc.Interrogate:
				statuses <- request.CurrentStatus
			case svc.Stop, svc.Shutdown:
				statuses <- svc.Status{State: svc.StopPending}
				service.server.Stop()
				<-served
				return false, 0
			}
		}
	}
}
