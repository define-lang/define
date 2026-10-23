// Package cas stores content-addressed blobs and action results in a local
// directory for remote execution on the same machine.
package cas

import (
	"cmp"
	"container/list"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"

	repb "github.com/bazelbuild/remote-apis/build/bazel/remote/execution/v2"
	"google.golang.org/protobuf/proto"
)

// Blob files are read-only so that an action cannot change a blob through
// the hardlink it gets as an input. They are executable because Bazel marks
// every input of a remotely executed action as executable.
const blobMode = 0o555

// Key identifies a blob by its SHA-256 hash and size.
type Key struct {
	Hash [sha256.Size]byte
	Size int64
}

// EmptyKey is the key of the empty blob, which every store holds without a
// file.
var EmptyKey = Key{Hash: sha256.Sum256(nil)}

// KeyFromDigest converts a REAPI digest into a key.
func KeyFromDigest(digest *repb.Digest) (Key, error) {
	var key Key
	if digest == nil {
		return key, errors.New("missing digest")
	}
	if digest.SizeBytes < 0 {
		return key, fmt.Errorf("digest %s has negative size %d", digest.Hash, digest.SizeBytes)
	}
	decoded, err := hex.DecodeString(digest.Hash)
	if err != nil || len(decoded) != sha256.Size {
		return key, fmt.Errorf("digest hash %q is not a SHA-256 hash", digest.Hash)
	}
	copy(key.Hash[:], decoded)
	key.Size = digest.SizeBytes
	return key, nil
}

// Digest converts the key into a REAPI digest.
func (key Key) Digest() *repb.Digest {
	return &repb.Digest{Hash: hex.EncodeToString(key.Hash[:]), SizeBytes: key.Size}
}

func (key Key) String() string {
	return hex.EncodeToString(key.Hash[:]) + "/" + strconv.FormatInt(key.Size, 10)
}

// fileName names a blob or action result file. The size in the name lets a
// startup scan drop files that a crash left shorter than their contents.
func (key Key) fileName() string {
	return hex.EncodeToString(key.Hash[:]) + "_" + strconv.FormatInt(key.Size, 10)
}

// MissingBlobsError reports blobs that an operation needed but the store does
// not hold.
type MissingBlobsError struct {
	Keys []Key
}

func (err *MissingBlobsError) Error() string {
	names := make([]string, len(err.Keys))
	for index, key := range err.Keys {
		names[index] = key.String()
	}
	return "missing blobs: " + strings.Join(names, ", ")
}

type entry struct {
	key     Key
	element *list.Element
}

// Store holds blobs under root/blobs and action results under root/ac. Blobs
// are evicted least recently used first once they exceed maxBytes. Files are
// never synced to disk, since everything in the store can be rebuilt.
type Store struct {
	root      string
	maxBytes  int64
	tempCount atomic.Uint64

	mu         sync.Mutex
	entries    map[Key]*entry
	recency    *list.List
	totalBytes int64

	directories *directoryCache
}

// Open opens the store in root, creating it if needed, and indexes the blobs
// already there.
func Open(root string, maxBytes int64, maxDirectories int) (*Store, error) {
	store := &Store{
		root:        root,
		maxBytes:    maxBytes,
		entries:     map[Key]*entry{},
		recency:     list.New(),
		directories: newDirectoryCache(maxDirectories),
	}
	if err := os.RemoveAll(store.tempDirectory()); err != nil {
		return nil, err
	}
	for _, directory := range []string{store.tempDirectory(), filepath.Join(root, "ac")} {
		if err := os.MkdirAll(directory, 0o755); err != nil {
			return nil, err
		}
	}
	for prefix := range 256 {
		directory := filepath.Join(root, "blobs", fmt.Sprintf("%02x", prefix))
		if err := os.MkdirAll(directory, 0o755); err != nil {
			return nil, err
		}
		if err := store.index(directory); err != nil {
			return nil, err
		}
	}
	store.mu.Lock()
	store.evictLocked()
	store.mu.Unlock()
	return store, nil
}

type indexedBlob struct {
	key     Key
	modTime int64
}

