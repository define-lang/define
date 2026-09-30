"""A callee's Guarantees that have not been applied to the caller's state yet."""

from __future__ import annotations

import typing

import msgspec

from define.compiler import chained_name

if typing.TYPE_CHECKING:
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
    """A callee's guarantees and the execution path where they apply."""

    # The triggered action's chain.
    action_chain: chained_name.ActionReferenceTuple
    contract: action_contract.ActionContract
    # The Action Execution that produced this nested guarantee. All of a
    # triggered contract's guarantees (own and nested) carry it, so guarantees
    # from the same Action Execution can be ordered by call_chain_depth.
    execution: codegen_input.ActionExecution
    # Call-chain depth from the directly-applied contract: its own guarantees
    # are depth 0; each nested guarantee increments the depth. Within a single
    # Action Execution, a lower-depth guarantee outranks a higher-depth one it
    # resolved.
    call_chain_depth: int = 0

    @property
    def parent_position(self) -> chained_name.ChainedNameTuple:
        """The parent of the callee's implied (global) positions.

        This is ``action_chain`` with its trailing action stripped: an implied
        quality lives on the action's parent particle, at the parent name of the
        action's interface position names. ``action_chain`` always ends in the
        triggered action, since that is the only thing that produces guarantees.
        """
        return chained_name.parent(self.action_chain)

    def key_for[T: chained_name.ChainedNameTuple](self, name: T) -> T:
        """Return the absolute key for a guarantee this action names ``name``."""
        return chained_name.in_caller(self.action_chain, name)

    @property
    def identity(self) -> PendingGuaranteeIdentity:
        """Fields that make two pending guarantees apply identical effects."""
        return PendingGuaranteeIdentity(
            self.action_chain,
            id(self.contract),
            self.execution,
            self.call_chain_depth,
        )


class PendingGuaranteeIdentity(msgspec.Struct, frozen=True):
    """Fields that make two pending guarantees apply identical effects."""

    action_chain: chained_name.ActionReferenceTuple
    # Contracts are compared by identity because comparing their contents
    # would walk every guarantee, and each definition has one contract.
    contract_id: int
    # Action Executions already compare by identity.
    execution: codegen_input.ActionExecution
    call_chain_depth: int
