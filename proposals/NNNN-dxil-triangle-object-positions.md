<!-- {% raw %} -->

# DXIL TriangleObjectPositions

* Proposal: [NNNN](NNNN-triangle-object-positions.md)
* Author(s): [Tex Riddell](https://github.com/tex3d)
* Sponsor: [Tex Riddell](https://github.com/tex3d)
* Status: **Under Consideration**

---

## Introduction

See the intro and motivation in the complementary [HLSL](NNNN-dxil-triangle-object-positions.md) proposal, applicable here.

---

### Interchange Format Additions

```llvm
; Availability: Shader Model (Version TBD)+
; Availability: anyhit,closesthit
; Function Attrs: nounwind readnone
declare f32 @dx.op.triangleObjectPosition.f32(
      i32,  ; DXIL OpCode
      i32,  ; VertexInTri, immediate constant [0..2]
      i32)  ; ColumnIndex, immediate constant [0..2]

; Availability: Shader Model (Version TBD)+
; Function Attrs: nounwind readonly
declare f32 @dx.op.rayQuery_CandidateTriangleObjectPosition.f32(
      i32,  ; DXIL OpCode
      i32,  ; RayQuery Handle
      i32,  ; VertexInTri, immediate constant [0..2]
      i32)  ; ColumnIndex, immediate constant [0..2]

; Availability: Shader Model (Version TBD)+
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

All of these DXIL operations require Shader Model (Version TBD).

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
`RuntimeDataFunctionInfo::MinShaderTarget` shader model to a minimum of (Version TBD) in
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

**Resolution**: Keep DXIL op scalar for consistency with other ops.

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
