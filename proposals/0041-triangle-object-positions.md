--- 
title: 0041 - TriangleObjectPositions
params:
  authors:
  - tex3d: Tex Riddell
  - jenatali: Jesse Natalie
  sponsors:
  - jenatali: Jesse Natalie
  status: Under Review
---

## Introduction

This proposal adds intrinsics that can be called from an Any hit or Closest
hit shader to obtain the positions of the vertices for the triangle that has
been hit.

## Motivation

Developers often need to know the positions of the vertices for the triangle
that was hit in an Any/Closest hit shader. Currently, the only way to do this is
for the developer to provide separate buffers containing this data. This
information is also available in the acceleration structure, but there is
currently no way to access it.

If developers can access this data from their shader code then this will remove
the need have a duplicate copy of it. In addition, this will provide drivers
with opportunities to optimize the data layout for their implementations.

## Proposed solution

Add intrinsics to look up the object-space vertex positions of the triangle for
the current hit, or RayQuery candidate/committed hits.

For context, see related sections in DirectX Raytracing Specification:
[TriangleObjectPositions][dxr-tri-obj-pos],
[RayQuery::CandidateTriangleObjectPositions][dxr-rq-can-tri-obj-pos],
[RayQuery::CommittedTriangleObjectPositions][dxr-rq-com-tri-obj-pos].

## Detailed design

### HLSL Additions

A new built-in structure for returning all three object-space triangle
positions is added: `BuiltInTrianglePositions`.

