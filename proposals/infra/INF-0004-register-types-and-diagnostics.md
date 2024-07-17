* Proposal: [0004](INF-0004-register-types-and-diagnostics.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Impacted Project(s): (LLVM)
* PRs: [#87578](https://github.com/llvm/llvm-project/pull/87578)
* Issues: [#57886](https://github.com/llvm/llvm-project/issues/57886)

## Introduction
Resources are often bound to registers of specific register types in HLSL.
For example:
```
RWBuffer<float> rwbuf: register(u0);
```
Here we have the resource type (or variable type), `RWBuffer` with a resource 
element type of `float` being declared as the variable `rwbuf`, and the variable 
is bound to a register. The register type is `u` and the register number is `0`.
There's a specific set of valid register types that can be used to bind a given 
resource in HLSL. When invalid register types are used to bind resources, helpful 
diagnostics need to be emitted so that the user knows why the resource type is 
invalid, or why the register type isn't correct. This spec defines the behavior
of the compiler for whenever an invalid register type is given, or for when a valid
register type is used to bind a resource type that for whatever reason is 
incompatible with that register type.

## Motivation

There are several cases in DXC in which diagnostics that are related to
invalid register types are out of date or invalid. For example, in the case of:

`float b : register(u4);`

an error will be emitted recommending the use of the 'b, c, or i' register
type. However the 'i' register type is no longer in support, and the 'b' 
register type is only reserved for resource types that are constant buffers.
It is worth noting that there is an overloading of the register(...) keyword
using the 'c' register type to indicate an offset into a constant buffer for
numeric types only, as opposed to specifying a resource binding.
Additionally, it is possible the user is unaware that this variable won't 
actually be used as a resource, but the compiler doesn't communicate that 
to the user. It would be great for any HLSL developer to immediately have
answers to the following questions:
For any valid variable type that needs to be bound as a resource,
what is the set of valid register types for that variable,
and what are all the possible diagnostics that can be emitted if the variable
is given a register type that isn't in the set of valid register types?
The design below aims to specify the answer to these questions.

## Proposed solution
The following table lists all the proposed diagnostic
names and diagnostic messages that are relevant in this spec:

| Diagnostic Name | Diagnostic message | Description |
|-|-|-|
| err_hlsl_mismatching_register_type_and_variable_type | "error: unsupported resource register binding '%select{t\|u\|b\|s}0' on variable of type '%1'"| Emitted if a variable type that isn't accompanied with a resource class attribute is bound with a standard register type (`t`, `u`, `b`, or `s`). |
| err_hlsl_unsupported_register_type_and_variable_type | "error: register binding type '%0' not supported for variable of type '%1'" | Emitted if a variable type is bound using an unsupported register type, like binding a float with the 'x' register type. |
| err_hlsl_mismatching_register_type_and_resource_type | "error: %select{srv\|uav\|cbv\|sampler}2 type '%0' requires register type '%select{t\|u\|b\|s}2', but register type '%1' was used." | Emitted if a known resource type is bound using a standard but mismatching register type, e.g., RWBuffer<int> getting bound with 's'.|
| err_hlsl_unsupported_register_type_and_resource_type | "error: invalid register type '%0' used; expected 't', 'u', 'b', or 's'"| Emitted if an unsupported register type is used to bind a resource, like 'y' being used with RWBuffer<int>.|
| err_hlsl_conflicting_register_annotations | "error: conflicting register annotations: multiple register annotations detected for register type '%0'" | Emitted if two register annotations with the same register type are applied to the same declaration. |
| warn_hlsl_register_type_c_not_in_global_scope | "warning: register binding 'c' ignored inside cbuffer/tbuffer declarations; use pack_offset instead" | Emitted if a basic type is bound with `c` within a `cbuffer` or `tbuffer` scope |
| warn_hlsl_deprecated_register_type_b | "warning: deprecated legacy bool constant register binding 'b' used. 'b' is only used for constant buffer resource binding." | Emitted if the register prefix `b` is used on a variable type without the resource class attribute, like a float type. |
| warn_hlsl_deprecated_register_type_i | "warning: deprecated legacy int constant register binding 'i' used." | Emitted if the register prefix `i` is used on a variable type without the resource class attribute, like a float type. |
| warn_hlsl_UDT_missing_resource_type_member | "warning: variable of type '%0' bound to register type '%1' does not contain a matching '%select{srv\|uav\|cbv\|sampler}2' resource" | Emitted if a UDT is lacking any eligible member to bind using a specific register type, like if a UDT `Foo` was bound with `s` but had no sampler members.|
| warn_hlsl_UDT_missing_basic_type | "warning: register 'c' used on type with no contents to allocate in a constant buffer" | Emitted if a UDT has no numerical members, and is being bound using the `c` register type.|


The overall approach this diagnostic infrastructure will take
in emitting the right diagnostic can be broken down into two steps:
1. Analyze the Decl and set the appropriate flags.
2. Emit a diagnostic driven solely by which flags are set.

Some common cases will be simply described below, and then
the analysis step will be specified, with the diagnostic emission
step right afterwards.

### Simple explanations for common cases

The most common case is when a resource type that is not a 
user-defined type is bound as a resource. The compiler will represent
this declaration as a `clang::VarDecl`, and the `VarDecl` will have attributes.
Any resource declaration will have an associated `HLSLResourceClassAttr` attribute
on the `VarDecl`, from which we can determine the 
resource class, which is sufficient to determine the expected register
type. Any other mismatching register type 
(among 't', 'u', 'b', 's', 'c', or 'i') will result in 
`err_hlsl_mismatching_register_type_and_resource_type`.
The recommended register type will be suggested in the diagnostic.
Alternatively, using `cbuffer` or `tbuffer` is represented as an `HLSLBufferDecl`
object. This object will have a helper function `IsCBuffer()` to help
determine what type of resource it is, and from this function we can determine
what the expected register type should be.
The table below specifies what register type will be expected for 
any resource type that falls under the specified resource class. 


| Resource Class | Register Type |
|-|-|
| SRV | t |
| UAV | u |
| CBuffer | b |
| Sampler | s |

If the given candidate variable is a user-defined type (UDT), then further
analysis is necessary. The analysis step will traverse the UDT and gather all distinct
resource class types contained within the UDT. Next, gather all register declarations
that are being applied to this variable declaration, and collect the register types
that are being specified. The UDT must contain at least one valid resource that can be
bound to the provided register type(s). If not, `warn_hlsl_UDT_missing_resource_type_member`
will be emitted. 
There are no issues if a UDT contains more resources than there
are register binding statements, the resources will be bound to the next available 
space automatically, and so compilation can succeed. It should also be noted that
the 'c' register type can be used on UDTs as well, which would function to
specify the constant offset for the numeric member(s) of the structure. Additionally, 
if the 'c' register type is used on the UDT, then the UDT must contain at least one 
numeric type. If not, `warn_hlsl_UDT_missing_basic_type`
will be emitted. Below are some examples of different UDT's and the diagnostics that
would be emitted when applying resource bindings to the variable:

```
struct Eg1 {
  float f;
  Buffer<float> Buf;
  RWBuffer<float> RWBuf;
  };
Eg1 e1 : register(t0) : register(u0); 
// Valid: f is skipped, Buf is bound to t0, RWBuf is bound to u0


struct Eg2 {
  float f;
  Buffer<float> Buf;
  RWBuffer<float> RWBuf;
  RWBuffer<float> RWBuf2;
  };
Eg2 e2 : register(t0) : register(u0); 
// Valid: f is skipped, Buf is bound to t0, RWBuf is bound to u0. 
// RWBuf2 gets automatically assigned to u1 even though there is no explicit binding for u1.

struct Eg3 {
  struct Bar {
    RWBuffer<int> a;
    };
    Bar b;
};
Eg3 e3 : register(u0);
// Valid: Bar, the struct within Eg3, has a valid resource that can be bound to t0. 

struct Eg4 {
  SamplerState s[3];
};

Eg4 e4 : register(s5);
// Valid: the first sampler state object within Eg5's s is bound to slot 5


struct Eg5 {
  float f;
}; 
// expected-warning@+1{{variable of type 'Eg5' bound to register type 't' does not contain a matching 'srv' resource}}
Eg5 e5 : register(t0);

struct Eg6 {
  struct Bar {
    float f;
  };
  Bar b;
};
// expected-warning@+1{{variable of type 'Eg6' bound to register type 't' does not contain a matching 'srv' resource}}
Eg6 e6 : register(t0);

struct Eg7 {
  RWBuffer<int> a;
}; 
// expected-warning@+1{{register 'c' used on type with no contents to allocate in a constant buffer}}
Eg7 e7 : register(c0);


struct Eg8{
  // expected-error@+1{{'register' attribute only applies to cbuffer/tbuffer and external global variables}}
  RWBuffer<int> a : register(u9);
};
Eg8 e8;


template<typename R>
struct Eg9 {
    R b;
};
// expecting warning: {{variable of type 'Eg9' bound to register type 'u' does not contain a matching 'uav' resource}}
Eg9<Texture2D> e9 : register(u0);
// invalid because after template expansion, there are no valid resources inside Eg10 to bind as a UAV.


struct Eg10{
  RWBuffer<int> a;
  RWBuffer<int> b;
};

// expected-error@+1{{conflicting register annotations: multiple register annotations detected for register type 'u'}}
Eg10 e10 : register(u9) : register(u10);
// expected-error@+1{{conflicting register annotations: multiple register annotations detected for register type 'u'}}
Eg10 e10a : register(u9, space0) : register(u9, space1);

```

The last common case is if the candidate type is not a valid resource type and not
a UDT. Types that are or contain a resource are known as "intangible". More generally,
"intangible types" are "types that have no defined object representation or value 
representation". In this case, we are dealing with types that cannot be intangible.
Types that can be immediately determined to not be intangible (that is, types that
cannot be a resource type or cannot contain a resource type) are types like booleans,
int, float, float4, etc. If the variable type is among any numerics or a type that
cannot be an intangible type, there is only one exception where the register keyword
can legally be applied to the variable. The only valid register type for such a 
numeric variable type is 'c'. The register keyword in this statement:
`float f : register(c0)`
isn't binding a resource, rather it is specifying a constant register binding offset
within the $Globals cbuffer, which is legacy behavior from DX9. Because this specific 
register overload is only applicable if the developer wants to make modifications to the
$Globals buffer, it is not useful when the overload is not used inside the $Globals
context. That is, if this register overload appears within a `cbuffer {...}` or 
`tbuffer {...}` scope, the register number will be ignored. In this case, 
`warn_hlsl_register_type_c_not_in_global_scope` will be emitted, and will be treated as an error by default.
All other legal register types applied to such a type will emit `err_hlsl_mismatching_register_type_and_variable_type`, 
except for 'b' or 'i'. If the register type is 'b' or 'i', then `warn_hlsl_deprecated_register_type_b` or 
`warn_hlsl_deprecated_register_type_i` will be emitted respectively, and treated as errors by default. 
The compiler will function as if `c` was passed. 
Invalid register types will cause `err_hlsl_unsupported_register_type_and_variable_type` to be emitted.

Below are some examples:

| Code | Diagnostic |
|-|-|
| `float f : register(t0)` | "error: unsupported resource register binding 't' on variable of type 'float'" |
| `float f : register(c0)` | Valid, no errors
| `float f : register(b0)` | "warning: deprecated legacy bool constant register binding 'b' used. 'b' is only used for constant buffer resource binding." |
| `float f : register(i0)` | "warning: deprecated legacy int constant register binding 'i' used." |
| `float f : register(x0)` | "error: invalid register type 'x' used; expected 't', 'u', 'b', or 's'" |
| `cbuffer g_cbuffer { float f : register(c2); }` | "warning: register binding 'c' ignored inside cbuffer/tbuffer declarations; use pack_offset instead" |
| `RWBuffer<float> f : register(c3);`| "error: UAV type 'RWBuffer<float>' requires register type 'u', but register type 'c' was used." |

## Detailed design

In DXC, the analysis and diagnostic emission steps would happen in DiagnoseRegisterType(),
under DiagnoseHLSLDecl in SemaHLSL.cpp. In clang, there is a function called 
`handleHLSLResourceBindingAttr` in `clang\lib\Sema\SemaDeclAttr.cpp` that is responsible for
diagnosing and validating the `register` keyword when it is applied to any decl. Any time the
`register` annotation is applied on a decl, the `AT_HLSLResourceBinding` attribute gets added
to the decl's attribute list in `clang\lib\Parse\ParseHLSL.cpp`, under `ParseHLSLAnnotations`.
Note that there are instances where multiple `register` statements can apply to a single 
decl, and this is only invalid if any of the register annotations have the same register types.
If this invalid case happens, `err_hlsl_conflicting_register_annotations` will be emitted. 
There is a separate case where two decls in separate locations in the translation unit have 
overlapping register numbers and register types, causing a conflict. This type of conflict 
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
`handleHLSLResourceBindingAttr` will be run, which contains a call to `DiagnoseHLSLResourceRegType`.
This function is responsible for the emission of the diagnostics described in this spec.

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
The `UDT` flag is set when the variable type is a udt, and it has an associated flag,
`ContainsNumeric`, which will be set if the UDT contains a numeric type.

These flags are all mutually exclusive, and are represented in the implementation
as a set of boolean flags that are part of a struct, `RegisterBindingFlags`.

The next group of flags are the resource class flags, which are `SRV`, `UAV`, `CBV`,
or `Sampler`. For example, if an SRV resource is detected in the decl, then the 
`Resource` flag is set and the associated resource class flag `SRV` is set too. For
UDTs, the `UDT` flag is set, and any resource class flags can be set if the associated
resource is found contained within the UDT.

The `DefaultGlobals` flag indicates whether or not the value ends up inside the 
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

RWBuffer<int> r0 : register(u0); // resource (uav is set)
Foo f0 : register(u1); // udt (Foo doesn't contain a numeric, so ContainsNumeric isn't set. UAV is set.)
RayQuery<0> r1: register(t0); // other (error)
float f1 : register (c0); // basic (ends up in $Globals constant buffer, so DefaultGlobals is set)
```

The first step is to simply check if the decl is inside a cbuffer or tbuffer
block. If it isn't, and it has a numeric type, set the `DefaultGlobals` flag,
because the value is bound to be placed in the `$Globals` buffer. If the decl is
in a FieldDecl of a class or struct, it is a member declaration, and register 
annotations aren't allowed on member declarations. The compiler will prevent the
register annotation attribute from ever being added to the FieldDecl, because 
`AttrParsedAttrImpl.inc` determines that the parsed attribute doesn't appertain 
to the decl. The attribute only appertains to HLSL buffer objects, or external
global variables. `err_attribute_wrong_decl_type_str` will be emitted in this case.

Next, determine if the decl is a `cbuffer` or `tbuffer`. These are special in that they have
their own decl class type, `HLSLBufferDecl`. To determine if the Decl is a `HLSLBufferDecl`,
the compiler dynamically casts the Decl to an `HLSLBufferDecl`, and then if it succeeds,
checks isCBuffer(). If true, the Decl is a cbuffer, otherwise it is a tbuffer. In either case,
we know the decl is a `Resource` and can infer the resource class (`cbv` or `srv`
respectively). Otherwise, if the dynamic cast fails, we cast to `VarDecl`, and check 
to see if the ResourceClassAttr attribute is present. If it is, the `Resource` flag can be 
set, and the corresponding resource class flag will be set. If the `VarDecl` dynamic cast
fails, then there is some critical validation error, since any Decl with the register 
annotation should either be a `HLSLBufferDecl` or a `VarDecl`.

If the decl has no resource attribute, then check if the decl has an arithmetic type,
and if so, we know that the decl is a `Basic` type. 
If the decl isn't any of those types, then we check if it is a record type.
If so, the decl is a UDT, so the `UDT` flag is set. For a `UDT`, recurse through the 
members of the UDT and its bases, collecting information on what types of resources 
are contained by the UDT, setting corresponding class flags (`SRV`, `UAV`, `CBV`, or 
`Sampler`). Also track whether there are any other numeric members and set the 
`ContainsNumeric` flag. Also, apply any template expansions on the UDT, so that all
types of members in the UDT are defined. Types of interest may be contained in arrays
of arbitrary dimension, so UDT analysis also requires drilling into arrays to determine
if the underlying element type is numeric, or any resource class type of interest.
If the decl is not a UDT, then the `other` flag is set.

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
The compiler will run diagnostics by iterating over all Decl objects with a register annotation.
Firstly, if `Other` is set, then the variable type is not valid for the given register type.
So, we can emit `err_hlsl_unsupported_register_type_and_variable_type`. Next, we validate the
register type. If the register type is not among the expected register types (t, u, b, s, c, or i)
then an error will be emitted depending on the resource type. If the `Resource` flag is set, 
`err_hlsl_mismatching_register_type_and_resource_type` will be emitted. If the `UDT` flag is set, 
`err_hlsl_unsupported_register_type_and_resource_type` will be emitted. If the `Basic` flag is set,
`err_hlsl_unsupported_register_type_and_variable_type` will be emitted. Next, some decls
may have multiple register annotations applied. Regardless of the decl type, there will be 
validation that any pair of register annotation statements may not have the same register type.
If this is detected, `err_hlsl_conflicting_register_annotations` will be emitted.

If the `Resource` flag is set, check the register type against the resource class flag.
If they do not match, `err_hlsl_mismatching_register_type_and_resource_type` is emitted.
If the `Basic` flag is set, then we first check if `DefaultGlobals` is set. If so, then 
we check the register type. If the register type is 'b' or 'i', then
`warn_hlsl_deprecated_register_type_b` or `warn_hlsl_deprecated_register_type_i` 
will be emitted respectively, and treated as errors by default. If the errors are silenced,
the compiler will function as if `c` was passed, and allocate the variables into the 
global constant buffer.
If the register type is 'c', it is allowed, but if `DefaultGlobals` is not set,
`warn_hlsl_register_type_c_not_in_global_scope` will be emitted, 
and will be treated as an error by default.

After this point, `DefaultGlobals` doesn't need to be set.
If 't', 'u', or 's' are given when `Basic` is set, then
`err_hlsl_mismatching_register_type_and_variable_type` will be emitted.
If any other register type is seen, `err_hlsl_unsupported_register_type_and_variable_type`
will be emitted instead.

Finally, in the case that `UDT` is set, we may have multiple register annotations
applied to the decl. For every unique register type that is used to bind the resources contained 
in the given UDT, we verify that the corresponding resource class flag has been set. These
are the register types `t`, `u`, `b`, and `s`. If the corresponding resource class flag is 
not set, `warn_hlsl_UDT_missing_resource_type_member` will be emitted.
If `c` is given, then we must check that `ContainsNumeric` is set, and if not, 
`warn_hlsl_UDT_missing_basic_type` is emitted. Otherwise, if any other register type is given, 
then we emit `err_hlsl_unsupported_register_type_and_variable_type`.

All the warnings introduced in this spec were not emitted in legacy versions of the compiler.
The warnings, `warn_hlsl_register_type_c_not_in_global_scope`,
`warn_hlsl_deprecated_register_type_b`,
`warn_hlsl_deprecated_register_type_i`,
`warn_hlsl_UDT_missing_resource_type_member`, and
`warn_hlsl_UDT_missing_basic_type`, are all within a warning group known as
`disallow-legacy-binding-rules`. However, only `warn_hlsl_UDT_missing_resource_type_member`
and  `warn_hlsl_UDT_missing_basic_type` are not treated as errors by default,
the rest of the warnings are errors by default. If legacy behavior is desired, a 
user can pass the `-Wno-disallow-legacy-binding-rules` flag to the compiler to silence the
errors and warnings.


Here is some pseudocode summarizing the diagnostic emission process:

```
if Other is set:
  emit err_hlsl_unsupported_register_type_and_variable_type

if the register type is invalid:
  if Resource is set:
    emit err_hlsl_mismatching_register_type_and_resource_type
  if UDT is set:
    emit err_hlsl_unsupported_register_type_and_resource_type
  if Basic is set:
    err_hlsl_unsupported_register_type_and_variable_type

if multiple register annotations exist:
  if any pair of register annotations share the same register type:
    emit err_hlsl_conflicting_register_annotations

if Resource is set:
  if register type does not match resource class flag:
    emit err_hlsl_mismatching_register_type_and_resource_type

if Basic is set:
  if DefaultGlobals is set:
    if register type is 'b' or 'i':
      emit warn_hlsl_deprecated_register_type_b or warn_hlsl_deprecated_register_type_i respectively

  if register type is 'c'
    if DefaultGlobals is not set:
      emit warn_hlsl_register_type_c_not_in_global_scope
  else if register type is 't' 'u' or 's':
    emit err_hlsl_mismatching_register_type_and_variable_type
  else: emit err_hlsl_unsupported_register_type_and_variable_type

if UDT is set:
  let r be the register annotation that is currently being diagnosed:
  if r has register type t:
    if SRV is not set:
      emit warn_hlsl_UDT_missing_resource_type_member
  else if r has register type u:
    if UAV is not set:
      emit warn_hlsl_UDT_missing_resource_type_member
  else if r has register type b:
    if CBV is not set:
      emit warn_hlsl_UDT_missing_resource_type_member
  else if r has register type s:
    if Sampler is not set:
      emit warn_hlsl_UDT_missing_resource_type_member
  else if r has register type c:
    if ContainsNumeric is not set:
      emit warn_hlsl_UDT_missing_basic_type
  else
    emit err_hlsl_unsupported_register_type_and_variable_type  
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
`err_attribute_wrong_decl_type_str` error would be emitted at code gen, but this
infrastructure will emit this error at Sema, and all of these errors will be emitted
at the Sema stage.


## Acknowledgments (Optional)
* Tex Riddell
* Chris Bieneman
* Justin Bogner
* Damyan Pepper
* Farzon Lotfi
<!-- {% endraw %} -->