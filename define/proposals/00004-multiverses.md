# Define Language Proposal 4: Multiverses

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** December 30, 2025
- **Date Finalized:**

## Problems

Many programming languages consider that there is only one complete ecosystem of
code: the open-source ecosystem consisting of all open-source programs and
packages in the language's standard package manager. However, in reality there
are many code ecosystems. Each company has its own ecosystem, which could
contain hundreds of thousands of universes. This causes various problems.

### 1: Privacy

Companies are not going to publish their internal authority names and universe
names to a public registry. They need some mechanism to publish their internal
names, and there needs to be some way to know that those names and authorities
are separate from the external names and authorities.

### 2: Uncoordinated Authorities

In the general open-source world, there will be a standard repository for
universes that ensures authorities are actually who they say they are and
records where the code of universes lives. This is a large activity where there
is no central coordinator other than the package repository.

People who do not work in large companies may think that somewhere in a large
company there is some person who is saying how everybody can name things. This
is wildly false in companies of almost any size. Some companies don't even have
a reliable inventory of all of their code, and there are many uncoordinated
teams doing development on disconnected projects.

In other words, large companies have the exact same problem that the open-source
world has: they need some way to assign names to code objects that won't
overlap, without having some human arbiter who decides how everything is going
to be named.

You could just say "everybody uses a single authority named after some internal
domain name in the company," but that doesn't really work---disconnected teams
within a company are essentially all separate authorities from each other that
can't coordinate how they name things.

### 3: Merging Codebases and Companies

The problems above are the worst when two disconnected ecosystems have to
interact, unexpectedly. Imagine two companies merge. One company has something
called `quality<internal:uri:/URI>` and the other company has something with the
_exact same name_ but very different code. Merging those two codebases becomes a
nightmare.

This doesn't require two companies to merge---it happens even when two
disconnected teams in a company suddenly discover they need to share code.

Or what if you used an authority and name internally that then became the name
of an open-source package? For example, imagine there's a new Cloud provider
called CoolCloud that doesn't have its own Define library. So internally at your
company you decided to make `quality<coolcloud.com:cloud:/Network>` or something
like that. _Should_ you have done that? Probably not, but there's nothing
stopping you from doing it (because you don't have to respect the open-source
central package repository rules, inside of your company), and in a large
company, you should assume that any error that can be made will be made. Then
CoolCloud ends up publishing their own open-source library with the exact same
name. Uh-oh.

The most common issue here is that when I'm developing locally, I can write any
authority name and universe name into my code, and I expect that to work.

### 4: Knowing Where to Get Packages

When I want to install a library, where do I get that library from? Most modern
programming languages have a standard central repository for all libraries (Rust
Crates, Ruby Gems, etc.). But inside a company, if I have a bunch of internal
authorities, how do I know where the packages live for those internal
authorities? Do I just have to ship a giant configuration file to every Define
developer at the company? That sounds like quite a bit of work to create and
maintain, as well as being fairly error-prone.

## Solution

This requires a few components.

### The Universe Disambiguator

There needs to be some server somewhere that contains the names of authorities
and universes. It must be able to associate a fully-qualified universe name with
a set of code. It does not have to be a source control server (that is, it does
not have to actually contain the code itself) but it must have a secure method
of associating exact codebases with an exact name.

For example, let's say my code was in GitHub in a repository named `/my/code`
and I wanted to name the universe `my_program`. The disambiguator would have to
maintain a map like:

```
authority: "github.com/my"
universe: "my_program"
location: "https://github.com/my/code"
```

It would need security mechanisms to ensure universe names were correctly
assigned and continued to be correctly assigned, which we will leave for another
proposal.

It would also need to be a standard protocol defined for interacting with the
disambiguator, which we will also leave for another proposal.

The functionality of the disambiguator and its API should remain very basic so
that it can be maintained and upgraded easily (both the central version and any
other copy of it that exists elsewhere, such as inside of a company). It should
be possible for other systems (such as Artifactory, Nexus, etc.) to be able to
easily reproduce the exact behavior and API.

### Allowing Multiple Disambiguators

More than one disambiguator can exist. This is how we solve the problem of "my
company internally has its own ecosystem of code." Each disambiguator represents
its own "multiverse," which is the term we use from here on out.

### Multiverse Names

Every multiverse must have a canonical name that is somehow known to Define's
package manager and/or compiler. This should be provided via two mechanisms:

1. A compiler configuration that can be used locally.
2. A central repository, called `omniverse`, that maintains a canonical mapping
   of names to multiverse servers.

Onmiverse may allow a download of its entire repository (at least the mapping of
multiverse names to their server locations) in the same format as the compiler
configuration.

Multiverse servers listed in Omniverse do not have to be accessible from the
Internet, in case companies wish to simplify their internal deployments and
guarantee there are no name conflicts between their multiverse and others, by
adding their internal multiverse to omniverse. This means that omniverse, though
extremely simple, is an extremely high-security system. It also means that
omniverse will need methods to scale, which we leave up to the maintainers of
omniverse.

For certain multiverses that have proven to be extremely stable and are unlikely
to change, Define should ship the configuration with the core language tools
themselves. This configuration should be able to be updated independently of the
language tools.

