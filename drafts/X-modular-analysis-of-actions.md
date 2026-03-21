# Define Language Proposal X: Modular Analysis of Actions

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** March 20, 2026
- **Date Finalized:**

## Problems

As described in [DLP 18 (Modular Constraints)](00018-modular-constraints.md),
the Define compiler must be able to analyze and prove the state of dimension
points within an action without having to first analyze the whole program (steps
3 and 4 of that proposal). Otherwise, proving correctness becomes an intractable
problem.

However, much like with
[DLP 19 (Guaranteeing Qualities in Positions)](00019-guaranteeing-qualities-in-positions.md),
this can get into tremendous complexity if we are not careful. There are a few
concrete problems we need to solve.

### 1: Self-Contained (Modular) Analysis of Actions

In order to have modular analysis, each action must be able to be verified in a
self-contained manner. To understand part of the problem, see this Java example:

```Java
public class BankAccount {
    private double balance;

    public BankAccount(double initialBalance) {
        this.balance = initialBalance;
    }

    public void withdraw(double amount) {
        this.balance -= amount;
    }
}
```

If a static analyzer looks only at the `withdraw` method in complete isolation,
it cannot determine if this code is correct or safe. What if `amount` is
negative? What if `amount` is larger than the balance? A static analyzer would
have to do whole-program dataflow analysis to actually prove safety for this
_very_ simple case.

Sure, the programmer could add checks to the `withdraw` method, but the
programming language doesn't _require_ them to, and thus modular analysis of
Java is not possible for all programs.

### 2: Cross-Action Verification

What if an action calls another action? How can we verify the caller's code
without having to look into the code of the callee? To understand this problem,
let's look at an example in Python:

```Python
def process_middle_element(data: list[int]) -> int:
    index = compute_safe_index(len(data))
    value = data[index]
    return value

def compute_safe_index(max_val: int) -> int:
    return max_val // 2
```

When we analyze `process_middle_element`, we need to know two things:

- Does `len(data)` produce a value that is acceptable to pass into
  `compute_safe_index`?
- Will `compute_safe_index` return an index that is always safely within the
  `data` array?

Sure, you and I can look at the code of `compute_safe_index` and see whether or
not that's the case (in fact, the code is broken for empty arrays) but that
fundamentally breaks modular analysis. Somehow, the _compiler_ has to know, when
analyzing `process_middle_element`, what the guarantees and requirements of
`compute_safe_index` are.

### 3: Preconditions Far Removed From Where They Apply

Most systems that try to solve these problems do so with a system of
"preconditions," where you have to specify a requirement as part of a function's
definition or at the top of a function. This causes some trouble reasoning about
programs when you are reading them, because the requirement about the variable
can be far removed from where the variable is accessed. Take this C# example
using an imaginary precondition system:

```C#
public void ProcessInternationalTransfer(Account sourceAccount, Account targetAccount, decimal amount)
{
    // --- PRECONDITIONS DECLARED HERE ---
    Contract.Requires(amount > 0, "Transfer amount must be positive.");
    Contract.Requires(sourceAccount.Balance >= amount, "Insufficient funds.");
    Contract.Requires(targetAccount.IsActive, "Target account is inactive.");

    // --- 40+ LINES OF SETUP AND INTERMEDIATE LOGIC ---
    // 1. Authenticate the current user's session token.
    // 2. Query an external API for current exchange rates.
    // 3. Query the database for the user's daily transfer limits.
    // 4. Calculate cross-border transaction fees and taxes.
    // 5. Send transaction details to a fraud-detection microservice.
    // 6. Log the transaction attempt to an audit trail.

    // ... (Code omitted for brevity) ...

    // --- USAGE: FAR REMOVED FROM PRECONDITIONS ---
    // At this point, the reader is deep into the transfer execution logic.
    // They are looking at the deduction and might wonder:
    // "Wait, did we ever verify the source account actually has enough money?"

    sourceAccount.Deduct(amount);
    targetAccount.Add(amount);
}
```

### 4: Duplicating the Code in the Postcondition

Many systems that solve for modular analysis require you to explicitly specify
"post-conditions" that say what state a variable must be in at the end of a
function. However, very often this forces the developer to duplicate something
that's totally obvious from the code itself. For example, take this example
using the Java Modeling Language (JML):

```Java
public class Counter {
    private int count;

    //@ ensures this.count == newCount;
    public void setCount(int newCount) {
        this.count = newCount;
    }
}
```

That postcondition is tedious, pointless duplication. It's necessary in JML, but
a language designed for verification can do better.

## Solution

Our solution requires three things:

1. A syntax for specifying requirements about the state of positions within an
   action.
2. A way to "lift" these requirements out to be the external precondition
   contract for the action.
3. A way to "lift" out the state the action actually guarantees on completion as
   its externally-visible postcondition guarantees.

All together, this allows actions to be internally modular while exposing the
external contracts needed for actions to modularly analyze their interactions
with other actions.

### Requirement Syntax

Within an action, developers may specify a requirement on any line in the Action
Statement Block like this:

```
require that {
    # Condition Statement
}
```

This is called a Requirement Statement.

The condition statement syntax is the same as the syntax for an Action's Trigger
Conditions Block, unless otherwise stated in a proposal.

Obviously, requirement statements may only refer to positions that the action
can reference (interface positions, local positions in the Action Statements
Block, and global positions from quality requirement statements). This also
means that they can refer to chained names from those positions.

### Lifting Preconditions (Requirements)

### Lifting Postconditions (Guarantees)

### Action Assumptions

Actions may not assume anything about the state of a dimension point other than
what is specified in position constraints and Requirement Statements.

An action does not know whether an external position is occupied or not unless a
requirement statement specifies that state, or unless an external action's
requirements/guarantees ensure that state.

After an external action completes, the local action does not know if a
dimension point returned is identical to a dimension point sent unless the
action provides that guarantee.

The compiler must fail on any statement in an action that involves making a
decision about an unknown state. For example, an action may not move a dimension
point out of an external position unless the action has first required that that
external position contains a dimension point.
