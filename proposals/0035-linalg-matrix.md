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
  NOp = 0,
  Negate = 1,
  Abs = 2,
  Sin = 3,
  Cos = 4,
  Tan = 5,
};

template <MatrixComponentType ComponentTy, uint M, uint N, MatrixUse Use,
          MatrixScope Scope>
class Matrix {
  using ElementType = __detail::ComponentTypeTraits<ComponentTy>::Type;

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
  Matrix ApplyUnaryOperation();

  template <typename T>
    requires ArithmeticScalar<T>
  static Matrix Splat(T Val);
  static Matrix
  Load(ByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
       uint Align = sizeof(ElementType));
  static Matrix
  Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
       uint Align = sizeof(ElementType));

  template <typename T>
    requires ArithmeticScalar<T>
  static Matrix Load(groupshared T Arr[], uint StartIdx, uint Stride,
                     bool ColMajor);

  void
  Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
        uint Align = sizeof(ElementType));

  template <typename T>
    requires ArithmeticScalar<T>
  void Store(groupshared T Arr[], uint StartIdx, uint Stride,
             bool ColMajor);

  // Row accesses
  vector<ElementType, M> GetRow(uint Index);
  void SetRow(vector<ElementType, M> V, uint Index);

  // Element access
  std::enable_if_t<__detail::ComponentTypeTraits<ComponentTy>::IsNativeScalar,
                   ElementType>
  Get(uint2 Index);
  std::enable_if_t<__detail::ComponentTypeTraits<ComponentTy>::IsNativeScalar,
                   void>
  Set(ElementType V, uint2 Index);

  template <typename T, uint K>
    requires ArithmeticScalar<T>
  std::enable_if_t<Use == MatrixUse::Accumulator && Scope == MatrixScope::Wave,
                   void>
  MultiplyAccumulate(const Matrix<T, M, K, MatrixUse::A, Scope> &,
                     const Matrix<T, K, N, MatrixUse::B, Scope> &);

  template <typename T, unit K>
    requires ArithmeticScalar<T>
  std::enable_if_t<Use == MatrixUse::Accumulator && Scope == MatrixScope::Wave,
                   void>
  SumAccumulate(const Matrix<T, M, K, MatrixUse::A, Scope>,
                const Matrix<T, K, N, MatrixUse::B, Scope>);

  // Cooperative Vector outer product accumulate.
  template <typename T>
  std::enable_if_t<Use == MatrixUse::Accumulator, void>
  OuterProductAccumulate(const vector<T, M> &, const vector<T, N> &);
};

template <typename T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::A, MatrixScope::Wave>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::Wave>);

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
vector<OutputElTy, K>
MultiplyAdd(vector<InputElTy, M> InputVector,
            Matrix<MatrixDT, M, K, MatrixUse::B, Scope> Matrix,
            vector<BiasElTy, K> BiasVector);

} // namespace linalg
} // namespace hlsl
```

## Detailed design

### HLSL API Concepts

The new HLSL API introduces a new `linalg::Matrix` type which represents an
opaque matrix object, and contains an intangible handle that refers to the
allocated matrix.

The `linalg::Matrix` template type is parameterized based on the matrix
component data type, dimensions, use, and scope. These parameters restrict where
and how a matrix can be used.

#### Matrix Use

The `Use` parameter of an instance of a `linalg::Matrix` denotes which argument
it can be in matrix-matrix operations or matrix-vector operations.

There are three matrix usages: `A`, `B`, and `Accumulator`.
* The `A` matrix usage denotes a matrix that can be the first argument to binary
  or ternary algebraic operations.
* The `B` matrix usage denotes a matrix that can the second argument to binary
  or ternary algebraic operations.
* The `Accumulator` matrix usage denotes a matrix that can either be a produced
  result from a binary arithmetic operation, or the third argument to a ternary
  algebraic operation.

#### Matrix Scope

The `Scope` parameter of an instance of a `linalg::Matrix` denotes the
uniformity scope of the matrix. The scope impacts which operations can be
performed on the matrix and may have performance implications depending on the
implementation.

There are two supported matrix scopes: `Thread` and `Wave`.
* The `Thread` matrix scope denotes that a matrix's values may vary by thread,
  which requires that an implementation handle divergent matrix values.
* The `Wave` matrix scope denotes that a matrix's values are uniform across a
  wave, which allows an implementation to assume all instances of the matrix
  across a wave are identical.

Some operations require `Wave` scope matrices, while others can operate on
`Thread` scope matrices. All operations that can operate on `Thread` scope
matrices can also operate on `Wave` scope matrices, and there may be significant
performance benefit when using `Wave` scope matrices.

### HLSL API Documentation

#### HLSL Enumerations
```c++
enum class MatrixComponentType {
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
};

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
  NOp = 0,
  Negate = 1,
  Abs = 2,
  Sin = 3,
  Cos = 4,
  Tan = 5,
};

