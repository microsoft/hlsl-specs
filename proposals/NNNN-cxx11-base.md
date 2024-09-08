<!-- {% raw %} -->

# Adopt C++ 11 Base

* Proposal: [NNNN](NNNN-cxx11-base.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: TBD
* Status: **Under Consideration**
* Planned Version: 202y

## Introduction

In DXC HLSL is a set of feature extensions on top of a subset of C++ 98. C++ 98
is now over 20 years old and most modern C++ users have adopted newer language
constructs. This proposal suggests taking the small step of updating HLSL 202y's
base C++ language to C++ 2011.

## Motivation

C++11 is over a decade old and introduced widely adopted features, many of which
have been frequently requested additions for HLSL.

## Proposed solution

Adopt a C++ 11 base language and include the following C++11 features in HLSL:
* auto
* decltype
* constexpr
* C++11 scoped enumerations
* variadic templates
* user-defined literals
* [C++11 attributes](/proposals/0002-cxx-attributes.md)
* Lambda expressions
* Static assert
* Range-based for loops

## Alternatives considered

### C++ 20

We could instead adopt an even more recent C++, like C++20. The main drawback of
that is that it significantly increases the rapid divergence from DXC, and it
gives us a longer list of features that we need to rectify against HLSL's
language features. Adopting a C++11 base for 202y does not prevent later
versions from adopting newer C++ base standards, but it does allow us to phase
the changes in iteratively as HLSL evolves.

### Target HLSL 202x

While the original Clang 3.7 release did support C++ 11 fully, the intrusive
changes to support HLSL broke many of the basic features Clang uses for
configuring language features and supporting language modes. To restore those
parts of clang sufficiently to support a C++11 base in DXC would be non-trivial.
For that reason this is proposed as a Clang-only HLSL 202y feature.

<!-- {% endraw %} -->
