"""Batching of a lint aspect's sources into command lines that Windows accepts."""

# ast-grep and Ruff can't read their paths from a file, and Windows limits a
# command line to 32,767 characters, so a target with many sources is scanned
# in batches whose paths fit well within that limit.
_MAX_BATCH_PATH_CHARS = 20000

def lint_batches(srcs):
    """Split `srcs` into lists whose paths fit on one Windows command line.

    Args:
        srcs: the files to lint
    """
    batches = [[]]
    batch_chars = 0
    for src in srcs:
        path_chars = len(src.path) + 1
        if batches[-1] and batch_chars + path_chars > _MAX_BATCH_PATH_CHARS:
            batches.append([])
            batch_chars = 0
        batches[-1].append(src)
        batch_chars += path_chars
    return batches
