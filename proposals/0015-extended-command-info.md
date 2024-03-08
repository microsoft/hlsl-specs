# Extended Command Information

v0.4 2023-09-27

Three new system-value semantics are required to be supported in HLSL shader model 6.8:

* SV_StartVertexLocation -
 Reports StartVertexLocation from DrawInstanced()
 or BaseVertexLocation from DrawIndexedInstanced() to a vertex shader.
* SV_StartInstanceLocation -
 Reports StartInstanceLocation From Draw*Instanced to a vertex shader.
* SV_IndirectCommandIndex -
 Reports the auto-incrementing index of the current indirect command operation
 to a shader.

Since SV_VertexID doesn't include the StartVertexLocation
 and SV_InstanceID doesn't include the StartInstanceLocation values provided to the API
 through the corresponding draw or execute calls,
 this information has been unavailable to HLSL unless independently passed in.
Availability of these values allows reconstruction of the vertex and instance representation
 used within the API.
It also provides compatibility support for APIs that include these values
 in their VertexID and PrimitiveID equivalents.

## Contents

* [SV_StartVertexLocation](#sv_startvertexlocation)
* [SV_StartInstanceLocation](#sv_startinstancelocation)
* [SV_IndirectCommandIndex](#sv_indirectcommandindex)
* [DXIL](#dxil)
* [Device Capability](#device-capability)
* [Issues](#issues)
* [Change Log](#change-log)

## SV_StartVertexLocation

| Semantic Input | Type |
|---------------------------|--------|
| SV_StartVertexLocation | int |

Value added to each index before reading a vertex from vertex buffer(s) if present.
Regardless of presence or use of vertex buffers,
 the value will behave the same and the shader can use this
 or any other system value for any purpose.
It corresponds to StartVertexLocation from the underlying DrawInstanced() call,
 to BaseVertexLocation from the underyling DrawIndexedInstanced() call,
 or to equivalent parameters to the the equivalent indirect calls from ExecuteIndirect()
 on the command list.

The value is signed to allow for negative values
 just like the BaseVertexLocation parameter is.
A negative BaseVertexLocation allows the first vertex to be referenced
 by a positive vertex index value that is shifted to a lower value,
 but should not index below zero.
The StartVertexLocation parameter is unsigned and
 it will continue to be used as unsigned when reading vertex data
 but will be reinterpret casted to a signed int for HLSL.

The system only populates this as input to the vertex shader.
For any subsequent stage that cares about this value, the shader must pass it manually
 using a user semantic.
SV_StartVertexLocation is an invalid semantic for any shader outputs.

## SV_StartInstanceLocation

| Semantic Input | Type |
|---------------------------|--------|
| SV_StartInstanceLocation  | uint       |

Value added to each index before reading instance data from instance buffer(s) if present.
Regardless of presence or use of instance buffers,
 the value will behave the same and the shader can use this
 or any other system value for any purpose.
It corresponds to StartInstanceLocation from the underlying Draw*Instanced() call
 or equivalent indirect call from ExecuteIndirect() on the command list.

For shader invocations outside Draw*Instanced()
 or corresponding indirect call from ExecuteIndirect(),
 SV_StartInstanceLocation is always 0.

The system only populates this as input to the vertex shader.
For any subsequent stage that cares about this value, the shader must pass it manually
 using a user semantic.
SV_StartVertexLocation is an invalid semantic for any shader outputs.
<!-- See issue 1 -->

## SV_IndirectCommandIndex

| Semantic Input | Type |
|---------------------------|--------|
| SV_IndirectCommandIndex | uint |

Index of the current command in an ExecuteIndirect() call.
Within an ExecuteIndirect() call, SV_IndirectCommandIndex starts at 0 for its first command
 and increments by one for each subsequent command.
For shader invocations outside ExecuteIndirect(), SV_IndirectCommandIndex is always 0.

The system will populate this as a system value input to vertex, mesh and amplification shader stages.
SV_IndirectCommandIndex is an invalid tag for any shader outputs.
<!-- See issue 3 -->

## DXIL

Three new DXIL operations that return the three semantic values are introduced in DXIL 1.8.
The associated opcodes are the only parameters.

```C++
// SV_StartVertexLocation
$result1 = call i32 @dx.op.StartVertexLocation(i32 256)

// SV_StartInstanceLocation
$result2 = call i32 @dx.op.StartInstanceLocation(i32 257)

// SV_IndirectCommandIndex
$result3 = call i32 @dx.op.IndirectCommandIndex(i32 258)
```

## Device Capability

Devices that support `D3D_SHADER_MODEL_6_8` are required to support these system values.

## Issues

1. For which shader stages should these values be available?
   * StartVertexLocation and StartPrintiveLocation are available to the vertex shader
     stage through system value inputs.
     They cannot be used on output variables.
     SV_IndirectCommandIndex is available to all shader stages.

2. How should SV_StartVertexLocation and SV_StartInstanceLocation be accessed?
   * Though these could be built-in functions,
     semantic values are consistent with how the corresponding existing information
     is accessed.

3. How should SV_IndirectCommandIndex be accessed?
   * UNRESOLVED: Some implmenetations of ExecuteIndirect involving replays
     will have a problem with the semantic value.
     Perhaps instead might use an incrementing root constant
     that increments by one for each invocation.

## Change Log

Version|Date|Description
-|-|-
0.4|27 Sep 2023|Limit StartInstanceLocation to vertex shaders
0.3|27 Sep 2023|clarified signed int. added command idx issue. fixed copy/paste issues
0.2|25 Sep 2023|Renamed BaseVertexLocation. Allowed multiple stages. Clarified value definitions.
0.1|25 Sep 2023|Initial version
