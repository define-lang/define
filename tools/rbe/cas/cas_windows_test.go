package cas

import (
	"os"
	"path/filepath"
	"strconv"
	"testing"
)

func TestLinksABlobMoreTimesThanAFileCanHaveLinks(t *testing.T) {
	store := openStore(t, t.TempDir(), 1<<20)
	key := keyOf("shared")
	if err := store.Put(key, []byte("shared")); err != nil {
		t.Fatal(err)
	}
	directory := t.TempDir()
	// NTFS allows 1023 links to a file.
	var path string
	for index := range 1100 {
		path = filepath.Join(directory, strconv.Itoa(index))
		if err := store.Link(key, path); err != nil {
			t.Fatal(err)
		}
	}
	if contents, err := os.ReadFile(path); err != nil || string(contents) != "shared" {
		t.Fatalf("the last link has %q, %v", contents, err)
	}
}

func TestEvictingABlobThatIsOpenStillLetsItBeStoredAgain(t *testing.T) {
	store := openStore(t, t.TempDir(), 8)
	first := keyOf("1111")
	if err := store.Put(first, []byte("1111")); err != nil {
		t.Fatal(err)
	}
	// An action that opened its input keeps the blob's file open.
	file, err := os.Open(store.blobPath(first))
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	for _, contents := range []string{"2222", "3333"} {
		if err := store.Put(keyOf(contents), []byte(contents)); err != nil {
			t.Fatal(err)
		}
	}
	if store.Has(first) {
		t.Fatal("the blob was not evicted")
	}
	if err := store.Put(first, []byte("1111")); err != nil {
		t.Fatal(err)
	}
	if contents, err := store.Read(first); err != nil || string(contents) != "1111" {
		t.Fatalf("read %q, %v", contents, err)
	}
}
