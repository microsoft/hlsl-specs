# Reference Data Types

* Proposal: [0006](0006-reference-types.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

The addition of reference types in HLSL will improve the expressivity of the
language, enable more code sharing between CPU and GPU code and enable future
language enhancements.

## Motivation

The continued absence of references in HLSL makes some C++ features and patterns
impossible to replicate. As specific examples, assignment operators, container
data types, and read-write parameters are all impossible without references.

## Proposed solution

Add support for references as local variables, function parameters and return
types. This enables common code patterns like returning references and
implementing assignment or subscript operators.

All addresses must be assumed to be in the GPUs addressing and cannot be assumed
to be valid from the CPU, nor can CPU addresses be assumed to be valid in HLSL.
For this reason HLSL references cannot be present in any input or output data
structure.

References may be annotated with an address space attribute. References cannot
be casted between address spaces, however data from a reference in one address
space can be loaded and stored to an object through a reference in another
address space.

References declared without an address space annotation will be references to
the default address space (0), which corresponds to thread-local addresses.
References to any other address space will need explicit annotation.

### Expanded Operator Overloading

Along with the introduction of references we can expand operator overloading to
remove the restrictions introduced in HLSL 2021. 

Support for overloading operators that idiomatically returned references are
prohibited in HLSL 2021. With the addition of limited reference support those
prohibitions can be lifted, enabling full compatibility with C++ operator
overloading.

Additionally, HLSL 2021 only allowed overloading member operators. With this
proposal, operator overloading is supported for global and namespace-level
operators following C++ syntax and semantics.

## Unanswered Questions From Review

* Elaborate on address spaces, their use and annotations
* Should `in`, `inout` and `out` be deprecated?
* What is the extent of updates required to the HLSL built-in types
