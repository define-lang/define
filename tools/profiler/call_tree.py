"""Function tables and call trees over weighted stacks from either profile kind."""

from __future__ import annotations

import collections.abc
import pathlib

import msgspec

NO_PYTHON_FRAME = "(no Python frame)"


class WeightedStack(msgspec.Struct, frozen=True):
    """Time one thread spent in one stack."""

    thread_id: int
    # Outermost first.
    functions: tuple[str, ...]
    total_ns: int
    # Time executing Python rather than waiting with the thread state released.
    working_ns: int


class _Weight(msgspec.Struct):
    total_ns: int = 0
    working_ns: int = 0

    def add(self, stack: WeightedStack):
        self.total_ns += stack.total_ns
        self.working_ns += stack.working_ns


class _Node(msgspec.Struct):
    weight: _Weight
    children: dict[str, _Node]


def is_import_machinery(filename: str) -> bool:
    """Return whether a frame belongs to the import system's own code.

    Each nested import adds several such frames, which say only that an import
    happened; the importing and imported modules' frames remain.
    """
    return filename.startswith("<frozen importlib")


# The directories below which a file's path is its module's dotted name.
_IMPORT_ROOT_MARKERS = ("site-packages", "_main", "Lib")


def _module_name(filename: str) -> str:
    parts = pathlib.PurePath(filename).parts
    for index in range(len(parts) - 1, -1, -1):
        part = parts[index]
        if part in _IMPORT_ROOT_MARKERS or part.startswith("python3."):
            module_parts = [*parts[index + 1 : -1], pathlib.PurePath(filename).stem]
            if module_parts[-1] == "__init__":
                _ = module_parts.pop()
            return ".".join(module_parts)
    return pathlib.PurePath(filename).name


def function_name(function: str, filename: str) -> str:
    """Name a sampled function, naming module code by its module."""
    # Every module's top-level code, mostly run by imports, is named <module>.
    if function == "<module>":
        return f"<module {_module_name(filename)}>"
    return function


def focused(stacks: list[WeightedStack], focus: str) -> list[WeightedStack]:
    """Return each stack's part from its outermost function containing the text."""
    result: list[WeightedStack] = []
    for stack in stacks:
        for index, function in enumerate(stack.functions):
            if focus in function:
                result.append(
                    WeightedStack(
                        thread_id=stack.thread_id,
                        functions=stack.functions[index:],
                        total_ns=stack.total_ns,
                        working_ns=stack.working_ns,
                    )
                )
                break
    return result


def _functions(stack: WeightedStack) -> tuple[str, ...]:
    return stack.functions or (NO_PYTHON_FRAME,)


class Report(msgspec.Struct, frozen=True):
    """How to print weights for one profile kind."""

    # Time of every selected stack, before any focus, which percentages divide.
    denominator_ns: int
    # Whether stacks distinguish working from waiting.
    shows_working: bool

    def weight_text(self, total_ns: int, working_ns: int) -> str:
        """Render a weight as seconds, a share of the denominator, and work."""
        text = (
            f"{total_ns / 1_000_000_000:8.3f} s "
            + f"{100 * total_ns / self.denominator_ns:5.1f}%"
        )
        if self.shows_working:
            text += f"  work {working_ns / total_ns:4.0%}"
        return text


def _dominant_function(node: _Node) -> str:
    # The deepest function holding most of the thread's time says what the
    # thread was for, which its name, often truncated, does not.
    thread_ns = node.weight.total_ns
    name = ""
    while node.children:
        child_name, child = max(
            node.children.items(), key=lambda item: item[1].weight.total_ns
        )
        if child.weight.total_ns * 2 < thread_ns:
            break
        name = child_name
        node = child
    return name


def emit_threads(
    stacks: list[WeightedStack], report: Report, thread_names: dict[int, str]
):
    """Print each thread's total, largest first, with its dominant function."""
    stacks_by_thread: dict[int, list[WeightedStack]] = collections.defaultdict(list)
    for stack in stacks:
        stacks_by_thread[stack.thread_id].append(stack)
    trees = {
        thread_id: _tree(thread_stacks)
        for thread_id, thread_stacks in stacks_by_thread.items()
    }
    print("Threads, with the deepest function holding most of each one's time:")
    for thread_id, tree in sorted(
        trees.items(), key=lambda item: -item[1].weight.total_ns
    ):
        description = f"{thread_id} {thread_names.get(thread_id, '')}".rstrip()
        dominant_function = _dominant_function(tree)
        if dominant_function:
            description += f": {dominant_function}"
        print(
            f"  {report.weight_text(tree.weight.total_ns, tree.weight.working_ns)}  "
            + description
        )


def _emit_rows(title: str, weights: dict[str, _Weight], report: Report, limit: int):
    print(f"\n{title}:")
    for function, weight in sorted(weights.items(), key=lambda item: -item[1].total_ns)[
        :limit
    ]:
        print(f"  {report.weight_text(weight.total_ns, weight.working_ns)}  {function}")


def emit_functions(stacks: list[WeightedStack], report: Report, limit: int):
    """Print the functions with the most cumulative time and the most self time."""
    cumulative: dict[str, _Weight] = collections.defaultdict(_Weight)
    self_weights: dict[str, _Weight] = collections.defaultdict(_Weight)
    for stack in stacks:
        functions = _functions(stack)
        # A recursive function is charged once per stack.
        for function in set(functions):
            cumulative[function].add(stack)
        self_weights[functions[-1]].add(stack)
    _emit_rows("Cumulative", cumulative, report, limit)
    _emit_rows("Self", self_weights, report, limit)


def _tree(stacks: collections.abc.Iterable[WeightedStack]) -> _Node:
    root = _Node(weight=_Weight(), children={})
    for stack in stacks:
        root.weight.add(stack)
        node = root
        for function in _functions(stack):
            child = node.children.get(function)
            if child is None:
                child = _Node(weight=_Weight(), children={})
                node.children[function] = child
            child.weight.add(stack)
            node = child
    return root


def emit_tree(stacks: list[WeightedStack], report: Report, minimum_percent: float):
    """Print the call tree, omitting calls below the minimum share."""
    minimum_ns = report.denominator_ns * minimum_percent / 100
    print("\nCall tree, with each function's own self time:")
    pending: list[tuple[int, str, _Node]] = []

    def push_children(depth: int, node: _Node):
        children = [
            (name, child)
            for name, child in node.children.items()
            if child.weight.total_ns >= minimum_ns
        ]
        # The largest child prints first, so it is pushed last.
        children.sort(key=lambda item: item[1].weight.total_ns)
        pending.extend((depth, name, child) for name, child in children)

    push_children(0, _tree(stacks))
    while pending:
        depth, name, node = pending.pop()
        weight_text = report.weight_text(node.weight.total_ns, node.weight.working_ns)
        # Self time says whether a function consumes its time or delegates it,
        # including to calls too small to show.
        self_ns = node.weight.total_ns - sum(
            child.weight.total_ns for child in node.children.values()
        )
        print(
            f"  {weight_text}  self {100 * self_ns / report.denominator_ns:4.1f}%  "
            + f"{'  ' * depth}{name}"
        )
        push_children(depth + 1, node)
