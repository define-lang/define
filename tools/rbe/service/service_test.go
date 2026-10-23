package service

import (
	"context"
	"crypto/sha256"
	"io"
	"net"
	"path/filepath"
	"testing"

	"cloud.google.com/go/longrunning/autogen/longrunningpb"
	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"google.golang.org/genproto/googleapis/bytestream"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
	"google.golang.org/protobuf/proto"

	"github.com/define-lang/define/tools/rbe/cas"
	"github.com/define-lang/define/tools/rbe/execution"
)

type client struct {
	connection *grpc.ClientConn
	cas        repb.ContentAddressableStorageClient
	cache      repb.ActionCacheClient
	execution  repb.ExecutionClient
	bytestream bytestream.ByteStreamClient
}

func startServer(t *testing.T) *client {
	t.Helper()
	root := t.TempDir()
	store, err := cas.Open(filepath.Join(root, "cas"), 1<<30, 100)
	if err != nil {
		t.Fatal(err)
	}
	executor, err := execution.New(store, filepath.Join(root, "work"), 4, 1)
	if err != nil {
		t.Fatal(err)
	}
	listener := bufconn.Listen(1 << 20)
	server := grpc.NewServer()
	New(store, executor).Register(server)
	go func() { _ = server.Serve(listener) }()
	t.Cleanup(server.Stop)
	connection, err := grpc.NewClient("passthrough:///bufnet",
		grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return listener.Dial() }),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = connection.Close() })
	return &client{
		connection: connection,
		cas:        repb.NewContentAddressableStorageClient(connection),
		cache:      repb.NewActionCacheClient(connection),
		execution:  repb.NewExecutionClient(connection),
		bytestream: bytestream.NewByteStreamClient(connection),
	}
}

func digestOf(contents []byte) *repb.Digest {
	return (&cas.Key{Hash: sha256.Sum256(contents), Size: int64(len(contents))}).Digest()
}

func (client *client) upload(t *testing.T, contents []byte) *repb.Digest {
	t.Helper()
	digest := digestOf(contents)
	response, err := client.cas.BatchUpdateBlobs(context.Background(), &repb.BatchUpdateBlobsRequest{
		Requests: []*repb.BatchUpdateBlobsRequest_Request{{Digest: digest, Data: contents}},
	})
	if err != nil {
		t.Fatal(err)
	}
	if code := codes.Code(response.Responses[0].Status.Code); code != codes.OK {
		t.Fatalf("upload returned %v", code)
	}
	return digest
}

func (client *client) uploadMessage(t *testing.T, message proto.Message) *repb.Digest {
	t.Helper()
	contents, err := proto.MarshalOptions{Deterministic: true}.Marshal(message)
	if err != nil {
		t.Fatal(err)
	}
	return client.upload(t, contents)
}

func (client *client) execute(t *testing.T, actionDigest *repb.Digest) (*repb.ExecuteResponse, []*longrunningpb.Operation) {
	t.Helper()
	stream, err := client.execution.Execute(context.Background(), &repb.ExecuteRequest{ActionDigest: actionDigest})
	if err != nil {
		t.Fatal(err)
	}
	var operations []*longrunningpb.Operation
	for {
		operation, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		operations = append(operations, operation)
	}
	last := operations[len(operations)-1]
	if !last.Done {
		t.Fatalf("the last operation is not done: %v", last)
	}
	response := &repb.ExecuteResponse{}
	if err := last.GetResponse().UnmarshalTo(response); err != nil {
		t.Fatal(err)
	}
	return response, operations
}

func (client *client) action(t *testing.T, script string, outputPaths ...string) *repb.Digest {
	t.Helper()
	command := client.uploadMessage(t, &repb.Command{
		Arguments:            []string{"sh", "-c", script},
		EnvironmentVariables: []*repb.Command_EnvironmentVariable{{Name: "PATH", Value: "/usr/bin:/bin"}},
		OutputPaths:          outputPaths,
	})
	return client.uploadMessage(t, &repb.Action{
		CommandDigest:   command,
		InputRootDigest: client.uploadMessage(t, &repb.Directory{}),
	})
}

