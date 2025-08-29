---
title: 0024 - Opacity Micromaps
params:
  authors:
  - tex3d: Tex Riddell
  sponsors:
  - tex3d: Tex Riddell
  status: Accepted
---

<!-- {% raw %} -->

 
* Planned Version: SM 6.9

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

`RAYTRACING_PIPELINE_FLAG` flags are used in the
[Raytracing pipeline config1][pipeline-config]
subobject in HLSL.  When `RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS` is
used in the current pipeline configuration, the pipeline supports Opacity
Micromaps. If a triangle with an OMM is encountered during traversal with this
flag cleared, behavior is undefined. This flag should not be set if there are
no OMMs present, since it may incur a small penalty on traversal performance
overall.  See the D3D12 flag definition for more details:
[`D3D12_RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`][dxr-flags].

`RayQuery` objects, used with [RayQuery::TraceRayInline()][rq-trace], 
also need to be aware that OMMs may be in use.  The above `RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS` 
doesn't apply for inline raytracing however. `RayQuery` objects are 
independent of raytracing pipelines. For `RayQuery`, the template for 
instantiating the object includes a new optional `RAYQUERY_FLAGS` parameter:

```
template<uint StaticRayFlags, uint RayQueryFlags = RAYQUERY_FLAG_NONE>
class RayQuery;
```

```hlsl
enum RAYQUERY_FLAG : uint
{
    RAYQUERY_FLAG_NONE = 0x00, // default
    RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS = 0x01,
};
```

The reason for separate `RAYQUERY_FLAGS` is existing `RAY_FLAGS` are
shared with non-inline raytracing ([TraceRay()][trace-ray]), where this new 
flag doesn't apply, and ray flag space is a precious resource.

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
static const uint RAYQUERY_FLAG_NONE = 0;
static const uint RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS = 0x1;
```

Each of the above flag value definitions except `RAYQUERY_FLAG_NONE` will 
have an availability attribute applied, restricting their use to
shader model 6.9 and above.

> Note: the fact that these flags have the same value is only a coincidence.

### Interchange Format Additions

This adds a new DXIL operation, `AllocateRayQuery2`, to Shader Model 6.9.
This is a new version of `AllocateRayQuery` that has a `RayQueryFlags`
parameter corresponding to the new template argument in HLSL.
When the `RayQueryFlags` template argument is non-zero, this new
`AllocateRayQuery2` DXIL op is used, otherwise the current `AllocateRayQuery`
DXIL op is used.

The new DXIL Op, `AllocateRayQuery2`, will have this signature:
```DXIL
; Function Attrs: nounwind 
declare i32 @dx.op.allocateRayQuery2(i32 OpCode, i32 constRayFlags, i32 RayQueryFlags)
```

The DXIL operations which either accept or return `RayFlags`, and therefore may
accept or return the new `RAY_FLAG_FORCE_OMM_2_STATE` are the following (along
with brief descriptions):
- `RayFlags` - returns ray flags currently in use
- `TraceRay` - Trace a ray (with ray flags)
- `AllocateRayQuery` - Creates a RayQuery and specifies the constant ray flags
- `RayQuery_TraceRayInline` - Trace a ray (with ray flags OR'd with the
  RayQuery's constant ray flags)

In `DxilConstants.h`, the `RayFlag::ForceOMM2State` flag is added, and a new 
`RayQueryFlag` enum is added, mirroring the `RAYQUERY_FLAG` enum 
defined in HLSL.

```cpp
// Corresponds to RAY_FLAG_* in HLSL
enum class RayFlag : uint32_t {
  ...
  ForceOMM2State = 0x400 // Force 2-state in Opacity Micromaps
};

