# Limited Pointers and References

* Proposal: [0006](0006-limited-pointers.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

The addition of pointers and references in limited contexts in HLSL will improve the expressivity of the language, enable code sharing between CPU and GPU code
and enable future language enhancements.

## Motivation

The continued absence of references in HLSL makes some C++ features and patterns
impossible to replicate. As specific examples, assignment operators, container
data types, and read-write parameters are all impossible without references.

## Proposed solution

Add support for single-indirection pointers and references as local variables,
function parameters and return types. This enables common code patterns like
returning references and implementing assignment or subscript operators.

All pointers must be assumed to be in the GPUs addressing and cannot be assumed
to be valid from the CPU, nor can CPU pointers be assumed to be valid in HLSL.
For this reason HLSL pointers and references cannot be present in any input or
output data structure.

Similarly integer to pointer conversion is prohibited.

Pointers may be annotated with an address space attribute. Pointers cannot be
casted between address spaces, however data from a pointer in one address space
can be loaded and stored to a pointer in another address space.

### Expanded Operator Overloading

Along with the introduction of pointers and references we can expand operator
overloading to remove the restrictions introduced in HLSL 2021. 

Support for overloading operators that idiomatically returned references are
prohibited in HLSL 2021. With the addition of limited reference support those
prohibitions can be lifted, enabling full compatibility with C++ operator
overloading.

Additionally, HLSL 2021 only allowed overloading member operators. With this
proposal, operator overloading is supported for global and namespace-level
operators following C++ syntax and semantics.

### Deprecating `in`, `inout` and `out`

In HLSL `inout` parameters have copy-in/copy-out semantics. In many common cases
this implementation detail has no bearing on the result of executed code because
calls are inlined and the redundant copies eliminated.

However, if an `inout` parameter is a read-write global or namespace variable
that is used inside the function, the `inout` semantics can have unintuitive and
unexpected results.

With the addition of references to the language, we can support reference
parameter passing and deprecate the `in`, `inout` and `out` keywords.
