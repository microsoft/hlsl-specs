* Proposal: [0002](0023-binding-prefixes.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Impacted Project(s): (LLVM)

*During the review process, add the following fields as needed:*

* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues: [#57886](https://github.com/llvm/llvm-project/issues/57886)

## Introduction

There's a specific set of valid types that can be bound as a resource in HLSL.
When invalid types are bound to resources, helpful diagnostics need to be emitted
so that the user knows why the bound type is invalid, or why the binding prefix
isn't correct.

## Motivation

There are currently several cases in which diagnostics that are related to
binding prefixes are out of date or invalid. For example, in the case of:

`float b : register(u4);`
an error will be emitted recommending the use of the 'b, c, or i' binding
prefix, however these prefixes are no longer in support. Additionally,
it is possible the user is unaware that this resource won't actually be
used, but the compiler doesn't communicate that to the user.
It would be great for any HLSL developer to immedaitely have answers to 
the following questions:
For any valid resource type that needs to be bound, what are the set of
valid binding prefixes for that resource, and what are all the possible 
diagnostics that can be emitted if the resource is given a binding 
prefix that isn't in the set of valid binding prefixes?
The design below aims to specify the answer to these questions.

## Proposed solution
Firstly, the most common case is when a resource type that is not a 
user-defined type is bound as a resource. Any resource will have an 
associated ResourceAttr attribute, from which we can determine the 
resource class and resource kind. These two inputs are sufficient to
determine the expected binding prefix, and any other binding prefix
will result in an error. The recommended binding prefix will be
suggested in the diagnostic. The table below specifies what binding 
prefix will be expected for any resource type that falls under the
specified resource class. 

| Resource Class | Binding Prefix | Diagnostic |
|-|-|-|
| Sampler | s | "Object type '%0' with resource class "Sampler" expects binding prefix 's', but binding prefix '%1' was given. |
| SRV | t | "Object type '%0' with resource class "SRV" expects binding prefix 't', but binding prefix '%1' was given. |
| UAV | u | "Object type '%0' with resource class "UAV" expects binding prefix 'u', but binding prefix '%1' was given. |
| CBuffer | b |  "Object type '%0' with resource class "CBuffer" expects binding prefix 'b', but binding prefix '%1' was given. |

There are certain resource kinds within the SRV resource
class that are "sampleable". These resources are typically
prefixed with "Texture" in actual HLSL source. So, there will
be a special check to see whether the candidate resource is 
prefixed with "Texture", and if so, the "s" binding prefix will
also be permitted for that resource.

If the given candidate resource is a user-defined type (UDT), then further
analysis is necessary. The first step is to gather all registers that
are being bound to this declaration, and collect the binding prefixes
that are being specified. The UDT must have at least one valid resource
that can be bound to the provided binding prefix. If not, an error must be
emitted stating that "No resource contained in struct '%0' can be bound
to binding prefix '%1'". There are no issues if a UDT has more resources
than there are register binding statements, the resources will be bound to
the next available space automatically, and so compilation can succeed.
Additionally, a singular resource can be bound multiple times to different
spaces, so multiple binding prefixes are allowed for a single resource.
Below is a table that represents the different behaviors that could arise
given some examples of different UDT's:

| UDT | Binding statements | Diagnostic |
|-|-|-|
| struct Foo {
  float f;
  Buffer<float> Buf;
  RWBuffer<float> RWBuf;
}; | register(t0) : register(s0); | None. Success because Buf gets bound to t0 and RWBuf gets bound to s0, and f is skipped. |
| struct Foo {
  float f;
  Buffer<float> Buf;
  RWBuffer<float> RWBuf;
  RWBuffer<float> RWBuf2;
}; | register(t0) : register(s0); | None. Success because Buf gets bound to t0 and RWBuf gets bound to s0, and f is skipped. RWBuf2 gets assigned to s1 even though there is no explicit binding for s1. |
| struct Foo {
  float f;
  Buffer<float> Buf;
}; | register(t0) : register(s0); | None. Success because Buf gets bound to t0. Buf will also be bound to s0.|
|struct Foo {
  struct Bar {
    RWBuffer<int> a;
    };
    Bar b;
}; | register(t0) | None. Success because Bar, the struct within Foo, has a valid resource that can be bound to t0. |
| struct Foo {
  float f;
}; | register(t0) | DefaultError warning. "UDT resource does not contain an applicable resource type for binding prefix 't'"|
| struct Foo {
    struct Bar {
      float f;
    }
    Bar b;
}; | register(t0) | DefaultError warning. "UDT resource does not contain an applicable resource type for binding prefix 't'"|

Finally, if the candidate type is not a valid resource type or not a
UDT, the final case will be entered. If the resource is among any
numeric or non-intangible types, there is only one exception where it can
be treated as a resource. That is, for all non-intangible types, types
that obviously are not, or cannot contain, a valid resource type (types 
like int, float, float4, etc), the only valid binding prefix is 'b', which
adheres to legacy behavior. All other binding prefixes applied to such
a type will emit an error diagnostic that "the given type '%0' cannot be
bound as a resource". If the binding prefix is 'b', a warning will be 
emitted instead, that will be treated as an error by default:
"binding prefix 'b' used for resource type '%0' which cannot be used
as a resource". Below are some examples:

| non-intangible type | Binding statements | Diagnostic |
|-|-|
| float f | register(t0) | "error: the given type 'float' cannot be bound as a resource." |
| float f | register(b0) | "warning: binding prefix 'b' used for resource type 'float' which cannot be used as a resource" |



## Detailed design

All the compiler has to work with is a Decl object. From the Decl object, 
the ResourceAttr attribute can be fetched, with which the resource 
class can be determined. Once this is known, we then check if the resource
type is a user-defined type or if it is a standard resource type. If the 
resource type is among the standard resource types (e.g., cbuffer, tbuffer,
RWBuffer, etc.), then the binding prefix is checked for validity. The resource
is also checked for sampleability (i.e., is it a texture resource?). If there is
an incompatibility between resource class and binding prefix, a diagnostic will
be emitted. Otherwise, the resource is a user-defined type, and so the type needs
to be validated to see whether it can properly be assigned to the geiven binding 
prefix. If the UDT does not have at least one resource that matches the given binding 
prefixes, then an error will be emitted. The only remaining case is when there
is no resource attribute, which implies the type is non-intangible. In this case,
if the type is strictly numeric, the only acceptable binding prefix is 'b'. In 
this case, a warning will be emitted that will be treated as an error by default,
which states that a numeric type is not usable as a resource. Any other binding
prefix will cause an error to be emitted, stating that the given type cannot be 
bound as a resource.

## Alternatives considered (Optional)

## Acknowledgments (Optional)
* Tex Riddell
<!-- {% endraw %} -->