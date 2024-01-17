# Mesh Nodes

* Proposal: [NNNN](NNNN-mesh-nodes.md)
* Author(s): [Amar Patel](https://github.com/amarpMSFT), [Tex Riddell](https://github.com/tex3d)
* Sponsor: [Tex Riddell](https://github.com/tex3d)
* Status: **Under Consideration**

## Introduction

This proposes the addition of a mesh node to Work Graphs as an experimental
feature.
The mesh node acts as a launching off point for a graphics pipeline,
using an adaptation of a mesh shader entry as a leaf node in a work graph.
The main changes to the mesh shader entry for use as a node in the work graph
is the replacement of the input payload with a node input record, and the use
of shader attributes, including a new launch type: `[NodeLaunch("mesh")]`.

This is an HLSL-focused summary of the graphics nodes feature proposed in the
[work graphs spec](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#graphics-nodes).
For now only mesh node support is considered as an experimental addition.

## Motivation

Work graphs are a great way to generate compute work on the GPU, and there is a
lot of interest in expanding this to scheduling graphics work as a replacement
for execute indirect.
Mesh shader is a natural place to start, as it's already a compute shader, and
has far fewer details to work out than supporting legacy graphics pipelines.

## Proposed solution

Add a new node launch type `"mesh"`, indicating a mesh shader leaf graphics node.
The new mesh node is based on a combination of a broadcast launch node and a
mesh shader. See more details about the runtime context in the work graphs spec
[here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#graphics-nodes).

Use the node input record as the mesh shader input payload, instead of an
explicit `payload` argument.
Like a broadcast node input record, this must have an `SV_DispatchGrid` field
indicating the grid size when `[NodeMaxDispatchGrid(x,y,z)]` is used.

The same system value inputs supported for broadcast launch nodes and mesh
shaders are supported in the same way here:
`SV_DispatchThreadID`, `SV_GroupThreadID`, `SV_GroupIndex`, and `SV_GroupID`.

Node outputs are not allowed - the mesh node must be a leaf in the work graph.

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

See the [DispatchMesh Launch Nodes](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#dispatchmesh-launch-nodes)
section of the work graphs spec, along with sections linked from there, to
complete the picture.

In the future, we may add subobjects to specify more of these details within
the DXIL library for convenience.

### Example Syntax

```cpp
struct MyMeshRecord {
  float3 perMeshConstant;
  uint3 dispatchGrid : SV_DispatchGrid;
}

groupshared uint numVerts;
groupshared uint numPrims;

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
    out vertices PerVertexValues verts[16],
    out primitives PerPrimitiveValues prim[8],
    out indices uint3 tris[16] )
{
  float3 data = nodeInput.Get().perMeshConstant;
  // compute numVerts, numPrims...
  SetMeshOutputCounts(numVerts, numPrims);
  // Cooperate across group to write output arrays...
}
```

### Compiling Experimental Mesh Node Shaders

As a kind of node shader in work graphs, mesh node shaders are functions
defined in a library.
To use the experimental feature, you must compile HLSL with options:
`-T lib_6_9 -select-validator internal`.
This produces a DXIL library for use with the state object API in accordance
with the work graphs spec
[here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#graphics-nodes.

`-select-validator internal` is for use during feature development to avoid
using an external released validator that does not recognize the feature or
the in-development shader model being used.

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
| `[shader("node")]` | Y | Indicates a node shader entry point |
| `[NodeLaunch("mesh")]` | Y | Signifies a mesh node |
| `[NodeIsProgramEntry]` | N | Node can be launched directly from the API in addition to or instead of from an upstream node in the work graph. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeID("nodeName")]` or `[NodeID("nodeName",arrayIndex)]` | N | Name for the node; uses function name if omitted. Optional `uint arrayIndex` overrides the default index of `0`. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeLocalRootArgumentsTableIndex(index)]` | N | `uint index` indicates the record index into the local root arguments table bound when the work graph is used. May be omitted or set to `-1` (equivalent to omitting).  If omitted and a local root signature is used, the runtime will auto-assign the index. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NumThreads(x,y,z)]` | Y | Specifies the launch size of the threadgroup of the Mesh shader, just like with compute shader. The number of threads can not exceed `X * Y * Z = 128`. See [numthreads](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#numthreads) in the Mesh Shader spec. |
| `[NodeShareInputOf("nodeName")]` or `[NodeShareInputOf("nodeName",arrayIndex)]` | N | Share the input of the specified NodeID with this node. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeDispatchGrid(x,y,z)]` | Yes, unless `NodeMaxDispatchGrid` is defined | Declare a fixed dispatch grid size for use with this node. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[NodeMaxDispatchGrid(x,y,z)]` | Yes, unless `NodeDispatchGrid` is defined | Declare a maximum dispatch grid size for use with this node.  In this case, the dispatch grid size is defined by the record field with the `SV_DispatchGrid` semantic. ([details](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#shader-function-attributes)) |
| `[OutputTopology(`*topology*`)]` | Y | Specifies the topology for the output primitives of the mesh shader. *topology* must be `"line"` or "`triangle"`. See [outputtopology](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#outputtopology) in the Mesh Shader spec. |

#### Function Parameters

##### Input Record

Zero or one input record declaration is supported for the mesh node entry.
Types supported are the same as for a broadcasting launch node shader.
The input record takes the place of the `payload` in the mesh shader.

| Input | Description |
|-|-|
| `DispatchNodeInputRecord<`*recordType*`>` | read only node input |
| [`globallycoherent`] `RWDispatchNodeInputRecord<`*recordType*`>` | Shared R/W access to input record across launched shaders. `globallycoherent` required for any cross-group coherency. |
| *none* | Input record can be omitted when there is no record content. `[NodeDispatchGrid(...)]` is then required to specify a fixed grid size. |

See the work graphs spec
[Node input declaration](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#node-input-declaration)
section under options for broadcasting launch for more detail.

##### Input System Values

For input values outside the input record, mesh nodes support the `broadcasting` launch [node shader system values](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#node-shader-system-values).
These are the same [system values supported by mesh shaders](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#hlsl-attributes-and-intrinsics).

| system value semantic | type    | description |
|-----------------------|---------|-------------|
| `SV_GroupThreadID`    | `uint3` | Thread ID within group |
| `SV_GroupIndex`       | `uint`  | Flattened thread index within group |
| `SV_GroupID`          | `uint3` | Group ID within dispatch |
| `SV_DispatchThreadID` | `uint3` | Thread ID within dispatch |

##### Node Outputs

No outputs to other nodes are allowed for `[LaunchMode("mesh")]`.

##### Mesh Shader Outputs

The mesh node entry function also supports the [shared output arrays](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#shared-output-arrays) from mesh shader.
The same definitions and rules from the mesh shader spec apply here.
These arrays address memory shared across the group of threads, just like
`groupshared` memory.
The intrinsic function [`SetMeshOutputCounts`](#setmeshoutputcounts) must be called before writing to
any of the output arrays.

| Mesh shader shared output arrays                      | Array dimension defines maximum number of | Required  |
|-|-|-|
| vertex [`indices`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#vertex-indices)                   | primitives    | Required  |
| attributes for [`vertices`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#vertex-attributes)       | vertices      | Required  |
| attributes for [`primitives`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#primitive-attributes)  | primitives    | Optional  |

See [shared output arrays](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#shared-output-arrays) in the mesh shader spec for more details.

#### SetMeshOutputCounts

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

### Interchange Format Additions

To the `DXIL::NodeLaunchType` enum, add `Mesh` (4).

New extended shader property metadata tags:

| Tag | value | description |
|-|-|-|
| kDxilNodeMaxVertexCountTag | 23 | `i32` max vertex count based on [`vertices`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#vertex-attributes) array size. |
| kDxilNodeMaxPrimitiveCountTag | 24 | `i32` max primitive count based on [`primitives`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/MeshShader.md#primitive-attributes) array size. |
| kDxilNodeOutputTopologyTag | 25 | `i32` encoded `DXIL::MeshOutputTopology` from `[OutputTopology(`*topology*`)]` attribute |

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

### Diagnostic Changes

> TBD:

> * What additional errors or warnings does this introduce?
> * What exisiting errors or warnings does this remove?

#### Validation Changes

> TBD:

> * What additional validation failures does this introduce?
> * What existing validation failures does this remove?

### Runtime Additions

#### Runtime information

> * What information does the compiler need to provide for the runtime and how?

For mesh launch mode, additional node details will need to be captured to RDAT.
For context, see [RDAT_LibraryTypes.inl](https://github.com/microsoft/DirectXShaderCompiler/blob/main/include/dxc/DxilContainer/RDAT_LibraryTypes.inl).
The approach proposed for this prototype is to add a `RDAT::NodeFuncAttribKind`
of `MeshShaderInfo`, and add an entry to the union:
`RDAT_RECORD_REF(MSInfo, MeshShaderInfo)`.
This will use the existing `MSInfo` structure to encode the required details
for the mesh shader.
There are a few redundant fields of this structure, given what's already
defined for the node shader, but for the experimental feature, the trade-off is
probably worth the simplicity of not adding another record table at this point.

For now, here is a breakdown of the fields in the `MSInfo` structure, and how
they will be used in a mesh node:
- `SigOutputElements` - used for the elements of the `vertices` output array.
- `SigPrimOutputElements` - used for the elements of the `primitives` output array.
- `ViewIDOutputMask` - unset for now.
- `ViewIDPrimOutputMask` - unset for now.
- `NumThreads` - redundant with `NodeShaderFuncAttrib` NumThreads.  Could be used instead of the additional attribute, or we could copy the ref so it's identical in both places.
- `GroupSharedBytesUsed` - redundant with same field in `NodeShaderInfo`.  Set to same value.
- `GroupSharedBytesDependentOnViewID` - set to zero for now.
- `PayloadSizeInBytes` - redundant with input record size info.  We shouldn't use this one.  Set to zero?
- `MaxOutputVertices` - based on `vertices` array size
- `MaxOutputPrimitives` - based on `primitives` array size
- `MeshOutputTopology` - `uint8_t` encoded `DXIL::MeshOutputTopology` based on `[OutputTopology(`*topology*`)]`

#### Device Capability

See the work graphs spec
[here](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#graphics-nodes)
for detail.

Devices that support experimental `D3D_SHADER_MODEL_6_9` and experimental [`D3D12_WORK_GRAPHS_TIER_1_1`](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/WorkGraphs.md#d3d12_work_graphs_tier) are required to support these features as part of graphics nodes in work graphs.

## Testing

> TBD

> * How will correct codegen for DXIL/SPIRV be tested?
> * How will the diagnostics be tested?
> * How will validation errors be tested?
> * How will validation of new DXIL elements be tested?
> * How will the execution results be tested?

## Alternatives considered (Optional)

> TBD:

> If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing. Having these solutions and why they were rejected documented may save
trouble from those who might want to suggest feedback or additional features that
might build on this on. Even variations on the chosen solution can be intresting.

## Open Questions

- Should vanilla mesh shaders be supported, or only mesh nodes?

## Acknowledgments (Optional)

> TBD:

> Take a moment to acknowledge the contributions of people other than the author
and sponsor.
