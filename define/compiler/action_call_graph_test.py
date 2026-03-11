from define.compiler import action_call_graph, ast
from define.compiler.validator import validation_result

# TODO: Make this parse source instead of generating AST nodes.


def _pos() -> ast.SourcePosition:
    return ast.SourcePosition(line=1, column=1, end_line=1, end_column=1)


def _fqun(domain: str = "d", lib: str = "u") -> ast.Fqun:
    return ast.Fqun(
        position=_pos(),
        multiverse=None,
        authority=ast.Authority(position=_pos(), name=domain),
        universe=ast.Universe(position=_pos(), name=lib),
    )


def _action_typed_name(
    path: str, fqun: ast.Fqun | None = None
) -> ast.GlobalTypedNameInDefinition:
    fqun = fqun or _fqun()
    return ast.GlobalTypedNameInDefinition(
        position=_pos(),
        name_type=ast.NameType.ACTION,
        name_content=ast.DefinitionGlobalNameContent(
            position=_pos(),
            fqun=fqun,
            path=ast.GlobalPathName(position=_pos(), name=path),
        ),
    )


def _chained_name(elements: list[ast.TypedNameReference]) -> ast.ChainedName:
    return ast.ChainedName(typed_names=elements, position=_pos())


def _local_chain(name: str) -> ast.ChainedName:
    return _chained_name(
        [
            ast.LocalTypedNameReference(
                position=_pos(),
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(position=_pos(), name=name),
            )
        ]
    )


def _global_action_local_pos(action_path: str, pos_name: str) -> ast.ChainedName:
    return _chained_name(
        [
            ast.GlobalTypedNameReference(
                position=_pos(),
                name_type=ast.NameType.ACTION,
                name_content=ast.ReferenceGlobalNameContent(
                    position=_pos(),
                    fqun=None,
                    path=ast.GlobalPathName(position=_pos(), name=action_path),
                ),
            ),
            ast.LocalTypedNameReference(
                position=_pos(),
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(position=_pos(), name=pos_name),
            ),
        ]
    )


def _make_create_stmt(
    chain: ast.ChainedName,
) -> ast.CreateDimensionPointStatement:
    return ast.CreateDimensionPointStatement(
        position=_pos(),
        position_reference=ast.PositionReference(position=_pos(), chain=chain),
    )


def _make_move_stmt(
    to_chain: ast.ChainedName,
) -> ast.MoveDimensionPointStatement:
    return ast.MoveDimensionPointStatement(
        position=_pos(),
        from_position=ast.PositionReference(position=_pos(), chain=_chained_name([])),
        to_position=ast.PositionReference(position=_pos(), chain=to_chain),
    )


def _make_result(
    trigger_positions: list[action_call_graph.TriggerPositionInfo] | None = None,
    action_body_effects: list[action_call_graph.ActionBodyEffect] | None = None,
) -> validation_result.DefinitionValidationResult:
    return validation_result.DefinitionValidationResult(
        definition=ast.PositionDefinition(
            name=ast.DefinitionGlobalNameContent(
                position=_pos(),
                fqun=_fqun(),
                path=ast.GlobalPathName(position=_pos(), name="/placeholder"),
            ),
            position=_pos(),
        ),
        trigger_positions=trigger_positions or [],
        action_body_effects=action_body_effects or [],
    )


