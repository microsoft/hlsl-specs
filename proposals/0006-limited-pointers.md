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
function parameters and return types. This enables common code patterns like returning references and implementing assignment or subscript operators.

All pointers must be assumed to be in the GPUs addressing and cannot be assumed
to be valid from the CPU, nor can CPU pointers be assumed to be valid in HLSL.
For this reason HLSL pointers and references cannot be present in any input or
output data structure.

Similarly integer to pointer conversion is prohibited.

Pointers may be annotated with an address space attribute. Pointers cannot be
casted between address spaces, however data from a pointer in one address space
can be loaded and stored to a pointer in another address space.