// index adds the blobs in one blob directory to the index, oldest first so
// that they are evicted first.
func (store *Store) index(directory string) error {
	dirEntries, err := os.ReadDir(directory)
	if err != nil {
		return err
	}
	blobs := make([]indexedBlob, 0, len(dirEntries))
	for _, dirEntry := range dirEntries {
		path := filepath.Join(directory, dirEntry.Name())
		key, ok := parseFileName(dirEntry.Name())
		info, err := dirEntry.Info()
		if err != nil {
			return err
		}
		if !ok || !info.Mode().IsRegular() || info.Size() != key.Size {
			if err := os.Remove(path); err != nil {
				return err
			}
			continue
		}
		blobs = append(blobs, indexedBlob{key: key, modTime: info.ModTime().UnixNano()})
	}
	slices.SortFunc(blobs, func(first, second indexedBlob) int {
		return cmp.Compare(first.modTime, second.modTime)
	})
	store.mu.Lock()
	defer store.mu.Unlock()
	for _, blob := range blobs {
		store.addLocked(blob.key)
	}
	return nil
}

func parseFileName(name string) (Key, bool) {
	var key Key
	hashText, sizeText, found := strings.Cut(name, "_")
	if !found {
		return key, false
	}
	decoded, err := hex.DecodeString(hashText)
	if err != nil || len(decoded) != sha256.Size {
		return key, false
	}
	size, err := strconv.ParseInt(sizeText, 10, 64)
	if err != nil || size < 0 {
		return key, false
	}
	copy(key.Hash[:], decoded)
	key.Size = size
	return key, true
}

func (store *Store) tempDirectory() string {
	return filepath.Join(store.root, "tmp")
}

func (store *Store) blobPath(key Key) string {
	name := key.fileName()
	return filepath.Join(store.root, "blobs", name[:2], name)
}

func (store *Store) actionResultPath(key Key) string {
	return filepath.Join(store.root, "ac", key.fileName())
}

func (store *Store) addLocked(key Key) {
	if existing, found := store.entries[key]; found {
		store.recency.MoveToBack(existing.element)
		return
	}
	newEntry := &entry{key: key}
	newEntry.element = store.recency.PushBack(newEntry)
	store.entries[key] = newEntry
	store.totalBytes += key.Size
}

func (store *Store) evictLocked() {
	for store.totalBytes > store.maxBytes {
		oldest := store.recency.Front()
		if oldest == nil {
			return
		}
		evicted := oldest.Value.(*entry)
		store.recency.Remove(oldest)
		delete(store.entries, evicted.key)
		store.totalBytes -= evicted.key.Size
		// An action that already linked the blob keeps its inode, and one that
		// has not yet linked it reports it missing so the client uploads it
		// again.
		if err := os.Remove(store.blobPath(evicted.key)); err != nil && !errors.Is(err, fs.ErrNotExist) {
			panic(fmt.Sprintf("evicting blob %s: %v", evicted.key, err))
		}
	}
}

