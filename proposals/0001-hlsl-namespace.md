# HLSL Namespace

* Proposal: [0001](0001-hlsl-namespace.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202y

## Introduction

Following conventions of other languages HLSL data types should be moved into a
namespace so that they can be disambiguated.

## Motivation

As HLSL is evolving to be more source compatible with C++, some HLSL names will
begin to conflict with C++ names which mean very different things (i.e.
`vector`) and other names which have subtly different usage (i.e. `sin` vs
`sinf`). Moving HLSL library functionality into a namespace removes the
ambiguity and will prevent common errors in the future as HLSL becomes more
C++-like.

We have also received requests in the past to allow developers to
define their own versions of built-in functions. Moving the built-in versions
into a namespace will enable this use case as well.

## Proposed solution

Each HLSL data type and builtin function will be moved from global scope to the
`hlsl` namespace. This can be implemented in the AST construction, HLSL headers,
and other lookup hooks. This would apply to all built in types (`vector`,
`matrix`, `Texture`, `Buffer`, etc), as well as to their typedefs (`float3`,
`float3x3`, etc), and to all builtin functions (`DeviceMemoryBarrier`,
`WaveIsFirstLane`, etc) including math operations (`abs`, `sin`, etc).
