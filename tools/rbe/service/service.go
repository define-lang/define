// Package service serves the REAPI and ByteStream gRPC services from a local
// store and executor.
package service

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"log"
	"strconv"
	"strings"
	"sync"
	"time"

	"cloud.google.com/go/longrunning/autogen/longrunningpb"
	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"github.com/bazelbuild/remote-apis/build/bazel/semver"
	"google.golang.org/genproto/googleapis/bytestream"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"

	"github.com/define-lang/define/tools/rbe/cas"
	"github.com/define-lang/define/tools/rbe/execution"
)

// Bazel sends batches up to the size the server advertises, and a request
// carries some overhead beyond its blobs.
const (
	maxBatchBytes   = 4 << 20
	MaxMessageBytes = maxBatchBytes + 1<<20
	readChunkBytes  = 1 << 20
)

// A client whose Execute stream breaks reconnects with WaitExecution, which
// finds a finished operation for this long.
const finishedOperationLifetime = time.Minute

type operation struct {
	name         string
	actionDigest *repb.Digest
	done         chan struct{}
	response     *repb.ExecuteResponse
}

// Server implements the services that Bazel uses for remote execution.
type Server struct {
	repb.UnimplementedActionCacheServer
	repb.UnimplementedCapabilitiesServer
	repb.UnimplementedContentAddressableStorageServer
	repb.UnimplementedExecutionServer
	bytestream.UnimplementedByteStreamServer

	store    *cas.Store
	executor *execution.Executor

	mu         sync.Mutex
	operations map[string]*operation
	running    map[cas.Key]*operation
}

// New creates a server.
func New(store *cas.Store, executor *execution.Executor) *Server {
	return &Server{
		store:      store,
		executor:   executor,
		operations: map[string]*operation{},
		running:    map[cas.Key]*operation{},
	}
}

// Register registers the server's services.
func (server *Server) Register(registrar *grpc.Server) {
	repb.RegisterActionCacheServer(registrar, server)
	repb.RegisterCapabilitiesServer(registrar, server)
	repb.RegisterContentAddressableStorageServer(registrar, server)
	repb.RegisterExecutionServer(registrar, server)
	bytestream.RegisterByteStreamServer(registrar, server)
}

func invalidDigest(err error) error {
	return status.Error(codes.InvalidArgument, err.Error())
}

// GetCapabilities implements repb.CapabilitiesServer.
func (server *Server) GetCapabilities(context.Context, *repb.GetCapabilitiesRequest) (*repb.ServerCapabilities, error) {
	return &repb.ServerCapabilities{
		CacheCapabilities: &repb.CacheCapabilities{
			DigestFunctions:               []repb.DigestFunction_Value{repb.DigestFunction_SHA256},
			ActionCacheUpdateCapabilities: &repb.ActionCacheUpdateCapabilities{UpdateEnabled: true},
			MaxBatchTotalSizeBytes:        maxBatchBytes,
			SymlinkAbsolutePathStrategy:   repb.SymlinkAbsolutePathStrategy_ALLOWED,
		},
		ExecutionCapabilities: &repb.ExecutionCapabilities{
			DigestFunction:  repb.DigestFunction_SHA256,
			DigestFunctions: []repb.DigestFunction_Value{repb.DigestFunction_SHA256},
			ExecEnabled:     true,
		},
		LowApiVersion:  &semver.SemVer{Major: 2},
		HighApiVersion: &semver.SemVer{Major: 2, Minor: 3},
	}, nil
}

// FindMissingBlobs implements repb.ContentAddressableStorageServer.
func (server *Server) FindMissingBlobs(_ context.Context, request *repb.FindMissingBlobsRequest) (*repb.FindMissingBlobsResponse, error) {
	response := &repb.FindMissingBlobsResponse{}
	for _, digest := range request.BlobDigests {
		key, err := cas.KeyFromDigest(digest)
		if err != nil {
			return nil, invalidDigest(err)
		}
		if !server.store.Has(key) {
			response.MissingBlobDigests = append(response.MissingBlobDigests, digest)
		}
	}
	return response, nil
}

