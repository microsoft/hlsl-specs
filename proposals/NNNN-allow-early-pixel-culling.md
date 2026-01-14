---
title: "NNNN - Allow Early Pixel Culling"
draft: true
params:
  authors:
    - mapodaca-nv: Mike Apodaca
  sponsors:
    - amarpMSFT: Amar Patel
  status: Under Consideration
---

## Introduction

This proposal introduces a new `[allowearlypixelculling]` attribute for HLSL
Pixel Shaders that enables implementations to perform early pixel culling
optimizations for shaders with side effects. Unlike the existing
`[earlydepthstencil]` attribute which provides deterministic early
depth/stencil testing, this new attribute allows non-deterministic culling
where occluded pixels may be skipped before shader execution. This is
particularly useful for shaders that use UAV writes or sampler feedback with
features like `discard`, `SV_Depth`, or coverage modification that prevent use
of `[earlydepthstencil]`. The attribute affects HLSL compilation, DXIL
encoding, and SPIR-V generation, enabling hardware-specific optimizations at
the compiler and driver level.

## Motivation

Current HLSL implementations can perform early depth/stencil culling
optimizations to skip Pixel Shader invocations for occluded pixels. However,
when a Pixel Shader declares UAV access or sampler feedback operations, these
optimizations must be disabled to maintain deterministic behavior. This is
because the specification requires predictable control over Pixel Shader
invocation counts when external effects are present. The existing
`[earlydepthstencil]` attribute provides deterministic early testing but
cannot be used with shaders that modify depth, use `discard`, or modify
coverage.

Many real-world rendering scenarios do not require deterministic UAV write
counts from occluded pixels. Virtual texture feedback systems only need to
know which texture tiles are visible, not how many occluded fragments
reference them. Sampler feedback streaming systems benefit from knowing which
mip levels are needed for visible surfaces, but occluded geometry loading
textures wastes bandwidth. Alpha-tested foliage rendering with UAV-based
effects could benefit from culling without requiring expensive depth pre-passes.

Without a mechanism to express that non-deterministic culling is acceptable,
developers must choose between suboptimal performance (all occluded pixels
execute) or complex workarounds like multiple shader variants or manual depth
pre-passes. A shader-level annotation allows the compiler and driver to enable
early culling optimizations where appropriate while maintaining backwards
compatibility for shaders requiring deterministic behavior.

## Proposed solution

This proposal adds a new `[allowearlypixelculling]` attribute for HLSL Pixel
Shaders. When applied, implementations may perform early pixel culling
optimizations that skip shader execution for some occluded pixels, even when
the shader has side effects like UAV writes. The exact number and selection of
culled pixels is implementation-dependent, and applications opt into this
non-determinism explicitly.

The attribute enables use of shader features incompatible with
`[earlydepthstencil]`, including `discard`, `SV_Depth`, `SV_DepthGreaterEqual`,
`SV_DepthLessEqual`, `SV_Coverage`, and `SV_StencilRef`. However, these two
attributes are mutually exclusive and cannot be combined on the same shader.

### Feature Compatibility

The following table shows which Pixel Shader features are compatible with each
early optimization attribute:

| Feature | `[earlydepthstencil]` | `[allowearlypixelculling]` |
|:---|:--:|:--:|
| `discard` | ✗ | ✓ |
| `SV_DepthGreaterEqual` | ✗ | ✓ |
| `SV_DepthLessEqual` | ✗ | ✓ |
| `SV_Depth` | ✗ | ✓ |
| `SV_Coverage` (output) | ✗ | ✓ |
| `SV_StencilRef` | ✗ | ✓ |
| UAV Writes | ✓ (Deterministic) | ✓ (Non-Deterministic) |
| SamplerFeedback Writes | ✓ (Deterministic) | ✓ (Non-Deterministic) |

> **Developer's note**: When `[allowearlypixelculling]` is used,
> implementations may perform early culling to skip some occluded pixels before
> shader execution. Depth/stencil writes occur based on the final shader
> outputs after the shader completes. For pixels that execute, if the shader
> discards the pixel, no depth/stencil write occurs; if the shader does not
> discard, depth/stencil testing and writes proceed normally. The only
> difference from the default mode is that some occluded pixels may be culled
> early and never execute the shader, which means their UAV/SamplerFeedback
> writes will not occur.

