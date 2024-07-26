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
Firstly, below is some sample code that would cause the proposed diagnostics to be emitted:
```
// UDTs with register bindings for resources that don't exist:
//
// - warn_hlsl_user_defined_type_missing_member
// warning: binding type '%select{t|u|b|s|c}0' only applies to types containing '%select{srv resources|uav resources|constant buffer resources|sampler state|constant buffer data}0'
struct Eg1 { float f; };
Eg1 e1 : register(t0);
// warning: binding type 't' only applies to types containing 'srv' resources.
//

// Mismatched register bindings:
//
// - err_hlsl_binding_type_mismatch
// error: binding type '%select{t|u|b|s|c}0' only applies to '%select{srv resources|uav resources|constant buffer resources|sampler state|constant buffer data}0'
float f : register(t0);
// error: binding type 't' only applies to 'srv' resources.
RWBuffer<float> f : register(c3);
// error: binding type 'c' only applies to constant buffer data.
//

// Invalid binding types:
//
// err_hlsl_binding_type_invalid
// error: binding type '%0' is invalid.
float f : register(x0);
// error: binding type 'x' is invalid.
//

// Multiple bindings with the same register type:
//
// - err_hlsl_duplicate_register_annotation
// error: binding type '%select{t|u|b|s|c|i}' cannot be applied more than once
struct Eg10{
  RWBuffer<int> a;
  RWBuffer<int> b;
};
Eg10 e10 : register(u9) : register(u10);
// error: binding type 'u' cannot be applied more than once
//

// Binding 'c' when it should be packoffset in non-global scope:
//
// - warn_hlsl_register_type_c_packoffset
// warning: binding type 'c' ignored in buffer declaration. Did you mean 'pack_offset'?
cbuffer g_cbuffer { float f : register(c2); }
// warning: binding type 'c' ignored in buffer declaration. Did you mean 'pack_offset'?
//

// Binding 'b' ignored / being used in the legacy way:
//
// - warn_hlsl_deprecated_register_type_b
// warning: binding type 'b' only applies to constant buffers. The "bool constant" binding type has been removed.
float f : register(b0);
// warning: binding type 'b' only applies to constant buffers. The "bool constant" binding type has been removed.
//

// Binding 'i' ignored (also wording):
//
// warn_hlsl_deprecated_register_type_i
// warning: binding type 'i' ignored. The "integer constant" binding type has been removed
float f : register(i0);
// warning: binding type 'i' ignored. The "integer constant" binding type has been removed
//
```

In DXC, the analysis and diagnostic emission steps would happen in DiagnoseRegisterType(),
under DiagnoseHLSLDecl in SemaHLSL.cpp. In clang, there is a function called in
`clang\lib\Sema\SemaDeclAttr.cpp` named `handleResourceBindingAttr` that is responsible for
diagnosing and validating the `register` keyword when it is applied to any decl. Any time the
`register` annotation is applied on a decl, the `AT_HLSLResourceBinding` attribute gets added
to the decl's attribute list in `clang\lib\Parse\ParseHLSL.cpp`, under `ParseHLSLAnnotations`.
When two decls in separate locations in the translation unit have 
overlapping register numbers and the same register type, a conflict arises. This type of conflict 
cannot be detected at this stage of compilation, because parsing is not yet complete. 
Detecting this conflict is out of scope for this diagnostic infrastructure, but will be 
caught later by the register allocation algorithm. 
In `dxc`, `\lib\HLSL\DxilCondenseResources.cpp` has a class called
`DxilResourceRegisterAllocator` with a member `AllocateRegisters` that is responsible for
allocating registers and validating that there aren't any conflicts or overlaps. As for 
`clang-dxc`, there is not yet any register allocation validation, but when resources are
finalized, allocation validation must be implemented, and will likely use the same algorithm 
used in DXC.

For each decl that contains this `AT_HLSLResourceBinding` attribute, 
`handleResourceBindingAttr` will be run, which contains a call to `DiagnoseHLSLRegisterAttribute`.
`DiagnoseHLSLRegisterAttribute` is responsible for the analysis of the decl and the emission
of the diagnostics described in this spec.

### Analysis 

All the compiler has to work with is a Decl object and the context the decl appears in.
From this information, the first goal is to set some flags that can fully inform the 
compiler of the right diagnostic to emit. The first group of flags are the variable type flags,
which are either `Basic`, `Resource`, `UDT`, or `Other`. 
`Basic` refers to a numeric or arithmetic variable type. `Other` refers to built-in HLSL object types
(intangible types) that are not resources (e.g., `RayQuery`) and thus cannot be placed into
a cbuffer or bound as a resource. It also refers to variables that are groupshared, and
cannot be bound to any register. So, if `Other` is set, an error will always be emitted.
The `Resource` flag is set when the variable type is a simple HLSL resource object, 
with the `HLSLResourceClassAttr` attribute attached to the VarDecl.
The `UDT` flag is set when the variable type is a UDT, and it has an associated flag,
`ContainsNumeric`, which will be set if the UDT contains a numeric type.

These variable type flags are all mutually exclusive, and are represented in the implementation
as a set of boolean flags that are part of a struct, `RegisterBindingFlags`.

The next group of flags are the resource class flags, which are `SRV`, `UAV`, `CBV`,
or `Sampler`. For example, if the decl has the `HLSLResourceClassAttr` and the attribute
indicates that the decl type is an SRV resource, then the `Resource` flag is set and the
associated resource class flag `SRV` is set too. For UDTs, the `UDT` flag is set, and any
resource class flags can be set if the associated resource is found contained within the UDT.

