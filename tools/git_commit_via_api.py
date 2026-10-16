"""Creates a signed commit on the branch of the current GitHub Actions run.

Commits created through the API are automatically signed by GitHub,
unlike commits created with ``git commit`` in a workflow. The commit fails if
the branch has moved past the commit that started the run.

The workflow runs this with a write token and the runner's Python, so it must
use only the standard library.

Requires GH_TOKEN, GITHUB_GRAPHQL_URL, GITHUB_REPOSITORY, GITHUB_REF_NAME, and
GITHUB_SHA environment variables.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys
import typing
import urllib.request

if typing.TYPE_CHECKING:
    import http.client

_MUTATION = """
mutation($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid } }
}
"""


class Arguments(argparse.Namespace):
    """Command-line arguments for the commit."""

    def __init__(self):
        """Initialize defaults that argparse replaces with parsed values."""
        super().__init__()
        self.message: str = ""
        self.files: list[pathlib.Path] = []


def main():  # noqa: D103
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("message")
    _ = parser.add_argument("files", nargs="+", type=pathlib.Path)
    args = parser.parse_args(namespace=Arguments())

    additions: list[dict[str, str]] = []
    for path in args.files:
        contents = base64.b64encode(path.read_bytes()).decode()
        additions.append({"path": path.as_posix(), "contents": contents})

    commit_input = {
        "branch": {
            "repositoryNameWithOwner": os.environ["GITHUB_REPOSITORY"],
            "branchName": os.environ["GITHUB_REF_NAME"],
        },
        "expectedHeadOid": os.environ["GITHUB_SHA"],
        "message": {"headline": args.message},
        "fileChanges": {"additions": additions},
    }
    body = {"query": _MUTATION, "variables": {"input": commit_input}}
    request = urllib.request.Request(  # noqa: S310
        os.environ["GITHUB_GRAPHQL_URL"],
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}"},
    )
    with typing.cast(
        "http.client.HTTPResponse",
        urllib.request.urlopen(request),  # noqa: S310
    ) as response:
        result = typing.cast("dict[str, object]", json.load(response))
    if "errors" in result:
        sys.exit(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()