> **Developer's note**: Conservative depth outputs
> (`SV_DepthGreaterEqual`/`SV_DepthLessEqual`) enable more effective early
> culling because they provide depth bounds guarantees that allow more
> aggressive optimization. Shaders that output `SV_Depth` are unlikely to
> benefit from early culling optimizations, but the attribute is still allowed.

### Example Usage

The following example demonstrates a Pixel Shader that uses `discard` for
alpha testing and writes to both UAVs and sampler feedback. This shader must
run in late depth mode due to the `discard`, but implementations may perform
early culling, meaning some occluded pixels may not execute:

```hlsl
RWTexture2D<float4> UAV0 : register(u0);
RWStructuredBuffer<uint> UAV1 : register(u1);

Texture2D<float4> TEX0 : register(t0);
SamplerState SMP0 : register(s0);
FeedbackTexture2D<SAMPLER_FEEDBACK_MIP_REGION_USED> FB0 : register(u2);

struct PSInput
{
    uint2 xy : COORD;
};

[allowearlypixelculling]
float4 PSMain(in PSInput input) : SV_Target
{
    float4 value = UAV0.Load(input.xy);

    // Discard pixels based on loaded value
    if (value.x < 0.0 || value.y < 0.0)
        discard;
    
    // UAV writes may be skipped for occluded pixels due to early culling
    InterlockedAdd(UAV1[0], (uint)(value.x * value.y));

    // Sampler feedback writes may be skipped for occluded pixels
    FB0.WriteSamplerFeedback(TEX0, SMP0, value.xy);

    return saturate(value);
}
```

## Detailed design

### HLSL Additions

A new attribute `[allowearlypixelculling]` is added to HLSL for Pixel Shader
entry points. The attribute has no parameters.

#### Syntax

```hlsl
[allowearlypixelculling]
ReturnType EntryPointName(Parameters) : SemanticList
{
    // Pixel Shader body
}
```

#### Semantic Rules

* The attribute is valid only on Pixel Shader entry points
* The attribute is mutually exclusive with `[earlydepthstencil]`
* When present, the shader may use any combination of:
  * `discard` statement
  * `SV_Depth` output
  * `SV_DepthGreaterEqual` output
  * `SV_DepthLessEqual` output
  * `SV_Coverage` output
  * `SV_StencilRef` output
  * UAV reads and writes
  * Sampler feedback operations
* The attribute requires Shader Model 6.X or later

#### Compilation Errors

The compiler shall issue an error if:

* The attribute is applied to a non-Pixel Shader entry point
* The attribute is combined with `[earlydepthstencil]` on the same entry point
* The attribute is used with a Shader Model earlier than 6.X

#### Non-Determinism Model

The presence of `[allowearlypixelculling]` relaxes the determinism guarantee
for Pixel Shader invocations. Implementations may skip execution for an
unspecified subset of occluded pixels, from none to all. The exact selection
is implementation-dependent and may vary between runs, hardware, or driver
versions.

For pixels that do execute:

* Depth/stencil testing occurs based on final shader outputs
* If the shader discards the pixel, no depth/stencil write occurs
* If the shader does not discard, depth/stencil testing and writes proceed
  normally
* All shader outputs and side effects occur as specified

For pixels that are culled early:

* The shader does not execute
* No UAV writes or sampler feedback operations occur
* No depth/stencil test or write occurs

This is analogous to existing non-determinism in vertex shader invocation
counts due to vertex caching optimizations.

> **Author's note**: This attribute addresses non-determinism in whether a
> Pixel Shader executes due to occlusion. This is distinct from Rasterizer
> Ordered Views (ROVs), which address non-determinism in the ordering of
> concurrent UAV writes from overlapping pixels.

### DXIL Changes

The `[allowearlypixelculling]` attribute is encoded in DXIL using the same
mechanism as the existing `[earlydepthstencil]` attribute. A shader flag bit
is added to the DXIL shader flags metadata to indicate the presence of this
attribute.

#### Shader Flag

A new shader flag bit `AllowEarlyPixelCulling` is added to the DXIL shader
flags enumeration. This flag is set when the `[allowearlypixelculling]`
attribute is present on the Pixel Shader entry point.

