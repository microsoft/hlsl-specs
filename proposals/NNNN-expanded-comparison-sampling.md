# Expanded Comparison Sampling

* Proposal: [NNNN](NNNN-expanded-comparison-sampling.md)
* Author(s): [Greg Roth](https://github.com/pow2clk),
             [Jesse Natalie](https://github.com/jenatali)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8
* Issues: [30](https://github.com/microsoft/hlsl-specs/issues/30),
          [81](https://github.com/microsoft/hlsl-specs/issues/81)

## Introduction

Sampler operations in HLSL perform either a comparison sampler or non-comparison
 sampler operation.
Comparison sample operations will perform the compare operation specified in the
 sampler between the sampled value and a provided value and produce a 0 or 1
 value indicating the failure or success of the comparison respectively.
In linear filtered samples, multiple values will be blended to produce the
 complete sample operation result.
Sampling operations sample from a texture according to the settings in the
 provided sampler object.
The most useful forms of sampling involve the calculation of a MIP level
 to determine which level(s) of detail(LOD) of the sampled texture should be
 used and how they should be weighted.

## Motivation

Different non-comparison sampler operations calculate the MIP level in different
 ways:

* `Sample(SamplerState S, vector<float, CoordsCt> Location)`
  samples using LOD values that are determined implicitly using gradients
  (sometimes called derivatives) representing how much the coordinates in
  `Location` that correspond to sampling dimension change across neighboring
  pixels.
* `SampleBias(SamplerState S, vector<float, CoordsCt> Location, float Bias)`
   samples using the same implicitly-determined LOD with an
   explicitly-provided `Bias` value added to that result.
* `SampleGrad(SamplerState S, vector<float, CoordsCt> Location, vector<float, DimsCt> DDX, vector<float, DimsCt> DDY)`
   samples using the LOD calculated using the explicitly-provided
   `DDX` and `DDY` gradients.
* `SampleLevel(SamplerState S, vector<float, CoordsCt> Location, float LOD)`
   samples using an explicitly-provided `LOD`.

Note that throughout this document, the template parameter `CoordsCt`
 represents the number of indexable coordinate dimensions and `DimsCt`
 represents the number of native dimension axes in the given texture resource.
This means that `CoordsCt` includes the native dimensions as well as an
 additional dimension for the slices in array textures and `DimsCt` excludes
 the additional array texture slice dimension.

Comparison sampler operations have fewer options for how the LOD is calculated:

* `SampleCmp(SamplerComparisonState S, vector<float, CoordsCt> Location)`
  performs a comparison sample using implicitly-determined LOD values.
* `SampleCmpLevelZero(SamplerComparisonState S, vector<float, CoordsCt> Location, float cmpVal)`
  performs a comparison sample using LOD 0
* `SampleCmpLevel(SamplerComparisonState S, vector<float, CoordsCt> Location, float cmpVal, float LOD)`
  performs a comparison sample using an explicitly provided `LOD`
  (as of shader model 6.7)

Additionally, the level of detail value can be calculated and retrieved directly
 for non-comparison samplers:

* `CalculateLevelOfDetailUnclamped(SamplerState S, vector<float, CoordsCt> Location)`
  returns the raw LOD value determined implicitly using gradients representing
  how much the dimension in `Location` change across neighboring pixels
  regardless of whether it falls outside the valid range.
* `CalculateLevelOfDetail(SamplerState S, vector<float, CoordsCt> Location)`
  returns the implicitly-determined LOD value clamped to the valid range.

There are no `CalculateLevelOfDetail` variants for comparison samplers.


Without the full complement of comparison sampler operations, techniques that
 require LOD calculation beyond the implicit calculations are missing the full
 support for different approaches to LOD calculation.
In particular, this can affect algorithms involving shadow maps and any case
 where standard samples have comparison sample counterparts that need to match.
In addition, this represents a discrepancy with comparable platforms where this
 deficiency makes porting, emulating, or developing for multiple platforms
 difficult or impossible.

## Proposed solution

To add full comparison sampling support, HLSL will introduce an optional feature
 that adds these new comparison sampling builtin methods to all texture objects
 that currently support the non-comparison methods:

* `SampleCmpBias(SamplerComparisonState S, vector<float, CoordsCt> Location, float Bias)`
  performs a comparison sample using the implicitly-determined LOD with the
  explicitly-provided `Bias` value added to that result.
* `SampleCmpGrad(SamplerState S, vector<float, CoordsCt> Location, float DDX, float DDY)`
   samples using the LOD calculated using the explicitly-provided
   `DDX` and `DDY` gradients.

Only the simplest overloads of the new and existing builtin methods are
 described in detail here for the sake of brevity,
Though not included above, all relevant overloads of `SampleBias` and
 `SampleGrad` will be reflected in their new `SampleCmpBias` and
 `SampleCmpGrad` counterparts.
The parameters not explicitly described here will function exactly as they do
 when used by the non-comparison builtin methods:

* `SampleCmpBias(SamplerComparisonState S, vector<float, CoordsCt> Location, float Bias)`
* `SampleCmpBias(SamplerComparisonState S, vector<float, CoordsCt> Location, float Bias, int<dims> Offset)`
* `SampleCmpBias(SamplerComparisonState S, vector<float, CoordsCt> Location, float Bias, int<dims> Offset, float Clamp)`
* `SampleCmpBias(SamplerComparisonState S, vector<float, CoordsCt> Location, float Bias, int<dims> Offset, float Clamp, uint Status)`
%* `SampleCmpGrad(SamplerState S, vector<float, CoordsCt> Location, vector<float, DimsCt> DDX, vector<float, DimsCt> DDY)`
* `SampleCmpGrad(SamplerState S, vector<float, CoordsCt> Location, vector<float, DimsCt> DDX, vector<float, DimsCt> DDY, int<dims> Offset)`
* `SampleCmpGrad(SamplerState S, vector<float, CoordsCt> Location, vector<float, DimsCt> DDX, vector<float, DimsCt> DDY, int<dims> Offset, float Clamp)`
* `SampleCmpGrad(SamplerState S, vector<float, CoordsCt> Location, vector<float, DimsCt> DDX, vector<float, DimsCt> DDY, int<dims> Offset, float Clamp, uint Status)`

To add LOD calculation for comparison samplers, HLSL will introduce and require
 these new comparison sampler method overloads to all texture objects that
 currently support the non-comparison method overloads:

* `CalculateLevelOfDetailUnclamped(SamplerComparisonState S, vector<float, CoordsCt> Location)`
  returns the raw LOD value determined implicitly using gradients representing
  how much the `Location` changes across neighboring pixels regardless of
  whether it falls outside the valid range.
* `CalculateLevelOfDetail(SamplerComparisonState S, vector<float, CoordsCt> Location)`
  returns the implicitly-determined LOD value clamped to the valid range.

## Detailed Design

### HLSL additions

These new HLSL texture methods will be added:

```c++
template<typename ElementType, int CoordsCt, int DimsCt>
vector<ElementType, DimsCt> TextureBase::SampleCmpGrad(
    SamplerComparisonState S,
    vector<float, CoordsCt> Location,
    vector<float, DimsCt> DDX,
    vector<float, DimsCt> DDY,
    float CompareValue,
    vector<int, DimsCt> Offset = 0,
    float Clamp = 0.0f);

template<typename ElementType, int CoordsCt, int DimsCt>
vector<ElementType, DimsCt> TextureCube::SampleCmpGrad(
    SamplerComparisonState S,
    vector<float, CoordsCt> Location,
    vector<float, DimsCt> DDX,
    vector<float, DimsCt> DDY,
    float CompareValue,
    float Clamp = 0.0f);
```

Where `TextureBase` represents any of Texture1D[Array] or Texture2D[Array]
 texture object types.
The `TextureCube` method does not have an `Offset` parameter in keeping
 with other `TextureCube` methods.
`TextureCubeArray` does not support the `SampleCmpGrad` method.
Note that these both have an additional overload that includes all the default
 parameters explicitly specified and a final output `status` parameter.
`SampleCmpGrad` is available in all shader stages.

```c++
template<typename ElementType, int CoordsCt, int DimsCt>
vector<ElementType, DimsCt> TextureBase::SampleCmpBias(
      SamplerComparisonState S,
      vector<float, CoordsCt> Location,
      float Bias,
      float CompareValue,
      vector<int, DimsCt> Offset = 0,
      float Clamp = 0.0f,
);
template<typename ElementType, int CoordsCt, int DimsCt>
vector<ElementType, DimsCt> TextureCube[Array]::SampleCmpBias(
      SamplerComparisonState S,
      vector<float, CoordsCt> Location,
      float Bias,
      float CompareValue,
      float Clamp = 0.0f
);
```

Where `TextureBase` represents any of Texture1D[Array] or Texture2D[Array]
 texture object types.
The `TextureCube*` methods do not have an `Offset` parameter in keeping with other
 `TextureCube*` methods.
Both methods have an additional overload that includes all the default
 parameters explicitly specified and a final output `status` parameter.
`SampleCmpBias` is only available in the pixel and compute shader stages where
 implicit derivatives can be calculated.

The semantics of the comparisons are identical to the existing `SampleCmp` and
 `SampleCmpLevel[Zero]` methods. The comparison is performed on the R channel of
 the texture after applying SRV swizzling.
The number of components in the `Location` and `Offset` value depends on the type
 of the texture being sampled from.

The only difference between these new functions and the existing comparison
 sample ops is how the LOD is computed.
The computation of the LOD is identical to the equivalent non-comparison
 sampling operation.
E.g. `SampleCmpGrad` behaves like `SampleGrad`, except that the comparison is
 performed on the result,
 and likewise for `SampleCmpBias` relative to `SampleBias`.
More specifically, `SampleCmpGrad` uses explicit gradients to compute the LOD
 rather than implicit ones from other pixels in the current pixel shader quad,
 and `SampleCmpBias` computes an implicit LOD and then adds a shader-computed
 bias value to the result.

Two new HLSL overloads for calculating the level of detail will be added:

```c++
template<int CoordsCt>
float TextureBase::CalculateLevelOfDetail(
      SamplerComparisonState S,
      vector<float, CoordsCt> Location
);
template<int CoordsCt>
float TextureBase::CalculateLevelOfDetailUnclamped(
      SamplerComparisonState S,
      vector<float, CoordsCt> Location
);
```

Where `TextureBase` represents any texture object type except `Texture2DMS*`.
`CalculateLevelOfDetail` is only available in the pixel and compute shader
 stages where implicit derivatives can be calculated.

The semantics of the level of detail calculations are identical to the existing
 `CalculateLevelOfDetail` overloads.
The only difference with the new overloads is that they calculate the level of
 detail using comparison sampler objects.

### DXIL Additions

Two new DXIL intrinsics are added:

```llvm
declare %dx.types.ResRet.f32 @dx.op.sampleCmpGrad.f32(
    i32,                  ; opcode
    %dx.types.Handle,     ; texture handle
    %dx.types.Handle,     ; sampler handle
    float,                ; coordinate c0
    float,                ; coordinate c1
    float,                ; coordinate c2
    float,                ; coordinate c3
    i32,                  ; offset o0
    i32,                  ; offset o1
    i32,                  ; offset o2
    float,                ; compare value
    float,                ; ddx0
    float,                ; ddx1
    float,                ; ddx2
    float,                ; ddy0
    float,                ; ddy1
    float,                ; ddy2
    float)                ; clamp
```

Valid resource types for the texture handle parameter and the corresponding
 active coordinates and offsets are the same as for the `sampleGrad` operation
 except that `TextureCubeArray` resources are invalid.
Valid active ddx and ddy are the same as offsets.
The sampler handle parameter must be of type `SamplerComparisonState`.

```llvm
declare %dx.types.ResRet.f32 @dx.op.sampleCmpBias.f32(
    i32,                  ; opcode
    %dx.types.Handle,     ; texture handle
    %dx.types.Handle,     ; sampler handle
    float,                ; coordinate c0
    float,                ; coordinate c1
    float,                ; coordinate c2
    float,                ; coordinate c3
    i32,                  ; offset o0
    i32,                  ; offset o1
    i32,                  ; offset o2
    float,                ; compare value
    float,                ; bias: in [-16.f,15.99f]
    float)                ; clamp
```

Valid resource types for the texture handle parameter and the corresponding
 active coordinates and offsets are the same as for the `sampleBias` operation
 except that `TextureCubeArray` resources are invalid for `sampleCmpGrad`.
The sampler handle parameter must be of type `SamplerComparisonState`.

The existing `dx.op.calculateLOD` intrinsic is reused for the new
 `CalculateLevelOfDetail` overloads taking `SamplerComparisonState` parameters.

### SPIR-V Additions

To implement the new `SampleCmpGrad` and `SampleCmpBias` texture methods,
 the existing `OpImage*SampleDrefImplicitLod` operations can be used with the
 optional image operands set to the value for `Grad`(0x4) or `Bias`(0x1) set
 to the values provided by the user.

To implement the new `CalculateLevelOfDetail[Unclamped]` overloads,
 the existing `OpImageQueryLod` operation may be used with comparison state images.

### Diagnostic Changes

#### Removed errors

* Using `CalculateLevelOfDetail[Unclamped]` with a `SamplerComparisonState`
  sampler will no longer produce an error when compiling with appropriate shader
  model versions.

#### New Errors

* Using `SampleCmpBias` in code reachable from the entry point of unsupported
  shader stages will produce an error.
* Using `SampleCmpBias`, `SampleCmpGrad`, or the new `CalculateLevelOfDetail*`
  overloads in an unsupported shader model version will produce an special error
  indicating that a later shader model version is required.

#### Validation Changes

* DXIL validation of shaders using this feature requiring that
  `@dx.op.calculateLOD` have a non-comparison sampler handle are removed.
* DXIL validation of LOD Bias range must be performed for `dx.op.sampleCmpBias`.
  (see Instr.ImmBiasForSampleB)
* DXIL validation of allowed resource types must be performed for
  `dx.op.sampleCmpBias` and `dx.op.sampleCmpGrad`.
  (See Instr.SampleCompType, Instr.SamplerModeForSampleC,
   Instr.ResourceKindForCalcLOD, Instr.ResourceKindForSample, and
   Instr.ResourceClassForSamplerGather)

### Runtime Additions

#### Runtime information

A new feature info flag is added to SFI0:

|         Tag             | Bit |   Value    | Description                             |
|-------------------------|-----|------------|-----------------------------------------|
|SampleCmpGradientOrBias  | 31  | 0x80000000 | SampleCmpBias or SampleCmpGrad are used |

It indicates to the runtime that the shader makes use of `SampleCmpBias` or
 `SampleCmpGrad`.
This indicates to the runtime that that the shader requires the presence of
 the corresponding capability bit (described below) indicating support.

#### Device Capability

Applications can query the availability
 of these features by
 passing `D3D12_FEATURE_D3D12_OPTIONS22`
 as the `Feature` parameter
 and retrieving the `pFeatureSupportData` parameter
 as a struct of type `D3D12_FEATURE_DATA_D3D12_OPTIONS22`.
The relevant parts of these structs are defined below.

```C++
typedef enum D3D12_FEATURE {
    ...
    D3D12_FEATURE_D3D12_OPTIONS22
} D3D12_FEATURE;

typedef struct D3D12_FEATURE_DATA_D3D12_OPTIONS22 {
    ...
    BOOL ExpandedComparisonSamplingSupported;
} D3D12_FEATURE_DATA_D3D12_OPTIONS22;
```

`ExpandedComparisonSamplingSupported` is a boolean that specifies
 whether the expanded comparison sample methods indicated here are supported
 by the given hardware and runtime.

## Testing

### Correct Behavior Testing

Verify that `SampleCmpGrad` and the new `CalculateLevelOfDetail*` overloads
 generate appropriate code including the new DXIL and SPIRV intrinsics for all
 shader stages.
Verify that `SampleCmpBias` produces appropriate code including the new DXIL and
 SPIRV intrinsics for pixel, compute, and node shader stages.
Where the `DerivativesInMeshAndAmplificationShadersSupported` capability bit is
 supported, verify that `SampleCmpBias` produces appropriate code including the
 new DXIL and SPIRV intrinsics for mesh and amplification shader stages.
For all of the above, verify that no validation errors are produced for the
 generated code.
For all of the above, wherever `SampleCmpGrad` and `SampleCmpBias` are used,
 check that the appropriate shader flag is set.
The above should all be doable with LIT filecheck tests.

#### Diagnostics Testing

Use `SampleCmpBias` in code reachable from the entry point of each unsupported
 shader stage (vertex, geometry, tesselation stages, ray tracing stages, and
 mesh stages if lacking hardware support for mesh derivatives)
Using `SampleCmpBias`, `SampleCmpGrad`, and the new `CalculateLevelOfDetail*`
 overloads in an unsupported shader model on a supported stage and verify that
 a special error indicating the required version is produced.

### Validation Testing

Test that the Bias range limits tested by `SampleBiasFail` are respected by
 `dx.op.sampleCmpBias`. (see Instr.ImmBiasForSampleB)
Test that DXIL validation of allowed resource types must be performed for
  `dx.op.sampleCmpBias` and `dx.op.sampleCmpGrad`:

* Instr.SampleCompType - texture resources are declared with types that are
  sampleable in the current environment.
* Instr.SamplerModeForSampleC - sampler resource used by `SampleCmpBias` and
  `SampleCmpGrad` are of type `SamplerComparisonState`.
* Instr.ResourceKindForCalcLOD  - texture resources used by
  CalculateLevelOfDetail* are among the valid texture objects.
* Instr.ResourceKindForSample  - texture resources used by
  `SampleCmpBias` and `SampleCmpGrad` are among the valid texture objects.
* Instr.ResourceClassForSamplerGather - texture resources used by
  `SampleCmpBias` and `SampleCmpGrad` must be SRVs.

### Execution Testing

Since there is no defined equation to determine which mip level an
 implementation should use, the best approach is to compare the results of
 different operations involving mip levels to ensure that they are consistent.

To test `CalculateLevelOfDetail*` methods,
use a texture with sentinel values in each mip level and ensure that the mip
  level returned by CalculateLevelOfDetail matches the behavior of the original
  SampleCmp operation by providing the sentinel value of the mip level
  CalculateLevelOfDetail* made you expect and making sure that it matches.
This will ensure that CalculateLevelOfDetail correctly returns the mip value
that sample would have used.
Ensure as well that `CalculateLevelOfDetail` clamps the mip result and
 `CalculateLevelOfDetailUnclamped` does not.

Given the nature of SampleCmp operations, the tests will have to be performed
 with comparison values and success determined based on whether it matches what
 is expected.
At any point, the tests described below have two possible values.
This allows quickly testing for one or the other to determine how to advance the
 test.
If it's the current value, the next iteration starts.
If it's the next expected value, the expected value is updated before the next
 iteration starts.
If any other value is found, the test should fail.

To test the `SampleCmpBias` method,
use a texture with sentinel values in each mip level, start with no bias
 and determine the default mip level, then increase the bias ensuring that the
 mip level the sample uses switches to the expected next level at a reasonable
 bias: somewhere between just over 0.0 and 1.0.
Repeat for a few levels.

To test the `SampleCmpGrad` method,
use a texture with sentinel values in each mip level, start with gradients of 0
 to determine the base mip level. Increase the gradients gradually and ensure
 that mip level the sample uses switches to the expected next level at
 reasonable gradient values.
Repeat for a few levels.