// BatchUpdateBlobs implements repb.ContentAddressableStorageServer.
func (server *Server) BatchUpdateBlobs(_ context.Context, request *repb.BatchUpdateBlobsRequest) (*repb.BatchUpdateBlobsResponse, error) {
	response := &repb.BatchUpdateBlobsResponse{}
	for _, blob := range request.Requests {
		blobStatus := status.New(codes.OK, "")
		key, err := cas.KeyFromDigest(blob.Digest)
		switch {
		case err != nil:
			blobStatus = status.New(codes.InvalidArgument, err.Error())
		case blob.Compressor != repb.Compressor_IDENTITY:
			blobStatus = status.New(codes.InvalidArgument, "compressed blobs are not supported")
		default:
			if err := server.store.Put(key, blob.Data); err != nil {
				blobStatus = status.New(codes.InvalidArgument, err.Error())
			}
		}
		response.Responses = append(response.Responses, &repb.BatchUpdateBlobsResponse_Response{
			Digest: blob.Digest,
			Status: blobStatus.Proto(),
		})
	}
	return response, nil
}

// BatchReadBlobs implements repb.ContentAddressableStorageServer.
func (server *Server) BatchReadBlobs(_ context.Context, request *repb.BatchReadBlobsRequest) (*repb.BatchReadBlobsResponse, error) {
	response := &repb.BatchReadBlobsResponse{}
	for _, digest := range request.Digests {
		key, err := cas.KeyFromDigest(digest)
		if err != nil {
			return nil, invalidDigest(err)
		}
		blob := &repb.BatchReadBlobsResponse_Response{Digest: digest}
		blob.Data, err = server.store.Read(key)
		blob.Status = blobStatus(err).Proto()
		response.Responses = append(response.Responses, blob)
	}
	return response, nil
}

func blobStatus(err error) *status.Status {
	var missingErr *cas.MissingBlobsError
	switch {
	case err == nil:
		return status.New(codes.OK, "")
	case errors.As(err, &missingErr):
		return status.New(codes.NotFound, err.Error())
	default:
		return status.New(codes.Internal, err.Error())
	}
}

// parseResourceName finds the blob that a ByteStream resource name refers to:
// "[{instance}/]blobs/{hash}/{size}" for reads and
// "[{instance}/]uploads/{uuid}/blobs/{hash}/{size}[/{metadata}]" for writes.
func parseResourceName(name string) (cas.Key, error) {
	segments := strings.Split(name, "/")
	for index, segment := range segments {
		if segment == "compressed-blobs" {
			return cas.Key{}, status.Error(codes.Unimplemented, "compressed blobs are not supported")
		}
		if segment != "blobs" || index+2 >= len(segments) {
			continue
		}
		size, err := strconv.ParseInt(segments[index+2], 10, 64)
		if err != nil {
			return cas.Key{}, status.Errorf(codes.InvalidArgument, "resource name %q has an invalid size", name)
		}
		key, err := cas.KeyFromDigest(&repb.Digest{Hash: segments[index+1], SizeBytes: size})
		if err != nil {
			return cas.Key{}, invalidDigest(err)
		}
		return key, nil
	}
	return cas.Key{}, status.Errorf(codes.InvalidArgument, "resource name %q names no blob", name)
}

// Read implements bytestream.ByteStreamServer.
func (server *Server) Read(request *bytestream.ReadRequest, stream bytestream.ByteStream_ReadServer) error {
	key, err := parseResourceName(request.ResourceName)
	if err != nil {
		return err
	}
	if request.ReadOffset < 0 || request.ReadOffset > key.Size || request.ReadLimit < 0 {
		return status.Error(codes.OutOfRange, "read offset or limit is out of range")
	}
	reader, err := server.store.Open(key)
	if err != nil {
		return blobStatus(err).Err()
	}
	defer reader.Close()
	if _, err := io.CopyN(io.Discard, reader, request.ReadOffset); err != nil {
		return err
	}
	remaining := key.Size - request.ReadOffset
	if request.ReadLimit > 0 && request.ReadLimit < remaining {
		remaining = request.ReadLimit
	}
	buffer := make([]byte, min(remaining, readChunkBytes))
	for remaining > 0 {
		chunk := buffer[:min(remaining, int64(len(buffer)))]
		if _, err := io.ReadFull(reader, chunk); err != nil {
			return err
		}
		if err := stream.Send(&bytestream.ReadResponse{Data: chunk}); err != nil {
			return err
		}
		remaining -= int64(len(chunk))
	}
	return nil
}

