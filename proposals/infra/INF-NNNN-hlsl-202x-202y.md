<!-- {% raw %} -->

# HLSL 202x and 202y

* Proposal: [INF-NNNN HLSL 202x and 202y](NNNN-hlsl-202x-202y.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Impacted Projects: DXC & Clang

## Introduction

This proposal seeks to provide a framework for defining the next two versions of
the HLSL programming language. It seeks to define HLSL 202x as a bridge between
DXC's implementation and Clang's implementation, and HLSL 202y as the next major
feature release.

## Motivation

The HLSL compiler is undergoing a massive transition moving to Clang. Since
the HLSL language is not formally specified and existing implementations
disagree about fundamental behaviors, the new compiler will not be fully
compatible with the previous compilers. This will create three conflicting
implementations.

This poses a challenge for users as they seek to migrate to Clang. Sources used
with DXC may not be compatible with Clang by preventing the ability to switch to
Clang piecemeal or being able to A/B test shaders.

## Proposed solution

This proposal adopts the development of two new language versions for HLSL in
parallel. The proposal adopts a narrowly focused HLSL 202x which will be
supported by both DXC and Clang, and a wider focused HLSL 202y feature release
which will only be supported by Clang.

### HLSL 202x

HLSL 202x shall contain features that bridge compatibility between DXC and
Clang. This shall be limited to cases where Clang's implementations do not match
DXC and it is expected to cause potential disruption.

Existing proposals that fall into this category are:
* [Numeric Constants](/proposals/0003-numeric-constants.md)
* [Removing literal types](https://github.com/microsoft/hlsl-specs/issues/73)

HLSL 202x will not include features for all differences between DXC and Clang.
Some of the
[differences](https://clang.llvm.org/docs/HLSL/ExpectedDifferences.html), are
not expected to have meaningful difference to users, or have reasonable source
compatible workarounds. HLSL 202x is specifically for differences that do not
have workarounds and may pose a barrier to adoption.

### HLSL 202y

HLSL 202y shall contain features that expand HLSL. This is all other outstanding
feature proposals.


<!-- {% endraw %} -->