```

#### Helper type traits

```c++
namespace __detail {
template<MatrixComponentType T>
struct ComponentTypeTraits {
    using Type = uint;
    static const bool IsNativeScalar = false;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::I16> {
    using Type = int16_t;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::U16> {
    using Type = uint16_t;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::I32> {
    using Type = int32_t;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::U32> {
    using Type = uint32_t;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::I64> {
    using Type = int64_t;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::U64> {
    using Type = uint64_t;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::F16> {
    using Type = float16_t;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::F32> {
    using Type = float;
    static const bool IsNativeScalar = true;
};

template<>
struct ComponentTypeTraits<MatrixComponentType::F64> {
    using Type = double;
    static const bool IsNativeScalar = true;
};
} // namespace __detail
```

The `linalg::__detail::ComponentTypeTraits` struct is provided as an
implementation detail to enable mapping `MatrixComponentType` values to their
native HLSL element types and differentiating between types that have native
scalar support.

#### Matrix::cast

```c++
template <MatrixComponentType NewCompTy, MatrixUse NewUse = Use>
Matrix<NewCompTy, M, N, NewUse, Scope> Matrix::cast();
```

The `Matrix::cast()` function supports casting component types and matrix `Use`.

#### Element-wise Operators

```c++
template <typename T>
  requires ArithmeticScalar<T>
Matrix Matrix::operator+(T);
template <typename T>
  requires ArithmeticScalar<T>
Matrix Matrix::operator-(T);
template <typename T>
  requires ArithmeticScalar<T>
Matrix Matrix::operator*(T);
template <typename T>
  requires ArithmeticScalar<T>
Matrix Matrix::operator/(T);
```

For any arithmetic scalar type the `+`, `-`, `*` and `/` binary operators
perform element-wise arithmetic on the matrix. The returned by-value `Matrix`
contains the same handle and refers to the same (now modified) `Matrix`.

#### Matrix::ApplyUnaryOperation<>()

```c++
template<linalg::UnaryOperation Op>
Matrix Matrix::ApplyUnaryOperation();
```

Taking the `linalg::UnaryOperation` enumeration value as a template parameter,
this function applies a unary operation to each element in the matrix. Each
unary operation will behave with regard to special values in the same way as if
the standalone HLSL intrinsic had been applied.

#### Matrix::Splat(T)


```c++
template <typename T>
  requires ArithmeticScalar<T>
static Matrix Matrix::Splat(T Val);
```

Constructs a matrix filled with the provided value casted to the element type.
If the matrix is a `Wave` scope matrix, this operation shall behave equivalent
to:

```c++
Matrix::Splat(WaveReadLaneFirst(Val));
```

#### Matrix::Load

```c++
static Matrix Matrix::Load(
    ByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
    uint Align = sizeof(__detail::ComponentTypeTraits<ComponentTy>::Type));

static Matrix Matrix::Load(
    RWByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
    uint Align = sizeof(__detail::ComponentTypeTraits<ComponentTy>::Type));

template <typename T>
  requires ArithmeticScalar<T>
static Matrix Matrix::Load(groupshared T Arr[], uint StartIdx, uint Stride,
                           bool ColMajor);
```

The matrix `Load` methods create a new matrix of the specified dimensions and
fill the matrix by reading data from the supplied source. Matrices can be read
from `[RW]ByteAddressBuffer` objects or `groupshared` arrays. When read from
`[RW]ByteAddressBuffer` objects the data is assumed to already be in the
expected target data format. When read from `groupshared` memory, the data may
be in any arithmetic or packed data type. If the type mismatches the target data
type of the matrix a data conversion is applied on load.


#### Matrix::Store

```c++
void Matrix::Store(
    RWByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
    uint Align = sizeof(__detail::ComponentTypeTraits<ComponentTy>::Type));

template <typename T>
  requires ArithmeticScalar<T>
void Matrix::Store(groupshared T Arr[], uint StartIdx, uint Stride,
                   bool ColMajor);
```

The matrix `Store` methods store the matrix data to a target
`RWByteAddressBuffer` or `groupshared` array. When storing to
`RWByteAddressBuffer` objects the data is stored in the component type of the
matrix object. When storing to `groupshared` memory, the matrix component data
is converted to the target arithmetic or packed data type if the data types do
not match.

#### Matrix::GetRow(uint)

```c++
vector<ElementType, M> Matrix::GetRow(uint Index);
```

Returns a row vector of the matrix as a vector of the underlying HLSL native
element type. If `Index` is out of range for the matrix size the result is a `0`
filled vector.


#### Matrix::SetRow(vector<ElementType, M>, uint)

```c++
void Matrix::SetRow(vector<ElementType, M> V, uint Index);
```

Sets the specified matrix row to the value in the vector V. If the matrix scope
is `Wave`, this behaves as if called as `SetRow(WaveReadLaneFirst(V), Index)`.
If the `Index` is out of range of the matrix, this is a no-op.

#### Matrix::Get(uint2)

```c++
std::enable_if_t<__detail::ComponentTypeTraits<ComponentTy>::IsNativeScalar,
                 ElementType>
Matrix::Get(uint2 Index);
```

Accesses a specific component of the matrix using two-dimensional indexing. This
method is only available if the component type has has native scalar support in
HLSL. If the `Index` parameter is out-of range for the matrix the result is `0`
casted to `ElementType`.

#### Matrix::Set(ElementType, uint2)

```c++
std::enable_if_t<__detail::ComponentTypeTraits<ComponentTy>::IsNativeScalar,
                 void>
Matrix::Set(ElementType V, uint2 Index);
```

Sets a specified element of the matrix to the provided value. If the matrix
scope is `Wave`, this behaves as if called as `Set(WaveReadLaneFirst(V), Index)`.
If the `Index` is out of range, this is a no-op.

#### Matrix::MultiplyAccumuate(Matrix, Matrix)

```c++
template <typename T, uint K>
  requires ArithmeticScalar<T>
std::enable_if_t<Use == MatrixUse::Accumulator && Scope == MatrixScope::Wave,
                 void>
Matrix::MultiplyAccumulate(const Matrix<T, M, K, MatrixUse::A, Scope>,
                           const Matrix<T, K, N, MatrixUse::B, Scope>);
```

A matrix with the `Accumulator` use and `Wave` scope has a method
`MultiplyAccumulate` which takes as parameters an M x K `A` matrix and a K x N
`B` matrix. The matrix arguments are multiplied against each other and added
back into the implicit object `Accumulator` matrix.

#### Matrix::SumAccumulate(Matrix, Matrix)

```c++
template <typename T>
  requires ArithmeticScalar<T>
std::enable_if_t<Use == MatrixUse::Accumulator, void>
Matrix::SumAccumulate(const Matrix<T, N, M, MatrixUse::A, Scope>,
              const Matrix<T, N, M, MatrixUse::B, Scope>);
```

A matrix with the `Accumulator` use and `Wave` scope has a method
`SumAccumulate` which takes as parameters an M x K `A` matrix and a K x N
`B` matrix. The matrix arguments are added together then added back into the
implicit object `Accumulator` matrix.

#### Matrix::OuterProductAccumulate(vector, vector)

```c++
template <typename T>
std::enable_if_t<Use == MatrixUse::Accumulator, void>
Matrix::OuterProductAccumulate(const vector<T, M> &, const vector<T, N> &);
```

A matrix with the `Accumulator` use has a method `OuterProductAccumulate` which
takes an M-element vector and an N-element vector. The operation performs an
outer product of the two vectors to produce an MxN matrix which is then added
back into the implicit object `Accumulator` matrix.

#### linalg::Multiply(Matrix, Matrix)

```c++
template <typename T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::A, MatrixScope::Wave>
linalg::Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::Wave>);
```

The `linalg::Multiply` function has an overload that takes an MxK `Wave`-scope
`A` matrix, and a KxN `Wave`-scope `B` matrix and yields an MxN `Wave`-scope
`Accumlator` matrix initialized with the product of the two input matrices.

#### linalg::Multiply(vector, Matrix)

``` c++
template <typename OutputElTy, typename InputElTy, uint M, uint K,
          MatrixComponentType MatrixDT, MatrixScope Scope, bool MatrixTranspose>
vector<OutputElTy, K>
linalg::Multiply(vector<InputElTy, M> InputVector,
         Matrix<MatrixDT, M, K, MatrixUse::B, Scope> Matrix);
```

The `linalg::Multiply` function has an overload that takes an `M`-element vector
and an MxK `B` matrix of any scope. The function returns a `K`-element vector.

#### linalg::MultiplyAdd(vector, Matrix, vector)

``` c++
template <typename OutputElTy, typename InputElTy, typename BiasElTy, uint M,
          uint K, MatrixComponentType MatrixDT, MatrixScope Scope,
          bool MatrixTranspose>
vector<OutputElTy, K>
linalg::MultiplyAdd(vector<InputElTy, M> InputVector,
            Matrix<MatrixDT, M, K, MatrixUse::B, Scope> Matrix,
            vector<BiasElTy, K> BiasVector);
```

The `linalg::MultiplyAdd` function has an overload that takes an `M`-element, an
MxK `B` matrix of any scope, and a `K`-element vector. The operation multiplies
the `M`-element vector by the matrix then adds the `K`-element vector producing
a result `K`-element vector.

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