// Write implements bytestream.ByteStreamServer.
func (server *Server) Write(stream bytestream.ByteStream_WriteServer) error {
	request, err := stream.Recv()
	if err != nil {
		return err
	}
	key, err := parseResourceName(request.ResourceName)
	if err != nil {
		return err
	}
	if server.store.Has(key) {
		return stream.SendAndClose(&bytestream.WriteResponse{CommittedSize: key.Size})
	}
	writer, err := server.store.NewWriter(key)
	if err != nil {
		return err
	}
	defer writer.Abort()
	for {
		if request.WriteOffset != writer.Written() {
			return status.Errorf(codes.InvalidArgument, "write offset %d does not follow the %d bytes written", request.WriteOffset, writer.Written())
		}
		if _, err := writer.Write(request.Data); err != nil {
			return status.Error(codes.InvalidArgument, err.Error())
		}
		if request.FinishWrite {
			break
		}
		request, err = stream.Recv()
		if err != nil {
			return err
		}
	}
	if err := writer.Commit(); err != nil {
		return status.Error(codes.InvalidArgument, err.Error())
	}
	return stream.SendAndClose(&bytestream.WriteResponse{CommittedSize: key.Size})
}

// GetActionResult implements repb.ActionCacheServer.
func (server *Server) GetActionResult(_ context.Context, request *repb.GetActionResultRequest) (*repb.ActionResult, error) {
	key, err := cas.KeyFromDigest(request.ActionDigest)
	if err != nil {
		return nil, invalidDigest(err)
	}
	result, err := server.store.ActionResult(key)
	if err != nil {
		return nil, err
	}
	if result == nil {
		return nil, status.Error(codes.NotFound, "no cached result")
	}
	return result, nil
}

// UpdateActionResult implements repb.ActionCacheServer.
func (server *Server) UpdateActionResult(_ context.Context, request *repb.UpdateActionResultRequest) (*repb.ActionResult, error) {
	key, err := cas.KeyFromDigest(request.ActionDigest)
	if err != nil {
		return nil, invalidDigest(err)
	}
	if err := server.store.PutActionResult(key, request.ActionResult); err != nil {
		return nil, err
	}
	return request.ActionResult, nil
}

// Execute implements repb.ExecutionServer.
func (server *Server) Execute(request *repb.ExecuteRequest, stream grpc.ServerStreamingServer[longrunningpb.Operation]) error {
	actionKey, err := cas.KeyFromDigest(request.ActionDigest)
	if err != nil {
		return invalidDigest(err)
	}
	if !request.SkipCacheLookup {
		result, err := server.store.ActionResult(actionKey)
		if err != nil {
			return err
		}
		if result != nil {
			finished := &operation{
				name:         newOperationName(),
				actionDigest: request.ActionDigest,
				response:     &repb.ExecuteResponse{Result: result, CachedResult: true},
			}
			return sendFinished(stream, finished)
		}
	}
	current := server.start(actionKey, request)
	if err := stream.Send(executingOperation(current)); err != nil {
		return err
	}
	return server.wait(current, stream)
}

// WaitExecution implements repb.ExecutionServer.
func (server *Server) WaitExecution(request *repb.WaitExecutionRequest, stream grpc.ServerStreamingServer[longrunningpb.Operation]) error {
	server.mu.Lock()
	current, found := server.operations[request.Name]
	server.mu.Unlock()
	if !found {
		return status.Errorf(codes.NotFound, "no operation named %q", request.Name)
	}
	return server.wait(current, stream)
}

func newOperationName() string {
	var random [16]byte
	_, _ = rand.Read(random[:])
	return hex.EncodeToString(random[:])
}

// start starts running an action, or joins the run of an identical action
// that is already running unless the request skips the cache.
func (server *Server) start(actionKey cas.Key, request *repb.ExecuteRequest) *operation {
	server.mu.Lock()
	defer server.mu.Unlock()
	if !request.SkipCacheLookup {
		if current, found := server.running[actionKey]; found {
			return current
		}
	}
	current := &operation{name: newOperationName(), actionDigest: request.ActionDigest, done: make(chan struct{})}
	server.operations[current.name] = current
	if !request.SkipCacheLookup {
		server.running[actionKey] = current
	}
	go server.run(actionKey, current)
	return current
}