func TestFindMissingBlobsAfterUpload(t *testing.T) {
	client := startServer(t)
	present := client.upload(t, []byte("present"))
	absent := digestOf([]byte("absent"))
	response, err := client.cas.FindMissingBlobs(context.Background(), &repb.FindMissingBlobsRequest{
		BlobDigests: []*repb.Digest{present, absent},
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(response.MissingBlobDigests) != 1 || !proto.Equal(response.MissingBlobDigests[0], absent) {
		t.Fatalf("missing %v", response.MissingBlobDigests)
	}
}

func TestBatchUpdateRejectsMismatchedBlob(t *testing.T) {
	client := startServer(t)
	response, err := client.cas.BatchUpdateBlobs(context.Background(), &repb.BatchUpdateBlobsRequest{
		Requests: []*repb.BatchUpdateBlobsRequest_Request{{Digest: digestOf([]byte("expected")), Data: []byte("actual!!")}},
	})
	if err != nil {
		t.Fatal(err)
	}
	if code := codes.Code(response.Responses[0].Status.Code); code != codes.InvalidArgument {
		t.Fatalf("upload of a mismatched blob returned %v", code)
	}
}

func TestBatchReadReportsEachBlob(t *testing.T) {
	client := startServer(t)
	present := client.upload(t, []byte("present"))
	absent := digestOf([]byte("absent"))
	response, err := client.cas.BatchReadBlobs(context.Background(), &repb.BatchReadBlobsRequest{
		Digests: []*repb.Digest{present, absent},
	})
	if err != nil {
		t.Fatal(err)
	}
	if string(response.Responses[0].Data) != "present" || codes.Code(response.Responses[1].Status.Code) != codes.NotFound {
		t.Fatalf("responses %v", response.Responses)
	}
}

func TestByteStreamWriteThenReadFromOffset(t *testing.T) {
	client := startServer(t)
	contents := []byte("0123456789")
	digest := digestOf(contents)
	resource := "instance/uploads/1234/blobs/" + digest.Hash + "/10"
	writer, err := client.bytestream.Write(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	for offset, chunk := range [][]byte{contents[:4], contents[4:]} {
		request := &bytestream.WriteRequest{Data: chunk, WriteOffset: int64(offset * 4), FinishWrite: offset == 1}
		if offset == 0 {
			request.ResourceName = resource
		}
		if err := writer.Send(request); err != nil {
			t.Fatal(err)
		}
	}
	written, err := writer.CloseAndRecv()
	if err != nil {
		t.Fatal(err)
	}
	if written.CommittedSize != 10 {
		t.Fatalf("committed %d bytes", written.CommittedSize)
	}

	reader, err := client.bytestream.Read(context.Background(), &bytestream.ReadRequest{
		ResourceName: "instance/blobs/" + digest.Hash + "/10",
		ReadOffset:   3,
		ReadLimit:    4,
	})
	if err != nil {
		t.Fatal(err)
	}
	var read []byte
	for {
		response, err := reader.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		read = append(read, response.Data...)
	}
	if string(read) != "3456" {
		t.Fatalf("read %q", read)
	}
}

func TestExecuteRunsActionThenServesItFromTheCache(t *testing.T) {
	client := startServer(t)
	actionDigest := client.action(t, "echo built > out", "out")

	response, operations := client.execute(t, actionDigest)
	if response.Status.GetCode() != int32(codes.OK) || response.CachedResult || response.Result.ExitCode != 0 {
		t.Fatalf("response %v", response)
	}
	if len(operations) != 2 {
		t.Fatalf("operations %v", operations)
	}
	read, err := client.cas.BatchReadBlobs(context.Background(), &repb.BatchReadBlobsRequest{
		Digests: []*repb.Digest{response.Result.OutputFiles[0].Digest},
	})
	if err != nil {
		t.Fatal(err)
	}
	if string(read.Responses[0].Data) != "built\n" {
		t.Fatalf("output %q", read.Responses[0].Data)
	}

	cached, _ := client.execute(t, actionDigest)
	if !cached.CachedResult || !proto.Equal(cached.Result.OutputFiles[0], response.Result.OutputFiles[0]) {
		t.Fatalf("second response %v", cached)
	}
	result, err := client.cache.GetActionResult(context.Background(), &repb.GetActionResultRequest{ActionDigest: actionDigest})
	if err != nil || !proto.Equal(result.OutputFiles[0], response.Result.OutputFiles[0]) {
		t.Fatalf("action cache returned %v, %v", result, err)
	}
}

func TestFailedActionIsNotCached(t *testing.T) {
	client := startServer(t)
	actionDigest := client.action(t, "exit 1")
	response, _ := client.execute(t, actionDigest)
	if response.Result.ExitCode != 1 {
		t.Fatalf("response %v", response)
	}
	_, err := client.cache.GetActionResult(context.Background(), &repb.GetActionResultRequest{ActionDigest: actionDigest})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("action cache returned %v", err)
	}
}

func TestExecuteReportsMissingInputsAsPreconditionFailure(t *testing.T) {
	client := startServer(t)
	missing := digestOf([]byte("never uploaded"))
	command := client.uploadMessage(t, &repb.Command{Arguments: []string{"true"}})
	actionDigest := client.uploadMessage(t, &repb.Action{
		CommandDigest:   command,
		InputRootDigest: client.uploadMessage(t, &repb.Directory{Files: []*repb.FileNode{{Name: "input", Digest: missing}}}),
	})

	response, _ := client.execute(t, actionDigest)
	failure := status.FromProto(response.Status)
	if failure.Code() != codes.FailedPrecondition {
		t.Fatalf("status %v", failure)
	}
	details := failure.Details()
	if len(details) != 1 {
		t.Fatalf("details %v", details)
	}
	violations := details[0].(*errdetails.PreconditionFailure).Violations
	expected := "blobs/" + missing.Hash + "/14"
	if len(violations) != 1 || violations[0].Type != "MISSING" || violations[0].Subject != expected {
		t.Fatalf("violations %v", violations)
	}
}

func TestGetCapabilitiesAdvertisesExecution(t *testing.T) {
	client := startServer(t)
	capabilities, err := repb.NewCapabilitiesClient(client.connection).GetCapabilities(context.Background(), &repb.GetCapabilitiesRequest{})
	if err != nil {
		t.Fatal(err)
	}
	if !capabilities.ExecutionCapabilities.ExecEnabled || !capabilities.CacheCapabilities.ActionCacheUpdateCapabilities.UpdateEnabled {
		t.Fatalf("capabilities %v", capabilities)
	}
}
