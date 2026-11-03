# Glossary

Use these exact terms for these Define concepts. "Not:" lists terms to avoid.

- **action**: A quality defined with `define the potential action<...>`. Once
  assigned to a particle, it triggers when its Trigger Conditions Block becomes
  true and then runs its Action Statements Block. Not: function, method,
  machine.
- **Action Guarantee**: A fact the compiler infers is true when an action
  completes.
- **Action Requirement**: An occupancy requirement or value requirement the
  compiler infers for a contracted position. Callers must satisfy it before
  triggering the action. Not: constraint.
- **constraint**: A name type. A named boolean expression on a particle's value,
  assigned like any other quality: `it has the constraint</positive>.` All of a
  position's or view's constraints must be true. Not: predicate, value
  constraint, refinement.
- **local view**: A view defined in an Operation Statements Block with
  `define the view<...>`, which holds an intermediate value. Not: temporary,
  scratch view.
- **logical operation**: A name type that expresses what a value operation does
  logically. It is defined with `define the logical_operation<...>` and executed
  in an Operation Statements Block with
  `execute the logical_operation<standard:/number/add>`. The compiler knows what
  every logical operation means.
- **occupancy requirement**: An Action Requirement that a position contain a
  particle or be empty.
- **particle**: A single atomic creation. It occupies one position and has the
  qualities assigned to it. It may hold a single value. Not: object, instance,
  dimension point.
- **position**: A name that at most one particle can occupy at a time; it is
  either empty or occupied. A potential position is a quality, which gives each
  particle it is assigned to a child position; a local position is defined in an
  action. Not: variable, slot, container.
- **Position Quality Assignment Block**: The
  `it may only contain particles where` block of a position.
- **quality**: Something that can be assigned to a particle: a potential
  position, potential action, value quality, encoding, or constraint. A quality
  exists only while it is assigned to a particle. Not: type, class.
- **Quality Assignment Statement**: An `it has the X<y>.` statement in a
  Position or View Quality Assignment Block. Not: Position Requirement
  Statement.
- **value**: The logical meaning a particle holds, such as a rational number.
  Its encoding and value operations determine its behavior. A particle's value
  is either set or unset.
- **value quality**: A quality defined with `define the potential value<...>`
  that names a kind of value. A particle may have only one value quality. Not:
  value type, data type, value constraint.
- **value requirement**: An Action Requirement that a position's particle have a
  set value. Not: set-value requirement.
- **View Quality Assignment Block**: The `it may only contain particles where`
  block of a view.
