<!-- {% raw %} -->

# HLSL Vector Matrix Operations

## Instructions

- Proposal: [0031](0031-hlsl-vector-matrix-operations.md)
- Author(s): [Damyan Pepper][damyanp], [Chris Bieneman][llvm-beanz],
  [Anupama Chandrasekhar][anupamachandra]
- Sponsor: [Damyan Pepper][damyanp]
- Status: **Under Consideration**
- Planned Version: Shader Model 6.9

[damyanp]: https://github.com/damyanp
[llvm-beanz]: https://github.com/llvm-beanz
[anupamachandra]: https://github.com/anupamachandra

## Introduction

This proposes a set of HLSL APIs that enable the use of the hardware-accelerated
vector/matrix operations described in [Proposal 0029].

[Proposal 0029]: 0029-cooperative-vector.md

## Motivation

Modern GPUs have dedicated silicon to accelerate matrix operations, but HLSL
doesn't provide a mechanism to easily utilize these units. Evaluation of
matrix-vector operations (multiply, muladd, accumulation) in HLSL was previously
scalarized at the DXIL level making it hard to employ these specialized units.
This proposal builds on the "Long vectors" feature described in [Proposal 0026],
providing a mechanism to express matrix-vector ops in HLSL that can be lowered
to the DXIL ops described [Proposal 0029], these primitives provide the right
level of abstraction for hardware acceleration.

An HLSL API needs to be defined to expose these new operations in a way that:

- works well with existing HLSL APIs
- is expected to work well with future HLSL APIs in the same problem space
- can be implemented reasonably in DXC and cleanly in clang

[Proposal 0026]: 0026-hlsl-long-vector-type.md

## Proposed solution

This API will be implemented using HLSL code. The exact mechanism for getting
this code into a developer's shader is TBD, but implementations have a few
possible options, including:

- Developers must explicitly #include a header file
- The compiler force-includes the header file
- The compiler force-includes a precompiled version of the header file