// run runs an operation's action to completion even if its clients go away,
// so that its result is cached for them when they try again.
func (server *Server) run(actionKey cas.Key, current *operation) {
	current.response = server.execute(actionKey)
	server.mu.Lock()
	if server.running[actionKey] == current {
		delete(server.running, actionKey)
	}
	server.mu.Unlock()
	close(current.done)
	time.AfterFunc(finishedOperationLifetime, func() {
		server.mu.Lock()
		delete(server.operations, current.name)
		server.mu.Unlock()
	})
}

func (server *Server) execute(actionKey cas.Key) *repb.ExecuteResponse {
	action := &repb.Action{}
	if err := server.store.ReadMessage(actionKey, action); err != nil {
		return &repb.ExecuteResponse{Status: executionStatus(err).Proto()}
	}
	commandKey, err := cas.KeyFromDigest(action.CommandDigest)
	if err != nil {
		return &repb.ExecuteResponse{Status: status.New(codes.InvalidArgument, err.Error()).Proto()}
	}
	command := &repb.Command{}
	if err := server.store.ReadMessage(commandKey, command); err != nil {
		return &repb.ExecuteResponse{Status: executionStatus(err).Proto()}
	}
	result, err := server.executor.Execute(context.Background(), action, command)
	if err != nil {
		return &repb.ExecuteResponse{Result: result, Status: executionStatus(err).Proto()}
	}
	if result.ExitCode == 0 && !action.DoNotCache {
		if err := server.store.PutActionResult(actionKey, result); err != nil {
			log.Printf("caching the result of action %s: %v", actionKey, err)
		}
	}
	return &repb.ExecuteResponse{Result: result}
}

// executionStatus describes a failed execution the way REAPI asks: missing
// inputs as a precondition failure that names each blob, so that the client
// uploads them and tries again.
func executionStatus(err error) *status.Status {
	var missingErr *cas.MissingBlobsError
	var timeoutErr *execution.TimeoutError
	switch {
	case errors.As(err, &missingErr):
		failure := &errdetails.PreconditionFailure{}
		for _, key := range missingErr.Keys {
			failure.Violations = append(failure.Violations, &errdetails.PreconditionFailure_Violation{
				Type:    "MISSING",
				Subject: "blobs/" + key.String(),
			})
		}
		missingStatus, detailsErr := status.New(codes.FailedPrecondition, err.Error()).WithDetails(failure)
		if detailsErr != nil {
			panic(fmt.Sprintf("attaching missing blobs to a status: %v", detailsErr))
		}
		return missingStatus
	case errors.As(err, &timeoutErr):
		return status.New(codes.DeadlineExceeded, err.Error())
	default:
		return status.New(codes.Internal, err.Error())
	}
}

func (server *Server) wait(current *operation, stream grpc.ServerStreamingServer[longrunningpb.Operation]) error {
	select {
	case <-current.done:
		return sendFinished(stream, current)
	case <-stream.Context().Done():
		return stream.Context().Err()
	}
}

func executingOperation(current *operation) *longrunningpb.Operation {
	return &longrunningpb.Operation{
		Name: current.name,
		Metadata: mustAny(&repb.ExecuteOperationMetadata{
			Stage:        repb.ExecutionStage_EXECUTING,
			ActionDigest: current.actionDigest,
		}),
	}
}

func sendFinished(stream grpc.ServerStreamingServer[longrunningpb.Operation], finished *operation) error {
	return stream.Send(&longrunningpb.Operation{
		Name: finished.name,
		Done: true,
		Metadata: mustAny(&repb.ExecuteOperationMetadata{
			Stage:        repb.ExecutionStage_COMPLETED,
			ActionDigest: finished.actionDigest,
		}),
		Result: &longrunningpb.Operation_Response{Response: mustAny(finished.response)},
	})
}

func mustAny(message proto.Message) *anypb.Any {
	packed, err := anypb.New(message)
	if err != nil {
		panic(fmt.Sprintf("packing %T: %v", message, err))
	}
	return packed
}
