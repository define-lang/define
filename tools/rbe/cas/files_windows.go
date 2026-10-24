package cas

import (
	"errors"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

// removeBlob deletes a blob's file. Windows can't delete a running program, or
// a file that an action opened through its link without sharing deletion,
// since the open applies to every link. Such a blob stays
// on disk outside the index, where the next upload of the same contents adopts
// it again, or the next startup indexes it.
func removeBlob(path string) error {
	err := deleteIgnoringReadOnly(path)
	if errors.Is(err, windows.ERROR_SHARING_VIOLATION) || errors.Is(err, windows.ERROR_ACCESS_DENIED) {
		return nil
	}
	return err
}

// openBlob opens a blob for reading so that eviction can still delete it.
func openBlob(path string) (*os.File, error) {
	name, err := windows.UTF16PtrFromString(extendedLengthPath(path))
	if err != nil {
		return nil, &fs.PathError{Op: "open", Path: path, Err: err}
	}
	handle, err := windows.CreateFile(name, windows.GENERIC_READ,
		windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE,
		nil, windows.OPEN_EXISTING, windows.FILE_ATTRIBUTE_NORMAL, 0)
	if err != nil {
		return nil, &fs.PathError{Op: "open", Path: path, Err: err}
	}
	return os.NewFile(uintptr(handle), path), nil
}

// link hardlinks a blob to path, or copies it when the blob already has as
// many links as NTFS allows, 1023.
//
// NTFS ignores case, so two names in an input tree that differ only in case
// are one file. Linking the same blob to it again succeeds; Windows SDK headers
// come in both cases for the same contents.
func (store *Store) link(key Key, blobPath string, path string) error {
	err := os.Link(blobPath, path)
	if errors.Is(err, fs.ErrExist) && sameFile(blobPath, path) {
		return nil
	}
	if errors.Is(err, windows.ERROR_TOO_MANY_LINKS) {
		return store.copyBlob(key, path)
	}
	return err
}

func sameFile(first string, second string) bool {
	firstInfo, err := os.Stat(first)
	if err != nil {
		return false
	}
	secondInfo, err := os.Stat(second)
	return err == nil && os.SameFile(firstInfo, secondInfo)
}

// writeEmptyBlob writes the empty blob to path, which may already have it under
// a name that differs only in case.
func writeEmptyBlob(path string) error {
	err := os.WriteFile(path, nil, blobMode)
	if info, statErr := os.Lstat(path); err != nil && statErr == nil && info.Mode().IsRegular() && info.Size() == 0 {
		return nil
	}
	return err
}

// renameBlob moves a verified file into the store. Windows can't replace a
// read-only file, or one that is open, but a file already there holds these
// contents, since its name is their hash.
func renameBlob(tempPath string, blobPath string, key Key) error {
	err := os.Rename(tempPath, blobPath)
	if info, statErr := os.Lstat(blobPath); err != nil && statErr == nil && info.Size() == key.Size {
		return nil
	}
	return err
}

func (store *Store) copyBlob(key Key, path string) error {
	source, err := store.Open(key)
	if err != nil {
		return err
	}
	defer source.Close()
	destination, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o755)
	if err != nil {
		return err
	}
	if _, err := io.Copy(destination, source); err != nil {
		_ = destination.Close()
		return err
	}
	if err := destination.Close(); err != nil {
		return err
	}
	return os.Chmod(path, blobMode)
}

// RemoveTree deletes a directory tree that holds links to blobs, without
// changing the blobs. Windows keeps the read-only attribute per file, not per
// link, so clearing it in order to delete a link, as os.RemoveAll does, would
// make the store's copy writable too.
func RemoveTree(root string) error {
	entries, err := os.ReadDir(root)
	if errors.Is(err, fs.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	for _, entry := range entries {
		path := filepath.Join(root, entry.Name())
		// A symlink to a directory is not a directory entry, so the link is
		// deleted and its target is left alone.
		if entry.IsDir() {
			if err := RemoveTree(path); err != nil {
				return err
			}
			continue
		}
		if err := deleteSoon(path); err != nil {
			return err
		}
	}
	return deleteSoon(root)
}

// deleteSoon deletes a path, waiting for a while for others to stop using it.
// Programs that scan new files, such as antivirus software, open them briefly
// without sharing deletion.
func deleteSoon(path string) error {
	deadline := time.Now().Add(10 * time.Second)
	for {
		err := deleteIgnoringReadOnly(path)
		if !errors.Is(err, windows.ERROR_SHARING_VIOLATION) || time.Now().After(deadline) {
			return err
		}
		time.Sleep(50 * time.Millisecond)
	}
}

// deleteIgnoringReadOnly deletes a file, an empty directory or a symlink
// itself. POSIX semantics remove its name at once, even while other handles
// that share deletion keep it open.
func deleteIgnoringReadOnly(path string) error {
	name, err := windows.UTF16PtrFromString(extendedLengthPath(path))
	if err != nil {
		return &fs.PathError{Op: "remove", Path: path, Err: err}
	}
	handle, err := windows.CreateFile(name, windows.DELETE,
		windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE|windows.FILE_SHARE_DELETE,
		nil, windows.OPEN_EXISTING, windows.FILE_FLAG_OPEN_REPARSE_POINT|windows.FILE_FLAG_BACKUP_SEMANTICS, 0)
	if err != nil {
		return &fs.PathError{Op: "remove", Path: path, Err: err}
	}
	defer windows.CloseHandle(handle)
	disposition := struct{ Flags uint32 }{
		Flags: windows.FILE_DISPOSITION_DELETE | windows.FILE_DISPOSITION_POSIX_SEMANTICS |
			windows.FILE_DISPOSITION_IGNORE_READONLY_ATTRIBUTE,
	}
	err = windows.SetFileInformationByHandle(handle, windows.FileDispositionInfoEx,
		(*byte)(unsafe.Pointer(&disposition)), uint32(unsafe.Sizeof(disposition)))
	if err != nil {
		return &fs.PathError{Op: "remove", Path: path, Err: err}
	}
	return nil
}

// extendedLengthPath lets Windows API calls that Go doesn't wrap reach paths
// longer than MAX_PATH, as Go does for its own calls.
func extendedLengthPath(path string) string {
	absolute, err := filepath.Abs(path)
	if err != nil || strings.HasPrefix(absolute, `\\`) {
		return path
	}
	return `\\?\` + absolute
}