The header-implementation accesses the DXIL operations described in [Proposal
0029] by calling low-level builtins. These builtins should be considered
implementation details and users should not call them directly. However, since
they are a part of the implementation plan for the first implementation of this
API they are described [below](#builtins).

Since this API is currently only supported by DirectX, all the new types /
methods described in it are placed in the `dx` namespace. Within this namespace,
a `linalg` namespace is also added to group together types and methods related
to linear algebra.

Throughout this API, template parameters are used to store values that must be
known at compile time, while member variables or function arguments are used to
store values that may only be determined at runtime.

This API defines the following supporting types:

- `struct dx::linalg::MatrixRef`
  - Reference to a matrix stored in a ByteAddressBuffer.
- `struct dx::linalg::RWMatrixRef`
  - Reference to a matrix stored in a RWByteAddressBuffer.
- `struct dx::linalg::VectorRef`
  - Reference to a vector stored in a ByteAddressBuffer.
- `struct dx::linalg::RWVectorRef`
  - Reference to a vector stored in a RWByteAddressBuffer.
- `struct dx::linalg::InterpretedVector`
  - Wrapper around a vector, allowing the elements of the vector to be
    reinterpreted in various ways.
- `enum dx::linalg::DataType`
  - Enum describing various data types that can be used to applied to matrices
    and vectors.
- `enum dx::linalg::MatrixLayout`
  - Enum describing the possible layouts for a matrix in memory.

This API defines the following functions:

- `dx::linalg::Mul`
  - Multiply a matrix in memory by a vector parameter.
- `dx::linalg::MulAdd`
  - Multiply a matrix in memory by a vector parameter, and add a vector from
    memory.
- `dx::linalg::OuterProductAccumulate`
  - Compute the outer product of two vectors and accumulate the result matrix
    atomically-elementwise in memory.
- `dx::linalg::VectorAccumulate`
  - Accumulate elements of a vector atomically-elementwise to corresponding
    elements in memory.
- `dx::linalg::MakeInterpretedVector`
  - Convenience function to construct an `InterpretedVector` inline while
    inferring various template parameters.

These are all described in more detail below, but the follow code example gives
a flavor of how these work together:

```c++
ByteAddressBuffer Model;

vector<float, 3> ApplyNeuralMaterial(vector<half, 8> InputVector) {
  using namespace dx::linalg;

  MatrixRef<DATA_TYPE_FLOAT8_E4M3, 32, 8, MATRIX_LAYOUT_MUL_OPTIMAL> Matrix0 = {
      Model, 0, 0};

  VectorRef<DATA_TYPE_FLOAT16> BiasVector0 = {Model, 1024};

  MatrixRef<DATA_TYPE_FLOAT8_E4M3, 32, 32, MATRIX_LAYOUT_MUL_OPTIMAL> Matrix1 =
      {Model, 2048, 0};

  VectorRef<DATA_TYPE_FLOAT16> BiasVector1 = {Model, 3072};

  MatrixRef<DATA_TYPE_FLOAT8_E4M3, 3, 32, MATRIX_LAYOUT_MUL_OPTIMAL> Matrix2 = {
      Model, 4096, 0};

  VectorRef<DATA_TYPE_FLOAT16> BiasVector2 = {Model, 5120};

  vector<half, 32> Layer0 = MulAdd<half>(
      Matrix0, MakeInterpretedVector<DATA_TYPE_FLOAT8_E4M3>(InputVector),
      BiasVector0);
  Layer0 = max(Layer0, 0);

  vector<half, 32> Layer1 = MulAdd<half>(
      Matrix1, MakeInterpretedVector<DATA_TYPE_FLOAT8_E4M3>(Layer0),
      BiasVector1);
  Layer1 = max(Layer1, 0);

  vector<float, 3> Output = MulAdd<float>(
      Matrix2, MakeInterpretedVector<DATA_TYPE_FLOAT8_E4M3>(Layer1),
      BiasVector2);
  Output = exp(Output);

  return Output;
}
```

## Detailed design

The API is implemented using the C++03 style templates supported in HLSL 2021.
Therefore HLSL 2021 is required to use this API.

Developers are expected to rely on template argument deduction for calls to the
various functions defined. In this document a higher-level view of how
developers should view each function is provided, along with a proposed
implementation.

### Builtins

Although these "builtins" are not intended to be part of the HLSL language, and
no promises are made that these will continue to be available over time, this
proposal describes an implementation in terms of builtins such as this. For
this reason it is useful to have them described here as a reference point.

Each builtin corresponds to one of the operations described in [0029].

```c++
namespace dx {

// dx.op.matvecmul
template <typename TYo, int NUMo, typename TYi, int NUMi, typename RESm>
void __builtin_MatVecMul(out vector<TYo, NUMo> OutputVector,
                         bool IsOutputUnsigned, vector<TYi, NUMi> InputVector,
                         bool IsInputUnsigned, uint InputVectorInterpretation,
                         RESm MatrixResource, uint MatrixStartOffset,
                         uint MatrixInterpretation, uint M, uint K,
                         uint MatrixLayout, bool IsMatrixTransposed,
                         uint MatrixStride);

// dx.op.matvecmuladd
template <typename TYo, int NUMo, typename TYi, int NUMi, typename RESm,
          typename RESv>
void __builtin_MatVecMulAdd(out vector<TYo, NUMo> OutputVector,
                            bool IsOutputUnsigned,
                            vector<TYi, NUMi> InputVector, bool IsInputUnsigned,
                            uint InputVectorInterpretation, RESm MatrixResource,
                            uint MatrixStartOffset, uint MatrixInterpretation,
                            uint M, uint K, uint MatrixLayout,
                            bool IsMatrixTransposed, uint MatrixStride,
                            RESv BiasVectorResource, uint BiasVectorOffset,
                            uint BiasVectorInterpretation);

// dx.op.outerproductaccumulate
template <typename TY, int M, int N, typename RES>
void __builtin_OuterProductAccumulate(vector<TY, M> InputVector1,
                                      vector<TY, N> InputVector2,
                                      RES MatrixResource,
                                      uint MatrixStartOffset,
                                      uint MatrixInterpretation,
                                      uint Layout, uint MatrixStride);

// dx.op.vectoraccumulate
template <typename TY, int NUM, typename RES>
void __builtin_VectorAccumulate(vector<TY, NUM> InputVector,
                                RES OutputArrayResource,
                                uint OutputArrayOffset);

} // namespace dx

```

### enum DataType

The `dx::linalg::DataType` enum defines the various data types that can be
applied to matrices and vectors. The numeric values of these enum entries are
picked to match those used in the underlying DXIL.

```c++
namespace dx {
namespace linalg {

enum DataType {
  DATA_TYPE_SINT16 = 2,           // ComponentType::I16
  DATA_TYPE_UINT16 = 3,           // ComponentType::U16
  DATA_TYPE_SINT32 = 4,           // ComponentType::I32
  DATA_TYPE_UINT32 = 5,           // ComponentType::U32
  DATA_TYPE_FLOAT16 = 8,          // ComponentType::F16
  DATA_TYPE_FLOAT32 = 9,          // ComponentType::F32
  DATA_TYPE_SINT8_T4_PACKED = 17, // ComponentType::PackedS8x32
  DATA_TYPE_UINT8_T4_PACKED = 18, // ComponentType::PackedU8x32
  DATA_TYPE_UINT8 = 19,           // ComponentType::U8
  DATA_TYPE_SINT8 = 20,           // ComponentType::I8
  DATA_TYPE_FLOAT8_E4M3 = 21,     // ComponentType::F8_E4M3
                                  // (1 sign, 4 exp, 3 mantissa bits)
  DATA_TYPE_FLOAT8_E5M2 = 22,     // ComponentType::F8_E5M2
                                  // (1 sign, 5 exp, 2 mantissa bits)
};

} // namespace linalg
} // namespace dx
```

See the Type Interpretations section of [Proposal 0029] for more information.

### enum MatrixLayout

The `dx::linalg::MatrixLayout` enum defines the different possible layouts of a
matrix in memory.

```c++
namespace dx {
namespace linalg {

enum MatrixLayout {
  MATRIX_LAYOUT_ROW_MAJOR = 0,
  MATRIX_LAYOUT_COLUMN_MAJOR = 1,
  MATRIX_LAYOUT_MUL_OPTIMAL = 2,
  MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL = 3
};

} // namespace linalg
} // namespace dx
```

See the Matrix Layouts section of [Proposal 0029] for more information.

### struct MatrixRef / RWMatrixRef

`dx::linalg::MatrixRef` and `dx::linalg::RWMatrixRef` specify a reference to a
matrix in memory, including information about the dimensions, layout and
numerical format of the matrix. Some of this information must be known at
compile time - these are captured in template parameters - while others can be
determined at runtime, and are therefore members of the struct.

Since the `ByteAddressBuffer` and `RWByteAddressBuffer` are not convertable to
each other, it is neccesary to use different named types for the matrix
references. A base class, `dx::linalg::MatrixRefImpl` is used for the common
code.

Other functions in the API are implemented in terms of
`dx::linalg::MatrixRefImpl`. An option considered was to use a template
parameter for the entire matrix type. However, this approach results in hard to
understand error messages if a non-MatrixRef type is passed for that parameter.

Example usage:

```c++
ByteAddressBuffer ROBuffer;
RWByteAddressBuffer RWBuffer;

void Example() {
  using namespace dx::linalg;

  MatrixRef<DATA_TYPE_FLOAT16, 4, 4, MATRIX_LAYOUT_MUL_OPTIMAL, true> MatrixA =
      {ROBuffer, /*offset=*/128, /*stride=*/0};

  MatrixRef<DATA_TYPE_FLOAT16, 4, 4, MATRIX_LAYOUT_ROW_MAJOR, true>
      MatrixB = {ROBuffer, /*offset=*/128, /*stride=*/16};

  RWMatrixRef<DATA_TYPE_FLOAT16, 128, 256, MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL>
      MatrixC = {RWBuffer, /*offset=*/64, /*stride=*/0};
}
```

Template parameters:

- `DT` - the type used to store elements of the matrix in memory
- `M` - the 'M' dimension of the matrix
- `K` - the 'K" dimension of the matrix
- `ML` - the layout of the matrix in memory
- `Transpose` - whether or not this matrix should be transposed before any
  operations

Members:

- `Buffer` - the buffer that the matrix is stored in
  - For `MatrixRef` this is a `ByteAddressBuffer`
  - For `RWMatrixRef` this is a `RWByteAddresssBuffer`
- `StartOffset` - the offset, in bytes, from the beginning of the buffer where
  the matrix is located.
- `Stride` - the stride, in bytes, between rows or columns of the matrix. This
  value must be zero if the matrix layout is `MATRIX_LAYOUT_MUL_OPTIMAL` or
  `MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL`.

Implementation:

```c++
namespace dx {
namespace linalg {

template <typename BufferTy, DataType DT, uint M, uint K, MatrixLayout ML,
          bool Transpose>
struct MatrixRefImpl {
  BufferTy Buffer;
  uint StartOffset;
  uint Stride;
};

template <DataType DT, uint M, uint K, MatrixLayout ML, bool Transpose = false>
using MatrixRef = MatrixRefImpl<ByteAddressBuffer, DT, M, K, ML, Transpose>;

template <DataType DT, uint M, uint K, MatrixLayout ML, bool Transpose = false>
using RWMatrixRef = MatrixRefImpl<RWByteAddressBuffer, DT, M, K, ML, Transpose>;

} // namespace linalg
} // namespace dx
```

### struct VectorRef

`dx::linalg::VectorRef` and `dx::linalg::RWVectorRef` specify a reference to a
vector in memory along with the format of each element.

As with `dx::linalg::MatrixRef`, two versions are provided - one for vectors
stored in `ByteAddressBuffer` and another for `RWByteAddressBuffer`. A base
class, `dx::linalg::VectorRefImpl`, covers both of them.

Example usage:

```c++
ByteAddressBuffer ROBuffer;
RWByteAddressBuffer RWBuffer;

void Example() {
  using namespace dx::linalg;

  VectorRef<DATA_TYPE_FLOAT16> VectorA = {ROBuffer, /*offset=*/128};
  VectorRef<DATA_TYPE_FLOAT32> VectorB = {ROBuffer, /*offset=*/128};
  RWVectorRef<DATA_TYPE_SINT16> VectorC = {RWBuffer, /*offset=*/64};
}
```

Template parameter:

- `DT` - the data type of each element stored in the buffer

Members:

- `Buffer` - the buffer that the vector is stored in
  - For `VectorRef` this is a `ByteAddressBuffer`
  - For `RWVectorRef` this is a `RWByteAddresssBuffer`
- `StartOffset` - the offset, in bytes, from the beginning of the buffer to
  where the vector is located.

Implementation:

```c++
namespace dx {
namespace linalg {

template <typename BufferTy, DataType DT> struct VectorRefImpl {
  BufferTy Buffer;
  uint StartOffset;
};

template <DataType DT> using VectorRef = VectorRefImpl<ByteAddressBuffer, DT>;

template <DataType DT>
using RWVectorRef = VectorRefImpl<RWByteAddressBuffer, DT>;

} // namespace linalg
} // namespace dx

```

### struct InterpretedVector

> NOTE: it's possible that one resolution of [441] may remove the need for this
> type entirely.

The `dx::linalg::InterpretedVector` struct is a wrapper around `vector`, adding
an interpretation value that controls how the data in the vector should be
interpreted. Although the struct can be used directly, it is likely more
ergonomic to use the `dx::linalg::MakeInterpretedVector` function that's also
described here.

Example usage:

```c++
ByteAddressBuffer Buffer;
void Example() {
  using namespace dx::linalg;

  MatrixRef<DATA_TYPE_FLOAT16, 128, 128, MATRIX_LAYOUT_MUL_OPTIMAL, true>
      Matrix = {Buffer, 0, 0};

  vector<float, 128> V = 0;
  vector<float, 128> Result =
      Mul<float>(Matrix, MakeInterpretedVector<DATA_TYPE_FLOAT8_E4M3>(V));

  // alternative:
  InterpretedVector<float, 128, DATA_TYPE_FLOAT8_E4M3> IV = {V};
  vector<float, 128> Result2 = Mul<float>(Matrix, IV);
}
```

Implementation:

```c++
namespace dx {
namespace linalg {

template <typename T, int N, DataType DT> struct InterpretedVector {
  vector<T, N> Data;
};

template <DataType DT, typename T, int N>
InterpretedVector<T, N, DT> MakeInterpretedVector(vector<T, N> Vec) {
  InterpretedVector<T, N, DT> IV = {Vec};
  return IV;
}

} // namespace linalg
} // namespace dx
```

[441]: https://github.com/microsoft/hlsl-specs/issues/441

### Function: Mul

The `dx::linalg::Mul` function performs a matrix-vector multiplication. The
matrix is stored in memory, while the vector comes from a variable. The Mul
function expects the memory backing the matrix object to be read-only
(for efficient loads and hardware optimizations) and, therefore, the matrix
must be of MatrixRef type (and not RWMatrixRef type).

> TODO: add an example for packed types, and make sure they work correctly

Example:

```c++
ByteAddressBuffer Buffer;
float4 Example(float4 Input) {
  using namespace dx::linalg;

  MatrixRef<DATA_TYPE_FLOAT16, 4, 4, MATRIX_LAYOUT_MUL_OPTIMAL, true> Matrix = {
      Buffer, 0, 0};

  return Mul<float>(Matrix, MakeInterpretedVector<DATA_TYPE_FLOAT16>(Input));
}
```

Conceptual API (only the template parameters required are shown - all others are
deduced):

```c++
namespace dx {
namespace linalg {

template<typename TYo>
vector<TYo, M_M> Mul(MatrixRefImpl<...> Matrix, Vector<...> InputVector);

} // namespace linalg
} // namespace dx
```

See [Proposal 0029] for details of this operation.

> TODO: details of what this function does really belong in here as well, but
> for now the source-of-truth is [Proposal 0029].

Implementation:

```c++
namespace dx {
namespace linalg {

template <typename OutputElTy, typename InputElTy, int InputElCount,
          typename MatrixBufferTy, DataType InputDT, DataType MatrixDT,
          uint MatrixM, uint MatrixK, MatrixLayout MatrixLayout,
          bool MatrixTranspose>
vector<OutputElTy, MatrixM>
Mul(MatrixRefImpl<MatrixBufferTy, MatrixDT, MatrixM, MatrixK, MatrixLayout,
                  MatrixTranspose>
        Matrix,
    InterpretedVector<InputElTy, InputElCount, InputDT> InputVector) {

  vector<OutputElTy, MatrixM> OutputVector;

  __builtin_MatVecMul(
      /*out*/ OutputVector, details::IsUnsigned<OutputElTy>(), InputVector.Data,
      details::IsUnsigned<InputElTy>(), InputDT, Matrix.Buffer,
      Matrix.StartOffset, MatrixDT, MatrixM, MatrixK, MatrixLayout,
      MatrixTranspose, Matrix.Stride);

  return OutputVector;
}

} // namespace linalg
} // namespace dx
```

## Function: MulAdd

The `dx::linalg::MulAdd` function behaves as `dx::linalg::Mul`, but also adds a
bias vector (loaded from memory) to the result. Similar to the the matrix
operand, the memory backing the bias vector must be read-only, and therefore an
object of `VectorRef` type (and not `RWVectorRef` type).

Example:

```c++
ByteAddressBuffer Buffer;

void Example() {
  using namespace dx::linalg;

  MatrixRef<DATA_TYPE_FLOAT8_E4M3, 32, 8, MATRIX_LAYOUT_MUL_OPTIMAL> Matrix = {
      Buffer, 0, 0};

  VectorRef<DATA_TYPE_FLOAT16> BiasVector = {Buffer, 1024};

  vector<float, 8> V = 0;
  vector<float, 32> Result = MulAdd<float>(
      Matrix, MakeInterpretedVector<DATA_TYPE_FLOAT8_E4M3>(V), BiasVector);
}
```

Conceptual API:

```c++
template<typename TYo>
vector<TYo, M_M> Mul(MatrixRefImpl<...> Matrix, Vector<...> InputVector, VectorRefImpl<...> BiasVector);
```

See [Proposal 0029] for details of this operation.

> TODO: details of what this function does really belong in here as well, but
> for now the source-of-truth is [Proposal 0029].

Implementation:

```c++
namespace dx {
namespace linalg {

template <typename OutputElTy, typename InputElTy, int InputElCount,
          typename MatrixBufferTy, DataType InputDT, DataType MatrixDT,
          uint MatrixM, uint MatrixK, MatrixLayout MatrixLayout,
          bool MatrixTranspose, typename BiasVectorBufferTy,
          DataType BiasVectorDT>
vector<OutputElTy, MatrixM>
MulAdd(MatrixRefImpl<MatrixBufferTy, MatrixDT, MatrixM, MatrixK, MatrixLayout,
                     MatrixTranspose>
           Matrix,
       InterpretedVector<InputElTy, InputElCount, InputDT> InputVector,
       VectorRefImpl<BiasVectorBufferTy, BiasVectorDT> BiasVector) {

  vector<OutputElTy, MatrixM> OutputVector;

  __builtin_MatVecMulAdd(
      /*out*/ OutputVector, details::IsUnsigned<OutputElTy>(), InputVector.Data,
      details::IsUnsigned<InputElTy>(), InputDT, Matrix.Buffer,
      Matrix.StartOffset, MatrixDT, MatrixM, MatrixK, MatrixLayout,
      MatrixTranspose, Matrix.Stride, BiasVector.Buffer, BiasVector.StartOffset,
      BiasVectorDT);

  return OutputVector;
}

} // namespace linalg
} // namespace dx
```

## Function: OuterProductAccumulate

`dx::linalg::OuterProductAccumulate` computes the outer product between column
vectors and an **M**x**N** matrix is accumulated component-wise atomically (with
device scope) in memory.

The operation is equivalent to:

> ResultMatrix += InputVector1 \* Transpose(InputVector2);

Example:

```c++
RWByteAddressBuffer RWBuf;

void Example(vector<half, 128> Input1, vector<half, 256> Input2) {
  using namespace dx::linalg;

  RWMatrixRef<DATA_TYPE_FLOAT16, 128, 256, MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL>
      Matrix = {RWBuf, 0, 0};

  OuterProductAccumulate(Input1, Input2, Matrix);
}
```

Conceptual API:

```c++
namespace dx {
namespace linalg {

void OuterProductAccumulate(vector<T, M> InputVector1,
                            vector<T, N> InputVector2,
                            RWMatrixRef<...> Matrix);

} // namespace linalg
} // namespace dx
```

Parameters:

- `InputVector1` - the first vector, containing M elements. Element type must
  be the same as InputVector2's.
- `InputVector2` - the second vector, containing N elements. Element type must
  be the same as InputVector1's.
- `Matrix` - the destination matrix. The matrix dimensions must be MxN. The
  `Transpose` parameter for the matrix must be `false`. The `ML`  parameter
  (matrix layout) for the matrix must be
  `dx::linalg::MatrixLayout::MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL`. The `stride`
  parameter must be zero (for optimal layouts).

Implementation:

```c++
namespace dx {
namespace linalg {

template <typename ElTy, int MatrixM, int MatrixN, DataType MatrixDT,
          MatrixLayout MatrixLayout>
void OuterProductAccumulate(
    vector<ElTy, MatrixM> InputVector1, vector<ElTy, MatrixN> InputVector2,
    RWMatrixRef<MatrixDT, MatrixM, MatrixN, MatrixLayout, false> Matrix) {
  __builtin_OuterProductAccumulate(InputVector1, InputVector2, Matrix.Buffer,
                                   Matrix.StartOffset, MatrixDT, MatrixLayout,
                                   Matrix.Stride);
}

} // namespace linalg
} // namespace dx
```

Diagnostics:

- Emit Diagnostic if MatrixLayout is not
  `dx::linalg::MatrixLayout::MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL`.

## Function: VectorAccumulate

`dx::linalg::VectorAccumulate` accumulates the components of a vector
component-wise atomically (with device scope) to the corresponding elements of
an array in memory.

Example:

```c++
RWByteAddressBuffer RWBuf;

void Test(vector<half, 128> Input) {
  using namespace dx::linalg;
  VectorAccumulate(Input, RWBuf, 0);
}
```

Conceptual API:

```c++
namespace dx {
namespace linalg {

void VectorAccumulate(vector<...> InputVector, RWByteAddressBuffer Buffer, uint Offset);

} // namespace linalg
} // namespace dx
```

Parameters:

- `InputVector` - the input vector
- `Buffer` - the buffer containing the output array
- `Offset` - the offset in bytes from the start of the buffer to the start of
  output array

Implementation:

```c++
namespace dx {
namespace linalg {

template <typename ElTy, int ElCount>
void VectorAccumulate(vector<ElTy, ElCount> InputVector,
                      RWByteAddressBuffer Buffer, uint Offset) {
  __builtin_VectorAccumulate(InputVector, Buffer, Offset);
}

} // namespace linalg
} // namespace dx
```

## Alternatives considered (Optional)

TBD

## Acknowledgments (Optional)

We would like to thank Jeff Bolz for his contribution to this spec.

<!-- {% endraw %} -->
