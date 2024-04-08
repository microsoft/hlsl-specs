# Mesh Nodes

* Proposal: [0019](0019-mesh-nodes.md)
* Author(s): [Tex Riddell](https://github.com/tex3d), [Amar Patel](https://github.com/amarpMSFT)
* Sponsor: [Tex Riddell](https://github.com/tex3d)
* Status: **Under Consideration**
* Proposed Version: SM 6.9 experimental

## Introduction

This spec describes the HLSL and DXIL shader details for a new 'mesh' launch
type for the Work Graph node shader, modelled after the existing mesh shader
stage. See the
[mesh nodes](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#mesh-nodes)
section of the Work Graphs spec for the surrounding details.

## Motivation

Work graphs are a great way to generate compute work on the GPU, and there is a
lot of interest in expanding this to scheduling graphics work as a replacement
for execute indirect.
Mesh shader is a natural place to start.
It is already a compute shader, and requires fewer modifications to adapt to a
node shader than the vertex shader would.
The input record can replace the mesh payload, and there is no input
signature that would require special parameter handling and connection to an
intermediate fixed-function input assembler stage.
There are also fewer details to work out for the integration with work
graphs.

## Proposed solution

Add a new node launch type `"mesh"`, indicating a mesh shader leaf graphics node.
The new mesh node is based on a combination of a broadcast launch node and a
mesh shader. See more details about the runtime context in the work graphs spec
[here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#mesh-nodes).

Use the node input record as the mesh shader input payload, instead of an
explicit `payload` argument.
Like a broadcast node input record, this must have an `SV_DispatchGrid` field
indicating the grid size when `[NodeMaxDispatchGrid(x,y,z)]` is used.

The same system value inputs supported for broadcast launch nodes and mesh
shaders are supported in the same way here:
`SV_DispatchThreadID`, `SV_GroupThreadID`, `SV_GroupIndex`, `SV_GroupID`,
with the exception of `SV_ViewID` (see [Open Questions](open-questions)).

Outputs to other nodes are not allowed - the mesh node must be a leaf in the
work graph.

The new `mesh` node supports outputs inherited from the mesh shaders:
`vertices`, `primitives`, and `indices`.  As with mesh shaders, the
`SetMeshOutputCounts` intrinsic must be used before writing to these outputs.
As with mesh shaders, the `vertices` and `primitives` outputs are combined to
provide the inputs the pixel shader requires.
Each of these require a user defined structure using semantics on fields, where
fields of HLSL basic types will be used to generate signature elements in the
same way they are for mesh shader signature handling.

Amplification shaders are not supported in this context, since work graph node
shaders provide the function of generating the mesh node dispatches on the GPU.

Mesh nodes can also be used as one or more entrypoints in a work graph
(standalone since they can't output to other nodes),
in which case the input record (payload) is supplied from DispatchGraph()
at the API just like any other work graph entrypoint input.

A complete mesh node is defined at the API by first creating a
[generic program](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#d3d12_generic_program_desc)
including the mesh node function name, a pixel shader, and other optional state,
then referring to that program in a
[work graph program node](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#d3d12_program_node),
which may optionally override node properties, such as the node ID.

See the [Mesh Nodes](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#mesh-nodes)
section of the work graphs spec, along with sections linked from there, to
complete the picture.

### Example Syntax

```cpp
struct MyMeshRecord {
  float3 perMeshConstant;
  uint3 dispatchGrid : SV_DispatchGrid;
}

groupshared uint numVerts;
groupshared uint numPrims;

#define MAX_VERTS 16
#define MAX_PRIMS 8

[shader("node")]
[NodeLaunch("mesh")]
[NodeIsProgramEntry]
[NodeID("meshNode", 2)]
[NodeLocalRootArgumentsTableIndex(4)]
[NumThreads(4,4,1)]
[NodeMaxDispatchGrid(16,16,1)]
[OutputTopology("triangle")]
void MyMeshNode(
    DispatchNodeInputRecord<MyMeshRecord> nodeInput,
    out vertices PerVertexValues verts[MAX_VERTS],
    out primitives PerPrimitiveValues prims[MAX_PRIMS],
    out indices uint3 tris[MAX_PRIMS],
    in uint gi : SV_GroupIndex )
{
  float3 data = nodeInput.Get().perMeshConstant;
  // compute numVerts, numPrims...
  SetMeshOutputCounts(numVerts, numPrims);
  // Cooperate across group to write output arrays...
  if (gi < numVerts) {
    verts[gi] = ComputeVertexValues(gi);
  }
  if (gi < numPrims) {
    prims[gi] = ComputePrimValues(gi);
    tris[gi] = ComputeTri(gi);
  }
}
```

### Compiling Experimental Mesh Node Shaders

As a kind of node shader in work graphs, mesh node shaders are functions
defined in a library.
To use the experimental feature, you must compile HLSL with options:
`-T lib_6_9 -select-validator internal`.
This produces a DXIL library for use with the state object API in accordance
with the work graphs spec
[here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#mesh-nodes).

`-select-validator internal` is for use during feature development to avoid
using an external released validator that does not recognize the feature or
the in-development shader model being used.

In the API, mesh nodes may be paired with an ordinary pixel shader compiled to
any `ps_6_*` profile.  The pixel shader would not be compiled into a library
target like the mesh node is.

## Detailed design

### HLSL Additions

A new `[NodeLaunch("mesh")]` mode for `[shader("node")]` indicates a mesh node
shader entry point.  This section describes this new entry type.

#### Function Attributes

Supports attributes from both broadcasting launch node and mesh shader, using
`[NodeLaunch("mesh")]`. The following table is strictly from the perspective of
mesh node shaders. Other values, or different descriptions could apply for
other node or shader types.
See [Shader function attributes in Work Graphs spec](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)
for more detailed descriptions of the node function attributes.

| Attribute | Required | Description |
|--|--|--|
| `[shader("node")]` | Yes | Indicates a node shader entry point |
| `[NodeLaunch("mesh")]` | Yes | Signifies a mesh node |
| `[NumThreads(x,y,z)]` | Yes | Specifies the launch size of the threadgroup of the Mesh shader, just like with compute shader. The number of threads can not exceed `X * Y * Z = 128`. See [numthreads](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#numthreads) in the Mesh Shader spec. |
| `[OutputTopology(`*topology*`)]` | Yes | Specifies the topology for the output primitives of the mesh shader. *topology* must be `"line"` or "`triangle"`. See [outputtopology](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#outputtopology) in the Mesh Shader spec. |
| `[NodeDispatchGrid(x,y,z)]` | Yes, unless `NodeMaxDispatchGrid` is defined | Declare a fixed dispatch grid size for use with this node. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeMaxDispatchGrid(x,y,z)]` | Yes, unless `NodeDispatchGrid` is defined | Declare a maximum dispatch grid size for use with this node.  In this case, the dispatch grid size is defined by the record field with the `SV_DispatchGrid` semantic. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeIsProgramEntry]` | No | Node can be launched directly from the API in addition to or instead of from an upstream node in the work graph. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeID("nodeName")]` or `[NodeID("nodeName",arrayIndex)]` | No | Name for the node; uses function name if omitted. Optional `uint arrayIndex` overrides the default index of `0`. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeLocalRootArgumentsTableIndex(index)]` | No | `uint index` indicates the record index into the local root arguments table bound when the work graph is used. May be omitted or set to `-1` (equivalent to omitting).  If omitted and a local root signature is used, the runtime will auto-assign the index. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeShareInputOf("nodeName")]` or `[NodeShareInputOf("nodeName",arrayIndex)]` | No | Share the input of the specified NodeID with this node. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |

#### Function Parameters

##### Input Record

Zero or one read-only input record declaration is supported for the mesh node entry.
Types supported are the same as for a broadcasting launch node shader.
The input record takes the place of the `payload` in the mesh shader.

| Input | Description |
|-|-|
| `DispatchNodeInputRecord<`*recordType*`>` | read only node input |
| [`globallycoherent`] `RWDispatchNodeInputRecord<`*recordType*`>` | Shared R/W access to input record across launched shaders. `globallycoherent` required for any cross-group coherency. |
| *none* | Input record can be omitted when there is no record content. `[NodeDispatchGrid(...)]` is then required to specify a fixed grid size. |

One system value is supported inside the *recordType* for `SV_DispatchGrid`,
see [here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#sv_dispatchgrid)
for more details, where mesh nodes are just like broadcast launch nodes in
this regard.
Any other semantics on fields in the record structure are ignored.

See the work graphs spec
[Node input declaration](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#node-input-declaration)
section under options for broadcasting launch for more detail.

##### Input System Values

For input values outside the input record, mesh nodes support the `broadcasting` launch
[node shader system values](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#node-shader-system-values).
These are the same [system values supported by mesh shaders](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#system-value-semantics),
with the exception of `SV_ViewID`.

| system value semantic | type    | description |
|-----------------------|---------|-------------|
| `SV_GroupThreadID`    | `uint3` | Thread ID within group |
| `SV_GroupIndex`       | `uint`  | Flattened thread index within group |
| `SV_GroupID`          | `uint3` | Group ID within dispatch |
| `SV_DispatchThreadID` | `uint3` | Thread ID within dispatch |

##### Node Outputs

No outputs to other nodes are allowed for `[LaunchMode("mesh")]`.
This means a mesh launch node does not allow any `[Empty]NodeOutput[Array]`
parameters to be declared.

##### Mesh Shader Outputs

The mesh node entry function also supports the [shared output arrays](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#shared-output-arrays) from mesh shader.
The same definitions and rules from the mesh shader spec apply here.
These arrays address memory shared across the group of threads, just like
`groupshared` memory.
The intrinsic function [`SetMeshOutputCounts`](#setmeshoutputcounts) must be called before writing to
any of the output arrays.

| Mesh shader shared output arrays                      | Array dimension defines maximum number of | Required  |
|-|-|-|
| vertex [`indices`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#vertex-indices)                   | primitives    | Yes |
| attributes for [`vertices`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#vertex-attributes)       | vertices      | Yes |
| attributes for [`primitives`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#primitive-attributes)  | primitives    | No  |

See [shared output arrays](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#shared-output-arrays) in the mesh shader spec for more details.

##### Mesh Node Output System Values

As mentioned earlier, node outputs are not allowed on mesh nodes.
Instead, this section outlines the system values that may be used on fields in
structures used for `vertices` and `primitives` arrays.

Like mesh shaders, `vertices` and `primitives` outputs require a semantic on
each field to produce corresponding output and primitive signature elements.
Outputs also support the same system values supported by mesh shaders, listed
below.  See links below for additional details relevant to mesh shaders for
`SV_PrimitiveID` and `SV_CullPrimitive`.

| system value semantic       | type     | required? | location | notes |
|-----------------------------|----------|-----------|----------|-------------|
| `SV_Position`               | `float4`     | Yes | `vertices`   |  |
| `SV_RenderTargetArrayIndex` | `uint`       | No | `primitives` |  |
| `SV_ViewPortArrayIndex`     | `uint`       | No | `primitives` |  |
| `SV_ClipDistance`           | `float<1-4>` | No | `vertices`   |  |
| `SV_CullDistance`           | `float<1-4>` | No | `vertices`   |  |
| `SV_ShadingRate`            | `uint`       | No | `primitives` |  |
| `SV_PrimitiveID`            | `uint`       | No | `primitives` | See [mesh shader spec](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#sv_primitiveid-in-the-pixel-shader) |
| `SV_CullPrimitive`          | `uint`       | No | `primitives` | See [mesh shader spec](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#sv_cullprimitive) |

#### SetMeshOutputCounts

`SetMeshOutputCounts` is an existing intrinsic, available in mesh shaders, that is used for the same purpose in mesh launch node shaders.

> Excerpts from [SetMeshOutputCounts](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#setmeshoutputcounts) in the mesh shader spec.

```hlsl
void SetMeshOutputCounts(
    uint numVertices,
    uint numPrimitives);
```

The intrinsic function `SetMeshOutputCounts` must be called before writing to
any of the output arrays.

Some restrictions on the function use and interactions with output arrays follow.
1. This function can only be called once per shader.
2. This call must occur before any writes to any of the shared output arrays. The validator will verify this is the case.
3. If the compiler can prove that this function is not called, then the threadgroup doesn't have any output. If the shader writes to any of the shared output arrays, compilation and shader validation will fail. If the shader does not call any of these functions, the compiler will issue a warning, and no rasterization work will be issued.
4. Only the input values from the first active thread are used.
5. This call must dominate all writes to shared output arrays. In other words, there must not be any execution path that even appears to reach any writes to any output array without first having executed this call.

See [SetMeshOutputCounts](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#setmeshoutputcounts)
in the mesh shader spec for specific details, restrictions, and examples.

### Derivative Operations
Because mesh shaders and node shaders with the broadcasting launch mode both support
derivative operations, the new `mesh` node will also support derivative
operations. The support of derivative operations is part of the 
`DerivativesInMeshAndAmplificationShadersSupported` optional feature.


### Interchange Format Additions

To the `DXIL::NodeLaunchType` enum, add `Mesh` (4).
In DXIL metadata, this value is used in the entry function extended property
metadata with the `NodeLaunchType` tag (13).

New extended shader property metadata tags are used to encode details needed
for the mesh node.  These will start at a special experimental mesh node offset
of `65536` (`1 << 16`) to prevent collisions with new official tags, if those
are added.

| Tag | value | description |
|-|-|-|
| kDxilNodeMeshOutputTopologyTag | 65536 | `i32` encoded `DXIL::MeshOutputTopology` from `[OutputTopology(`*topology*`)]` attribute |
| kDxilNodeMeshMaxVertexCountTag | 65537 | `i32` max vertex count based on [`vertices`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#vertex-attributes) array size. |
| kDxilNodeMeshMaxPrimitiveCountTag | 65538 | `i32` max primitive count based on [`primitives`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#primitive-attributes) array size. |

These new extended attributes are only allowed with mesh node shader entries.
Mesh node shaders require all three of these extended attributes.

The `PayloadSizeInBytes` for Mesh shader is subsumed by the record size already
encoded for the node input.

The mesh node entry metadata supports two signature definitions:
- The Output signature describes `vertices` output elements
- The PatchConstantOrPrimitive signature describes `primitives` output elements.

In addition to the intrinsics supported by a broadcast launch node shader with
no output nodes, the following mesh shader intrinsics are also supported by
node shaders with `mesh` launch type:
- `dx.op.setMeshOutputCounts`
- `dx.op.EmitIndices`
- `dx.op.StoreVertexOutput`
- `dx.op.StorePrimitiveOutput`

Notably, the `dx.op.GetMeshPayload` intrinsic from mesh shader is not supported
by mesh nodes. Instead, payload data is available through the node input record.

### Runtime Additions

#### Runtime information

For mesh launch mode, additional node details will need to be captured to RDAT.
For context, see [RDAT_LibraryTypes.inl](https://github.com/microsoft/DirectXShaderCompiler/blob/main/include/dxc/DxilContainer/RDAT_LibraryTypes.inl).
The approach proposed for this prototype is to add a `RDAT::NodeFuncAttribKind`
of `MeshShaderInfo`, and add an entry to the union:
`RDAT_RECORD_REF(MSInfo, MeshShaderInfo)`.
This will use the existing `MSInfo` structure to encode the required details
for the mesh shader.
There are a few redundant fields of this structure, given what's already
defined for the node shader, but for the experimental feature, the trade-off is
probably worth the simplicity of avoiding another record table at this point.

Here is a breakdown of the fields in the `MSInfo` structure, and how
they will be used in a mesh node:
- `SigOutputElements` - used for the elements of the `vertices` output array.
- `SigPrimOutputElements` - used for the elements of the `primitives` output array.
- `ViewIDOutputMask` - unset.
- `ViewIDPrimOutputMask` - unset.
- `NumThreads` - redundant with `NodeShaderFuncAttrib` NumThreads.  Could be used instead of the additional attribute, or we could copy the ref so it's identical in both places.
- `GroupSharedBytesUsed` - redundant with same field in `NodeShaderInfo`.  Set to same value.
- `GroupSharedBytesDependentOnViewID` - set to zero.
- `PayloadSizeInBytes` - redundant with input record size info.  We shouldn't use this one.  Set to zero?
- `MaxOutputVertices` - based on `vertices` array size
- `MaxOutputPrimitives` - based on `primitives` array size
- `MeshOutputTopology` - `uint8_t` encoded `DXIL::MeshOutputTopology` based on `[OutputTopology(`*topology*`)]`

#### Device Capability

See the work graphs spec
[here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#mesh-nodes)
for detail.

Devices that support experimental `D3D_SHADER_MODEL_6_9` and experimental [`D3D12_WORK_GRAPHS_TIER_1_1`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#d3d12_work_graphs_tier) are required to support these features as part of graphics nodes in work graphs.  Note: mesh shader support is already required for experimental `D3D12_WORK_GRAPHS_TIER_1_1` support.

## Open Questions

- Should vanilla mesh shaders be supported, or only mesh nodes?
  - No, only mesh nodes will be supported.  Ordinary mesh shaders lack key information, such as the `SV_DispatchGrid` location in the input record.
- `[NodeMaxInputRecordsPerGraphEntryRecord(...)]` is proposed [here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#helping-mesh-nodes-work-better-on-some-hardware).  Should this attribute be added to HLSL?
  - It can be specified through the API, and is not currently a priority for feature preview.
- `SV_ViewID` is a [Mesh Shader input system value](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#sv_viewid).  Should it be supported in this feature preview?
  - Currently, this is not a priority, so support is not planned for is preview.
- In the future, subobjects may be added to specify runtime details within the DXIL library for convenience.
