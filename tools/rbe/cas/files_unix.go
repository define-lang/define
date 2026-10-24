//go:build unix

package cas

import (
	"io/fs"
	"os"
	"path/filepath"
)

func removeBlob(path string) error {
	return os.Remove(path)
}

func openBlob(path string) (*os.File, error) {
	return os.Open(path)
}

func (store *Store) link(_ Key, blobPath string, path string) error {
	return os.Link(blobPath, path)
}

func writeEmptyBlob(path string) error {
	return os.WriteFile(path, nil, blobMode)
}

func renameBlob(tempPath string, blobPath string, _ Key) error {
	return os.Rename(tempPath, blobPath)
}

// RemoveTree deletes a directory tree that holds links to blobs, without
// changing the blobs.
func RemoveTree(root string) error {
	if err := os.RemoveAll(root); err == nil {
		return nil
	}
	// Read-only directories that an action left behind cannot be emptied
	// until they are writable again.
	makeWritable(root)
	return os.RemoveAll(root)
}

func makeWritable(root string) {
	_ = filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err == nil && entry.IsDir() {
			_ = os.Chmod(path, 0o755)
		}
		return nil
	})
}
