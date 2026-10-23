package cas

import (
	"crypto/sha256"
	"errors"
	"os"
	"path/filepath"
	"testing"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
)

func keyOf(contents string) Key {
	return Key{Hash: sha256.Sum256([]byte(contents)), Size: int64(len(contents))}
}

func openStore(t *testing.T, root string, maxBytes int64) *Store {
	t.Helper()
	store, err := Open(root, maxBytes, 10)
	if err != nil {
		t.Fatal(err)
	}
	return store
}

func TestPutThenRead(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	key := keyOf("contents")
	if err := store.Put(key, []byte("contents")); err != nil {
		t.Fatal(err)
	}
	contents, err := store.Read(key)
	if err != nil {
		t.Fatal(err)
	}
	if string(contents) != "contents" {
		t.Fatalf("read %q", contents)
	}
	if !store.Has(key) {
		t.Fatal("the store does not have the blob it was given")
	}
}

func TestPutRejectsContentsThatDoNotMatchTheKey(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	key := keyOf("expected")
	if err := store.Put(key, []byte("actual!!")); err == nil {
		t.Fatal("the store accepted a blob whose contents do not match its key")
	}
	if store.Has(key) {
		t.Fatal("the store kept a blob whose contents do not match its key")
	}
}

func TestEmptyBlobIsAlwaysPresent(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	if !store.Has(EmptyKey) {
		t.Fatal("the store does not have the empty blob")
	}
	contents, err := store.Read(EmptyKey)
	if err != nil || len(contents) != 0 {
		t.Fatalf("read %q, %v", contents, err)
	}
	path := filepath.Join(t.TempDir(), "empty")
	if err := store.Link(EmptyKey, path); err != nil {
		t.Fatal(err)
	}
	if info, err := os.Stat(path); err != nil || info.Size() != 0 {
		t.Fatalf("linked empty blob: %v, %v", info, err)
	}
}

func TestReadOfMissingBlobReportsIt(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	key := keyOf("missing")
	_, err := store.Read(key)
	var missingErr *MissingBlobsError
	if !errors.As(err, &missingErr) || len(missingErr.Keys) != 1 || missingErr.Keys[0] != key {
		t.Fatalf("read of a missing blob returned %v", err)
	}
}

func TestEvictsLeastRecentlyUsedBlob(t *testing.T) {
	store := openStore(t, t.TempDir(), 8)
	first, second, third := keyOf("1111"), keyOf("2222"), keyOf("3333")
	for _, contents := range []string{"1111", "2222"} {
		if err := store.Put(keyOf(contents), []byte(contents)); err != nil {
			t.Fatal(err)
		}
	}
	store.Has(first)
	if err := store.Put(third, []byte("3333")); err != nil {
		t.Fatal(err)
	}
	if missing := store.Missing([]Key{first, second, third}); len(missing) != 1 || missing[0] != second {
		t.Fatalf("missing after eviction: %v", missing)
	}
}

func TestReopenKeepsBlobsAndDropsTruncatedOnes(t *testing.T) {
	root := t.TempDir()
	store := openStore(t, root, 1<<20)
	kept, truncated := keyOf("kept"), keyOf("truncated")
	for _, contents := range []string{"kept", "truncated"} {
		if err := store.Put(keyOf(contents), []byte(contents)); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.Chmod(store.blobPath(truncated), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Truncate(store.blobPath(truncated), 2); err != nil {
		t.Fatal(err)
	}
	reopened := openStore(t, root, 1<<20)
	if missing := reopened.Missing([]Key{kept, truncated}); len(missing) != 1 || missing[0] != truncated {
		t.Fatalf("missing after reopening: %v", missing)
	}
	if _, err := os.Stat(store.blobPath(truncated)); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("the truncated blob's file is still there: %v", err)
	}
}

func TestAddFileLinksItIntoTheStore(t *testing.T) {
	root := t.TempDir()
	store := openStore(t, filepath.Join(root, "cas"), 1<<20)
	path := filepath.Join(root, "output")
	if err := os.WriteFile(path, []byte("output"), 0o644); err != nil {
		t.Fatal(err)
	}
	key, err := store.AddFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if key != keyOf("output") {
		t.Fatalf("added file has key %v", key)
	}
	outputInfo, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	blobInfo, err := os.Stat(store.blobPath(key))
	if err != nil {
		t.Fatal(err)
	}
	if !os.SameFile(outputInfo, blobInfo) {
		t.Fatal("the store copied the file instead of linking it")
	}
}

func TestLinkedBlobIsReadOnly(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	key := keyOf("input")
	if err := store.Put(key, []byte("input")); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "input")
	if err := store.Link(key, path); err != nil {
		t.Fatal(err)
	}
	if _, err := os.OpenFile(path, os.O_WRONLY, 0); err == nil && os.Geteuid() != 0 {
		t.Fatal("an action could write to a blob through its input")
	}
}

func TestDirectoryIsDecodedAndCached(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	directory := &repb.Directory{Files: []*repb.FileNode{{Name: "file", Digest: keyOf("file").Digest()}}}
	key, err := store.PutMessage(directory)
	if err != nil {
		t.Fatal(err)
	}
	decoded, err := store.Directory(key)
	if err != nil {
		t.Fatal(err)
	}
	if len(decoded.Files) != 1 || decoded.Files[0].Name != "file" {
		t.Fatalf("decoded %v", decoded)
	}
	if err := os.Remove(store.blobPath(key)); err != nil {
		t.Fatal(err)
	}
	cached, err := store.Directory(key)
	if err != nil || cached != decoded {
		t.Fatalf("the directory was not cached: %v, %v", cached, err)
	}
}

func TestActionResultWithEvictedOutputIsNotReturned(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	output := keyOf("output")
	if err := store.Put(output, []byte("output")); err != nil {
		t.Fatal(err)
	}
	actionKey := keyOf("action")
	result := &repb.ActionResult{OutputFiles: []*repb.OutputFile{{Path: "out", Digest: output.Digest()}}}
	if err := store.PutActionResult(actionKey, result); err != nil {
		t.Fatal(err)
	}
	cached, err := store.ActionResult(actionKey)
	if err != nil || cached == nil || cached.OutputFiles[0].Path != "out" {
		t.Fatalf("cached result: %v, %v", cached, err)
	}
	store.mu.Lock()
	store.maxBytes = 0
	store.evictLocked()
	store.mu.Unlock()
	cached, err = store.ActionResult(actionKey)
	if err != nil || cached != nil {
		t.Fatalf("a result whose output was evicted was returned: %v, %v", cached, err)
	}
}

func TestKeyFromDigestRejectsInvalidDigests(t *testing.T) {
	for _, digest := range []*repb.Digest{
		nil,
		{Hash: "not hex", SizeBytes: 1},
		{Hash: "abcd", SizeBytes: 1},
		{Hash: keyOf("x").Digest().Hash, SizeBytes: -1},
	} {
		if _, err := KeyFromDigest(digest); err == nil {
			t.Errorf("accepted digest %v", digest)
		}
	}
}
