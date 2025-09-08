<!-- {% raw %} -->

# HLSL TriangleObjectPositions

* Proposal: [NNNN](NNNN-triangle-object-positions.md)
* Author(s): [Tex Riddell](https://github.com/tex3d), [Jesse Natalie](https://github.com/jenatali)
* Sponsor: [Jesse Natalie](https://github.com/jenatali)
* Status: **Under Consideration**

---

## Introduction

This proposal adds intrinsics that can be called from an Any hit or Closest
hit shader to obtain the positions of the vertices for the triangle that has
been hit.

---

## Motivation

Developers often need to know the positions of the vertices for the triangle
that was hit in an Any/Closest hit shader. Currently, the only way to do this is
for the developer to provide separate buffers containing this data. This
information is also available in the acceleration structure, but there is
currently no way to access it.

If developers can access this data from their shader code then this will remove
the need have a duplicate copy of it. In addition, this will provide drivers
with opportunities to optimize the data layout for their implementations.

---

## Proposed solution

Add intrinsics to look up the object-space vertex positions of the triangle for
the current hit, or RayQuery candidate/committed hits.

For context, see related sections in DirectX Raytracing Specification:
[TriangleObjectPositions][dxr-tri-obj-pos],
[RayQuery::CandidateTriangleObjectPositions][dxr-rq-can-tri-obj-pos],
[RayQuery::CommittedTriangleObjectPositions][dxr-rq-com-tri-obj-pos].

---

## Detailed design

---

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
/// otherwise undefined behavior results.
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
  /// `CANDIDATE_TYPE::CANDIDATE_NON_OPAQUE_TRIANGLE`, otherwise undefined
  /// behavior results.
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
  /// `COMMITTED_STATUS::COMMITTED_TRIANGLE_HIT`, otherwise undefined behavior
  /// results.
  ///
  /// Ordering of positions returned is based on the order used to build the
  /// acceleration structure, and must match barycentric ordering.
  BuiltInTrianglePositions CommittedTriangleObjectPositions() const;
};
```

These return the object-space position for all vertices that make up the
triangle for a hit.  The hit is the current hit inside an
[AnyHit][dxr-anyhit] or [ClosestHit][dxr-closesthit] shader, or
the candidate or committed hit state of a RayQuery object.

May only be used if the hit BLAS was built with
`D3D12_RAYTRACING_ACCELERATION_STRUCTURE_BUILD_FLAG_ALLOW_DATA_ACCESS`
(See [build flags defined here][dxr-build-flags]),
otherwise behavior is undefined.

These intrinsics may only be used with a triangle hit, otherwise behavior is
undefined. A shader can check for a triangle hit with
[`HitKind()`][dxr-hitkind], [`RayQuery::CandidateType()`][dxr-rq-can-type], or
[`CommittedStatus()`][dxr-rq-com-status] depending on the context.

Shader model 6.10 is required to use these intrinsics.

---

### Diagnostic Changes

New diagnostics:

* When any intrinsic is used and the Shader Model is less than 6.10:
  * `"<intrinsic> is only available on Shader Model 6.10 or newer"`
* When the `TriangleObjectPositions` intrinsic is used outside an `anyhit` or
  `closesthit` shader:
  * `"TriangleObjectPositions is not available in <stage> on Shader Model <shadermodel>"`

> Open Issue: [Use Availability Attributes](#use-availability-attributes)

---

#### Validation Changes

New Validation:

* When the VertexInTri or ColumnIndex is not an immediate constant or out of
  range:
  * `"<DXIL Op> %select{VertexInTri|ColumnIndex}0 (%1) must be an immediate constant value in range [0..2]"`

Existing infrastructure for enforcing shader model and shader stage
requirements for DXIL ops will be used.
Existing validation for RayQuery handle will be used.

---

### Runtime Additions

---

#### Device Capability

Use of Triangle Object Positions intrinsics require Shader Model 6.10 and
[D3D12_RAYTRACING_TIER_1_0][dxr-tier].

> Note: any raytracing tier requirement is implied by the shader stage
> requirement or use of RayQuery, so no other changes are required in the
> compiler, aside from the shader model requirement.

---

## Testing

---

### Compiler output

* Test AST generation for each new HLSL intrinsic
* Test CodeGen for each new HLSL intrinsic
* Test final DXIL output for each HLSL intrinsic
  * Test static and dynamic vertex index
* Use D3DReflect test to verify min shader model of 6.10 with each intrinsic
  usage for library target.

---

### Diagnostics

* Test shader model diagnostic for each new HLSL intrinsic.
* Test shader stage diagnostic for `TriangleObjectPositions` intrinsic.

---

### Interchange Format Additions

```llvm
; Availability: Shader Model 6.10+
; Availability: anyhit,closesthit
; Function Attrs: nounwind readnone
declare f32 @dx.op.triangleObjectPosition.f32(
      i32,  ; DXIL OpCode
      i32,  ; VertexInTri, immediate constant [0..2]
      i32)  ; ColumnIndex, immediate constant [0..2]

; Availability: Shader Model 6.10+
; Function Attrs: nounwind readonly
declare f32 @dx.op.rayQuery_CandidateTriangleObjectPosition.f32(
      i32,  ; DXIL OpCode
      i32,  ; RayQuery Handle
      i32,  ; VertexInTri, immediate constant [0..2]
      i32)  ; ColumnIndex, immediate constant [0..2]

; Availability: Shader Model 6.10+
; Function Attrs: nounwind readonly
declare f32 @dx.op.rayQuery_CommittedTriangleObjectPosition.f32(
      i32,  ; DXIL OpCode
      i32,  ; RayQuery Handle
      i32,  ; VertexInTri, immediate constant [0..2]
      i32)  ; ColumnIndex, immediate constant [0..2]
```

New DXIL operations: `TriangleObjectPosition`,
`RayQuery_CandidateTriangleObjectPosition`,
`RayQuery_CommittedTriangleObjectPosition`.
These accept an immediate constant `VertexInTri`, and immediate constant
`ColumnIndex` to read a single `x`, `y`, or `z` component from the specified
vertex position for the triangle.

All of these DXIL operations require Shader Model 6.10.

`TriangleObjectPosition` may only be called from entry functions of type
`anyhit` or `closesthit`.

`TriangleObjectPosition` has `readnone` attribute because it reads fixed state
for the shader invocation.
However, the new RayQuery methods must be `readonly` because they read from
RayQuery state, which is impacted by various other RayQuery methods.

---

### Diagnostic Changes

---

#### Validation Changes

New Validation:

* When the VertexInTri or ColumnIndex is not an immediate constant or out of
  range:
  * `"<DXIL Op> %select{VertexInTri|ColumnIndex}0 (%1) must be an immediate constant value in range [0..2]"`

Existing infrastructure for enforcing shader model and shader stage
requirements for DXIL ops will be used.
Existing validation for RayQuery handle will be used.

---

### Runtime Additions

---

#### Runtime information

Use of any of these new DXIL ops will set the
`RuntimeDataFunctionInfo::MinShaderTarget` shader model to a minimum of 6.10 in
the `RDAT` part for the calling function.

---

## Testing

---

### Validation

* Test shader model requirement for all DXIL ops.
* Test shader stage requirement for `TriangleObjectPosition` op.
  * Include called no-inline function usage scenario.
* Test non-constant argument validation with each DXIL op.
* Test out-of-range argument validation with each DXIL op.

---

### Execution

Testing for triangle object position operations will be added to the existing
Raytracing HLK tests.

---

## Resolved Issues

---

### Return Type

Other approaches have been proposed for the return type of this intrinsic:

* Current approach: return built-in struct containing all three vertices as `float3` fields:
  * Benefit: all values returned from one call
  * Benefit: user can use same struct elsewhere and easily assign to result of call
  * Benefit: no appearance of native dynamic indexing support
  * Benefit: should work with DXC intrinsic system relatively easily
* Add a vertex index parameter to the intrinsic and return a single position: `float3`:
  * Drawback: three calls required to store all vertices in a single variable in HLSL
  * Drawback: checking index requires an explicit diagnostic check
  * Benefit: A dynamic vertex index would easily lower directly to underlying DXIL op parameter without ugly codegen, if support for this was desired.
* Use a matrix return type: `float3x3`:
  * Drawback: It's not really a matrix
  * Drawback: language suggests native indexing supported, which would result in ugly codegen
  * Drawback: layout isn't obvious
* Use a by-value array return type: `float3[3]`:
  * checking static index is automatic
  * Drawback: likely difficult to introduce this into intrinsic system
  * Drawback: language suggests native indexing supported, which would result in ugly codegen
  * Drawback: might want to remove return array-by-value support in future HLSL version, as this is not allowed in C++.
* Use a constant reference-to-array return type: `const float3[3] &`:
  * checking static index is automatic
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

---

### Intrinsic Naming

`TriangleObjectPositions` doesn't match the name used in SPIR-V, which is more
like `HitTriangleVertexPositions`.  Should we adjust naming to align?

**Resolution**: `TriangleObjectPositions` aligns with our conventions for related
intrinsics.

---

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

---

### Use Availability Attributes

Instead of custom diagnostics for these functions, we could potentially use
availability attributes for a more general mechanism.  For DXC, this will
require some investigation into the intrinsic system to see how these
attributes could be added to intrinsic function declarations that are created
on-demand in a custom way.

**Resolution**: This seems worthwhile to investigate in Clang but out of scope for DXC.

---

## Open Issues

---

### Built-in struct return type

`BuiltInTrianglePositions` isn't necessarily the best name for the struct,
so suggestions for a better name are welcome.

---

### Return type for DXIL ops

There is some open debate about the return type used for DXIL operations.
The current approach is to return one component at a time, as this matches the
similar pre-existing operations for looking up matrix components for
object/world transforms.  Keeping the DXIL operations consistent with the other
operations in the same area would seem to carry less risk and keep the DXIL
more regular.  This seems to outweigh a desire to do something special here.

A couple other options:

* Use built-in struct containing all positions.
  * struct layout up for debate
  * actual form in op signature up for debate (return value, return pointer, sret - write to output pointer arg?).
* Use native llvm array type, actual form in op signature up for debate.
* Leverage shader model 6.9 vectorized DXIL and return
  * one `<3 x float>` per call, taking a vertex ID as a parameter
  * one `<9 x float>` with all values at once

**Proposed Resolution**: Keep DXIL op scalar for consistency with other ops.

---

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

<!-- {% endraw %} -->
