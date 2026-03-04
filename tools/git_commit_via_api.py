#!/usr/bin/env python3
"""Creates a signed commit via the GitHub REST API.

Commits created through the API are automatically signed by GitHub,
unlike commits created with ``git commit`` in a workflow.

Requires GH_TOKEN (or GITHUB_TOKEN), GITHUB_REPOSITORY, and
GITHUB_REF_NAME environment variables.
"""

import base64
import os

import click
import github


@click.command()
@click.argument("message")
@click.argument("files", nargs=-1, required=True)
def main(message: str, files: tuple[str, ...]):  # noqa: D103
    token = os.environ.get("GH_TOKEN") or os.environ["GITHUB_TOKEN"]
    gh = github.Github(token)
    repo = gh.get_repo(os.environ["GITHUB_REPOSITORY"])
    branch = os.environ["GITHUB_REF_NAME"]

    ref = repo.get_git_ref(f"heads/{branch}")
    head_commit = repo.get_git_commit(ref.object.sha)

    tree_elements: list[github.InputGitTreeElement] = []
    for path in files:
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        blob = repo.create_git_blob(content, "base64")
        tree_elements.append(
            github.InputGitTreeElement(
                path=path, mode="100644", type="blob", sha=blob.sha
            )
        )

    tree = repo.create_git_tree(tree_elements, base_tree=head_commit.tree)
    commit = repo.create_git_commit(message, tree, [head_commit])
    ref.edit(commit.sha)


if __name__ == "__main__":
    main()
