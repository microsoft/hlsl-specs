# `const`-qualified Instance Methods

* Proposal: [0007](0007-const-instance-methods.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: TBD
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

HLSL does not currently support `const` instance methods for user-defined data
types. This proposal seeks to add support for `const` instance methods.

## Motivation

The absence of `const` instance methods causes some challenges since HLSL
injected ASTs do have `const` and non-`const` instance methods. Further, since
variables can be `const`-qualified, without the ability to specify `const` there
are some cases that cannot be worked around without breaking
`const`-correctness.

DXC has received a number of issues relating to this. Two recent issues are
listed below:

* https://github.com/microsoft/DirectXShaderCompiler/issues/4340
* https://github.com/microsoft/DirectXShaderCompiler/issues/4706

In the first issue, a user defined data type's methods are basically unusable if
the data type is placed in a `ConstantBuffer`. This results from the
`ConstantBuffer` access returning `const &` objects.

The second issue describes a similar problem, where overloaded operators on
instances of `const`-qualified user-defined types are unusable.

## Proposed solution

Following C++, we should enable support for `const` instance methods and
operator overloads. When a method is marked `const`, the implicit `this`
parameter should become a `const &`.

This change should not introduce any syntactic ambiguities or have any
incompatibilities with existing HLSL code.
