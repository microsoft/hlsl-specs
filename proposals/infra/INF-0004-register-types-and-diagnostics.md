* Proposal: [0004](INF-0004-register-types-and-diagnostics.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Impacted Project(s): (LLVM)
* PRs: [#87578](https://github.com/llvm/llvm-project/pull/87578)
* Issues: [#57886](https://github.com/llvm/llvm-project/issues/57886)

## Introduction
Register binding syntax in HLSL is used to assign binding locations for
resources and offsets for constants in constant buffers.
For example:
```hlsl
RWBuffer<float> rwbuf : register(u0);
```
In this syntax, `: register(u0)` indicates a resource binding location for a
UAV resource. Further, the resource type (or variable type) is `RWBuffer`, with a 
resource element type of `float` being declared as the variable `rwbuf`. 
The register type is `u` and the register number is `0`.
There are a variety of rules for register bindings that require compiler
diagnostics.  This document proposes a clear set of rules and diagnostics for
this register binding annotation and outlines an approach to implementing these
rules in the compiler.

## Motivation

Diagnostic behavior for register binding annotations in DXC and FXC can be
problematic in a variety of ways.  Attempting to copy the behavior of these
compilers going forward is undesirable. As such, there is a need to more
clearly specify the expected compiler behavior to make it more friendly and
predictable for users.
Problematic cases include unsupported DirectX 9 bindings that are allowed,
ignored, or even suggested as fixes for invalid bindings by the compiler.
For example, in the case of:

`float b : register(u4);`

an error will be emitted recommending the use of the 'b, c, or i' register
type. However the 'i' register type is no longer in support, and the 'b' 
register type is only reserved for resource types that are constant buffers.
It is worth noting that there is an overloading of the register(...) keyword
using the 'c' register type to indicate an offset into a constant buffer for
numeric types only, as opposed to specifying a resource binding.
Additionally, it is possible the user is unaware that this variable won't 
actually be used as a resource, but the compiler doesn't communicate that 
to the user. We should make it clear in this document which variables are 
compatible with which register types.

## Proposed Solution

The resource binding attribute will be attached to any declaration object (Decl)
that has the `: register(...)` annotation. In Sema, this attribute has a function to
validate its correctness, called `handleResourceBindingAttr`, within 
`clang\lib\Sema\SemaHLSL.cpp`. The diagnostic infrastructure will be implemented 
within this validation function to analyze the declaration that the annotation
is applied to, and validate that the register type used within the annotation is 
compatible with the Decl type. There are other details that need validation, such
as whether there are any duplicate register annotations with the same register 
type that have been applied to the Decl. Even the context in which the Decl
appears (inside or outside a cbuffer or tbuffer) influences the legality of 
certain register types. All of this analysis and validation will be executed
inside a new function, `DiagnoseHLSLResourceRegType`.

There are 4 register types that are expected to be used to bind common resources:

| Resource Class | Register Type |
|-|-|
| SRV | t |
| UAV | u |
| CBuffer | b |
| Sampler | s |

`DiagnoseHLSLResourceRegType` will validate that resources are bound using the 
expected register type. There are other register types that may legally appear in 
the register annotation, `c` and `i`. `DiagnoseHLSLResourceRegType` will be 
responsible for determining if these register types are used correctly in certain
legacy contexts, or whether such uses are invalid. `DiagnoseHLSLResourceRegType` 
will also be responsible for emitting a diagnostic if any other invalid register
type is detected. This infrastructure will prioritize emitting diagnostics that
explain why the variable type isn't suitable for the register type, rather than 
why the register type isn't suitable for the variable type.

If `DiagnoseHLSLResourceRegType` finds any critical errors, the attribute,
`handleResourceBindingAttr`, won't be added to the Decl, and compilation will
fail. However, `handleResourceBindingAttr` may emit some warnings and allow
the attribute to be attached.


## Detailed design

TODO: Fill out and agree on detailed design

## Acknowledgments (Optional)
* Tex Riddell
* Chris Bieneman
* Justin Bogner
* Damyan Pepper
* Farzon Lotfi
<!-- {% endraw %} -->