# Project Roots

Every Define codebase on a filesystem has a **project root**: the top-level
directory that contains all the code in the project.

## Setting Up a Project Root

To mark a directory as a project root, create the file
`.define/project/config.defcl` inside it:

```
my-project/
  .define/
    project/
      config.defcl
```

Then your code goes into `my-project`. (Don't put your code in `.define`!)

## Configuring the Universe Name

The `config.defcl` file must declare your project's **universe name**. This is
the fully-qualified universe name (FQUN) that appears in the global names of
your source files. The universe name in the config must match exactly what you
use in your source code.

For example, if your `config.defcl` contains:

```textproto
project: {
  universe_name: "mv:my-company.com:my_lib"
}
```

Then your source files must use the same FQUN in their global names:

```
define the potential position<mv:my-company.com:my_lib:/widgets/button>.
```

The compiler will report an error if a source file's global name uses a
different universe name than what the project config declares.

## Running the Compiler

The Define compiler must be run from the project root directory. If you see an
error about a missing project root, make sure:

1. You are running the compiler from the correct directory.
2. The file `.define/project/config.defcl` exists in that directory.

## Further Reading

See the
[Project Roots section of the Define spec](../spec/spec.md#project-roots) for
the full specification.
