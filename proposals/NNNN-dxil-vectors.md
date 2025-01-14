<!-- {% raw %} -->

# DXIL Vectors

---

* Proposal: [NNNN](NNNN-dxil-vectors.md)
* Author(s): [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.9

## Introduction

While DXIL is intended and able to support language vectors,
 those vectors must be broken up into individual scalars to be valid DXIL.
This feature introduces the ability to represent native vectors in DXIL for some uses.

## Motivation

Although many GPUs support vector operations, DXIL has been unable to directly leverage those capabilities.
Instead, it has scalarized all vector operations, losing their original representation.
To restore those vector representations, platforms have had to rely on auto-vectorization to
 rematerialize vectors late in the compilation.
Scalarization is a trivial compiler transformation that never fails,
 but auto-vectorization is a notoriously difficult compiler optimization that frequently generates sub-optimal code.
Allowing DXIL to retain vectors as they appeared in source allows hardware that can utilize
 vector optimizations to do so more easily without penalizing hardware that requires scalarization.

Native vector support can also help with the size of compiled DXIL programs.
Vector operations can express in a single instruction operations that would have taken N instructions in scalar DXIL.
This may allow reduced file sizes for compiled DXIL programs that utilize vectors.

DXIL is based on LLVM 3.7 which already supports native vectors.
These could only be used to a limited degree in DXIL library targets, and never for DXIL operations.
This innate support is expected to make adding them a relatively low impact change to DXIL tools.

## Proposed solution

Native vectors are allowed in DXIL version 1.9 or greater.
These can be stored in allocas, static globals, groupshared variables, and SSA values.
They can be loaded from or stored to raw buffers and used as arguments to a selection
 of element-wise intrinsic functions as well as the standard math operators.
They cannot be used in shader signatures, constant buffers, typed buffer, or texture types.

## Detailed design

### Vectors in memory representations

In their alloca and variable representations, vectors in DXIL will always be represented as vectors.
Previously individual vectors would get scalarized into scalar arrays and arrays of vectors would be flattened
 into a one-dimensional scalar array with indexing to reflect the original intents.
Individual vectors will now be represented as a single native vector and arrays of vectors will remain
 as arrays of native vectors, though multi-dimensional arrays will still be flattened to one dimension.

Single-element vectors are generally not valid in DXIL.
At the language level, they may be supported for corresponding intrinsic overloads,
 but such vectors should be represented as scalars in the final DXIL output.
Since they only contain a single scalar, single-element vectors are
 informationally equivalent to actual scalars.
Rather than include conversions to and from scalars and single-element vectors,
 it is cleaner and functionally equivalent to represent these as scalars in DXIL.
The exception is in exported library functions, which need to maintain vector representations
 to correctly match overloads when linking.

### Changes to DXIL Intrinsics

A new form of rawBufferLoad allows loading of full vectors instead of four scalars.
The status integer for tiled resource access is loaded just as before.
The returned vector value and the status indicator are grouped into a new `ResRet` helper structure type
 that the load intrinsic returns.

```asm
  ; overloads: SM6.9: f16|f32|i16|i32
  ; returns: status, vector
  declare %dx.types.ResRet.v[NUM][TY] @dx.op.rawBufferLoad.v[NUM][TY](
      i32,                  ; opcode
      %dx.types.Handle,     ; resource handle
      i32,                  ; coordinate c0 (index)
      i32,                  ; coordinate c1 (elementOffset)
      i8,                   ; mask
      i32,                  ; alignment
  )
```

The return struct contains a single vector and a single integer representing mapped tile status.

```asm
  %dx.types.ResRet.v[NUM][TY] = type { vector<TYPE, NUM>, i32 }
```

Here and hereafter, `NUM` is the number of elements in the loaded vector, `TYPE` is the element type name,
 and `TY` is the corresponding abbreviated type name (e.g. `i64`, `f32`).

#### Vector access

Dynamic access to vectors were previously converted to array accesses.
Native vectors can be accessed using `extractelement`, `insertelement`, or `getelementptr` operations.
Previously usage of `extractelement` and `insertelement` in DXIL didn't allow dynamic index parameters.

#### Elementwise intrinsics

A selection of elementwise intrinsics are given additional native vector forms.
Elementwise intrinsics are those that perform their calculations irrespective of the location of the element
 in the vector or matrix arguments except insofar as that position corresponds to those of the other elements
 that might be used in the individual element calculations.
An elementwise intrinsic `foo` that takes scalar or vector arguments could theoretically implement its vector version using a simple loop and the scalar intrinsic variant.

```c++
vector<TYPE, NUM> foo(vector<TYPE, NUM> a, vector<TYPE, NUM> b) {
  vector<TYPE, NUM> ret;
  for (int i = 0; i < NUM; i++)
    ret[i] = foo(a[i], b[i]);
}
```
  
For example, `fma` is an elementwise intrinsic because it multiplies or adds each element of its argument vectors,
 but `cross` is not because it performs an operation on the vectors as units,
 pulling elements from different locations as the operation requires.

The elementwise intrinsics that have native vector variants represent the
 unary, binary, and tertiary generic operations:

```asm
 <[NUM] x [TYPE]> @dx.op.unary.v[NUM][TY](i32 opcode, <[NUM] x [TYPE]> operand1)
 <[NUM] x [TYPE]> @dx.op.binary.v[NUM][[TY]](i32 opcode, <[NUM] x [TYPE]> operand1, <[NUM] x [TYPE]> operand2)
 <[NUM] x [TYPE]> @dx.op.tertiary.v[NUM][TY](i32 opcode, <[NUM] x [TYPE]> operand1, <[NUM] x [TYPE]> operand2, <[NUM] x [TYPE]> operand3)
```

The scalarized variants of these DXIL intrinsics will remain unchanged and can be used in conjunction
 with the vector variants.
This means that the same language-level vector could be used in scalarized operations and native vector operations
 within the same shader by being scalarized as needed even within the same shader.

### Validation Changes

Blanket validation errors for use of native vectors DXIL are removed.
Specific disallowed usages of native vector types will be determined by
 examining arguments to operations and intrinsics and producing errors where appropriate.
Aggregate types will be recursed into to identify any native vector components.

Native vectors should produce validation errors when:

* Used in cbuffers.
* Used in unsupported intrinsics or operations as before, but made more specific to the operations.
* Any usage in previous shader model shaders apart from exported library functions.

Error should be produced for any representation of a single element vector outside of
 exported library functions.

Specific errors might be generated for invalid overloads of `LoadInput` and `StoreOutput`
 as they represent usage of vectors in entry point signatures.

### Device Capability

Devices that support Shader Model 6.9 will be required to fully support this feature.

## Testing

### Compilation Testing

A compiler targeting shader model 6.9 should be able to represent vectors in the supported memory spaces
 in their native form and generate native calls for supported intrinsics.

Test that appropriate output is produced for:

* Supported intrinsics and operations will retain vector types.
* Dynamic indexing of vectors produces the correct `extractelement`, `insertelement`
 operations with dynamic index parameters.

### Validation testing

The DXIL 6.9 validator should allow native vectors in the supported memory and intrinsic uses.
It should produce errors for uses in unsupported intrinsics, cbuffers, and typed buffers.

Single-element vectors are allowed only as interfaces to library shaders.
Other usages of a single element vector should produce a validation error.

### Execution testing

Full runtime execution should be tested by using the native vector intrinsics using
 groupshared and non-groupshared memory.
Calculations should produce the correct results in all cases for a range of vector sizes.
In practice, this testing will largely represent verifying correct intrinsic output
 with the new shader model.

## Acknowledgments

* [Anupama Chandrasekhar](https://github.com/anupamachandra) and [Tex Riddell](https://github.com/tex3d) for foundational contributions to the design.

<!-- {% endraw %} -->
