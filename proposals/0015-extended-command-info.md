# Extended Command Information

* Proposal: [0015](0015-extended-command-info.md)
* Author(s): [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8

## Introduction

Two new system-value semantics are to be supported in HLSL shader
 model 6.8:

* `SV_StartVertexLocation` -
 Reports `StartVertexLocation` from `DrawInstanced()`
 or `BaseVertexLocation` from `DrawIndexedInstanced()` to a vertex shader.
* SV_StartInstanceLocation -
 Reports `StartInstanceLocation` from `DrawInstanced()` or
 `DrawIndexedInstanced()` to a vertex shader.

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
 in their VertexID and InstanceID equivalents.

## Proposed solution

The values provided to `DrawInstanced()` or `DrawIndexInstanced()` that
 represent the start or base vertex and instance location should be made
 available through semantic values applied to parameters to the entry function
 of a vertex shader.
These values will be lowered to DXIL intrinsics that represent a
 platform-specific mechanism to retrieve the corresponding values provided by
 the API draw call that invoked the vertex shader.

## Detailed Design

### HLSL additions

New semantic inputs are added to HLSL vertex shaders.

|     Semantic Input        | Type | Stages |
|---------------------------|------|--------|
| SV_StartInstanceLocation  | uint | Vert   |
| SV_StartVertexLocation    | int  | Vert   |

`SV_StartInstanceLocation` represents the value added to each index before
 reading instance data from instance buffer(s) if present.
Regardless of presence or use of instance buffers,
 the value will behave the same and the shader can use this
 or any other system value for any purpose.
It corresponds to `StartInstanceLocation` from the underlying `DrawInstanced()`
 or `DrawIndexedInstanced()` call
 or equivalent indirect call from `ExecuteIndirect()` on the command list.
For shader invocations outside `DrawInstanced()`, `DrawIndexedInstanced()`
 or corresponding indirect call from `ExecuteIndirect()`,
 `SV_StartInstanceLocation` is always zero.

`SV_StartVertexLocation` represents the value added to each index before reading
 a vertex from vertex buffer(s) if present.
Regardless of presence or use of vertex buffers,
 the value will behave the same and the shader can use this
 or any other system value for any purpose.
It corresponds to `StartVertexLocation` from the underlying `DrawInstanced()` call,
 to `BaseVertexLocation` from the underlying `DrawIndexedInstanced()` call,
 or to equivalent parameters to the the equivalent indirect calls from ExecuteIndirect()
 on the command list.
`SV_StartVertexLocation` is signed to allow for negative values
 just like the `BaseVertexLocation` parameter is.
A negative value allows the first vertex to be referenced
 by a positive vertex index value that is shifted to a lower value,
 but should not index below zero.
The `StartVertexLocation` parameter to `DrawInstanced()` is unsigned and
 it will continue to be used as unsigned when reading vertex data
 but will be reinterpret-casted to a signed int for HLSL.

The system only populates these values as inputs to the vertex shader.
For any subsequent stage that cares about them, the shader must pass them manually
 using a user semantic.
These semantics are invalid for any shader outputs.

### DXIL Additions

Two new DXIL operations that return the two semantic values are introduced in
 DXIL 1.8.
As they return values that are determined by the draw calls,
 they require no input from the shader and have only the associated opcodes as
 parameters.

```C++
// SV_StartVertexLocation
$result1 = call i32 @dx.op.StartVertexLocation(i32 256)

// SV_StartInstanceLocation
$result2 = call i32 @dx.op.StartInstanceLocation(i32 257)
```

### SPIR-V Additions

Use of HLSL entry parameters with the new semantic annotations
 `SV_StartInstanceLocation` or `SV_StartVertexLocation` can be supported in
 SPIR-V using OpVariables with the result <id> of the OpVariable set to
 `BaseInstance`(4425) or `BaseVertex`(4424) respectively.

### Diagnostic Changes

#### New Errors

These are where new errors are produced:

* A parameter with `SV_StartInstanceLocation` is not `uint` type.
  (currently blocked by  bug [#5768](https://github.com/microsoft/DirectXShaderCompiler/issues/5768))
* A parameter with `SV_StartVertexLocation` is not `int` type.
  (currently blocked by  bug [#5768](https://github.com/microsoft/DirectXShaderCompiler/issues/5768))
* `SV_StartVertexLocation` or `SV_StartInstanceLocation` are used
  in any non-vertex shader stages
* `SV_StartVertexLocation` or `SV_StartInstanceLocation` are used on any vertex
  shader outputs.
* `SV_StartVertexLocation` or `SV_StartInstanceLocation` are used
  in a vertex shader targeting a shader model earlier than 6.8.

#### Validation Changes

Validation should confirm:

* That neither `dx.op.StartVertexLocation` nor `dx.op.StartInstanceLocation`
  are used in any DXIL compiled for any non-vertex shader stage.

### Runtime Additions

#### Runtime information

No additions are needed here.

#### Device Capability

Devices that support `D3D_SHADER_MODEL_6_8` are required to support these system values.

## Testing

### Correct Behavior Testing

Verify the following compiler output:

* A vertex shader with an int entry point parameter annotated with
  `SV_StartInstanceLocation` that is passed directly into the output produces
  DXIL IR with a call op to `dx.op.StartInstanceLocation` that returns that
  result to the output.
* A vertex shader with an input struct with an element annotated with
  `SV_StartInstanceLocation` that is passed directly into the output produces
  DXIL IR with a call op to `dx.op.StartInstanceLocation` that returns that
  result to the output.
* A vertex shader with an int entry point parameter annotated with
  `SV_StartVertexLocation` that is passed directly into the output produces
  DXIL IR with a call op to `dx.op.StartVertexLocation` that returns that
  result to the output.
* A vertex shader with an input struct with an element annotated with
  `SV_StartVertexLocation` that is passed directly into the output produces
  DXIL IR with a call op to `dx.op.StartVertexLocation` that returns that
  result to the output.
* Each of the above tests produces the expected output within a library shader
  with a "vertex" shader attribute.

### Diagnostics Testing

Ensure that each of the following scenarios produces appropriate errors:

* Use invalid types for entry parameters with the new semantics
  (currently blocked by  bug [#5768](https://github.com/microsoft/DirectXShaderCompiler/issues/5768))
  * A `float` parameter with `SV_StartInstanceLocation`
  * An `int` parameter with `SV_StartInstanceLocation`
  * A `float` parameter with `SV_StartVertexLocation`
  * A `uint` parameter with `SV_StartInstanceLocation`
* Use new semantics in invalid shader targets
  * `SV_StartVertexLocation` is used in each 6.8 non-vertex shader stage target
  * `SV_StartInstanceLocation` is used in each 6.8 non-vertex shader stage target
  * `SV_StartVertexLocation` is used in a 6.7 vertex shader stage target
  * `SV_StartInstanceLocation` is used in a 6.7 vertex shader stage target

### Validation Testing

Assemble shaders targeting each non-vertex shader stage with calls to
 `dx.op.StartInstanceLocation` and `dx.op.StartVertexLocation` and ensure that
 the validator produces an appropriate error.

### Execution Testing

Create a vertex shader with a uint entry point parameter annotated with
 `SV_StartInstanceLocation` and an int entry point parameter annotated with
 `SV_StartVertexLocation` that stores those values into a raw buffer.
Invoke this shader using `DrawInstanced()`, `DrawIndexedInstanced()`, and
 equivalent indirect call from `ExecuteIndirect()` with positive integer values
 for the parameters that correspond to start vertex and start instance values.
Read back the content of the raw buffer to ensure that the values match the
 parameters used in the API calls.
Perform an additional test where the start vertex parameters are negative values
 and ensure that the read back values match the parameters.

## Alternatives considered

There may have been utility to making StartVertexLocation and StartInstanceLocation
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

* Jesse Natalie
* Amar Patel
* Tex Riddell