> See Issue [Return Type](#return-type)

```cpp
/// \brief Stores the positions for all vertices of a triangle
struct BuiltInTrianglePositions {
  float3 p0, p1, p2;
};
```

A new intrinsic function to retrieve triangle object-space positions for the
currently hit triangle: `TriangleObjectPositions`.

> See Issue [Intrinsic Naming](#intrinsic-naming)

```cpp
/// \brief Retrieve current hit triangle object-space vertex positions
/// \returns position of vertex in object-space
///
/// Minimum shader model: 6.10
/// Allowed shader types: anyhit, closesthit.
///
/// Hit kind must be a triangle, where HitKind() returns either
/// HIT_KIND_TRIANGLE_FRONT_FACE (254) or HIT_KIND_TRIANGLE_BACK_FACE (255),
/// otherwise results are undefined.
///
/// Ordering of positions returned is based on the order used to build the
/// acceleration structure, and must match barycentric ordering.
BuiltInTrianglePositions TriangleObjectPositions();
```

Two new intrinsic methods on `RayQuery` to retrieve triangle object-space
positions for the candidate or committed triangle hits:
`CandidateTriangleObjectPositions`, and `CommittedTriangleObjectPositions`.

```cpp
template<uint ConstRayFlags>
class RayQuery {
  // Existing Methods: no change.

  // New Methods:

  /// \brief Retrieve candidate hit triangle object-space vertex positions
  /// \returns position of vertex in object-space
  ///
  /// Minimum shader model: 6.10
  ///
  /// The RayQuery must be in a state where `RayQuery::Proceed()` has returned
  /// true, and where `RayQuery::CandidateType()` returns
  /// `CANDIDATE_TYPE::CANDIDATE_NON_OPAQUE_TRIANGLE`, otherwise results
  /// are undefined.
  ///
  /// Ordering of positions returned is based on the order used to build the
  /// acceleration structure, and must match barycentric ordering.
  BuiltInTrianglePositions CandidateTriangleObjectPositions() const;

  /// \brief Retrieve committed hit triangle object-space vertex positions
  /// \returns position of vertex in object-space
  ///
  /// Minimum shader model: 6.10
  ///
  /// The RayQuery must be in a state with a committed triangle hit,
  /// where `CommittedStatus()` returns
  /// `COMMITTED_STATUS::COMMITTED_TRIANGLE_HIT`, otherwise results are
  /// undefined.
  ///
  /// Ordering of positions returned is based on the order used to build the
  /// acceleration structure, and must match barycentric ordering.
  BuiltInTrianglePositions CommittedTriangleObjectPositions() const;
};
```

One new intrinsic method for `HitObject` to retrieve triangle object-space
positions:

```c++
/// \brief Retrieve current hit triangle object-space vertex positions
/// \returns position of vertex in object-space
///
/// Minimum shader model: 6.10
///
/// Hit kind must be a triangle, where dx::HitObject::GetHitKind() returns
/// HIT_KIND_TRIANGLE_FRONT_FACE (254) or HIT_KIND_TRIANGLE_BACK_FACE (255),
/// or else results are undefined.
///
/// Ordering of positions returned is based on the order used to build the
/// acceleration structure, and must match barycentric ordering.
BuiltInTriangleHitPositions dx::HitObject::TriangleObjectPositions() const;
```

These return the object-space position for all vertices that make up the
triangle for a hit.  The hit is the current hit inside an
[AnyHit][dxr-anyhit] or [ClosestHit][dxr-closesthit] shader, or
the candidate or committed hit state of a RayQuery object, or the
committed hit state of a HitObject.

May only be used if the hit BLAS was built with
`D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_ALLOW_DATA_ACCESS`
(See [build flags defined here][dxr-build-flags]),
otherwise behavior is undefined.

These intrinsics may only be used with a triangle hit, otherwise behavior is
undefined. A shader can check for a triangle hit with
[`HitKind()`][dxr-hitkind], [`RayQuery::CandidateType()`][dxr-rq-can-type], or
[`CommittedStatus()`][dxr-rq-com-status], or
[`dx::HitObject::GetHitKind()`][dxr-ser-hit-kind] depending on the context.

Shader model 6.10 is required to use these intrinsics.

The DXIL implementation for all of these will be effectively lowered to an
implementation that behaves like the following HLSL pseudocode, given a
built-in function for the DXIL intrinsic.

```c++
vector<float, 9> __builtin_TriangleObjectPositions();
BuiltInTriangleHitPositions TriangleObjectPositions()
{
  vector<float, 9> LocalPositions;
  BuiltInTriangleHitPositions result;
  result.p0 = slice<0, 3>(LocalPositions);
  result.p1 = slice<3, 3>(LocalPositions);
  result.p2 = slice<6, 3>(LocalPositions);
  return result;
}
```

### Diagnostic Changes

New diagnostics:

* When any intrinsic is used and the Shader Model is less than 6.10:
  * `"<intrinsic> is only available on Shader Model 6.10 or newer"`
* When the `TriangleObjectPositions` intrinsic is used outside an `anyhit` or
  `closesthit` shader:
  * `"TriangleObjectPositions is not available in <stage> on Shader Model <shadermodel>"`

> Open Issue: [Use Availability Attributes](#use-availability-attributes)

#### Validation Changes

New Validation:

Existing infrastructure for enforcing shader model and shader stage
requirements for DXIL ops will be used.
Existing validation for RayQuery handle will be used.
Existing validation for HitObject handle will be used.

### Runtime Additions

#### Device Capability

Use of Triangle Object Positions intrinsics require Shader Model 6.10 and
[D3D12_RAYTRACING_TIER_1_0][dxr-tier].

Use of RayQuery intrinsics require Shader Model 6.10 and
[D3D12_RAYTRACING_TIER_1_1][dxr-tier].

Use of HitObject intrinsics require Shader Model 6.10 and
[D3D12_RATRACING_TIER_1_2][dxr-tier].

> Note: any raytracing tier requirement is implied by the shader stage
> requirement or use of RayQuery or use of HitObject, so no other changes
> are required in the compiler, aside from the shader model requirement.

## Testing

### Compiler output

* Test AST generation for each new HLSL intrinsic
* Test CodeGen for each new HLSL intrinsic
* Test final DXIL output for each HLSL intrinsic
  * Test static and dynamic vertex index
* Use D3DReflect test to verify min shader model of 6.10 with each intrinsic
  usage for library target.

### Diagnostics

* Test shader model diagnostic for each new HLSL intrinsic.
* Test shader stage diagnostic for `TriangleObjectPositions` intrinsic.

### DXIL Additions

```llvm
; Availability: Shader Model 6.10+
; Availability: anyhit,closesthit
; Function Attrs: nounwind readnone
declare <9 x float> @dx.op.triangleObjectPosition.f32(
      i32)  ; DXIL OpCode

; Availability: Shader Model 6.10+
; Function Attrs: nounwind readonly
declare <9 x float> @dx.op.rayQuery_CandidateTriangleObjectPosition.f32(
      i32,  ; DXIL OpCode
      i32)  ; RayQuery Handle

; Availability: Shader Model 6.10+
; Function Attrs: nounwind readonly
declare <9 x float> @dx.op.rayQuery_CommittedTriangleObjectPosition.f32(
      i32,  ; DXIL OpCode
      i32)  ; RayQuery Handle

; Availability: Shader Model 6.10+
; Function Attrs: nounwind readonly
declare <9 x float> @dx.op.hitObject_TriangleObjectPosition.f32(
      i32,                 ; DXIL OpCode
      %dx.types.HitObject) ; HitObject handle
```

New DXIL operations: `TriangleObjectPosition`,
`RayQuery_CandidateTriangleObjectPosition`,
`RayQuery_CommittedTriangleObjectPosition`,
`HitObject_TriangleObjectPosition`. These return a vector of 9 floats,
which is comprised of 3 components from vertex 0, followed by 3 floats
from vertex 1, followed by 3 floats from vertex 2.

All of these DXIL operations require Shader Model 6.10.

`TriangleObjectPosition` may only be called from entry functions of type
`anyhit` or `closesthit`.

`TriangleObjectPosition` has `readnone` attribute because it reads fixed state
for the shader invocation.
However, the new RayQuery methods must be `readonly` because they read from
RayQuery state, which is impacted by various other RayQuery methods.

### SPIR-V Mapping

The `TriangleObjectPositions()` HLSL intrinsic can be implemented against the
[`SPV_KHR_ray_tracing_position_fetch`](spv-ext) extension by effectively
using the following inline HLSL:

```c++
[[vk::builtin("HitTriangleVertexPositionsKHR")]]
float3 HitTriangleVertexPositionsKHR[3];

inline BuiltInTriangleHitPositions TriangleObjectPositions()
{
  BuiltInTriangleHitPositions result;
  result.p0 = HitTriangleVertexPositionsKHR[0];
  result.p1 = HitTriangleVertexPositionsKHR[1];
  result.p2 = HitTriangleVertexPositionsKHR[2];
  return result;
}
```

The `RayQuery` methods can be implemented against the same extension by mapping
HLSL intrinsic to the `OpRayQueryGetIntersectionTriangleVertexPositionsKHR`
opcode, with `Intersection` set to `RayQueryCandidateIntersectionKHR` for
`CandidateTriangleObjectPositions`, and `Intersection` set to
`RayQueryCommittedIntersectionKHR` for `CommittedTriangleObjectPositions`.

#### Runtime information

Use of any of these new DXIL ops will set the
`RuntimeDataFunctionInfo::MinShaderTarget` shader model to a minimum of 6.10 in
the `RDAT` part for the calling function.

## Testing

### Validation

* Test shader model requirement for all DXIL ops.
* Test shader stage requirement for `TriangleObjectPosition` op.
  * Include called no-inline function usage scenario.
* Test non-constant argument validation with each DXIL op.
* Test out-of-range argument validation with each DXIL op.

### Execution

Testing for triangle object position operations will be added to the existing
Raytracing HLK tests.

## Resolved Issues

### Return Type

Other approaches have been proposed for the return type of this intrinsic:

* Return built-in struct containing all three vertices as `float3` fields:
  * Benefit: all values returned from one call
  * Benefit: user can use same struct elsewhere and easily assign to result of call
  * Benefit: no appearance of native dynamic indexing support
  * Benefit: should work with DXC intrinsic system relatively easily
  * Drawback: adds a new built-in type which effectively matches the memory layout of matrices or arrays
* Add a vertex index parameter to the intrinsic and return a single position: `float3`:
  * Drawback: three calls required to store all vertices in a single variable in HLSL
  * Drawback: checking index requires an explicit diagnostic check
  * Benefit: A dynamic vertex index would easily lower directly to underlying DXIL op parameter without ugly codegen, if support for this was desired.
* Use a matrix return type: `float3x3`:
  * Benefit: resulting data is likely to be used for linear algebra
  * Benefit: avoids adding a new built-in type
  * Drawback: It's not really a matrix
  * Drawback: language suggests native indexing supported, which would result in ugly codegen
  * Drawback: layout isn't obvious
  * Drawback: matrices can participate in implicit conversions that are likely to be programmer bugs, e.g. truncation to vector
* Use a by-value array return type: `float3[3]`:
  * Benefit: checking static index is automatic
  * Benefit: convergence with SPIR-V
  * Benefit: avoids adding a new built-in type
  * Drawback: likely difficult to introduce this into intrinsic system
  * Drawback: language suggests native indexing supported, which would result in ugly codegen
  * Drawback: might want to remove return array-by-value support in future HLSL version, as this is not allowed in C++.
* Use a constant reference-to-array return type: `const float3[3] &`:
  * Benefit: checking static index is automatic
  * Drawback: likely difficult to introduce this into intrinsic system
  * Drawback: language suggests native indexing supported, which would result in ugly codegen
* Return a special object type that implements the array subscript, returning `float3`:
  * Benefit: precedent in DXC intrinsic system for such a device
  * Drawback: checking index requires custom diagnostic check
  * Drawback: language suggests native indexing supported, which would result in ugly codegen
  * Drawback: new special built-in object with special codegen/lowering
  * Drawback: three calls+subscript operations required to store all vertices somewhere, unless intermediate object is exposed somehow
  * Drawback: potential exposure of intermediate object could complicate things

**Resolution**: Return built-in struct containing all three positions.

### Return type for DXIL ops

Several options are available for how to define the DXIL ops for this feature:

* Return one component at a time
* Use built-in struct containing all positions.
  * struct layout up for debate
  * actual form in op signature up for debate (return value, return pointer, sret - write to output pointer arg?).
* Use native llvm array type, actual form in op signature up for debate.
* Leverage shader model 6.9 vectorized DXIL and return
  * one `<3 x float>` per call, taking a vertex ID as a parameter
  * one `<9 x float>` with all values at once

**Resolution**: Use `<9 x float>`. Since the HLSL API returns all components in one call, there
is no opportunity (outside of dead code elimination) to omit some calls, so we might as well just
return all components in DXIL as well. This structure is straightforward with SM6.9's value
semantics with long vectors, and it's trivial to shuffle the resulting vector to convert to
the HLSL return value.

### Intrinsic Naming

`TriangleObjectPositions` doesn't match the name used in SPIR-V, which is more
like `HitTriangleVertexPositions`.  Should we adjust naming to align?

**Resolution**: `TriangleObjectPositions` aligns with our conventions for related
intrinsics.

### Share OpCodeClass

Should RayQuery DXIL methods share OpCodeClass for the DXIL ops?
There doesn't appear to be any reason they couldn't, since they have identical
signatures and function attributes.  If so, these could be replaced with
`dx.op.rayQuery_TriangleObjectPosition.f32` which would differentiate between
candidate and committed via the DXIL OpCode.  This would reduce the number of
redundant DXIL function declarations, and thus the size of DXIL by a small
amount when both are used.

This would diverge from other RayQuery methods that are split into different
opcode classes for no good reason.

**Resolution**: Use separate OpCodeClass for consistency with related ops.

### Use Availability Attributes

Instead of custom diagnostics for these functions, we could potentially use
availability attributes for a more general mechanism.  For DXC, this will
require some investigation into the intrinsic system to see how these
attributes could be added to intrinsic function declarations that are created
on-demand in a custom way.

**Resolution**: This seems worthwhile to investigate in Clang but out of scope for DXC.

## Open Issues

No outstanding open issues.

## Acknowledgments

* Amar Patel

<!-- External References -->

[dxr-tri-obj-pos]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#triangleobjectposition> "TriangleObjectPositions"
[dxr-rq-can-tri-obj-pos]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-candidatetriangleobjectposition> "RayQuery CandidateTriangleObjectPositions"
[dxr-rq-com-tri-obj-pos]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-committedtriangleobjectposition> "RayQuery CommittedTriangleObjectPositions"
[dxr-anyhit]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#any-hit-shader> "AnyHit Shader"
[dxr-closesthit]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#closest-hit-shader> "ClosestHit Shader"
[dxr-build-flags]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#d3d12_raytracing_acceleration_structure_build_flags> "D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAGS"
[dxr-hitkind]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#hitkind> "HitKind()"
[dxr-rq-can-type]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-candidatetype> "RayQuery CandidateType"
[dxr-rq-com-status]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-committedstatus> "RayQuery CommittedStatus"
[dxr-ser-hit-kind]: <https://microsoft.github.io/DirectX-Specs/d3d/Raytracing.html#hitobject-gethitkind> "dx::HitObject::GetHitKind()"
[dxr-tier]: <https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#d3d12_raytracing_tier> "D3D12_RAYTRACING_TIER"

