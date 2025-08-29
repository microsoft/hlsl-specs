---
title: 0034 - Vulkan Sampled Textures
params:
  authors:
  - cassiebeckley: Cassandra Beckley
  status: Under Review
---



 
* Required Version: HLSL 2021
<!--
* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues:
  [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/issues/NNNN)
-->

## Introduction

We propose a new set of `vk::SampledTexture*` texture types representing
Vulkan's combined image sampler types (`OpTypeSampledImage`).

## Motivation

The [existing annotation](https://github.com/microsoft/DirectXShaderCompiler/wiki/Vulkan-combined-image-sampler-type)
for combined image samplers (`[[vk::combinedImageSampler]]`) was designed with
the explicit goal of avoiding defining new HLSL types and functions. This was
intended to minimize the number of changes to the frontend needed to implement
the feature. However, it is verbose, confusing for users, and requires a
backend pass to pair up textures and samplers which is prone to subtle errors.
We do not intend to implement it in upstream Clang.

## High-level description

The `vk::SampledTexture*` types will have the same interface and methods as the
existing `Texture*` types, with the exception that the methods will not take a
sampler state argument.

Consider this example pixel shader which uses a texture:

```hlsl
Texture2D tex0 : register(t0);
SamplerState s : register(s0);

float4 main(float2 uv: TEXCOORD) : SV_Target {
  return tex0.Sample(s, uv);
}
```

Using the proposed types, this could be rewritten to use a combined image
sampler:

```hlsl
vk::SampledTexture2D tex0 : register(t0);

float4 main(float2 uv: TEXCOORD) : SV_Target {
  return tex0.Sample(uv);
}
```

This is simpler and a more accurate representation of the underlying interface
than using the existing annotation, which looks like:

```hlsl
[[vk::combinedImageSampler]]
Texture2D tex0 : register(t0);
[[vk::combinedImageSampler]]
SamplerState s : register(s0);

float4 main(float2 uv: TEXCOORD) : SV_Target {
  return tex0.Sample(s, uv);
}
```

A benefit of the `[[vk::combinedImageSampler]]` annotation is the ability to
use the same code to represent a combined image sampler in Vulkan and a
separate texture and sampler in DirectX. The new types will only be usable with
Vulkan, but a similar effect can be produced by checking for the existence of
the `__spirv__` macro.

## Detailed design

### HLSL Additions

The following resource types will be added to the `vk` namespace:

| HLSL Object               | Type Parameters                   |
|---------------------------|-----------------------------------|
| `SampledTexture1D`        | _type_                            |
| `SampledTexture1DArray`   | _type_                            |
| `SampledTexture2D`        | _type_                            |
| `SampledTexture2DArray`   | _type_                            |
| `SampledTexture2DMS`      | _type_, uint _samples_            |
| `SampledTexture2DMSArray` | _type_, uint _samples_            |
| `SampledTexture3D`        | _type_                            |
| `SampledTextureCUBE`      | _type_                            |
| `SampledTextureCUBEArray` | _type_                            |

As with the `Texture*` types, the _type_ parameter may be omitted, in which
it will default to `float4`. Values of these types may be assigned to specific
registers or annotated with the Vulkan binding annotations.

The following builtin methods will be defined for these types:

* `CalculateLevelOfDetail`
* `CalculateLevelOfDetailUnclamped`
* `Gather`
* `GetDimensions`
* `GetSamplePosition`
* `Load`
* `Sample`
* `SampleBias`
* `SampleCmp`
* `SampleCmpLevelZero`
* `SampleGrad`
* `SampleLevel`

They will have the same interface as the corresponding methods for the
`Texture*` types, with the exception that they will not take a `SamplerState`
or `SamplerComparisonState` argument. (SPIR-V does not have separate sampler
types for comparison operations, and the combined sampler will be sufficient
for all methods listed).

`[[vk::combinedImageSampler]]` will be marked as deprecated in HLSL 2021, and
removed in HLSL 202x.

A new feature check `__has_feature(hlsl_vk_sampled_texture)` will be added to
the preprocessor.

### Interchange Format Additions

This proposal exists to better represent an existing feature of SPIR-V, and no
changes to the specification will be required. Since this is a Vulkan-specific
feature scoped to the `vk` namescape, no changes to the DXIL format or DXIL
lowering will be required.

The `vk::SampledTexture*` types will be lowered to SPIR-V `OpTypeSampledImage`
type declarations, with an _Image Type_ operand which will be the `OpTypeImage`
produced by lowering the equivalent `Texture*` type.

The builtin methods will be lowered to the same instructions as the equivalent
methods for `Texture*` types. SPIR-V instructions which operate on images take
these images in one of two formats: either an `OpTypeImage`, for instructions
which do not require a sampler, or an `OpTypeSampledImage`, for instructions
which do. For instructions which require an `OpTypeImage`, we can obtain such
a value by passing the `OpTypeSampledImage` value to the `OpImage` instruction.

We will likely represent these types in LLVM IR for upstream Clang by the
addition of a new "sampled" attribute for the resource type.

### Diagnostic Changes

The `vk::SampledTexture*` types and builtin methods should provide the same
diagnostics as the corresponding `Texture*` types.

#### Validation Changes

No additional changes to the SPIR-V validator will be required.

### Runtime Additions

No runtime additions or information are required.

#### Device Capability

`OpTypeSampledImage` is a core feature of SPIR-V, and part of Vulkan since 1.0.
It should be supported by all existing Vulkan hardware. No changes to either
drivers or hardware will be needed.

## Testing

The existing tests for the SPIR-V lowering of `Texture*` types can be expanded
to ensure that `vk::SampledTexture` types exhibit the same behavior, in all
cases.

## Alternatives considered

We considered using a `vk::Sampled` template that would take a texture as a
template parameter. For example, `vk::Sampled<Texture2D> >`. We decided against
this as it would require additional validation that the template parameter is a
texture type, and because HLSL has an existing convention for resource types to
have additional behavior by prepending information to the type name – for
example, `Buffer` to `RWBuffer` and `RWStructuredBuffer`.

We also considered using inline SPIR-V for implementation; however, doing so
would require the ability to assign an HLSL-defined class an HLSL register
and/or Vulkan location binding, and then use that register for a member
variable of the class holding the low-level inline SPIR-V representation. We
decided that such a mechanism would be too general, as new resource types in
HLSL are rare and users should not have the ability to create them themselves.


