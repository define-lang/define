"""A callee's Guarantees that have not been applied to the caller's state yet."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from define.compiler.validator import codegen_input
    from define.compiler.validator.reference_graph import action_contract

# Nested guarantees are deferred instead of being flattened into every caller's
# state, and this laziness is a critical performance optimization. Eagerly
# flattening the whole guarantee list re-copies a callee's entire guarantee
# subtree at each level of a deep call chain, so an action graph with fan-out F
# and call depth D produces O(F^D) guarantees: an exponential blowup that
# eventually makes compilation impossible.
#
# Deferring the resolution of guarantees keeps each contract at a size of
# O(own guarantees + F references) and only materializes the guarantees a
# specific caller actually depends on directly in their code.


class PendingGuarantee(msgspec.Struct, frozen=True):
    """A callee's guarantees, waiting on the particle its action acts on."""

    # The triggered action's typed name. Its chain is the particle's position
    # followed by this name, so the guarantee follows the particle when it moves.
    action: str
    contract: action_contract.ActionContract
    # The Action Execution that produced this nested guarantee. All of a
    # triggered contract's guarantees (own and nested) carry it, so guarantees
    # from the same Action Execution can be ordered by completion_index.
    execution: codegen_input.ActionExecution
    # Where this action finished among every action in the Action Execution.
    # Callees finish in triggering order, and each action finishes after its
    # callees. Within one Action Execution, a guarantee with a higher index
    # comes from an action that finished later.
    completion_index: int
    # How many nested guarantees separate this one from the directly-applied
    # contract, whose depth is 0.
    call_depth: int = 0

    def action_chain(
        self, particle: chained_name.ChainedNameTuple
    ) -> chained_name.ActionReferenceTuple:
        """Return the triggered action's chain when it acts on the particle at ``particle``."""
        return chained_name.action((*particle, self.action))

    @property
    def identity(self) -> PendingGuaranteeIdentity:
        """Fields that make two pending guarantees apply identical effects."""
        return PendingGuaranteeIdentity(
            self.action,
            id(self.contract),
            self.execution,
            self.call_depth,
        )

    def callees(
        self, action_chain: chained_name.ActionReferenceTuple
    ) -> Iterator[tuple[chained_name.ActionReferenceTuple, PendingGuarantee]]:
        """Yield each callee's chain and pending guarantee, in triggering order, when this action acts through ``action_chain``."""
        # This action's callees own the completion indexes just before its own.
        completed = self.completion_index - self.contract.action_execution_count
        for callee in self.contract.callees:
            callee_chain = chained_name.in_caller(action_chain, callee.action_chain)
            completed += callee.contract.action_execution_count
            yield (
                callee_chain,
                PendingGuarantee(
                    callee_chain[-1],
                    callee.contract,
                    self.execution,
                    completed,
                    self.call_depth + 1,
                ),
            )


class PendingGuaranteeIdentity(msgspec.Struct, frozen=True):
    """Fields that make two pending guarantees apply identical effects."""

    action: str
    # Contracts are compared by identity because comparing their contents
    # would walk every guarantee, and each definition has one contract.
    contract_id: int
    # Action Executions already compare by identity.
    execution: codegen_input.ActionExecution
    call_depth: int