The `DefaultGlobals` flag indicates whether or not the decl's value ends up inside the 
`$Globals` constant buffer. It will not be set if the decl appears inside a cbuffer 
or tbuffer. The `$Globals` constant buffer will only be filled with non-HLSL-Objects.

```
Flags:
  Resource,
  UDT,
  Other,
  Basic,

  SRV,
  UAV,
  CBV,
  Sampler

  ContainsNumeric
  DefaultGlobals

struct Foo {
  RWBuffer<int> f;
};

// examples
RWBuffer<int> r0 : register(u0); // resource (uav is set)
Foo f0 : register(u1); // udt (Foo doesn't contain a numeric, so ContainsNumeric isn't set. UAV is set.)
RayQuery<0> r1: register(t0); // other (error)
float f1 : register (c0); // basic (ends up in $Globals constant buffer, so DefaultGlobals is set)
```
Below is some pseudocode to describe the flag-setting process:

```
if the decl is groupshared:
  set other flag

if the Decl is not inside a cbuffer or tbuffer:
  if the Decl type is a numeric type:
    set DefaultGlobals

if the Decl is an HLSLBufferDecl:
  set resource
  if cbuffer: set cbv
  else: set srv
else if the Decl is a VarDecl:
  if resource attribute: 
    get resource attribute, set resource and corresponding resource class flag
  else:
    if Decl is vector, matrix, or otherwise numeric type:
      set basic flag
    else if Decl is struct or class type (if it is a udt):
      set udt flag
      recurse through members, set resource class flags that are found
      set ContainsNumeric if the UDT contains a numeric member
    else:
      set other flag
else:
  raise error: (unknown decl type)
```


### Diagnostic emisison

Now enough information has been gathered to determine the right diagnostics to emit, if any.
The compiler will emit diagnostics by iterating over all Decl objects with a `register` annotation,
and for each annotation, running `DiagnoseHLSLRegisterAttribute` once.

All the warnings introduced in this spec were not emitted in legacy versions of the compiler.
The warnings, `warn_hlsl_register_type_c_packoffset`,
`warn_hlsl_deprecated_register_type_b`,
`warn_hlsl_deprecated_register_type_i`, and
`warn_hlsl_user_defined_type_missing_member`, are all within a warning group known as
`DisallowLegacyBindingRules`. However, only `warn_hlsl_user_defined_type_missing_member` is not 
treated as errors by default, the rest of the warnings are errors by default. If legacy behavior 
is desired, a user can pass the `-Wno-disallow-legacy-binding-rules` flag to the compiler to silence 
the errors and warnings.


Here is some pseudocode summarizing the diagnostic emission process:

```
if the register type is invalid:
  emit err_hlsl_binding_type_invalid

if Other is set:
  emit err_hlsl_binding_type_mismatch

if multiple register annotations exist:
  if any pair of register annotations share the same register type:
    emit err_hlsl_duplicate_register_annotation

if Resource is set:
  if register type does not match resource class flag:
    emit err_hlsl_binding_type_mismatch

if Basic is set:
  if DefaultGlobals is set:
    if register type is 'b' or 'i':
      emit warn_hlsl_deprecated_register_type_b or warn_hlsl_deprecated_register_type_i respectively

  if register type is 'c'
    if DefaultGlobals is not set:
      emit warn_hlsl_register_type_c_packoffset
  else if register type is 't' 'u' or 's':
    emit err_hlsl_binding_type_mismatch
  else: emit err_hlsl_binding_type_invalid

if UDT is set:
  if register type is t:
    if SRV is not set:
      emit warn_hlsl_user_defined_type_missing_member
  else if register type is u:
    if UAV is not set:
      emit warn_hlsl_user_defined_type_missing_member
  else if register type is b:
    if CBV is not set:
      emit warn_hlsl_user_defined_type_missing_member
  else if register type is s:
    if Sampler is not set:
      emit warn_hlsl_user_defined_type_missing_member
  else if register type is c:
    if ContainsNumeric is not set:
      emit warn_hlsl_user_defined_type_missing_member
  else
    emit err_hlsl_binding_type_invalid  
```

## Behavioral Differences

This infrastructure will introduce some behavioral differences between `clang` and `dxc`.
The whole approach of setting flags based on decl characteristics and using them
to drive diagnostics is an approach that wasn't taken in DXC. Secondly, as mentioned above, 
the `disallow-legacy-binding-rules` warning group did not exist in `dxc`, and neither
did any of the warnings that are contained in that group. Those warnings are being 
introduced to `clang-dxc`. Many of these warnings will be treated as errors, causing some
HLSL source to fail compilation in `clang-dxc` that would otherwise pass in `dxc`. 
Another difference is that some of these errors will occur earlier in the compilation
pipeline compared to `dxc`. For example, in `dxc`, the equivalent of the
`err_attribute_wrong_decl_type_str` error would be emitted at code gen (this error is emitted
when the register annotation is applied to a struct member, which is illegal), but this
infrastructure will emit this error at Sema, and all of these errors will be emitted
at the Sema stage.


## Acknowledgments (Optional)
* Tex Riddell
* Chris Bieneman
* Justin Bogner
* Damyan Pepper
* Farzon Lotfi
<!-- {% endraw %} -->
