"""Downloads the dprint plugins that a dprint config file lists."""

def _jsonc_to_json(text):
    """Removes the comments and trailing commas of JSONC, which json.decode rejects."""
    result = []
    comment = None
    in_string = False
    escaped = False
    skip_next = False
    for index in range(len(text)):
        character = text[index]
        following = text[index + 1:index + 2]
        if skip_next:
            skip_next = False
        elif comment == "line":
            if character == "\n":
                comment = None
                result.append(character)
        elif comment == "block":
            if character == "*" and following == "/":
                comment = None
                skip_next = True
        elif in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "\"":
                in_string = False
        elif character == "/" and following == "/":
            comment = "line"
        elif character == "/" and following == "*":
            comment = "block"
            skip_next = True
        else:
            if character == "\"":
                in_string = True
            elif character in "]}":
                _remove_trailing_comma(result)
            result.append(character)
    return "".join(result)

def _remove_trailing_comma(result):
    for index in range(len(result) - 1, -1, -1):
        if result[index] == ",":
            result.pop(index)
            return
        if not result[index].isspace():
            return

def _dprint_plugins_impl(repository_ctx):
    files = []
    for url, sha256 in repository_ctx.attr.sha256s_by_url.items():
        # dprint only loads plugins whose file names end in .wasm.
        file = url.rpartition("/")[2]
        repository_ctx.download(url = url, output = file, sha256 = sha256)
        files.append(file)
    repository_ctx.file("BUILD.bazel", """filegroup(
    name = "dprint_plugins",
    srcs = {files},
    visibility = ["//visibility:public"],
)
""".format(files = repr(files)))

_dprint_plugins = repository_rule(
    implementation = _dprint_plugins_impl,
    attrs = {
        "sha256s_by_url": attr.string_dict(mandatory = True),
    },
)

def _dprint_impl(module_ctx):
    for module in module_ctx.modules:
        for plugins in module.tags.plugins:
            config = json.decode(_jsonc_to_json(module_ctx.read(plugins.config)))
            sha256s_by_url = {}
            for plugin in config["plugins"]:
                url, separator, sha256 = plugin.rpartition("@")
                if not separator:
                    fail("The dprint plugin {} needs an @ and its sha256 at the end of its URL.".format(plugin))
                sha256s_by_url[url] = sha256
            _dprint_plugins(name = "dprint_plugins", sha256s_by_url = sha256s_by_url)
    return module_ctx.extension_metadata(reproducible = True)

dprint = module_extension(
    implementation = _dprint_impl,
    tag_classes = {
        "plugins": tag_class(attrs = {
            "config": attr.label(mandatory = True),
        }),
    },
)