The flag is mutually exclusive with the `ForceEarlyDepthStencil` flag. DXIL
with both flags set is invalid.

#### Metadata Encoding

The shader flag appears in the DXIL module metadata:

```llvm
!dx.shaderModel = !{!N}
!N = !{!"ps", i32 6, i32 X}

!dx.entryPoints = !{!M}
!M = !{void ()* @main, !"main", null, null, !O}
!O = !{i32 8, i32 P}  ; Tag 8 = shader flags
; P includes AllowEarlyPixelCulling bit
```

The exact bit position shall be defined in the DXIL specification following
established conventions for shader flag bits.

#### Shader Model Requirement

This flag is valid only in Shader Model 6.X and later. The DXIL validator
shall reject modules with this flag in earlier shader models.

### SPIR-V Changes

The `[allowearlypixelculling]` attribute maps to SPIR-V using the same
mechanism as the existing `[earlydepthstencil]` attribute.

#### Execution Mode

For Vulkan targets, the attribute is expressed using an appropriate SPIR-V
execution mode on the fragment shader entry point. The specific execution mode
shall follow the same pattern used for early depth/stencil testing.

If `[earlydepthstencil]` maps to `ExecutionMode EarlyFragmentTests`, then
`[allowearlypixelculling]` requires a corresponding execution mode or extension
to express non-deterministic early culling semantics.

#### Vulkan Extension Considerations

If no standard SPIR-V execution mode exists to express non-deterministic early
culling, a vendor extension may be required. The extension should:

* Define an execution mode for fragment shaders
* Be compatible with depth output, discard, and coverage modification
* Indicate that fragment invocation counts are implementation-dependent
* Be supported by implementations that can benefit from early culling

Implementations that do not support the extension or optimization may execute
all pixels deterministically with no functional difference.

### Validation Changes

#### Compiler Validation

The DXC compiler shall validate:

* `[allowearlypixelculling]` is only applied to Pixel Shader entry points
* `[allowearlypixelculling]` and `[earlydepthstencil]` are not combined
* The Shader Model is 6.X or later when the attribute is used

Error messages shall clearly indicate the constraint violation.

#### DXIL Validator

The DXIL validator shall enforce:

* The `AllowEarlyPixelCulling` shader flag is present only in Pixel Shaders
* The `AllowEarlyPixelCulling` and `ForceEarlyDepthStencil` flags are not both
  set
* The flag is present only in Shader Model 6.X or later
* The flag is properly encoded in shader metadata

Validation failures shall produce clear error messages indicating the specific
constraint that was violated.

#### SPIR-V Validation

SPIR-V validation shall ensure:

* The execution mode is applied only to fragment shader entry points
* The execution mode is compatible with any Vulkan extensions in use
* Required capabilities or extensions are declared

## Testing

Correct DXIL and SPIR-V codegen will be verified through DXC unit tests that
compile shaders with the `[allowearlypixelculling]` attribute and verify the
presence of the correct shader flag or execution mode in the generated code.
Tests will cover shaders using various combinations of features (discard,
depth outputs, UAV writes, sampler feedback) to ensure the flag is correctly
propagated. Validation errors will be tested through filecheck-based unit
tests that verify appropriate errors are produced when the attribute is
misused (wrong shader stage, combined with `[earlydepthstencil]`, unsupported
shader model). These tests will ensure clear error messages guide developers
to correct usage. Codegen tests will verify that the compiler correctly
encodes the attribute in both DXIL metadata and SPIR-V execution modes,
following the established patterns for `[earlydepthstencil]`.

## Alternatives considered

An alternative approach would add a `D3D12_PIPELINE_STATE_FLAG` that enables
early pixel culling at PSO creation time rather than via a shader attribute.
This would allow the same shader to be used with different culling behaviors
in different render passes (depth pre-pass vs. main pass). However, this
approach has several drawbacks: it moves the decision from shader compile time
to runtime, reducing opportunities for compiler optimizations; it creates
ambiguity about when the optimization is active; and it complicates the shader
contract by making behavior dependent on external PSO state. The attribute
approach provides a clear, explicit shader-level contract that the compiler
can reason about during optimization, similar to how `[earlydepthstencil]`
works today. A hybrid approach where both the attribute and a PSO flag are
required could be considered in future work if runtime control proves
necessary.
