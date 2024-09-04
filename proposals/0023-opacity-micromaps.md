<!-- {% raw %} -->

# Opacity Micromaps

## Instructions

* Proposal: [0023](0023-opacity-micromaps.md)
* Author(s): [Tex Riddell](https://github.com/tex3d)
* Sponsor: [Tex Riddell](https://github.com/tex3d)
* Status: **Under Review**

<!--
*During the review process, add the following fields as needed:*

* Planned Version: Shader Model X.Y
* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues:
  [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/issues/NNNN)
  -->

> NOTE: some links in this document are to internal documents that are not
> currently publically available. This file will be updated once they are
> published.

## Introduction

The Opacity Micromaps (OMM) feature allows DirectX Ray Tracing developers to
allow ray-triangle hits to be trivially classified as miss or hit without having
to invoke an any-hit shader.

This spec is narrowly focused on the HLSL compiler related aspects required to
implement and test the feature from the compiler perspective.
See the Opacity micromaps section in the [Raytracing spec][dxr-omm]
for more details on the overall feature and D3D runtime context.

## Motivation

There needs to be a way to enable OMM through subobjects in HLSL, equivalent
to [`D3D12_RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`][dxr-flags] in the
API.

Additionally, the runtime allows instances to be tagged with
`D3D12_RAYTRACING_INSTANCE_FLAG_FORCE_OMM_2_STATE`, but allowing this to be
specified at ray tracing time in a shader would provide flexibility for
developers.

## Proposed solution

A new `RAYTRACING_PIPELINE_FLAG` is proposed to enable OMM in HLSL:
`RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`.
These flags are used in the [Raytracing pipeline config1][pipeline-config]
subobject in HLSL.

A new `RAY_FLAG` is proposed that allows ray tracing in shaders to force OMM
2-state for a particular trace: `RAY_FLAG_FORCE_OMM_2_STATE`.

## Detailed design

### HLSL Additions

Add a built-in `RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS` to the
`RAYTRACING_PIPELINE_FLAG` flags in HLSL to enable OMM.
Add built-in `RAY_FLAG_FORCE_OMM_2_STATE` to `RAY_FLAG` flags in HLSL.

`RAYTRACING_PIPELINE_FLAG` flags are used in the
[Raytracing pipeline config1][pipeline-config]
subobject in HLSL.  When `RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS` is
used in the current pipeline configuration, the pipeline supports Opacity
Micromaps. If a triangle with an OMM is encountered during traversal with this
flag cleared, behavior is undefined. This flag should not be set if there are
no OMMs present, since it may incur a small penalty on traversal performance
overall.  See the D3D12 flag definition for more details:
[`D3D12_RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`][dxr-flags].

Add a built-in `RAY_FLAG_FORCE_OMM_2_STATE` flag to the `RAY_FLAG` flags.
`RAY_FLAG` flags are only meaningful when used in the `RayFlags` parameter of
the [TraceRay()][trace-ray] or [RayQuery::TraceRayInline()][rq-trace]
intrinsic functions, or in the `RAY_FLAGS` template argument of a
[RayQuery][ray-query] object.  When used with [Opacity Micromaps][dxr-omm]
(`RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS` or
[`D3D12_RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`][dxr-flags]),
the raytracing pipeline will ignore the Unknown state and only consider the
Transparent/Opaque bit for all 4-state Opacity Micromaps encountered during
traversal. This flag has no effect if
`D3D12_RAYTRACING_INSTANCE_FLAG_DISABLE_OMMS` is set on the instance, or if
Opacity Micromaps are globally not set, not allowed, or not supported.
If set, this flag will be present in the returned flags of the
[RayFlags()][rayflags] intrinsic function.

In HLSL under DXC, these are defined as static const uint values:

```hlsl
static const uint RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS = 0x400;
static const uint RAY_FLAG_FORCE_OMM_2_STATE = 0x400;
```

> Note: the fact that these flags have the same value is only a coincidence.

### Interchange Format Additions

This adds no DXIL operations or metadata, it only adds a new flag value that
may be used with existing DXIL operation parameters, returned by a DXIL
operation.

The DXIL operations which either accept or return `RayFlags`, and therefore may
accept or return the new `RAY_FLAG_FORCE_OMM_2_STATE` are the following (along
with brief descriptions):
- `RayFlags` - returns ray flags currently in use
- `TraceRay` - Trace a ray (with ray flags)
- `AllocateRayQuery` - Creates a RayQuery and specifies the constant ray flags
- `RayQuery_TraceRayInline` - Trace a ray (with ray flags OR'd with the
  RayQuery's constant ray flags)

When lowering to DXIL intrinsics, we will mask the flags using the legal mask
for the shader target.  This will prevent undefined behavior if invalid flags
were specified and either warnings were ignored, or the flags were not a known
constant value during semantic analysis.

In `DxilConstants.h`, the `RayFlag::ForceOMM2State` flag is added.
Propose adding ValidMask values for diagnostics and validation.

```cpp
// Corresponds to RAY_FLAG_* in HLSL
enum class RayFlag : uint32_t {
  ...
  ForceOMM2State = 0x400, // Force 2-state in Opacity Micromaps
  ValidMask_1_8 = 0x3ff, // valid mask up through DXIL 1.8
  ValidMask = 0x7ff, // current valid mask
};
```

### Diagnostic Changes

A warning diagnostic (default: warning) will be introduced and emitted when
a reachable use of one of the new flags is encountered.
A reachable use is one that is found by traversing AST from active entry and
export functions, or from subobject declarations when compiling a library.
Traversal will follow local function calls, as well as traversing referenced
decls and initializers.

As an implementation detail, an attribute may be used on the new flag
definitions, such as an existing Clang availability attribute or a new custom
HLSL-specific attribute.

AST traversal from entry points will traverse DeclRefs and initializers to
detect the use of the new ray flag.  AST traversal will be added for subobject
declarations on library targets to detect any use of the new pipeline flag.

This will have implications for uses of these flags outside of the intended
targets.  Since they are just uint values, it's technically legal to refer to
them elsewhere, so we will use a warning which defaults to warning rather than
using DefaultError like we would for calls to unsupported intrinsic functions.

Proposed warning diagnostic:

- `"potential misuse of built-in constant %0 in shader model %1; introduced in shader model %2"`.
  This new warning will have a new warning group to allow it to be targeted
  easily for command-line override, such as `hlsl-availability-constant`.

When compiling a library with the
`RaytracingPipelineFlags::AllowOpacityMicromaps` flag set in a
[Raytracing pipeline config1][pipeline-config] subobject,
a new DefaultError warning diagnostic will be added if the shader model is less
than 6.9. This will detect the case where the flag is not spelled out and
caught by AST traversal.

Current HLSL diagnostics in DXC do not verify `RayFlags` values in any context.
`TraceRay()` and `RayQuery::TraceRayInline()` accept non-immediate values, but
the `RayFlags` provided as a template argument to `RayQuery` must be immediate.

In addition to the AST traversal detecting any explicit use of the new flag,
the same DefaultError warning diagnostic will be added to detect when the
new ray flag is used at the `RayQuery` template argument, `TraceRay()`, or
`RayQuery::TraceRayInline()` (when it is immediate).
This can make use of the new `ValidMask*` values.

Proposed DefaultError warning diagnostic:

- `"%select{RaytracingPipelineFlags|RayFlags}0 (0x%1) includes unsupported bits for shader model %2; valid mask: 0x%3"`.
  This new warning will have a different warning group, such as
  `hlsl-availability`.

> See Issue [RayQuery Template Diagnostics](#rayquery-template-diagnostics).

#### Validation Changes

Validation will be added to ensure that the shader model is at least 6.9 when
the `RaytracingPipelineFlags::AllowOpacityMicromaps` is used in a
[Raytracing pipeline config1][pipeline-config] subobject.

Proposed validation error diagnostic:

- `"RaytracingPipelineFlags in RaytracingPipelineConfig1 subobject '%0' specifies unknown flags (0x%1) for shader model %2; valid mask: 0x%3"`

Three DXIL operations accept `RayFlags` as input, but only one requires this
input to be immediate: `AllocateRayQuery`.

Validation will be added to check the `RayFlags` parameters for each applicable
DXIL operation, with an error emitted if the flags are constant, the new flag
is used, and the shader model is less than 6.9.

Proposed validation error diagnostic:

- `"RayFlags used in '%0' specifies unknown flags (0x%1) for shader model %2; valid mask: 0x%3"`

Validation will also be added to ensure the flags are constant on input to
the `AllocateRayQuery` DXIL operation.

Proposed validation error diagnostic:

- `"ConstRayFlags argument of AllocateRayQuery '%0' must be constant"`

### Runtime Additions

#### Runtime information

##### RDAT

In the `RDAT` data for the runtime, a new flag is added to the `Flags` field
of the `RaytracingPipelineConfig1` subobject type.

In `DxilConstants.h`, the `RaytracingPipelineFlags::AllowOpacityMicromaps`
flag is added.

```cpp
enum class RaytracingPipelineFlags : uint32_t {
  ...
  ValidMask_1_8 = 0x300, // valid mask up through DXIL 1.8
  AllowOpacityMicromaps = 0x400, // Allow Opacity Micromaps to be used
  ValidMask = 0x700, // current valid mask
};
```

In `RDAT_SubobjectTypes.inl`, the enum value is mapped and ValidMask updated.

```cpp
RDAT_DXIL_ENUM_START(hlsl::DXIL::RaytracingPipelineFlags, uint32_t)
  ...
  RDAT_ENUM_VALUE_NODEF(AllowOpacityMicromaps)
#if DEF_RDAT_ENUMS == DEF_RDAT_DUMP_IMPL
  static_assert((unsigned)hlsl::DXIL::RaytracingPipelineFlags::ValidMask ==
                    0x700,
                "otherwise, RDAT_DXIL_ENUM definition needs updating");
#endif
RDAT_ENUM_END()\
```

Any statically-determined use of `RayFlag::ForceOMM2State` in a ray flags
parameter of the corresponding DXIL op will set the
`RuntimeDataFunctionInfo::MinShaderTarget` shader model to a minimum of 6.9 for
the calling function. However, since RayFlags parameters are not required to be
an immediate constant for some of the intrinsics, dynamic usage of this flag
will not impact the shader model minimum.

Since `RaytracingPipelineFlags::AllowOpacityMicromaps` is only interpreted in
the `RaytracingPipelineConfig1` subobject, there is no fixed association with
any function, and no impact on the DXIL passed to the driver.  Thus it has no
impact on any `RuntimeDataFunctionInfo::MinShaderTarget`.
Since this flag may only be included in a shader model 6.9 library, the library
cannot be used on a device that doesn't support shader model 6.9.

#### Device Capability

The use of `RayFlag::ForceOMM2State` only requires Shader Model 6.9, since the
flag is ignored when OMM is not present or not supported.

Use of the `RaytracingPipelineFlags::AllowOpacityMicromaps` flag will require
Shader Model 6.9.  Additionally, the runtime will enforce the Opacity Micromaps
device feature support requirement if the subobject is used.
See [Opacity Micromaps][dxr-omm] in the Raytracing spec for details.

## Testing

### Compiler output

- Test use and value of new flags using ast-dump
- Test that new flag values in intrinsics and RayQuery template argument make
  it through to appropriate DXIL operation arguments.
- Use D3DReflect test to verify new flag value in `RaytracingPipelineConfig1`
  subobject `Flags` field.
- Use D3DReflect test to verify min shader model of 6.9 when new ray flag has
  constant usage.
- Check for `and` instruction masking of non-constant values, and for masking
  off of a constant invalid flag when turning off the associated warnings.
  These also verify that you can disable all the warning diagnostics.

### Diagnostics

- Check availability-based diagnostics for each flag, including recursing
  through DeclRefs and their initializers.
  - Check both DXR entry scenarios and non-library RayQuery scenarios.
- Check diagnostics for subobject, and lack of diagnostics for non-library
  target, where subobjects are ignored.
- Check diagnostics for constant flag values used without the explicit
  spelling of the new flags (like using `0x400`) in each applicable scenario.
- Check diagnostics for constant flag scenarios with unknown bits set.

### Validation

- Check constant flag validation for shader models 6.9 and for an earlier
  shader model, for each applicable intrinsic.
  - Also check validation for when unknown flag bits are set.
- Check subobject flag validation for a shader model less than 6.9.
  - Compile with the flag to 6.9 and change the target for manual assembly.

### Execution

- Opacity Micromap tests will be added to the existing DXR HLK tests that
  verify driver behavior using these flags.

## Resolved Issues

### Subobject Diagnostics and Validation

We will add diagnostics and validation for the use of the new flag in a DXR
subobject when the shader model is less than 6.9.

### RayFlag Diagnostics and Validation

We will add diagnostics and validation for RayFlag cases where they must be
constant (RayQuery template and `AllocateRayQuery` DXIL op), or where they
happen to be constant.  We will only check them against a mask for the shader
model, rather than checking for invalid combinations of valid flags.

We will add masking for generated DXIL in the compiler, but will not check that
unknown values are masked in the DXIL validator.

### Shader Model Predicated Flag Definitions

We will not gate definitions of the flag by shader model, but will use a
mechanism, such as availability attributes, to mark definitions as only being
available in shader model 6.9.
These diagnostics will be a warning by default, since it is legal to use the
flag values in other contexts, but might indicate a mistaken usage.
Diagnostics based on these will only be triggered when these definitions are
reachable in the current compilation.

## Open Issues

### Availability Diagnostics

Some investigation is required to determine the approach for DXC to emit
availability diagnostics for use of the new flag definitions themselves.
We might use the built-in availability attribute, or use a new attribute,
depending on practicalities in DXC.

Use of availability attributes for diagnostics will introduce changes in our
current AST traversal that checks a few existing intrinsics.  It will also
require that we traverse subobject declarations when compiling a library.
There may be an opportunity to replace some existing custom diagnostics in
this path with the use of an availability attribute approach.

### RayQuery Template Diagnostics

How should the `RayQuery` `ConstRayFlag` template argument be checked against
the valid mask in the compiler?  We have a custom check for arguments such as
the dimensions passed to `vector` and `matrix` templates.  It was suggested
that we might be able to implement this with some sort of static assert
instead.  However, I'm concerned that this approach may unintentionally impact
unreachable uses of `RayQuery`.

## Acknowledgments (Optional)

* Amar Patel

<!-- External References -->

[dxr-omm]: <https://dev.azure.com/cga-exchange/_git/docs?path=/d3d/Raytracing.md&_a=preview&anchor=opacity-micromaps> "Opacity Micromaps (internal only)"
[pipeline-config]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#d3d12_raytracing_pipeline_config1> "RaytracingPipelineConfig1"
[trace-ray]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#traceray> "TraceRay"
[rq-trace]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-tracerayinline> "RayQuery::TraceRayInline"
[ray-query]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery> "RayQuery"
[dxr-flags]: <https://dev.azure.com/cga-exchange/_git/docs?path=/d3d/Raytracing.md&_a=preview&anchor=d3d12_raytracing_pipeline_flags> "D3D12_RAYTRACING_PIPELINE_FLAGS  (internal only)"
[rayflags]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayflags> "RayFlags()"

<!-- {% endraw %} -->
