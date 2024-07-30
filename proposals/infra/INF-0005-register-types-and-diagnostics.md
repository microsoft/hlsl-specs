<!-- {% raw %} -->
* Proposal: [INF-0005](INF-0005-register-types-and-diagnostics.md)
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
is applied to, and validate that the register type used within the annotation is semantically
compatible with the Decl. All of this analysis and validation will be executed
inside a new function, `DiagnoseHLSLRegisterAttribute`. This function will be
responsible for validating the semantic meaning behind the application of the
attribute, while the rest of `handleResourceBindingAttr` is responsible for
validating the syntax of the attribute.

### Recognized Register Types

There are two types of register bindings, resource bindings and constant register bindings.

Resource register bindings bind a resource like a texture or sampler to a location that is
mapped using the root signature in DX12.

Constant register bindings were originally used to bind values to one of three specialized
constant register banks in DX9.  In DX10 and above, the `c` register binding for the `float`
register bank maps to an offset into the `$Globals` constant buffer and the other two bindings
are unused.

This table lists the recognized register types, the associated resource class if applicable,
along with some brief notes.

| Register | Resource | Notes                                                                                 |
| -------- | -------- | ------------------------------------------------------------------------------------- |
| `t`      | SRV      | read-only texture, buffer, or `tbuffer`/`TextureBuffer`                               |
| `u`      | UAV      | read/write texture or buffer                                                          |
| `s`      | Sampler  | `SamplerState` or `SamplerComparisonState`                                            |
| `b`      | CBV      | `cbuffer`/`ConstantBuffer` resource; also unsupported legacy `bool` constant register |
| `c`      | N/A      | legacy `float` constant register - offset into `$Globals`                             |
| `i`      | N/A      | unsupported legacy `int` constant register

### Register binding contexts

Register bindings may be applied to declarations in several contexts.  This table lists contexts and potentially applicable bindings.

| Decl                                                       | Registers          | Context                                    | Notes                                                                                                                                                                                     |
| ---------------------------------------------------------- | ------------------ | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cbuffer` or `tbuffer` decl                                | `b`, `t`           | any global                                 | `b` for `cbuffer`, `t` for `tbuffer`                                                                                                                                                      |
| (array of) resource                                        | `t`, `u`, `b`, `s` | any global                                 | depends on resource class                                                                                                                                                                 |
| struct/class instance (UDT)                                | `c`, `t`, `s`      | global outside `cbuffer` or `tbuffer` decl | `c` specifies starting location for data members of struct in `$Globals` constant buffer; `t` and `s` specify starting registers for binding any contained SRV and Samplers, respectively |
| struct/class instance (UDT)                                | `t`, `s`           | global inside `cbuffer` or `tbuffer` decl  | `c` register binding may not be used inside `cbuffer` or `tbuffer` context; must use `packoffset` instead                                                                                 |
| (array of) scalar, vector, or matrix numeric or bool types | `c`                | global outside `cbuffer` or `tbuffer` decl | `c` specifies starting location for numeric/bool values in `$Globals` constant buffer                                                                                                     |


`DiagnoseHLSLRegisterAttribute` will validate that the variable type is bound using the
expected register type. `DiagnoseHLSLRegisterAttribute` will be
responsible for determining if register types are used correctly in certain
legacy contexts, or whether such uses are invalid. Specifically, the `c` register
type may only be used in global contexts. In those contexts, a resource isn't being bound,
rather a variable is being placed in the $Globals buffer with a specified offset.
Using `c` within a cbuffer or tbuffer is legacy behavior that should no longer be
supported, so `DiagnoseHLSLRegisterAttribute` will emit a warning in this case
that will be treated as an error by default. When this attribute appears in a non-global
context, `packoffset` will be recommended as an alternative.
The `i` register type is also a legacy DirectX 9 register type that
will no longer be supported, and so a warning will be emitted that is treated
as an error by default when this register type is used.
The `b` register type, when used on a variable that isn't a resource, and doesn't
have a `CBuffer` resource class, is also legacy behavior that will no longer be
supported. In such cases, a warning will be emitted that is treated as an error by
default, and a suggestion will be made that the register type is only used for resources with
the `CBuffer` resource class.
These warnings are all part of a distinct warning group, `LegacyConstantRegisterBinding`
which can be silenced if a developer would prefer to enable compilation of legacy shaders.

Another common case for this annotation to appear in HLSL is for user-defined-types (UDTs).
UDTs may have multiple register annotations applied onto the variable declaration.
`DiagnoseHLSLRegisterAttribute` will be responsible for ensuring that none of the
register annotations conflict (none may have the same register type). `DiagnoseHLSLRegisterAttribute`
will also ensure that any register annotations with a specific register type applied to
the UDT will have a corresponding member in the UDT that can be bound by that register
type (or can be placed into the $Globals constant buffer in the case of `c`). If there
is no corresponding member, a warning will be emitted that is treated as an error by default,
because this behavior was permissible in legacy versions of the compiler. These warnings
are also part of the same warning group, `LegacyConstantRegisterBinding`.

`DiagnoseHLSLRegisterAttribute` will also be responsible for emitting a diagnostic
if any other invalid register type is detected. If `DiagnoseHLSLRegisterAttribute`
finds any critical errors, the attribute, `HLSLResourceBindingAttr`, won't be added
to the Decl, and compilation will fail. However, `DiagnoseHLSLRegisterAttribute` may
emit some warnings and allow the attribute to be attached. In summary,
`DiagnoseHLSLRegisterAttribute` will be responsible for analyzing the context of the
decl to which the register annotation is being applied, and using the data in the
annotation to determine what diagnostics, if any, to emit.
`DiagnoseHLSLRegisterAttribute` will be fully responsible for halting compilation
if there is any semantic fault in the application of the register annotation.


## Detailed design

TODO: Fill out and agree on detailed design

## Acknowledgments (Optional)
* Tex Riddell
* Chris Bieneman
* Justin Bogner
* Damyan Pepper
* Farzon Lotfi
<!-- {% endraw %} -->
