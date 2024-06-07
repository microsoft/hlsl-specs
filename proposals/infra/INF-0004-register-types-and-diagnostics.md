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
Here we have the resource type, `RWBuffer` with a resource element type of `float`
being declared as the variable `rwbuf`, and the variable is bound to a register. 
The register type is `u` and the register number is `0`.
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
For any valid resource type that needs to be bound, what are the set of
valid register types for that resource, and what are all the possible 
diagnostics that can be emitted if the resource is given a register 
type that isn't in the set of valid register types?
The design below aims to specify the answer to these questions.

## Proposed solution
Firstly, for future reference, the set of relevant diagnostics that would be emitted
depending on how the resource type and register type interact should
be named and defined. Below is a table that lists out all the proposed diagnostic
names and diagnostic messages that are relevant in this spec:

| Diagnostic Name | Diagnostic message | Description |
|-|-|-|
| err_hlsl_mismatching_register_type_and_variable_type | "error: unsupported resource register binding '%select{t\|u\|b\|s}1' on variable of type '%0'"| Emitted if a variable type that isn't accompanied with a resource attribute is bound with a standard register type (`t`, `u`, `b`, or `s`). |
| err_hlsl_unsupported_register_type_and_variable_type | "error: register binding type '%1' not supported for variable of type '%0'" | Emitted if a variable type is bound using an unsupported register type, like binding a float with the 'x' register type. |
| err_hlsl_mismatching_register_type_and_resource_type | "error: %select{SRV\|UAV\|CBV\|Sampler}2 type '%0' requires register type '%select{t\|u\|b\|s}2', but register type '%1' was used." | Emitted if a known resource type is bound using a standard but mismatching register type, e.g., RWBuffer<int> getting bound with 's'.|
| err_hlsl_unsupported_register_type_and_resource_type | "error: invalid register type '%0' used; expected 't', 'u', 'b', or 's'"| Emitted if an unsupported register prefix is used to bind a resource, like 'y' being used with RWBuffer<int>.|
| err_hlsl_conflicting_register_annotations | "error: conflicting register annotations| Emitted if two register annotations with the same register type but different register numbers are applied to the same declaration. |
| err_hlsl_register_annotation_on_member | "error: location annotations cannot be specified on members| Emitted if the register annotation is specified on a member of a UDT. |
| warn_hlsl_register_type_c_not_in_global_scope | "warning: register binding 'c' ignored inside cbuffer/tbuffer declarations; use pack_offset instead" | Emitted if a basic type is bound with `c` within a `cbuffer` or `tbuffer` scope |
| warn_hlsl_deprecated_register_type_b | "warning: deprecated legacy bool constant register binding 'b' used. 'b' is only used for constant buffer resource binding." | Emitted if the register prefix `b` is used on a variable type without the resource attribute, like a float type. |
| warn_hlsl_deprecated_register_type_i | "warning: deprecated legacy int constant register binding 'i' used." | Emitted if the register prefix `i` is used on a variable type without the resource attribute, like a float type. |
| warn_hlsl_UDT_missing_resource_type_member | "warning: variable of type '%0' bound to register type '%1' does not contain a matching '%select{SRV\|UAV\|CBV\|Sampler}2' resource" | Emitted if a UDT is lacking any eligible member to bind using a specific register type, like if a UDT `Foo` was bound with `s` but had no sampler members.|
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
Any resource declaration will have an associated ResourceAttr attribute,
on the `VarDecl`, from which we can determine the 
resource class, which is sufficient to determine the expected register
type. Any other valid register type (among 't', 'u', 'b', or 's') will 
result in `err_hlsl_mismatching_register_type_and_resource_type`.
The recommended register type will be suggested in the diagnostic.
Any other invalid register type will emit `err_hlsl_unsupported_register_type_and_resource_type`.
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
  float f;
  Buffer<float> Buf;
  }; 
Eg3 e3 : register(t0) : register(u0);
// Valid: Buf gets bound to t0. Buf will also be bound to u0.

struct Eg4 {
  struct Bar {
    RWBuffer<int> a;
    };
    Bar b;
};
Eg4 e4 : register(t0) 
// Valid: Bar, the struct within Eg4, has a valid resource that can be bound to t0. 

struct Eg5 {
  SamplerState s[3];
};

Eg5 e5 : register(s5);
// Valid: the first sampler state object within Eg5's s is bound to slot 5

struct Eg6 {
  float f;
}; 
Eg6 e6 : register(t0) 
// "warning: variable of type 'Eg6' bound to register type 't' does not contain a matching 'SRV' resource"

struct Eg7 {
  struct Bar {
      float f;
    }
    Bar b;
};
Eg7 e7 : register(t0) 
// "warning: variable of type 'Eg7' bound to register type 't' does not contain a matching 'SRV' resource"

struct Eg8 {
  RWBuffer<int> a;
}; 
Eg8 e8 : register(c0) 
// "warning: register 'c' used on type with no contents to allocate in a constant buffer"

struct Eg9{
  RWBuffer<int> a : register(u9);
};

