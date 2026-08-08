# Vendored dependencies

## RE2

`re2/` is based on [google/re2](https://github.com/google/re2) commit
`972a15cedd008d846f1a39b2e88ce48d7f166cbd`. The source tree keeps RE2's own
`MODULE.bazel` and is excluded from Define's Bazel package discovery and
repository-wide formatting.

To update the upstream baseline, clone google/re2, generate a binary diff from
the commit above to the desired upstream commit, and apply it with
`git apply --directory=vendored/re2`. Update the commit recorded here in the
same change and resolve any conflicts with Define's RE2 patches.

Build the Python target from the independent module directory:

```shell
cd vendored/re2
bazelisk build //python:re2
```