All of this does theoretically still allow a small possibility of multiverse
name conflicts, but it should be unlikely, and less common than universe-name
conflicts.

### Name Restrictions

Multiverses have the same naming restrictions as universes, except that they may
not be configured to have different naming restrictions than the default.

### The Standard Multiverse for Shared Libraries

There will be a standard multiverse that is operated as a public service, where
most shared libraries live (essentially, the language's standard package
management repository). It will be called `mv`, which is short for "multiverse."

### The Default Multiverse

The language should specify that there is a default multiverse that code lives
in, so that most code does not have to specify the multiverse that it is being
written in. There are three types of code that will be most commonly used and
modified:

1. The local program the developer is working on.
2. Shared libraries from the standard multiverse.
3. The Define Standard Library.

Which one of those should we make require no multiverse specification? We choose
to make the local program require no multiverse, and to live in a special
multiverse of its own, called `local` that is never specified but whose name is
reserved and used internally by the compiler.

The programmer working on a local codebase is the one least likely to be able to
reason about what multiverse their code lives in. The owners of the Define
standard library will be experts in Define, and people publishing and using
shared libraries from the standard repository know they are doing it.

The restriction on `local` is that nothing outside of the `local` multiverse may
depend on or access code inside the `local` multiverse. In other words, if you
want to publish your code, you must move it out of `local`. It also may not be
the name of any multiverse server in any configuration. Omniverse will reject
any multiverse with that name.

### Multiverses in Names

When required, multiverses appear in names in this format:

`type<multiverse:authority:universe:/name>`

For example, a reference to a name inside of a library might look like:

`quality<mv:pydata.org:pandas:/data_frame>`

If a multiverse name is specified, an authority and universe name must be
specified.

When a multiverse name is not specified, it defaults to `local`.

The name `local` may not be explicitly specified in names, it may only be
implicitly inferred.

### Reserved Multiverse Names

Define should reserve multiverse names for:

- `local`
- `mv`
- All of the package managers of popular programming languages (JavaScript's
  npm, JavaScript's yarn, Java's maven, Ruby's gems, Rust's crates, etc.) to not
  overlap with them in case they implement an interface for Define.
- The names of all popular programming languages.
- All the same words that are reserved for universes.

Also, note that reserved universe names are reserved in all multiverses.

Reserved names are case-insensitive.

### The Standard Library

In code, the Define Standard Library may be referred to as simply `standard`
with no multiverse or authority specified. The official fully-qualified universe
name for the Define Standard Library is `mv:standard:standard`, though that may
never be written in code.

### Disconnected Resolution and Compiler Inputs

The language must specify a mechanism that allows for safety and disambiguation
even when the compiler cannot access the Internet. Ideally, the compiler itself
never has to access the Internet when compiling, both because some computers may
be disconnected and because Internet access is an unnecessary performance
constraint on a compiler.

This should be mostly solved by the local compiler configuration that indicates
which universes are in which location, if we simply assume that multiverse
names, once we read them locally, are an inherent part of universe names.

## A Real Program

A program with a theoretical syntax, since Define does not yet exist:

```
# This is local in my program, so it is invisibly using the "local" multiverse
define the quality<example.com:my_program:/math/adder> {
    define the trigger<combine_different_squares> {
        takes args {
            position<first> is a quality<mv:harvard.edu:geometry:/square>
            position<second> is a quality<other_multiverse:mycompany.com:geometry:/square>
        }
        # And then we do something with those arguments.
    }
}
```

That trigger takes a `geometry:/square` from two different multiverses and does
something with them.

## Why This is the Right Solution

I presently believe it is correct to tie the concept of a multiverse to a
package repository, or at least a "resolver" that points to where packages are.
We have not required that the multiverse itself host the packages, which would
be much more fragile (hosting is more complex and insisting on the hosting
server and the registry being the same seems likely to cause numerous problems
in the future). We only require that the multiverse know where packages live.
The potential fragility of the solution lies mostly in the protocol for
interacting with the multiverse server, which we are leaving for another
proposal.

### Syntax Reasoning

This syntax can be deterministically refactored, even with a search-and-replace
regular expression, in many cases:

`type<multiverse:authority:universe:/name>`

This works because if you specify a multiverse, you must specify an authority
and universe. In all situations, what the prefix means on a name has no
ambiguity:

- `multiverse:authority:universe` means exactly that package in that multiverse.
- `authority:universe` means exactly that package in the `local` universe.
- `universe` alone is an error unless it is `standard`, which we know means
  `mv:standard:standard`, always.

It works as long as `:` is forbidden in multiverse, authority, and universe
names.

### Alternative Implementations

We have, essentially, all the same alternative implementation possibilities as
universes have. We may similarly adopt a syntax like
`in the universe<mv:pydata.org:pandas>` in the future.

## Forward Compatibility

See the "Syntax Reasoning" section above, which gives a fairly good intuitive
proof of forward compatibility. Given there is never ambiguity, deterministic
refactoring is possible.

## Refactoring Existing Systems

No existing systems exist at the time this is being written. It would be very
challenging to deterministically refactor systems to have this property before
they have it, which is why we are including it from the start of the life of the
language.
