---
title: "NNNN - `groupshared` Arguments"
params:
  authors:
    - llvm-beanz: Chris Bieneman
  sponsors:
    - tbd: TBD
  status: Under Consideration
---

* Planned Version: 202x

## Introduction

This proposal introduces a new use of the `groupshared` keyword for function
arguments to allow passing `groupshared` arguments by address rather than by
value or copy-in/copy-out.

## Motivation

DXC's implementation of HLSL includes a set of Interlocked functions
implementing atomic operations on `groupshared` memory. These functions are not
expressible in HLSL and rely on special case implementation in DXC.

## Proposed solution

HLSL 202x will allow the `groupshared` type annotation keyword on function
parameter declarations. The keyword when applied to a parameter declaration of
type `T`, alters the qualified type of the parameter to a `groupshared T &`
(a reference to `groupshared` memory of type `T`).

No implicit or explicit conversion can change the memory space of an object. To
perform such a conversion, a user must declare a new object in the destination
memory space and initialize it appropriately. For overload resolution, the
parameter type must be an exact match in order for overload resolution to
succeed since no conversions will be valid.

## Alternatives considered

[Reference
types](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0006-reference-types.md)
is an obvious alternative. This proposal introduces a slightly conflicting
syntax from what we would prefer with reference types available.

This more minimal feature has material benefit today for both DXC and Clang, and
can avoid Clang requiring special case handling for library functions. As such,
this proposal is preferred to waiting until references can be finalized.

## Outstanding Questions

* Can we enable this feature in earlier language modes? I think yes, but we
  should explore.
* DXC does some odd handling for user-defined data types, does this work in DXC
  or do we need to limit the types it can apply to?
