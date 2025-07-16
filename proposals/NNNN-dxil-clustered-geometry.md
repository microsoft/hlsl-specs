<!-- {% raw %} -->

# DXIL support for Clustered Geometry in Raytracing

---

* Proposal: [NNNN](NNNN-dxil-clustered-geometry.md)
* Author(s): [Author 1](https://github.com/author_username)
* Sponsor: [Amar Patel](https://github.com/amarpMSFT)
* Status: **Under Consideration**

---

## Introduction

See the intro and motivation in the complementary [HLSL](NNNN-hlsl-clustered-geometry.md) proposal, applicable here.

---

### DXIL

| Opcode | Opcode name | Description
|:---    |:---         |:---
XXX      | ClusterID | Returns the cluster ID of this hit
XXX + 1  | RayQuery_CandidateClusterID  | Returns the candidate hit cluster ID
XXX + 2  | RayQuery_CommittedClusterID  | Returns the committed hit cluster ID
XXX + 2  | HitObject_ClusterID  | Returns the cluster ID of this committed hit

---

#### ClusterID DXIL Opcode

```DXIL
declare i32 @dx.op.clusterID(
    i32)                 ; Opcode (ClusterID)
    nounwind readnone
```

Valid shader kinds defined in [ClusterID HLSL](#clusterid).

---

#### RayQuery_CandidateClusterID DXIL Opcode

```DXIL
declare i32 @dx.op.rayQuery_StateScalar.i32(
    i32,                 ; Opcode (RayQuery_CandidateClusterID)
    i32)                 ; RayQuery handle
    nounwind readonly
```

Validation errors:
* Validate that the RayQuery handle is not `undef`.

---

#### RayQuery_CommittedClusterID DXIL Opcode

```DXIL
declare i32 @dx.op.rayQuery_StateScalar.i32(
    i32,                 ; Opcode (RayQuery_CommittedClusterID)
    i32)                 ; RayQuery handle
    nounwind readonly
```

Validation errors:
* Validate that the RayQuery handle is not `undef`.

---

#### HitObject_ClusterID DXIL Opcode

```DXIL
declare i32 @dx.op.hitObject_StateScalar.i32(
    i32,                 ; Opcode (HitObject_ClusterID)
    %dx.types.HitObject) ; HitObject
    nounwind readnone
```

Validation errors:
* Validate that the HitObject is not `undef`.

---

### Diagnostic Changes

This proposal does not introduce or remove diagnostics or warnings.

### Runtime Additions

TODO: link the DXR spec propsoal when available

## Testing

### Unit Tests

#### CodeGen & AST Tests

* Expected AST for new implicit HLSL ops.
* Lowering from HLSL to HL.
* Lowering from HL to DXIL.
* Lowering from HLSL to DXIL.

#### Diagnostics Tests

* Expected error when ClusterID builtins called from unsupported shader kinds.

### Validation Tests

* Valid calls to new DXIL ops pass validation.
* Invalid calls fail validation (undef `i32` RayQuery handle or `%dx.types.HitObject` HitObject parameter).

### Execution Tests

#### ClusterID Execution Tests

Test in both `anyhit` and `closesthit` shader kinds.

* Query for CLAS hit returns expected Cluster ID.
* Query for non-clustered BLAS hit returns `CLUSTER_ID_INVALID`.

#### RayQuery Execution Tests

Test both [RayQuery::CandidateClusterID](#rayquery-candidateclusterid) and [RayQuery::CommittedClusterID](#rayquery-committedclusterid).
Builtins to test in the these RayQuery object states:

* Queries for CLAS committed hits return expected Cluster ID (`COMMITTED_TRIANGLE_HIT`).
* Query for committed cluster ID in no-hit-committed state returns `CLUSTER_ID_INVALID`.
* Queries for candidate cluster ID for CLAS candidate hits return expected Cluster ID (`CANDIDATE_NON_OPAQUE_TRIANGLE` and when first call to `Proceed` returns `FALSE` ).
* Queries for non-clustered BLAS candidate/committed hits return `CLUSTER_ID_INVALID`.

#### HitObject Execution Tests

Test CLAS and non-CLAS hit return expected values for candidate hit.
Builtin [HitObject::GetClusterID](#hitobjectgetclusterid) to test in these HitObject setups:

* Add `HitObject::FromRayQuery` + `HitObject::GetClusterID` variants in [RayQuery execution tests](#rayquery-execution-tests).
* Test expected cluster ID value for HitObject obtained from `HitObject::TraceRay` (CLAS hit, CLAS miss, non-CLAS hit).
* Test `CLUSTER_ID_INVALID` for HitObject constructed from `HitObject::MakeMiss` and `HitObject::MakeNop`. 

<!-- {% endraw %} -->
