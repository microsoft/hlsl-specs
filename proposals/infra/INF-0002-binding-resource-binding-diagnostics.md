* Proposal: [0023](0023-binding-prefixes.md)
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
It would be great for any HLSL developer to immedaitely have access to 
the following questions:
For any valid resource type that needs to be bound, what are the set of
valid binding prefixes for that resource, and what are all the possible 
diagnostics that can be emitted if the resource is given a binding 
prefix that isn't in the set of valid binding prefixes?
The design below aims to specify the answer to these questions.

## Proposed solution

| Resource Class | Resource Kind | Binding Prefix | Diagnostic |
|-|-|-|-|
| SRV, Sampler | "Texture1D" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "Texture2D" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "Texture2DMS" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "Texture3D" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "TextureCube" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "Texture1DArray" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "Texture2DArray" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "Texture2DMSArray" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV, Sampler | "TextureCubeArray" | t, s | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV | "TypedBuffer" | u | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. (e.g. RWBuffer) |
| SRV | "RTAccelerationStructure" | ? | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| SRV | "FeedbackTexture2D" | u | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. SAMPLER_FEEDBACK_MIN_MIP was used as a template argument.|
| SRV | "FeedbackTexture2DArray" | u | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. SAMPLER_FEEDBACK_MIN_MIP was used as a template argument.|
| UAV | "RawBuffer" | u | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. (e.g. RWByteAddressBuffer outbuf) |
| UAV | "StructuredBuffer" | t | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. |
| UAV | "TBuffer" | t | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. (e.g. tbuffer tbuf) |
| CBuffer | "CBuffer" | b | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. (e.g. cbuffer cbuf)|
| Sampler | "Sampler" | t | If the binding prefix doesn't match, emit an error that the expected binding prefix is expected. (e.g. sampler) |
| None | non-intangible types | any | Any non-intangible type will emit a warning declaring that it cannot be used as a resource. The warning will be treated as an error by default, but a compiler option may be used to treat it as just a warning. |
| None | unions| any | Unions will emit a warning declaring that it cannot be used as a resource. The warning will be treated as an error by default, but a compiler option may be used to treat it as just a warning. |
| None | bitfields | any | Bitfields will emit a warning declaring that it cannot be used as a resource. The warning will be treated as an error by default, but a compiler option may be used to treat it as just a warning. |

## Detailed design

All the compiler has to work with is a Decl object. From the Decl object, 
the ResourceAttr attribute can be fetched, with which the resource kind and 
resource class can be determined. Once these are known, the binding prefix is
checked for validity. If there is an incompatibility, a diagnostic will be
emitted. In the case that there is no resource attribute, futher analysis is
required. The compiler will run some analysis on the given type to see whether
or not it is among the prohibited types. If the type is non-intangible, a union,
or a bitfield, an error will be emitted. Otherwise, the type will be assumed
to be an aggregate type, a UDT. The UDT will be analyzed to determine whether
any valid resource objects exist within. If none exist, then an error will be 
emitted. Otherwise, the compiler will bind the first resource that is found
within the struct.

## Alternatives considered (Optional)

## Acknowledgments (Optional)
* Tex Riddell
<!-- {% endraw %} -->