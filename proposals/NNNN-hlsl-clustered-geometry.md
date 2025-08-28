<!-- {% raw %} -->

# HLSL support for Clustered Geometry in Raytracing

---

* Proposal: [NNNN](NNNN-hlsl-clustered-geometry.md)
* Author(s): [Jan Schmid](https://github.com/jschmid-nvidia), [Simon Moll](https://github.com/simoll)
* Sponsor: [Amar Patel](https://github.com/amarpMSFT)
* Status: **Under Consideration**

---

## Introduction

Acceleration structure build times can become a bottleneck in raytracing
applications that require large amounts of dynamic geometry. Example scenarios
include new geometry being streamed in from disk, high numbers of animated
objects, level-of-detail systems, or dynamic tessellation.

Clustered Geometry is a proposed future DXR feature that aims to address this 
issue by enabling the application to construct bottom-level acceleration structures 
from previously generated clusters of primitives, resulting in significant speedups 
in acceleration structure build times. The DXR spec details for this are not available 
yet, but as an example for now see [NVIDIA's blog](https://developer.nvidia.com/blog/nvidia-rtx-mega-geometry-now-available-with-new-vulkan-samples/) describing the overall concept of clustered 
geometry (among other topics). 

How clustered geometry gets exposed in D3D overall is to be determined but this document is
certainly a part: a proposal for the HLSL operations needed for clustered geometry.

Also see the complementary [DXIL](NNNN-dxil-clustered-geometry.md) proposal.

---

## Motivation

Clustered Geometry refers to a building block for Bottom Level Acceleration Structures 
(BLASes). Most of the details of what a cluster is are out of scope for this spec.  
What's relevant is that the application can build BLASes out of cluster building
blocks.  When raytracing, hit shaders will want to know the ID of the cluster that is hit
so the shader can do things like look up cluster-specific user data.  Hence the need for a `ClusterID()` intrinsic.

This isn't an index into the clusters in a given BLAS but rather an ID assigned by 
the user for each cluster in a BLAS.  Different BLASs could reuse simmilar building blocks, and 
thus share cluster ID.

---

## HLSL

---

### Enums

```C
enum CLUSTER_ID_CONSTANTS : uint
{
    CLUSTER_ID_INVALID = 0xffffffff,
};
```

ClusterID values returned by [ClusterID()](#clusterid) with predefined meaning

Value                | Definition
-----                | ----
`CLUSTER_ID_INVALID` | Returned if a BLAS was intersected that was not constructed from CLAS

---

### DXR 1.0 System Value Intrinsics

A new DXR System Value Intrinsic is added to support fetching the `ClusterID` of an intersected CLAS.

---

#### ClusterID

```C
uint ClusterID()
```

Returns a `uint` containing the user-defined `ClusterID` value a CLAS was
built with. If a non-clustered BLAS was intersected, `CLUSTER_ID_INVALID`
is returned.

The following table shows which shaders can access it:
| **values \\ shaders**                                     | ray generation | intersection | any hit | closest hit | miss | callable |
|:---------------------------------------------------------:|:--------------:|:------------:|:-------:|:-----------:|:----:|:--------:|
| *Primitive/object space system values:*               |                |              |         |         |            |      |
| uint [ClusterID()](#clusterid)                            |                |              |   \*    |    \*   |            |      |

---

## Extension to DXR 1.1 RayQuery API

New intrinsics [CandidateClusterID()](#rayquery-candidateclusterid) and 
[CommittedClusterID()](#rayquery-committedclusterid) are added to `RayQuery`.
Behavior of all other intrinsics is unchanged.

---

### RayQuery intrinsics

The following table lists intrinsics available when
[RayQuery::Proceed()](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-proceed) returned `TRUE`,
meaning a type of hit candidate that requires shader evaluation has been found.
Methods named `Committed*()` in this table may actually not be available
depending on the current [CommittedStatus()](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-committedstatus)
(i.e. what type of hit has been committed yet, if any) - this is further
clarified in another table further below.

| **Intrinsic** \ **CandidateType()** | `HIT_CANDIDATE_NON_OPAQUE_TRIANGLE` | `HIT_CANDIDATE_PROCEDURAL_PRIMITIVE`
|:--------------|:-----------:|:-----------:|
| uint [CandidateClusterID()](#rayquery-candidateclusterid)|   \*      |              |
| uint [CommittedClusterID()](#rayquery-committedclusterid)|   \*      |              |

The following table lists intrinsics available depending on the current
[COMMITTED_STATUS](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#committed_status) (i.e. what type of
hit has been committed, if any). This applies regardless of whether
[RayQuery::Proceed()](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/Raytracing.md#rayquery-proceed) has returned
`TRUE` (shader evaluation needed for traversal), or `FALSE` (traversal
complete). If `TRUE`, additional methods than those shown below are
available (see the above table).

| **Intrinsic** \ **CommittedStatus()** | `COMMITTED_TRIANGLE_HIT` | `COMMITTED_PROCEDURAL_PRIMITIVE_HIT` | `COMMITTED_NOTHING` |
|:--------------|:-----------:|:-----------:|:-----------:|
| uint [CommittedClusterID()](#rayquery-committedclusterid)|   \*      |             |        |

---

#### RayQuery CandidateClusterID

The user-provided `ClusterID` of the intersected CLAS, if a Cluster BLAS was
intersected for the current hit candidate.
Returns `CLUSTER_ID_INVALID` if a non-Cluster BLAS was intersected.

```C++
uint RayQuery::CandidateClusterID();
```

[RayQuery intrinsics](#rayquery-intrinsics) illustrates when this is valid to
call.
Lowers to [RayQuery_CandidateClusterID DXIL Opcode](#rayquery_candidateclusterid-dxil-opcode).

---

#### RayQuery CommittedClusterID

The user-provided `ClusterID` of the intersected CLAS, if a Cluster BLAS was
intersected for the closest hit committed so far.
Returns `CLUSTER_ID_INVALID` if a non-Cluster BLAS was intersected.

```C++
uint RayQuery::CommittedClusterID();
```

[RayQuery intrinsics](#rayquery-intrinsics) illustrates when this is valid to
call.
Lowers to [RayQuery_CommittedClusterID DXIL Opcode](#rayquery_committedclusterid-dxil-opcode).

---

### Extension to the DXR 1.2 HitObject API

Cluster Geometries are also supported with the HitObject feature.
The following intrinsic is added to `HitObject` type.

#### HitObject::GetClusterID

```C
uint HitObject::GetClusterID();
```

Returns the user-provided `ClusterID` of the intersected CLAS of a hit.
Returns `CLUSTER_ID_INVALID` if a non-Cluster BLAS was intersected or if
the `HitObject` does not encode a hit.
Lowers to [HitObject_ClusterID DXIL Opcode](#hitobject_clusterid-dxil-opcode).

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

<!-- {% endraw %} -->