Eg9 e9;
// error: location annotations cannot be specified on members

}

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
All other register types applied to such a type will emit `err_hlsl_unsupported_register_type_and_variable_type`, except for 'b' or 'i'.
If the register type is 'b' or 'i', then `warn_hlsl_deprecated_register_type_b` or `warn_hlsl_deprecated_register_type_i` 
will be emitted respectively, and treated as errors by default. The compiler will function as if `c` was passed.

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
under DiagnoseHLSLDecl in SemaHLSL.cpp. However, there is currently no infrastructure
that implements the register keyword as an unusual annotation. The method through which a
decl retains the information from a `register` annotation has yet to be designed, and is
out of scope for this spec. However, one approach is that in
clang\lib\Parse\ParseHLSL.cpp, under ParseHLSLAnnotations, an attribute will be constructed
that will be added to any decl which has the `register` keyword applied to it. Note that there 
are instances where multiple `register` statements can apply to a single decl, and this is 
only invalid if the register annotations have the same register types but different register
numbers. If this invalid case happens, `err_hlsl_conflicting_register_annotations`
will be emitted. 

Then, in SemaHLSL.cpp, there will be a location responsible for diagnosing each Decl in the 
translation unit, and for each Decl, if the attribute that is associated with the presence 
of the `register` annotation is detected, the two steps described below will be run.

### Analysis 

All the compiler has to work with is a Decl object and the context the decl appears in.
From this information, the first goal is to set some flags that can fully inform the 
compiler of the right diagnostic to emit. The first group of flags are the decl type flags,
which are either `basic`, `resource`, `udt`, or `other`. 
`basic` refers to a numeric variable type. `other` refers to built-in HLSL object types
(intangible types) that are not resources (e.g., `RayQuery`) and thus cannot be placed into
a cbuffer or bound as a resource. So, if `other` is set, an error will always be emitted.

These flags are all mutually exclusive, and are represented in the code with an enum.
The `udt` flag has an associated flag, `contains_numeric`, which will be set if the
UDT contains a numeric type.

The next group of flags are the resource class flags, which are `srv`, `uav`, `cbv`,
or `sampler`. For example, if an SRV resource is detected in the decl, then the 
`resource` flag is set and the associated resource class flag `srv` is set too. For
UDTs, the `udt` flag is set, and any resource class flags can be set if the associated
resource is found contained within the UDT.

The `default_globals` flag indicates whether or not the value ends up inside the 
`$Globals` constant buffer. It will not be set if the decl appears inside a cbuffer 
or tbuffer. The `$Globals` constant buffer will only be filled with non-HLSL-Objects.

The `is_member` flag is set if the decl is a member declaration of a struct or class.
This flag will inevitably lead to an error, because register annotations aren't allowed
on member declarations. `err_hlsl_register_annotation_on_member` will be emitted.

```
Flags:
  resource,
  udt,
  other,
  basic,

  srv,
  uav,
  cbv,
  sampler

  contains_numeric
  default_globals
  is_member

struct Foo {
  RWBuffer<int> rwbuf : register(u3); // is_member is set for this decl
};

RWBuffer<int> r0 : register(u0); // resource (uav is set)
Foo f0 : register(u0); // udt (Foo doesn't contain a numeric, so contains_numeric isn't set)
RayQuery<0> r1: register(t0); // other (error)
float f1 : register (c0); // basic (ends up in $Globals constant buffer, so default_globals is set)
```

The first step is to simply check if the decl is inside a cbuffer or tbuffer
block. If it isn't, and it has a numeric type, set the `default_globals` flag,
because the value is bound to be placed in the `$Globals` buffer. If the decl is
in a class or struct, it is a member declaration, and register annotations aren't
allowed here, so we must set the `is_member` flag.

Next, determine if the decl is a `cbuffer` or `tbuffer`. These are special in that they have
their own decl class type, `HLSLBufferDecl`. To determine if the Decl is a `HLSLBufferDecl`,
the compiler dynamically casts the Decl to an `HLSLBufferDecl`, and then if it succeeds,
checks isCBuffer(). If true, the Decl is a cbuffer, otherwise it is a tbuffer. In either case,
we know the decl is a `resource` and can infer the resource class (`cbv` or `srv`
respectively). Otherwise, if the dynamic cast fails, we cast to `VarDecl`, and check 
to see if the ResourceAttr attribute is present. If it is, the `resource` flag can be 
set, and the corresponding resource class flag will be set. If the `VarDecl` dynamic cast
fails, then there is some critical validation error, since any Decl with the register 
annotation should either be a `HLSLBufferDecl` or a `VarDecl`.

If the decl has no resource attribute, then check if the decl is a vector, matrix, 
or otherwise numeric type, and if so, we know that the decl is a `basic` type. 
If the decl isn't any of those types, then we check if it is a struct or class type.
If so, the decl is a UDT, so the `udt` flag is set. For a `udt`, recurse through the 
members of the UDT and its bases, collecting information on what types of resources 
are contained by the UDT,setting corresponding class flags (`uav`, `cbv`, `srv`, or 
`sampler`). Also track whether there are any other numeric members and set the 
`contains_numeric` flag. If the decl is not a UDT, then the `other` flag is set.