// Has reports whether the store holds the blob, and marks it as used.
func (store *Store) Has(key Key) bool {
	if key.Size == 0 {
		return key == EmptyKey
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	existing, found := store.entries[key]
	if found {
		store.recency.MoveToBack(existing.element)
	}
	return found
}

// Missing returns the keys that the store does not hold.
func (store *Store) Missing(keys []Key) []Key {
	var missing []Key
	for _, key := range keys {
		if !store.Has(key) {
			missing = append(missing, key)
		}
	}
	return missing
}

// Open opens a blob for reading.
func (store *Store) Open(key Key) (io.ReadCloser, error) {
	if key.Size == 0 && key == EmptyKey {
		return io.NopCloser(strings.NewReader("")), nil
	}
	if !store.Has(key) {
		return nil, &MissingBlobsError{Keys: []Key{key}}
	}
	file, err := os.Open(store.blobPath(key))
	if errors.Is(err, fs.ErrNotExist) {
		return nil, &MissingBlobsError{Keys: []Key{key}}
	}
	return file, err
}

// Read returns the contents of a blob.
func (store *Store) Read(key Key) ([]byte, error) {
	reader, err := store.Open(key)
	if err != nil {
		return nil, err
	}
	defer reader.Close()
	contents := make([]byte, key.Size)
	if _, err := io.ReadFull(reader, contents); err != nil {
		return nil, fmt.Errorf("reading blob %s: %w", key, err)
	}
	return contents, nil
}

// ReadMessage decodes a blob as a protocol buffer message.
func (store *Store) ReadMessage(key Key, message proto.Message) error {
	contents, err := store.Read(key)
	if err != nil {
		return err
	}
	if err := proto.Unmarshal(contents, message); err != nil {
		return fmt.Errorf("decoding blob %s: %w", key, err)
	}
	return nil
}

// Directory returns a decoded Directory blob. Decoded directories are cached,
// since many actions share the same input subtrees.
func (store *Store) Directory(key Key) (*repb.Directory, error) {
	if directory := store.directories.get(key); directory != nil {
		return directory, nil
	}
	directory := &repb.Directory{}
	if err := store.ReadMessage(key, directory); err != nil {
		return nil, err
	}
	store.directories.put(key, directory)
	return directory, nil
}

// Link hardlinks a blob to path.
func (store *Store) Link(key Key, path string) error {
	if key.Size == 0 && key == EmptyKey {
		return os.WriteFile(path, nil, blobMode)
	}
	err := os.Link(store.blobPath(key), path)
	if errors.Is(err, fs.ErrNotExist) {
		if _, statErr := os.Lstat(filepath.Dir(path)); statErr != nil {
			return err
		}
		return &MissingBlobsError{Keys: []Key{key}}
	}
	return err
}

// Writer writes one blob and verifies its digest when committed.
type Writer struct {
	store    *Store
	key      Key
	file     *os.File
	hash     hashWriter
	written  int64
	finished bool
}

type hashWriter interface {
	io.Writer
	Sum([]byte) []byte
}

// NewWriter starts writing a blob with the given key.
func (store *Store) NewWriter(key Key) (*Writer, error) {
	file, err := os.CreateTemp(store.tempDirectory(), "upload-")
	if err != nil {
		return nil, err
	}
	return &Writer{store: store, key: key, file: file, hash: sha256.New()}, nil
}

// Written returns how many bytes have been written.
func (writer *Writer) Written() int64 {
	return writer.written
}

func (writer *Writer) Write(data []byte) (int, error) {
	if writer.written+int64(len(data)) > writer.key.Size {
		return 0, fmt.Errorf("blob %s received more than %d bytes", writer.key, writer.key.Size)
	}
	written, err := writer.file.Write(data)
	writer.written += int64(written)
	_, _ = writer.hash.Write(data[:written])
	return written, err
}

// Commit verifies the blob's contents and adds it to the store.
func (writer *Writer) Commit() error {
	writer.finished = true
	tempPath := writer.file.Name()
	defer os.Remove(tempPath)
	if err := writer.file.Close(); err != nil {
		return err
	}
	var hash [sha256.Size]byte
	writer.hash.Sum(hash[:0])
	if writer.written != writer.key.Size || hash != writer.key.Hash {
		return fmt.Errorf("blob %s does not match its contents, which are %x/%d", writer.key, hash, writer.written)
	}
	return writer.store.adopt(tempPath, writer.key)
}

// Abort discards the blob.
func (writer *Writer) Abort() {
	if writer.finished {
		return
	}
	writer.finished = true
	_ = writer.file.Close()
	_ = os.Remove(writer.file.Name())
}

// Put stores a blob from memory.
func (store *Store) Put(key Key, contents []byte) error {
	if store.Has(key) {
		return nil
	}
	writer, err := store.NewWriter(key)
	if err != nil {
		return err
	}
	if _, err := writer.Write(contents); err != nil {
		writer.Abort()
		return err
	}
	return writer.Commit()
}

func encode(message proto.Message) (Key, []byte, error) {
	contents, err := proto.MarshalOptions{Deterministic: true}.Marshal(message)
	if err != nil {
		return Key{}, nil, err
	}
	return Key{Hash: sha256.Sum256(contents), Size: int64(len(contents))}, contents, nil
}

// KeyFromMessage returns the key of a protocol buffer message's encoding.
func KeyFromMessage(message proto.Message) (Key, error) {
	key, _, err := encode(message)
	return key, err
}

// PutMessage stores an encoded protocol buffer message and returns its key.
func (store *Store) PutMessage(message proto.Message) (Key, error) {
	key, contents, err := encode(message)
	if err != nil {
		return Key{}, err
	}
	return key, store.Put(key, contents)
}

// AddFile stores the contents of a file that is on the store's filesystem by
// hardlinking it, without copying it. The file must not change afterwards.
func (store *Store) AddFile(path string) (Key, error) {
	file, err := os.Open(path)
	if err != nil {
		return Key{}, err
	}
	hash := sha256.New()
	size, err := io.Copy(hash, file)
	closeErr := file.Close()
	if err != nil {
		return Key{}, err
	}
	if closeErr != nil {
		return Key{}, closeErr
	}
	var key Key
	hash.Sum(key.Hash[:0])
	key.Size = size
	if size == 0 || store.Has(key) {
		return key, nil
	}
	tempPath := filepath.Join(store.tempDirectory(), "output-"+strconv.FormatUint(store.tempCount.Add(1), 10))
	if err := os.Link(path, tempPath); err != nil {
		return Key{}, err
	}
	defer os.Remove(tempPath)
	return key, store.adopt(tempPath, key)
}

// adopt moves a verified file into the store under key.
func (store *Store) adopt(tempPath string, key Key) error {
	if err := os.Chmod(tempPath, blobMode); err != nil {
		return err
	}
	if err := os.Rename(tempPath, store.blobPath(key)); err != nil {
		return err
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	store.addLocked(key)
	store.evictLocked()
	return nil
}

// ActionResult returns the cached result of an action, or nil if there is
// none or any of its outputs are no longer stored.
func (store *Store) ActionResult(actionKey Key) (*repb.ActionResult, error) {
	contents, err := os.ReadFile(store.actionResultPath(actionKey))
	if errors.Is(err, fs.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	result := &repb.ActionResult{}
	if err := proto.Unmarshal(contents, result); err != nil {
		return nil, fmt.Errorf("decoding action result for %s: %w", actionKey, err)
	}
	complete, err := store.outputsStored(result)
	if err != nil || !complete {
		return nil, err
	}
	return result, nil
}

func (store *Store) outputsStored(result *repb.ActionResult) (bool, error) {
	digests := []*repb.Digest{}
	if result.StdoutDigest != nil {
		digests = append(digests, result.StdoutDigest)
	}
	if result.StderrDigest != nil {
		digests = append(digests, result.StderrDigest)
	}
	for _, file := range result.OutputFiles {
		digests = append(digests, file.Digest)
	}
	for _, directory := range result.OutputDirectories {
		treeKey, err := KeyFromDigest(directory.TreeDigest)
		if err != nil {
			return false, err
		}
		if !store.Has(treeKey) {
			return false, nil
		}
		tree := &repb.Tree{}
		if err := store.ReadMessage(treeKey, tree); err != nil {
			return false, err
		}
		for _, treeDirectory := range append([]*repb.Directory{tree.Root}, tree.Children...) {
			for _, file := range treeDirectory.Files {
				digests = append(digests, file.Digest)
			}
		}
	}
	for _, digest := range digests {
		key, err := KeyFromDigest(digest)
		if err != nil {
			return false, err
		}
		if !store.Has(key) {
			return false, nil
		}
	}
	return true, nil
}

// PutActionResult caches the result of an action.
func (store *Store) PutActionResult(actionKey Key, result *repb.ActionResult) error {
	contents, err := proto.MarshalOptions{Deterministic: true}.Marshal(result)
	if err != nil {
		return err
	}
	tempPath := filepath.Join(store.tempDirectory(), "ac-"+strconv.FormatUint(store.tempCount.Add(1), 10))
	if err := os.WriteFile(tempPath, contents, 0o644); err != nil {
		return err
	}
	return os.Rename(tempPath, store.actionResultPath(actionKey))
}

// directoryCache keeps recently used decoded Directory messages.
type directoryCache struct {
	maxEntries int
	mu         sync.Mutex
	entries    map[Key]*list.Element
	recency    *list.List
}

type cachedDirectory struct {
	key       Key
	directory *repb.Directory
}

func newDirectoryCache(maxEntries int) *directoryCache {
	return &directoryCache{maxEntries: maxEntries, entries: map[Key]*list.Element{}, recency: list.New()}
}

func (cache *directoryCache) get(key Key) *repb.Directory {
	cache.mu.Lock()
	defer cache.mu.Unlock()
	element, found := cache.entries[key]
	if !found {
		return nil
	}
	cache.recency.MoveToBack(element)
	return element.Value.(*cachedDirectory).directory
}

func (cache *directoryCache) put(key Key, directory *repb.Directory) {
	cache.mu.Lock()
	defer cache.mu.Unlock()
	if _, found := cache.entries[key]; found {
		return
	}
	cache.entries[key] = cache.recency.PushBack(&cachedDirectory{key: key, directory: directory})
	for cache.recency.Len() > cache.maxEntries {
		oldest := cache.recency.Front()
		cache.recency.Remove(oldest)
		delete(cache.entries, oldest.Value.(*cachedDirectory).key)
	}
}
