---
title: 0030 - DXIL Vectors
params:
  authors:
  - pow2clk: Greg Roth
  sponsors:
  - llvm-beanz: Chris Bieneman
  status: Accepted
---


 
* Planned Version: SM 6.9

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
  declare %dx.types.ResRet.v[NUM][TY] @dx.op.rawBufferVectorLoad.v[NUM][TY](
      i32,                  ; opcode
      %dx.types.Handle,     ; resource handle
      i32,                  ; coordinate c0 (byteOffset)
      i32,                  ; coordinate c1 (elementOffset)
      i32)                  ; alignment
```


The return struct contains a single vector and a single integer representing mapped tile status.

```asm
  %dx.types.ResRet.v[NUM][TY] = type { vector<TYPE, NUM>, i32 }
```

Here and hereafter, `NUM` is the number of elements in the loaded vector, `TYPE` is the element type name,
 and `TY` is the corresponding abbreviated type name (e.g. `i64`, `f32`).

#### Vector access

Dynamic access to vectors were previously converted to array accesses.
Native vectors can be dynamically accessed using `extractelement`, `insertelement`, `shufflevector` or `getelementptr` operations.
Previously usage of `extractelement` and `insertelement` in DXIL didn't allow dynamic index parameters.

#### Elementwise intrinsics

A selection of elementwise intrinsics are given additional native vector forms.
The full list of intrinsics with elementwise overloads is listed in [Appendix 1](#appendix-1-new-elementwise-overloads).
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

The scalar variants of these DXIL intrinsics will remain unchanged and can be used in conjunction
 with the vector variants.
This means that the same language-level vector (of any length) could be used
 in scalarized operations and native vector operations even within the same shader.

### New DXIL Intrinsics

#### `VectorReduce` OpCodeClass

A new generic OpCodeClass `VectorReduce` is introduced for usage in new operations
below. `VectorReduce` combines a vector of elements into a single element with
the same type as the vector element type. The elements are combined using an
operation specified by the opcode parameter.

#### Boolean Vector Reduction Intrinsics

**VectorReduceAnd**

Bitwise AND reduction of the vector returning a scalar. Return type matches vector element type.

The scalar type may be `i1`, `i8`, `i16,` `i32`, or `i64`.

```C++
DXIL::OpCode::VectorReduceAnd = 309
```

```asm
 [TYPE] @dx.op.vectorReduce.v[NUM][TY](309, <[NUM] x [TYPE]> operand)
```

**VectorReduceOr**

Bitwise OR reduction of the vector returning a scalar. Return type matches vector element type.

The scalar type may be `i1`, `i8`, `i16,` `i32`, or `i64`.

```C++
DXIL::OpCode::VectorReduceOr = 310
```

```asm
 [TYPE] @dx.op.vectorReduce.v[NUM][TY](310, <[NUM] x [TYPE]> operand)
```

#### Vectorized Dot

A new OpCodeClass `dot` is introduced. The return type matches the vector element
return type. The 2nd and 3rd parameters are two vectors of the same dimention and
element type. The 1st parameter is an opcode that specifies what type of dot
operation to calculate. The only supported opcode as of this proposal is floating
point dot.

**FDot**

Current `dot` intrinsics are scalarized and limited to 2/3/4 vectors. With support for
native vectors in DXIL `dot` can now be treated similarly to a binary operation.

Returns `op1[0] * op2[0] + op1[1] * op2[1] + ... + op1[NUM - 1] * op2[NUM - 1]`

The scalar type for `FDot` may be `half` or `float`.

```C++
DXIL::OpCode::FDot = 311
```

```asm
 [TYPE] @dx.op.dot.v[NUM][TY](311, <[NUM] x [TYPE]> operand1, <[NUM] x [TYPE]> operand2)
```

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

## Appendix 1: New Elementwise Overloads

| Opcode |  Name              | Class              |
| ------ | --------------     | --------           |
| 6      | FAbs               | Unary              |
| 7      | Saturate           | Unary              |
| 8      | IsNaN              | IsSpecialFloat     |
| 9      | IsInf              | IsSpecialFloat     |
| 10     | IsFinite           | IsSpecialFloat     |
| 11     | IsNormal           | IsSpecialFloat     |
| 12     | Cos                | Unary              |
| 13     | Sin                | Unary              |
| 14     | Tan                | Unary              |
| 15     | Acos               | Unary              |
| 16     | Asin               | Unary              |
| 17     | Atan               | Unary              |
| 18     | Hcos               | Unary              |
| 19     | Hsin               | Unary              |
| 20     | Htan               | Unary              |
| 21     | Exp                | Unary              |
| 22     | Frc                | Unary              |
| 23     | Log                | Unary              |
| 24     | Sqrt               | Unary              |
| 25     | Rsqrt              | Unary              |
| 26     | Round_ne           | Unary              |
| 27     | Round_ni           | Unary              |
| 28     | Round_pi           | Unary              |
| 29     | Round_z            | Unary              |
| 30     | Bfrev              | Unary              |
| 31     | Countbits          | UnaryBits          |
| 32     | FirstBitLo         | UnaryBits          |
| 33     | FirstBitHi         | UnaryBits          |
| 34     | FirstBitSHi        | UnaryBits          |
| 35     | FMax               | Binary             |
| 36     | FMin               | Binary             |
| 37     | IMax               | Binary             |
| 38     | IMin               | Binary             |
| 39     | UMax               | Binary             |
| 40     | UMin               | Binary             |
| 46     | FMad               | Tertiary           |
| 47     | Fma                | Tertiary           |
| 48     | IMad               | Tertiary           |
| 49     | UMad               | Tertiary           |
| 83     | DerivCoarseX       | Unary              |
| 84     | DerivCoarseY       | Unary              |
| 85     | DerivFineX         | Unary              |
| 86     | DerivFineY         | Unary              |
| 115    | WaveActiveAllEqual | WaveActiveAllEqual |
| 117    | WaveReadLaneAt     | WaveReadLaneAt     |
| 118    | WaveReadLaneFirst  | WaveReadLaneFirst  |
| 119    | WaveActiveOp       | WaveActiveOp       |
| 120    | WaveActiveBit      | WaveActiveBit      |
| 121    | WavePrefixOp       | WavePrefixOp       |
| 122    | QuadReadLaneAt     | QuadReadLaneAt     |
| 123    | QuadOp             | QuadOp             |
| 165    | WaveMatch          | WaveMatch          |
| 166    | WaveMultiPrefixOp  | WaveMultiPrefixOp  |



## Acknowledgments

* [Anupama Chandrasekhar](https://github.com/anupamachandra) and [Tex Riddell](https://github.com/tex3d) for foundational contributions to the design.