class TestActionCallGraph:
    def test_empty_graph(self):
        graph = action_call_graph.ActionCallGraph()
        assert graph.all_edges() == []

    def test_single_trigger_edge(self):
        graph = action_call_graph.ActionCallGraph()
        chain = _global_action_local_pos("/act_a", "my_pos")
        stmt = _make_create_stmt(chain)

        result_a = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_a"),
                    checked_position=_local_chain("my_pos"),
                )
            ],
        )
        result_b = _make_result(
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_b"),
                    statement=stmt,
                )
            ],
        )

        graph.process_definition_result(
            result_a.trigger_positions, result_a.action_body_effects
        )
        graph.process_definition_result(
            result_b.trigger_positions, result_b.action_body_effects
        )

        edges = graph.all_edges()
        assert len(edges) == 1
        assert edges[0].source_action == "action<d:u:/act_b>"
        assert edges[0].target_action == "action<d:u:/act_a>"
        assert edges[0].statement is stmt

    def test_self_trigger(self):
        graph = action_call_graph.ActionCallGraph()
        typed_name = _action_typed_name("/act_a")
        chain = _local_chain("my_pos")
        stmt = _make_create_stmt(chain)

        result = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=typed_name,
                    checked_position=chain,
                )
            ],
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=typed_name,
                    statement=stmt,
                )
            ],
        )

        graph.process_definition_result(
            result.trigger_positions, result.action_body_effects
        )
        edges = graph.all_edges()
        assert len(edges) == 1
        assert edges[0].source_action == "action<d:u:/act_a>"
        assert edges[0].target_action == "action<d:u:/act_a>"

    def test_deferred_resolution(self):
        graph = action_call_graph.ActionCallGraph()
        chain = _global_action_local_pos("/act_a", "my_pos")
        stmt = _make_create_stmt(chain)

        # Register effect first, before trigger.
        result_b = _make_result(
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_b"),
                    statement=stmt,
                )
            ],
        )
        result_a = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_a"),
                    checked_position=_local_chain("my_pos"),
                )
            ],
        )

        graph.process_definition_result(
            result_b.trigger_positions, result_b.action_body_effects
        )
        assert graph.all_edges() == []

        graph.process_definition_result(
            result_a.trigger_positions, result_a.action_body_effects
        )
        edges = graph.all_edges()
        assert len(edges) == 1
        assert edges[0].source_action == "action<d:u:/act_b>"
        assert edges[0].target_action == "action<d:u:/act_a>"

    def test_same_result_resolution(self):
        graph = action_call_graph.ActionCallGraph()
        chain = _global_action_local_pos("/act_a", "my_pos")
        stmt = _make_create_stmt(chain)

        result = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_a"),
                    checked_position=_local_chain("my_pos"),
                )
            ],
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_b"),
                    statement=stmt,
                )
            ],
        )

        graph.process_definition_result(
            result.trigger_positions, result.action_body_effects
        )

        edges = graph.all_edges()
        assert len(edges) == 1
        assert edges[0].source_action == "action<d:u:/act_b>"
        assert edges[0].target_action == "action<d:u:/act_a>"

    def test_duplicates_not_targeted_twice(self):
        graph = action_call_graph.ActionCallGraph()
        chain = _global_action_local_pos("/act_a", "shared")
        stmt = _make_create_stmt(chain)

        result_triggers = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_a"),
                    checked_position=_local_chain("shared"),
                ),
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_c"),
                    checked_position=_local_chain("shared"),
                ),
            ],
        )
        result_effect = _make_result(
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_b"),
                    statement=stmt,
                )
            ],
        )

        graph.process_definition_result(
            result_triggers.trigger_positions, result_triggers.action_body_effects
        )
        graph.process_definition_result(
            result_effect.trigger_positions, result_effect.action_body_effects
        )

        edges = graph.all_edges()
        assert len(edges) == 1
        assert edges[0].source_action == "action<d:u:/act_b>"
        assert edges[0].target_action == "action<d:u:/act_a>"

    def test_multiple_effects_to_same_target(self):
        graph = action_call_graph.ActionCallGraph()
        chain = _global_action_local_pos("/act_a", "my_pos")
        stmt_b = _make_create_stmt(chain)
        stmt_c = _make_move_stmt(chain)

        result_a = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_a"),
                    checked_position=_local_chain("my_pos"),
                )
            ],
        )
        result_effects = _make_result(
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_b"),
                    statement=stmt_b,
                ),
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_c"),
                    statement=stmt_c,
                ),
            ],
        )

        graph.process_definition_result(
            result_a.trigger_positions, result_a.action_body_effects
        )
        graph.process_definition_result(
            result_effects.trigger_positions, result_effects.action_body_effects
        )

        all_edges = graph.all_edges()
        assert len(all_edges) == 2
        sources = {e.source_action for e in all_edges}
        assert sources == {"action<d:u:/act_b>", "action<d:u:/act_c>"}
        for edge in all_edges:
            assert edge.target_action == "action<d:u:/act_a>"

    def test_local_prefix_before_action_reference(self):
        graph = action_call_graph.ActionCallGraph()
        chain = _chained_name(
            [
                ast.LocalTypedNameReference(
                    position=_pos(),
                    name_type=ast.NameType.POSITION,
                    name_content=ast.LocalNameContent(position=_pos(), name="x"),
                ),
                ast.GlobalTypedNameReference(
                    position=_pos(),
                    name_type=ast.NameType.ACTION,
                    name_content=ast.ReferenceGlobalNameContent(
                        position=_pos(),
                        fqun=None,
                        path=ast.GlobalPathName(position=_pos(), name="/act_a"),
                    ),
                ),
                ast.LocalTypedNameReference(
                    position=_pos(),
                    name_type=ast.NameType.POSITION,
                    name_content=ast.LocalNameContent(position=_pos(), name="my_pos"),
                ),
            ]
        )
        stmt = _make_create_stmt(chain)

        result_a = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_a"),
                    checked_position=_local_chain("my_pos"),
                )
            ],
        )
        result_b = _make_result(
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_b"),
                    statement=stmt,
                )
            ],
        )

        graph.process_definition_result(
            result_a.trigger_positions, result_a.action_body_effects
        )
        graph.process_definition_result(
            result_b.trigger_positions, result_b.action_body_effects
        )

        edges = graph.all_edges()
        assert len(edges) == 1
        assert edges[0].source_action == "action<d:u:/act_b>"
        assert edges[0].target_action == "action<d:u:/act_a>"

    def test_no_edge_when_position_does_not_match(self):
        graph = action_call_graph.ActionCallGraph()
        chain = _global_action_local_pos("/act_a", "other_pos")
        stmt = _make_create_stmt(chain)

        result = _make_result(
            trigger_positions=[
                action_call_graph.TriggerPositionInfo(
                    enclosing_typed_name=_action_typed_name("/act_a"),
                    checked_position=_local_chain("trigger_pos"),
                )
            ],
            action_body_effects=[
                action_call_graph.ActionBodyEffect(
                    enclosing_typed_name=_action_typed_name("/act_b"),
                    statement=stmt,
                )
            ],
        )

        graph.process_definition_result(
            result.trigger_positions, result.action_body_effects
        )
        assert graph.all_edges() == []
