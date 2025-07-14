<!-- {% raw %} -->

# Linear Algebra Matrix

* Proposal: [0035](0035-linalg-matrix.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: TBD
* Status: **Under Review**
* Planned Version: SM 6.x

## Introduction

GPUs are exceptional parallel data processors, but increasingly it is becoming
important to model operations with cross-thread data dependencies. In HLSL and
Direct3D these operations have been called Wave operations, or in Vulkan
Subgroup operations. Related terms like Quad or derivatives have similar
meaning in different scoping contexts. Vulkan has also recently introduced the
term "cooperative" when talking about operations that require participation from
multiple threads, these can be viewed much like derivative operations but across
the full SIMD unit instead of a subset of threads.

All of these terms refer to the way the underlying instructions execute, not
necessarily what they do. One big part of this proposal is to take 5 steps back
and talk about what they do: linear algebra.

## Motivation

HLSL has a Vulkan extension for SIMD matrix types [0021 - vk::Cooperative
Matrix](0021-vk-coop-matrix.md), and DirectX had previewed a similar feature in
SM 6.8 called [Wave Matrix](https://github.com/microsoft/hlsl-specs/pull/61).
This proposal is aimed at merging the two into a unified language feature that
can be supported on all platforms (with some platform-specific limitations).

This proposal is similar but not directly aligned with [0031 - HLSL Vector
Matrix Operations](/proposals/0031-hlsl-vector-matrix-operations.md).

## Proposed solution

Below is a proposed pseudo-HLSL API. The proposal uses C++20 concepts to
represent template type constraints so as to avoid needing SFINAE complications.

```c++
namespace hlsl {

template <class T>
concept ArithmeticScalar = std::is_arithmetic<T>::value;

namespace linalg {

enum class MatrixUse {
  A = 0,
  B = 1,
  Accumulator = 2,
};

enum class MatrixScope {
  Thread = 0,
  Wave = 1,
};

enum class UnaryOperation {
  nop = 0,
  negate = 1,
  abs = 2,
  sin = 3,
  cos = 4,
  tan = 5,
  // What elementwise unary operations make sense?
};

template <MatrixComponentType ComponentTy, uint M, uint N, MatrixUse Use,
          MatrixScope Scope>
class Matrix {
  template <MatrixComponentType NewCompTy, MatrixUse NewUse = Use>
  Matrix<NewCompTy, M, N, NewUse, Scope> cast();

  // Element-wise operations
  template <typename T>
    requires ArithmeticScalar<T>
  Matrix operator+(T);
  template <typename T>
    requires ArithmeticScalar<T>
  Matrix operator-(T);
  template <typename T>
    requires ArithmeticScalar<T>
  Matrix operator*(T);
  template <typename T>
    requires ArithmeticScalar<T>
  Matrix operator/(T);

  // Apply a unary operation to each element.
  template<UnaryOperation Op>
  Matrix unaryOperation();

  template <typename T>
    requires ArithmeticScalar<T>
  static Matrix Splat(T Val);
  static Matrix
  Load(ByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
       uint Align = sizeof(__detail::ComponentTyMapping<ComponentTy>::Type));
  static Matrix
  Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
       uint Align = sizeof(__detail::ComponentTyMapping<ComponentTy>::Type));

  template <typename T>
    requires ArithmeticScalar<T>
  static Matrix Load(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
                     bool ColMajor);

  void
  Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
        uint Align = sizeof(__detail::ComponentTyMapping<ComponentTy>::Type));

  template <typename T>
    requires ArithmeticScalar<T>
  void Store(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
             bool ColMajor);

  // Row accesses
  vector<ComponentTy, M> GetRow(uint Index);
  void SetRow(vector<ComponentTy, M> V, uint Index);

  // Element access
  ComponentTy Get(uint2 Index);
  void Set(ComponentTy V, uint2 Index);

  template <typename T>
    requires ArithmeticScalar<T>
  std::enable_if_t<Use == MatrixUse::Accumulator, void>
  MultiplyAccumulate(const Matrix<T, N, M, MatrixUse::A, Scope> &,
                     const Matrix<T, N, M, MatrixUse::B, Scope> &);

  template <typename T>
    requires ArithmeticScalar<T>
  std::enable_if_t<Use == MatrixUse::Accumulator, void>
  SumAccumulate(const Matrix<T, N, M, MatrixUse::A, Scope> &,
                const Matrix<T, N, M, MatrixUse::B, Scope> &);

  // Cooperative Vector outer product accumulate.
  template <typename T>
  std::enable_if_t<Use == MatrixUse::Accumulator, void>
  OuterProductAccumulate(const vector<T, M> &, const vector<T, N> &);
};

template <typename T, uint M, uint N, uint K, MatrixScope Scope>
Matrix<T, M, N, MatrixUse::A, Scope>
Multiply(const Matrix<T, M, K, MatrixUse::A, Scope>,
         const Matrix<T, K, N, MatrixUse::B, Scope>);

// Cooperative Vector Replacement API
// Cooperative Vector operates on per-thread vectors multiplying against B
// matrices.

template <typename OutputElTy, typename InputElTy, uint M, uint K,
          MatrixComponentType MatrixDT, MatrixScope Scope, bool MatrixTranspose>
vector<OutputElTy, K>
Multiply(vector<InputElTy, M> InputVector,
         Matrix<MatrixDT, M, K, MatrixUse::B, Scope> Matrix);

template <typename OutputElTy, typename InputElTy, typename BiasElTy, uint M,
          uint K, MatrixComponentType MatrixDT, MatrixScope Scope,
          bool MatrixTranspose>
vector<OutputElTy, M>
MultiplyAdd(vector<InputElTy, K> InputVector,
            Matrix<MatrixDT, M, K, MatrixUse::B, Scope> Matrix,
            vector<BiasElTy, M> BiasVector);

} // namespace linalg
} // namespace hlsl
```

## Detailed design

### DXIL Enumerations

This feature adds the following new DXIL enumerations, which used as immediate
arguments to the new operations.

```c++
enum class DXILMatrixUse {
  A = 0,
  B = 1,
  Accumulator = 2,
};

enum class DXILMatrixScope {
  Thread = 0,
  Wave = 1,
};

enum class DXILMatrixUnaryOperation {
  nop = 0,
  negate = 1,
  abs = 2,
  sin = 3,
  cos = 4,
  tan = 5,
};

enum class DXILMatrixElementwiseOperation {
  invalid = 0;
  add = 1;
  sub = 2;
  mul = 3;
  div = 4;
};

enum class DXILMatrixComponentType {
  Invalid = 0,
  I1 = 1,
  I16 = 2,
  U16 = 3,
  I32 = 4,
  U32 = 5,
  I64 = 6,
  U64 = 7,
  F16 = 8,
  F32 = 9,
  F64 = 10,
  SNormF16 = 11,
  UNormF16 = 12,
  SNormF32 = 13,
  UNormF32 = 14,
  SNormF64 = 15,
  UNormF64 = 16,
  PackedS8x32 = 17,
  PackedU8x32 = 18,
}
```

### DXIL Operations

```llvm
declare %dx.types.MatrixRef *@dx.op.createMatrix(
  immarg i32, ; opcode
  immarg i32, ; component type (DXILMatrixComponentType)
  immarg i32, ; M dimension
  immarg i32, ; N dimension
  immarg i32, ; matrix Use (DXILMatrixUse)
  immarg i32  ; matrix Scope (DXILMatrixScope)
  )
```

Creates a new uninitialized matrix with the component, dimensions, use and scope
as specified.

```llvm
declare @dx.op.fillMatrix.[TY](
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix
  [Ty]                   ; fill value
  )
```

Fills a matrix with a scalar value. The scalar's type does not need to match the
matrix component's type.

```llvm
declare void @dx.op.castMatrix(
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix destination
  %dx.types.MatrixRef *  ; matrix source
  )
```

Converts the element and use type of the source matrix to the destination
matrix. Validation shall enforce that both matrices have the same scope.

```llvm
declare void @dx.op.matrixElementwiseUnaryOp(
  immarg i32,            ; opcode
  immarg i32,            ; unary operation (DXILMatrixUnaryOperation)
  %dx.types.MatrixRef *, ; matrix
  )
```

Applies a unary math function to each element of the provided matrix.


```llvm
declare void @dx.op.matrixElementwiseBinaryOp.[TY](
  immarg i32,            ; opcode
  immarg i32,            ; unary operation (DXILMatrixElementwiseOperation)
  %dx.types.MatrixRef *, ; matrix
  [TY]                   ; Value to binary operation
  )
```

Applies a binary math operation with a wave-uniform value to the elements of the
provided matrix.

```llvm
declare void @dx.op.matrixLoadFromDescriptor(
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix
  %dx.types.Handle *,    ; ByteAddressBuffer
  i32,                   ; Offset
  i32,                   ; Stride
  i1,                    ; isColumnMajor
  )
```

Populates a matrix with data from a [RW]ByteAddressBuffer. If any member of the
matrix is OOB the matrix is returned zero-initialized.

> Question: Do we need to specify a source format for the data or should we
> assume DXILMatrixComponentType?

```llvm
declare void @dx.op.matrixLoadFromMemory.p[Ty](
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix
  [Ty] * addrspace(4),   ; groupshared T[M * N]
  i32,                   ; Offset
  i32,                   ; Stride
  i1,                    ; isColumnMajor
  )
```

Populates a matrix with data from a `groupshared` array. Data conversions
between opaque matrices and groupshared memory are defined in the [Conversions
on groupshared memory](#conversions-on-groupshared-memory) section below.

```llvm
declare void @dx.op.matrixStoreToDescriptor(
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix
  %dx.types.Handle *,    ; ByteAddressBuffer
  i32,                   ; Offset
  i32,                   ; Stride
  i1,                    ; isColumnMajor
  )
```

Store a matrix to a RWByteAddressBuffer at a specified offset. If any
destination address is out of bounds the entire store is a no-op.

```llvm
declare void @dx.op.matrixStoreToMemory.p[Ty](
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix
  [Ty] *,                ; groupshared T[M * N]
  i32,                   ; Offset
  i32,                   ; Stride
  i1,                    ; isColumnMajor
  )
```

Store a matrix to groupshared memory. Data conversions between opaque matrices
and groupshared memory are defined in the [Conversions on groupshared
memory](#conversions-on-groupshared-memory) section below.

```llvm
declare void @dx.op.matrixOp(
  immarg i32             ; opcode
  %dx.types.MatrixRef *, ; matrix A
  %dx.types.MatrixRef *, ; matrix B
  %dx.types.MatrixRef *  ; matrix C
  )
```

Two opcodes are available for this operation class, one for multiplying matrices
and storing the result as `C = A * B`. The second for multiply accumulation `C
+= A * B`.

Validation rules will enforce that:
* argument A is an `A` matrix
* argument B is a `B` matrix
* argument C is an `Accumulator` matrix
* All three matrices are `Wave` scope
* Matrix A's dimensions shall be M x K
* Matrix B's dimensions shall be K x N
* Matrix C's dimensions shall be M x N
* The element types are compatible

``` llvm
declare <[NUMo] x [TYo]> @dx.op.matvecmul.v[NUMo][TYo].v[NUMi][TYi](
  immarg i32            ; opcode
  <[NUMi] x [TYi]>,     ; input vector
  %dx.types.MatrixRef * ; matrix A
)
```

This operation implements a row-vector multiplication against a `B` matrix.

> Note for this operation the matrix can be of any scope.

Validation will enforce that:
* The input vector is an `N` element vector
* The matrix A is a `B` matrix

``` llvm
declare <[NUMo] x [TYo]> @dx.op.matvecmuladd.v[NUMo][TYo].v[NUMi][TYi](
  immarg i32             ; opcode
  <[NUMi] x [TYi]>,      ; input vector
  %dx.types.MatrixRef *, ; matrix A
  <[NUMo] x [TYo]>       ; bias vector
)
```

This operation implements a row-vector multiplication against a `B` matrix with
a bias vector added to the result.

> Note for this operation the matrix can be of any scope.

```llvm
declare <[NUMo] x [TYo]> @dx.op.matrixLoadRow.v[NUMo][Tyo](
  immarg i32             ; opcode
  %dx.types.MatrixRef *, ; matrix A
  i32                    ; row index
  )
```

Loads a row-vector from a matrix. Out of bounds reads return `0`.

```llvm
declare void @dx.op.matrixStoreRow.v[NUMi][Tyi](
  immarg i32             ; opcode
  %dx.types.MatrixRef *, ; matrix A
  i32,                   ; index
  <[NUMi] x [Tyi]>       ; row vector
  )
```

Stores a row-vector to a matrix. Out of bounds writes no-op.

### Conversions on groupshared memory

## Outstanding Questions

* What is the exhaustive list of data types we need to support?
* What data type conversions do we need to support?
* Do we need load and store per-element accessors or is row enough?
* Support for other number formats that aren't natively supported by HLSL?
* Do we need to specify a source/destination format for the data in the load and
  store operations that operate on descriptors or should we assume
  DXILMatrixComponentType?

<!-- {% endraw %} -->
