# Define Language Proposal 3: Authorities

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** December 30, 2025
- **Date Finalized:**

## Problems

### 1: Flat Package Namespaces Become Land Grabs

When you have a flat namespace for all of a programming language's packages, you
start to quickly run out of useful names. For example, in the early days of
Rust's Cargo ecosystem, developers rushed to grab all the most common, useful
names, like `http`, `server`, `client`, etc. This forces library publishers to
start using crazy names like `http_req_2` instead of intuitive names for their
libraries.

### 2: Typosquatting

If I publish a package named `fast_log` and a different developer publishes a
package named `fsat_log` or `faster_log` then developers can accidentally
install the wrong one without knowing, possibly believing it is my library. This
isn't just an inconvenience, but an actual security issue that has happened with
real package managers, where malicious actors publish malware with names very
similar to official packages.

This issue also causes a very difficult support burden for the maintainers of
package repositories, because they then have to remove those malicious or
accidental packages. Sometimes they are even legally required to do so. That is
too much burden for a language whose community is potentially composed of
volunteers.

### 3: Verification and Ownership of Names

With a flat namespace of universes, anybody can publish a package named
`aws-sdk` and I would have no idea if that was published by Amazon or some
random person. What if somebody random publishes that library, and then later
Amazon wants to publish an actual official SDK?

## Solution

We need to make clear the source of each universe. Conceptually, this actually
represents the view point from our [Concepts](../spec/concepts.md). However, we
will use the term "authority" for it, as it makes it clearer that this is the
authority that published the package.

Universes will need an additional component when specified, so names will look
like this: `type<authority:universe:/name>`.

Anywhere a program or configuration file specifies a universe, it must specify
the authority. The authority should be considered to be a part of the universe
name in all implementations that process universe names. (That is, except as
allowed by the Define Language Standard, you can never specify a universe
without specifying its authority.)

### Verification

Authorities will need to be verified as actually representing the entity they
claim to be.

Very likely, this means that authorities need to be domain names (for publishers
that own a domain) or simple URLs without a scheme, fragment, or query string
(for individual publishers that don't own a domain but want to publish a
package). However, specifying that and how security works is complex enough to
leave for another proposal.

### Format

An authority has two parts: a domain, and an optional path.

The domain is everything before the first `/`. It must be a valid lowercase
domain name (though it does not have to contain a `.`). That means it can only
contain lowercase ASCII letters, digits, `.`, and `-`, and it may not start or
end with `-` or `.`.

The domain portion of an authority must be at least two characters long.

The path is everything after the first `/`. If present, it starts with `/` and
is made of one or more segments separated by `/`. Each segment may only contain
lowercase ASCII letters, digits, `_`, `-`, `.`, and `~`. A segment may not start
with `.`, but it may contain `.` elsewhere. There cannot be empty segments, so
`//` and a trailing `/` are forbidden.

### Reserved Authority Names

The following authority names are reserved for use by Define itself:

- All words reserved for universes are also reserved for authority names.
- `define`
- `local`
- `example.com`
- In the `mv` and `local` multiverses, all authorities without a `.` in them are
  reserved.

### Excepting the Standard Library

The standard library does not need to specify an authority. It may specify its
universe simply as `standard` with no authority, so standard library names look
like: `quality<standard:/integer>`.

When Define tooling needs to represent the `standard` universe internally, they
may represent it as `define:standard`.

## A Real Program

Since I am writing this before Define exists, here is a theoretical program
using the syntax:

```
define the quality<example.com:my_program:adder> {
    define the potential_form<add> {
        a dimension point in position<first_arg> {
            it has the quality<standard:/integer>
        }
        a dimension point in position<second_arg> {
            it has the quality<scikit-learn.org:scikit:/numbers/int32>
        }
    }
    # Code goes here that does something with the arguments.
}
```

## Why This is the Right Solution

In terms of the structure of the name, with colon separators, the reasoning is
the same as the format of universes.

The one potential issue with the format is that `:1000` is valid syntax in a URL
(adding a port number to the domain). However, we expect it to be rare that
developers would want to specify a port number in an authority. Also, a port
number is essentially an implementation detail that can be changed without a
registry, unlike a domain name.

In terms of why we need authorities, they are the only solution that I'm aware
of that solves all of the problems mentioned above in the Problems section.

### Why Ban Unicode?

We ban Unicode characters in authorities to prevent typosquatting. In the
future, we may create a more nuanced restriction that allows Unicode in the path
component (like, the part that would be after the domain name, in a URL) of an
authority, though we would need protections against typosquatting if we did
that.

You might ask, "But what about International Domain Names?" Those have not
really gained traction except in a few places, and they have a lot of
typosquatting issues. For security and simplicity, I don't intend for Define to
support them as authorities (you have to use the ugly Punycode translation,
sorry).

### Why Not Like Go?

Go uses module names like this:

```
package main

import (
	// The Standard Library (No domain)
	"net/http"

	// Google (Cloud Client Libraries)
	"cloud.google.com/go/storage"

    // Projects on GitHub
	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
    "github.com/docker/docker/pkg/archive"

	// Personal domain of Russ Cox (former Go technical lead)
	"rsc.io/quote"
)
```

It's actually impossible there to deterministically differentiate the authority
from the module name. I personally happen to know that `github.com/docker/` is
the authority in that docker URL, but how can a static analysis tool know that
deterministically across all possible authorities?

### Why Not Infinitely Nestable Parent Packages?

Rust's Cargo package system is moving in the direction of being able to claim a
package just as a namespace, so you claim `google` and then you can create
`google::guava`.

We wanted to be more definite about the nature of authorities so that they are
always verifiable. We also want to require authorities for all packages from the
start, which other language communities seem to regret when they don't do it.

In the future, we may want hierarchical authorities or hierarchical universes.
At the moment, I'm not aware of a _requirement_ for that, but theoretically the
system as we have specified it could be deterministically refactored into a
system that allows for hierarchies.

## Forward Compatibility

As long as we maintain the requirement that all universes must specify their
authority other than the specifically-named exceptions in the Define Language
Standard, and we don't allow the `:` character in authorities or universes, all
existing Define programs should be deterministically refactorable into a
different syntax.

## Refactoring Existing Systems

No existing systems exist, but we can imagine names written with the proposals
that existed before this one: `quality<my_program:/path/to/name>`.

This _cannot_ be deterministically refactored into having an authority
universally across all codebases, because we can't figure out the authority if
it wasn't already specified. This is why we need authorities up front as part of
the original language design.

However, we could have theoretically allowed a user to say "this is how I want
to provide an authority here," but we would consider that a breaking change in
the world of Define (because it requires manual human intention about how to
refactor).