// Corresponds to RAYQUERY_FLAG_* in HLSL
enum class RayQueryFlag : uint32_t {
  None = 0,
  AllowOpacityMicromaps = 1
};
```

#### SPIR-V

This change is comaptible with the
[SPV_EXT_opactity_micromap](https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/EXT/SPV_EXT_opacity_micromap.asciidoc)
extension, where the new flag is `ForceOpacityMicromap2StateEXT`. It also,
coincidentally, has the same number value as `ForceOMM2State`.


### Diagnostic Changes

A warning diagnostic (default: warning) will be introduced and emitted when
a reachable use of one of the new flags is encountered.
A reachable use is one that is found by traversing AST from active entry and
export functions, or from subobject declarations when compiling a library.
Traversal will follow local function calls, as well as traversing referenced
decls (`DeclRef`s and `DeclRefExpr`s) and initializers.

As an implementation detail, a new custom HLSL-specific availability 
attribute will be used on the new flag definitions. Specifically, of the new 
flags introduced, `RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`, 
`RAY_FLAG_FORCE_OMM_2_STATE`, and `RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS`
will have an availability attribute, which restricts their usage to
shader model 6.9. `RAYQUERY_FLAG_NONE` will be left unrestricted.

This will have implications for uses of these flags outside of the intended
targets.  Since they are just uint values, it's technically legal to refer to
them elsewhere, so we will use a DefaultError warning, since this will be the
only diagnostic used to catch use of these flags in an earlier shader model.

Proposed warning diagnostic:

- `"potential misuse of built-in constant %0 in shader model %1; introduced in shader model %2"`.
  This new warning will have a new warning group to allow it to be targeted
  easily for command-line override, such as `hlsl-availability-constant`.

A check will be added on the declaration of a RayQuery object 
(when not dependent), so that when the RayQueryFlags template argument is
non-zero, it requires shader model 6.9 or above.

Proposed DefaultError warning diagnostic:
- `"A non-zero value for the RayQueryFlags template argument requires shader model 6.9 or above."`.

A check will be added on the declaration of a RayQuery object 
(when not dependent), so that when `RAY_FLAG_FORCE_OMM_2_STATE` is set on
the RayFlags template argument, and `RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS`
is not set on the RayQueryFlags template argument, a DefaultError warning 
is emitted.

Proposed DefaultError warning diagnostic:
- `"When using 'RAY_FLAG_FORCE_OMM_2_STATE' in RayFlags, RayQueryFlags must have RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS set."`.

A check will be added at the call site of `RayQuery::TraceRayInline` that will
emit a DefaultError warning when a constant `RayFlags` parameter has the
`RAY_FLAG_FORCE_OMM_2_STATE` flag set, and the RayQuery object's
`RayQueryFlags` template argument does not have the
`RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS` flag set.
The same warning message is emitted, but a diagnostic note should also
point to the RayQuery object declaration, where this RayQueryFlag needs to be
specified.

#### Validation Changes
Four DXIL operations accept `RayFlags` as input, but only two require these
flags' input to be immediate: `AllocateRayQuery` and `AllocateRayQuery2`.

Validation will be added to ensure the flags are constant on input to
the `AllocateRayQuery` and `AllocateRayQuery2` DXIL operation.

Proposed validation error diagnostics:

- `"constRayFlags argument of AllocateRayQuery '%0' must be constant"`
- `"constRayFlags and RayQueryFlags arguments of AllocateRayQuery2 '%0' must be constant"`

Finally, validation will be added for the `AllocateRayQuery2` DXIL operation
to ensure that when `RAY_FLAG_FORCE_OMM_2_STATE` is set on the constRayFlags
argument, the `RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS` is also set on the
RayQueryFlags argument.

Proposed validation error diagnostic:

- `"RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS must be set for RayQueryFlags when RAY_FLAG_FORCE_OMM_2_STATE is set for constRayFlags on AllocateRayQuery2 operation %0."`.


### Runtime Additions

The new `AllocateRayQuery2` DXIL op is a required part of shader model 6.9.
Drivers that do not support OMM must ignore the new flags:
`RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`,
`RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS`, and `RAY_FLAG_FORCE_OMM_2_STATE`.
This is equivalent to a driver that does support OMM traversing a BVH built
without OMM data.

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
- Test optional template argument to RayQuery generates appropriate DXIL
  opreation and that the optional flag makes it through to the argument list.
- Test that the new flag value, `RAYTRACING_PIPELINE_FLAG_ALLOW_OPACITY_MICROMAPS`,
  appears in the `RaytracingPipelineConfig1` subobject's `Flags` field.

### Diagnostics

- Check availability-based diagnostics for each flag, including recursing
  through DeclRefExprs to Decls and their initializers.
  - Check both DXR entry scenarios and non-library RayQuery scenarios.
- Check that any RayQuery object with the `RayFlag::ForceOMM2State` flag
  in its first template argument also has an accompanying 
  `RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS` flag.
- Check diagnostics for subobject, and lack of diagnostics for non-library
  target, where subobjects are ignored.
- Test the custom HLSL availability attribute, that it correctly locates
  values declared in unintuitive ways, through function calls, namespaces,
  etc.

### Validation

- Check constant value validation on `AllocateRayQuery` and `AllocateRayQuery2`
  DXIL ops.
- Check `AllocateRayQuery2` DXIL op validation for
  `RAYQUERY_FLAG_ALLOW_OPACITY_MICROMAPS` requirement when
  `RAY_FLAG_FORCE_OMM_2_STATE` is used.

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
happen to be constant.

### Shader Model Predicated Flag Definitions

We will not gate definitions of the flag by shader model, but will use 
availability attributes to mark definitions as only being available in 
shader model 6.9.
These diagnostics will be a warning by default, since it is legal to use the
flag values in other contexts, but might indicate a mistaken usage.
Diagnostics based on these will only be triggered when these definitions are
reachable in the current compilation.

## Open Issues

## Acknowledgments (Optional)

* Amar Patel
* Josh Batista

<!-- External References -->

[dxr-omm]: <https://dev.azure.com/cga-exchange/_git/docs?path=/d3d/Raytracing.md&_a=preview&anchor=opacity-micromaps> "Opacity Micromaps (internal only)"
[pipeline-config]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#d3d12_raytracing_pipeline_config1> "RaytracingPipelineConfig1"
[trace-ray]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#traceray> "TraceRay"
[rq-trace]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-tracerayinline> "RayQuery::TraceRayInline"
[ray-query]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery> "RayQuery"
[dxr-flags]: <https://dev.azure.com/cga-exchange/_git/docs?path=/d3d/Raytracing.md&_a=preview&anchor=d3d12_raytracing_pipeline_flags> "D3D12_RAYTRACING_PIPELINE_FLAGS  (internal only)"
[rayflags]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayflags> "RayFlags()"

<!-- {% endraw %} -->
