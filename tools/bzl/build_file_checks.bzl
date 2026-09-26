"""Loading-time checks for hand-maintained BUILD file conventions."""

# Formatting, linting, type-checking, and package setup targets live in their
# own sections of a BUILD file instead of among the ordered targets.
_META_FUNCTIONS = [
    "format_multirun",
    "format_test",
    "npm_link_all_packages",
    "pyright_test",
    "rust_clippy_test",
    "rustfmt_test",
]

_PYTHON_FUNCTIONS = ["py_binary", "py_library", "py_test"]

# rules_go instantiates go_binary through an internal macro.
_FUNCTION_ALIASES = {"go_binary_macro": "go_binary"}

def _label_name(label):
    return label.split(":")[-1].split("/")[-1]

def _calls(rules):
    """Group rules into the BUILD file calls that declared them, in order.

    Args:
        rules: (name, attributes) pairs from native.existing_rules(), in
            declaration order.

    Returns:
        A list of structs with the call's `name`, its `function`, and the
        attributes of the rule that the call named.
    """
    order = []
    functions = {}
    attributes = {}
    for rule_name, rule in rules:
        call_name = rule.get("generator_name") or rule_name
        if call_name not in functions:
            order.append(call_name)
            function = rule.get("generator_function") or rule["kind"]
            functions[call_name] = _FUNCTION_ALIASES.get(function, function)
            attributes[call_name] = rule
        if rule_name == call_name:
            attributes[call_name] = rule
    return [
        struct(name = call_name, function = functions[call_name], attributes = attributes[call_name])
        for call_name in order
    ]

def _size_violations(calls):
    violations = []
    for call in calls:
        if not call.function.endswith("_test") or call.function in _META_FUNCTIONS:
            continue
        if "manual" in call.attributes.get("tags", []):
            continue
        if call.attributes.get("size") != "small":
            violations.append('test target "%s" must set size = "small"' % call.name)
    return violations

def _single(values):
    if values == None or len(values) != 1:
        return None
    return _label_name(values[0])

def _expected_name(call, package_name, call_names, embedded):
    attributes = call.attributes
    if call.function in _PYTHON_FUNCTIONS:
        source = _single(attributes.get("srcs"))
        if source == None:
            return None
        if source == "__init__.py":
            # A package whose directory name is taken by another target names
            # its Python package target with a `_py` suffix.
            if package_name in call_names and package_name != call.name:
                return package_name + "_py"
            return package_name
        return source.removesuffix(".pyi").removesuffix(".py")
    if call.function == "proto_library":
        source = _single(attributes.get("srcs"))
        return None if source == None else source.removesuffix(".proto") + "_proto"
    if call.function == "py_proto_library":
        dependency = _single(attributes.get("deps"))
        return None if dependency == None else dependency + "_py"
    if call.function == "go_binary":
        return package_name
    if call.function == "go_library":
        return package_name + "_lib" if call.name in embedded else package_name
    if call.function == "go_test":
        return package_name + "_test"
    return None

def _name_violations(calls, package_name):
    call_names = [call.name for call in calls]
    embedded = []
    for call in calls:
        if call.function == "go_binary":
            embedded.extend([_label_name(label) for label in call.attributes.get("embed", [])])
    violations = []
    for call in calls:
        expected = _expected_name(call, package_name, call_names, embedded)
        if expected != None and call.name != expected:
            violations.append('%s "%s" must be named "%s"' % (call.function, call.name, expected))
    return violations

def _order_key(call):
    # A language-specific proto target sorts immediately after the
    # proto_library it wraps.
    if call.function == "py_proto_library":
        dependency = _single(call.attributes.get("deps"))
        if dependency != None:
            return (dependency, call.name)
    if call.function == "go_proto_library":
        proto = call.attributes.get("proto")
        if proto:
            return (_label_name(proto), call.name)
    return (call.name, "")

def _order_violations(calls):
    ordered = [call for call in calls if call.function not in _META_FUNCTIONS]
    violations = []
    for index in range(1, len(ordered)):
        previous = ordered[index - 1]
        current = ordered[index]
        if _order_key(current) < _order_key(previous):
            violations.append('"%s" must come before "%s"' % (current.name, previous.name))
    return violations

def _pyright_violations(calls, rules):
    pyright_calls = [call for call in calls if call.function == "pyright_test"]
    if not pyright_calls:
        return []
    covered = []
    for rule_name, rule in rules:
        if rule_name == pyright_calls[0].name + "_deps":
            covered = [_label_name(label) for label in rule.get("deps", [])]
    return [
        'Python target "%s" must be in the deps of pyright_test "%s"' % (call.name, pyright_calls[0].name)
        for call in calls
        if call.function in _PYTHON_FUNCTIONS and call.name not in covered
    ]

def build_file_violations(package_name, rules):
    """Return the BUILD file convention violations in a package.

    Args:
        package_name: The last component of the package's path.
        rules: (name, attributes) pairs from native.existing_rules(), in
            declaration order.

    Returns:
        A list of violation messages.
    """
    calls = _calls(rules)
    return (
        _size_violations(calls) +
        _name_violations(calls, package_name) +
        _order_violations(calls) +
        _pyright_violations(calls, rules)
    )

def _check_build_file_impl(name, visibility):  # buildifier: disable=unused-variable
    violations = build_file_violations(
        native.package_name().split("/")[-1],
        native.existing_rules().items(),
    )
    if violations:
        fail("BUILD file conventions in //%s:\n  %s" % (
            native.package_name(),
            "\n  ".join(violations),
        ))

_check_build_file = macro(
    doc = "Fails loading the package when its BUILD file breaks the repository's conventions.",
    implementation = _check_build_file_impl,
    finalizer = True,
)

def check_build_file():
    """Fails loading the package when its BUILD file breaks the repository's conventions."""
    _check_build_file(name = "check_build_file")
