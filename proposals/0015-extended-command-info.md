# Extended Command Information

* Proposal: [NNNN](NNNN-extended-command-info.md)
* Author(s): [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8

## Introduction

Two new system-value semantics are required to be supported in HLSL shader
 model 6.8:

* SV_StartVertexLocation -
 Reports StartVertexLocation from DrawInstanced()
 or BaseVertexLocation from DrawIndexedInstanced() to a vertex shader.
* SV_StartInstanceLocation -
 Reports StartInstanceLocation From Draw*Instanced to a vertex shader.

## Motivation

Since SV_VertexID doesn't include the StartVertexLocation
 and SV_InstanceID doesn't include the StartInstanceLocation values provided to
 the API through the corresponding draw or execute calls,
 this information has been unavailable to HLSL unless independently passed in.
Availability of these values allows reconstruction of the vertex and instance
 representation used within the API.
In particular, if the vertex or instance information is offset by a certain
 amount in the API, the shader can access that information and potentially
 make use of data before that offset for special usage.
It also provides compatibility support for APIs that include these values
 in their VertexID and PrimitiveID equivalents.

## Proposed solution

## Detailed Design

### HLSL additions

##### SV_StartVertexLocation

New semantic inputs are added to HLSL vertex shaders.

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

##### SV_StartInstanceLocation

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

### DXIL Additions

Two new DXIL operations that return the two semantic values are introduced in DXIL 1.8.
The associated opcodes are the only parameters.

```C++
// SV_StartVertexLocation
$result1 = call i32 @dx.op.StartVertexLocation(i32 256)

// SV_StartInstanceLocation
$result2 = call i32 @dx.op.StartInstanceLocation(i32 257)
```

### SPIR-V Additions

### Diagnostic Changes

#### New Errors

#### Validation Changes

### Runtime Additions

#### Runtime information

#### Device Capability

Devices that support `D3D_SHADER_MODEL_6_8` are required to support these system values.

## Testing

### Correct Behavior Testing

#### Diagnostics Testing
### Validation Testing
### Execution Testing

## Alternatives considered

There may have been utility to making StartVertexLocation and StartPrimitiveLocation
 available in entry shader stages beyond just the vertex shader.
That would have exceeded the requirement that motivated this feature without
 certainty that it would be useful for anyone,
 so availability was limited to the vertex stage.

The StartVertexLocation and StartInstanceLocation information might have been
 accessible to the HLSL author by built-in functions rather than semantics.
It was a technical possibility that would have made them more readily available
 without having to pipe entry parameters to subfunctions,
 however semantic values are consistent with how the corresponding information
 is accessed such as VertexID.
For the sake of consistency and the principal of least surprise,
 they are represented as semantic values as well.


## Acknowledgements

* Amar Patel
* Tex Riddell
