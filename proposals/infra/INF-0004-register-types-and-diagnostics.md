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
type. However the 'b' and 'i' register types are no longer in support. It
is worth noting that there is an overloading of the register(...) keyword
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
| err_hlsl_mismatching_register_type_and_variable_type | "error: unsupported resource register binding '%select{t|u|b|s}1' on variable of type '%0'"|  |
| err_hlsl_unsupported_register_prefix | "error: invalid resource class specifier '%0' used; expected 't', 'u', 'b', or 's'"| |
| warn_hlsl_register_type_c_not_in_global_scope | "warning: register binding 'c' ignored inside cbuffer/tbuffer declarations; use pack_offset instead" | This is emitted when a basic type is bound with `c` within a `cbuffer` or `tbuffer` scope |
| warn_hlsl_deprecated_register_type_b | "warning: deprecated legacy bool constant register binding 'b' used. 'b' is only used for constant buffer resource binding." | |
| warn_hlsl_deprecated_register_type_i | "warning: deprecated legacy int constant register binding 'i' used." | |
| err_hlsl_mismatching_register_type_and_resource_type | "error: %select{SRV|UAV|CBV|Sampler}2 type '%0' requires register type '%select{t|u|b|s}2', but register type '%1' was used." | |
| err_hlsl_mismatching_unsupported_register_type_and_variable_type | "error: register binding type '%1' not supported for variable of type '%0'" | |
| err_hlsl_UDT_missing_resource_member | "error: variable of type '%0' bound to register type '%1' does not contain a matching '%select{SRV|UAV|CBV|Sampler}2' resource" | |

The most common case is when a resource type that is not a 
user-defined type is bound as a resource. Any resource will have an 
associated ResourceAttr attribute, from which we can determine the 
resource class, which is sufficient to determine the expected register
type. Any other register type will result in `err_hlsl_mismatching_register_type_and_variable_type`.
The recommended register type will be suggested in the diagnostic. 
The table below specifies what register type will be expected for 
any resource type that falls under the specified resource class. 
The diagnostic that will be emitted for incorrect register types is
`err_hlsl_mismatching_register_type_and_resource_type`

| Resource Class | Register Type | Diagnostic |
|-|-|
| Sampler | s |
| SRV | t |
| UAV | u |
| CBuffer | b |

If the given candidate variable is a user-defined type (UDT), then further
analysis is necessary. The first step is to gather all register declarations
that are being applied to this variable declaration, and collect the register types
that are being specified. The UDT must contain at least one valid resource
that can be bound to the provided register type(s). If not, a warning will be
emitted stating that "No resource contained in struct '%0' can be bound to register 
type '%1'". The warning will be treated as an error by default, and can be disabled
with Disable with --Wno-disallow-unused-register-bindings. There are no issues if a UDT 
contains more resources than there are register binding statements, the resources 
will be bound to the next available space automatically, and so compilation can 
succeed. It should also be noted that the 'c' register type can be used on UDT 
members as well, which would function to specify the constant offset for the 
numeric member(s) of the structure. Below are some examples of different UDT's
and the diagnostics that would be emitted when applying resource bindings to the 
variable:

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
// Valid: f is skipped, Buf is bound to t0, RWBuf is bound to u0. RWBuf2 gets automatically assigned to u1 even though there is no explicit binding for u1.

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
// DefaultError warning: "No resource contained in struct 'Eg6' can be bound to register type 't'"

struct Eg7 {
  struct Bar {
      float f;
    }
    Bar b;
};
Eg7 e7 : register(t0) 
// DefaultError warning: "No resource contained in struct 'Eg7' can be bound to register type 't'"

```

Finally, if the candidate type is not a valid resource type and not a UDT, the
final case will be entered. Types that are or contain a resource are known as
"intangible". In this case, we are dealing with types that cannot be intangible.
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
`warn_hlsl_basic_type_not_bound_in_global_scope` will be emitted, and will be treated as an error by default.
All other register types applied to such a type will emit `err_hlsl_unsupported_register_prefix"`, except for 'b' or 'i'.
If the register type is 'b' or 'i', a warning will be emitted instead, that will be 
treated as an error by default. 

Below are some examples:

| Code | Diagnostic |
|-|-|
| `float f : register(t0)` | "error: unsupported resource register binding 't' on variable of type 'float'" |
| `float f : register(c0)` | Valid, no errors
| `float f : register(b0)` | "warning: deprecated legacy bool constant register binding 'b' used. 'b' is only used for constant buffer resource binding." |
| `float f : register(i0)` | "warning: deprecated legacy int constant register binding 'i' used. Disable with --Wno-disallow-unused-register-bindings" |
| `float f : register(x0)` | "error: invalid resource class specifier 'x' used; expected 't', 'u', 'b', or 's'" |
| `cbuffer g_cbuffer { float f : register(c2); }` | "warning: register binding 'c' should only be used in global contexts. Disable with --Wno-disallow-unused-register-bindings" |
| `struct Foo { RWBuffer<float> f; }; Foo foo : register(c2);`| "warning: 'c' register type should only be used for basic types. Disable with --Wno-disallow-unused-register-bindings" |
| `RWBuffer<float> f : register(c3);`| "error: UAV type 'RWBuffer<float>' requires register type 'u', but register type 'c' was used." |