Below is some pseudocode to describe the flag-setting process:

```
if the Decl is inside a cbuffer or tbuffer:
  do not set default_globals  
else if the Decl type is a numeric type:
  set default_globals

if the Decl is an HLSLBufferDecl
  if cbuffer: set resource, set cbv
  else:  set resource, set srv
else if the Decl is a VarDecl:
  if no resource attribute: 
    if Decl is vector, matrix, or otherwise numeric type:
      set basic flag
    else if Decl is struct or class type (if it is a udt):
      set udt flag
      recurse through members, set resource class flags that are found
      set contains_numeric if the UDT contains a numeric member
    else:
      set other flag
  else:
    get resource attribute, set resource and corresponding resource class flag
else:
  raise error: (unknown decl type)
```


### Diagnostic emisison

Now enough information has been gathered to determine the right diagnostics to emit, if any.
The compiler will run diagnostics by iterating over all Decl objects with a register annotation.
Firstly, if `other` is set, then the variable type is not valid for the given register type.
So, we can emit `err_hlsl_unsupported_register_type_and_variable_type`.
Next, check if `is_member` is set. If so, the register annotation was applied to a member, 
which is not allowed, so `err_hlsl_register_annotation_on_member` is emitted. 
Next, some decls may have multiple register annotations applied. Regardless of the decl type,
there will be validation that any pair of annotation statements may not have the same register
type but different register number. If this is detected, `err_hlsl_conflicting_register_annotations`
will be emitted.

If the `resource` flag is set, check the register type against the resource class flag.
If they do not match, `err_hlsl_mismatching_register_type_and_resource_type` is emitted.
If the `basic` flag is set, then we first check if `default_globals` is set. If so, then 
we check the register type. If the register type is 'b' or 'i', then
`warn_hlsl_deprecated_register_type_b` or `warn_hlsl_deprecated_register_type_i` 
will be emitted respectively, and treated as errors by default. If the errors are silenced,
the compiler will function as if `c` was passed, and allocate the variables into the 
global constant buffer.
If the register type is 'c', it is allowed, but if `default_globals` is not set,
`warn_hlsl_register_type_c_not_in_global_scope` will be emitted, 
and will be treated as an error by default.

After this point, `default_globals` doesn't need to be set.
If 't', 'u', or 's' are given when `basic` is set, then
`err_hlsl_mismatching_register_type_and_variable_type` will be emitted.
If any other register type is seen, `err_hlsl_unsupported_register_type_and_variable_type`
will be emitted instead.

Finally, in the case that `udt` is set, we may have multiple register annotations
applied to the decl. For every register type that is used to bind the resources contained 
in the given UDT, we verify that the corresponding resource class flag has been set. These
are the register types `t`, `u`, `b`, and `s`. If the corresponding resource class flag is 
not set, `warn_hlsl_UDT_missing_resource_type_member` will be emitted.
If `c` is given, then we must check that `contains_numeric` is set, and if not, 
`warn_hlsl_UDT_missing_basic_type` is emitted.
Otherwise, if any other register type is given, 
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
user can pass the `--Wno-disallow-legacy-binding-rules` flag to the compiler to silence the
errors, leaving just the warnings. For the two UDT warnings above, the warnings will be 
silenced so that no diagnostics will be emitted. 


Here is some pseudocode summarizing the diagnostic emission process:

```
if other is set:
  emit err_hlsl_unsupported_register_type_and_variable_type

if is_member is set:
  emit err_hlsl_register_annotation_on_member

if multiple register annotations exist:
  if any pair of register annotations share the same register type but different register number:
    emit err_hlsl_conflicting_register_annotations

if resource is set:
  if register type does not match resource class flag:
    emit err_hlsl_mismatching_register_type_and_resource_type

if basic is set:
  if default_globals is set:
    if register type is 'b' or 'i':
      emit warn_hlsl_deprecated_register_type_b or warn_hlsl_deprecated_register_type_i respectively

  if register type is 'c'
    if default_globals is not set:
      emit warn_hlsl_register_type_c_not_in_global_scope
  else if register type is 't' 'u' or 's':
    emit err_hlsl_mismatching_register_type_and_variable_type
  else: emit err_hlsl_unsupported_register_type_and_variable_type

if udt is set:
  for each register annotation r applied to the udt decl:
    if r has register type t:
      if srv is not set:
        emit warn_hlsl_UDT_missing_resource_type_member
    else if r has register type u:
      if uav is not set:
        emit warn_hlsl_UDT_missing_resource_type_member
    else if r has register type b:
      if cbv is not set:
        emit warn_hlsl_UDT_missing_resource_type_member
    else if r has register type s:
      if sampler is not set:
        emit warn_hlsl_UDT_missing_resource_type_member
    else if r has register type c:
      if contains_numeric is not set:
        emit warn_hlsl_UDT_missing_basic_type
    else
      emit err_hlsl_unsupported_register_type_and_variable_type  
```

## Alternatives considered (Optional)

## Acknowledgments (Optional)
* Tex Riddell
* Chris Bieneman
* Justin Bogner
* Damyan Pepper
<!-- {% endraw %} -->