## Detailed design

All the compiler has to work with is a Decl object and the context the decl appears in.
From this information, the first goal is to set a specific set of flags that can fully inform
the right diagnostic to emit. The first group of flags are the decl type flags, which
are either `basic`, `resource`, `udt`, or `other`. `basic` refers to a numeric variable
type. `other` refers to a type that cannot possibly be resource, because it lacks the 
resource attribute.

The next group of flags are the resource class flags,
which are `srv`, `uav`, `cbv`, or `sampler`.

The final flag is `default_globals`, which indicates whether or not the decl appears
inside the $Globals scope.

From the Decl object, first determine if the decl is a cbuffer or tbuffer decl. If so,
we know the decl is a `resource` and can infer the resource class (`cbv` or `srv`
respectively). Otherwise, the decl is classified according to the underlying canonical 
type.

If the decl is implicit, then check if the decl is a vector, matrix, or otherwise numeric type,
and if so, we know that the decl is a `basic` type. If the decl isn't any of those types, then 
check if the decl has a resource attribute. If so, we can set the `resource` flag, and can also 
obtain the resource class and set the resource class flag accordingly. Otherwise, we know the
decl is not a resource and not basic, and so the `other` flag is set.

If the decl type is not implicit, then we check if it is a struct or class type.
If so, the decl is a UDT, so the `udt` flag is set, otherwise, it's a basic type,
so we set the `basic` flag. For a `udt`, recurse through the members of the UDT and 
its bases, collecting information on what types of resources are contained by the UDT,
setting corresponding class flags (`uav`, `cbv`, `srv`, or `sampler`). Also track 
whether there are any other numeric members and set a `contains_numeric` flag.

The last step is to simply check if the global decl is inside a cbuffer or tbuffer
block. If not, set the `default_globals` flag.

Now enough information has been gathered to determine the right diagnostics to emit, if any.
Firstly, if `other` is set, then the variable type is not valid for the given register type.
So, we can emit `err_hlsl_mismatching_unsupported_register_type_and_variable_type`
If the `resource` flag is set, check the register type against the resource class flag.
If they do not match, `err_hlsl_mismatching_register_type_and_resource_type` is emitted.
If the `basic` flag is set, then we first check if `default_globals` is set. If so, then 
we check the register type. If the register type is 'i' or 'b', then `warn_hlsl_deprecated_register_type_i`
or `warn_hlsl_deprecated_register_type_b` will be emitted respectively, and treated as errors by default.
If the register type is 'c', it is allowed, but if `default_globals` is not set,
`warn_hlsl_register_type_c_not_in_global_scope` will be emitted, and will be treated as an error by default.
This warning is part of the warning group `disallow-legacy-binding-rules`.

After this point, `default_globals` doesn't need to be set.
If 't', 'u', or 's' are given, then this `err_hlsl_mismatching_register_type_and_variable_type` will be emitted.
If any other register type is seen, `err_hlsl_mismatching_unsupported_register_type_and_variable_type`
will be emitted instead.

Finally, in the case that `udt` is set, we first check `default_globals`. If it is set,
then we can permit the 'c' register type if `contains_numeric` is set. If it is not set,
a warning that is treated as an error by default will be emitted: 
`warning: register 'c' used on type with no contents to allocate in a constant buffer`
Otherwise, cbuffers and tbuffers are not permitted within UDT's, and so we don't need to
check if 'c' is given within the UDT nor emit a warning for legacy behavior that is 
treated as an error. An error will already be emitted preventing the declaration of 
these buffers within a UDT. After this point, `default_globals` doesn't need to be set.
For every register type that is used to bind the resources contained in the given UDT, 
we verify that the corresponding resource class flag has been set. If the
corresponding resource class flag is not set, `err_hlsl_UDT_missing_resource_member` will be emitted.
Otherwise, if any other register type is given, then we emit `err_hlsl_unsupported_register_prefix`

Legacy behavior can be allowed with the --Wno-disallow-unused-register-bindings
flag. When this flag is active, and legacy behavior is present, a warning will 
be emitted instead of an error.


## Alternatives considered (Optional)

## Acknowledgments (Optional)
* Tex Riddell
* Chris Bieneman
* Justin Bogner
* Damyan Pepper
<!-- {% endraw %} -->