---
title: 0035 - Linear Algebra Matrix
params:
  authors:
  - llvm-beanz: Chris Bieneman
  status: Under Review
---


 
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

Some portion of this API surface is portable between DirectX and Vulkan using the [proposed
DXIL](#dxil-operations) for DirectX and
[SPV_KHR_cooperative_matrix](https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/KHR/SPV_KHR_cooperative_matrix.asciidoc)
for Vulkan. Not all features proposed here are supported in Vulkan, so the API
as described is in the `dx` namespace.

A subsequent revision to HLSL's [0021 - Vulkan Cooperative
Matrix](0021-vk-coop-matrix.md) support could be considered separately to align
on a base set of functionality for inclusion in the `hlsl` namespace.

```c++
namespace dx {
namespace linalg {

template <MatrixComponentType ComponentTy, uint M, uint N, MatrixUse Use,
          MatrixScope Scope>
class Matrix {
  using ElementType = typename __detail::ComponentTypeTraits<ComponentTy>::Type;
  // If this isn't a native scalar, we have an 8-bit type, so we have 4 elements
  // packed in each scalar value.
  static const uint ElementsPerScalar =
      __detail::ComponentTypeTraits<ComponentTy>::IsNativeScalar ? 1 : 4;
  // Computes the number of scalars actually stored in the matrix M dimension
  // accounting for packing.
  static const uint MScalars =
      (M + (ElementsPerScalar - 1)) / ElementsPerScalar;
  // Computes the number of scalars actually stored in the matrix N dimension
  // accounting for packing.
  static const uint NScalars =
      (N + (ElementsPerScalar - 1)) / ElementsPerScalar;

  template <MatrixComponentType NewCompTy, MatrixUse NewUse = Use>
  Matrix<NewCompTy, M, N, NewUse, Scope> cast();

  // Element-wise operations
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator+=(T);
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator-=(T);
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator*=(T);
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator/=(T);

  // Apply a unary operation to each element.
  template <UnaryOperation Op> Matrix ApplyUnaryOperation();

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Splat(T Val);
  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ElementType));
  static Matrix Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ElementType));

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Load(/*groupshared*/ T Arr[], uint StartIdx, uint Stride, bool ColMajor);

  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::A && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           Matrix>::type
      FromThreadVectors(vector<ElementType, MScalars>);

  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::B && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           Matrix>::type
      FromThreadVectors(vector<ElementType, NScalars>);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             bool ColMajor, uint Align = sizeof(ElementType));

  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, void>::type
  Store(/*groupshared*/ T Arr[], uint StartIdx, uint Stride, bool ColMajor);

  // Extract the thread-specific vector.
  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::A && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           vector<ElementType, MScalars>>::type
  GetThreadVector(uint Index = 0);

  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::B && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           vector<ElementType, NScalars>>::type
  GetThreadVector(uint Index = 0);

  template <MatrixComponentType LHSTy, MatrixComponentType RHSTy, uint K,
            MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                               Scope != MatrixScope::Thread && UseLocal == Use,
                           void>::type
  MultiplyAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                     const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);

  template <MatrixComponentType LHSTy, MatrixComponentType RHSTy, uint K,
            MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                               Scope != MatrixScope::Thread && UseLocal == Use,
                           void>::type
  SumAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);

  // Cooperative Vector outer product accumulate.
  template <typename T, MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  OuterProductAccumulate(const vector<T, M>, const vector<T, N>);
};

MatrixUse AccumulatorLayout();

template <MatrixComponentType OutTy, MatrixComponentType ATy,
          MatrixComponentType BTy, uint M, uint N, uint K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::Wave>);

template <MatrixComponentType T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::Wave>);

template <MatrixComponentType OutTy, MatrixComponentType ATy,
          MatrixComponentType BTy, uint M, uint N, uint K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

template <MatrixComponentType T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

// Cooperative Vector Replacement API
// Cooperative Vector operates on per-thread vectors multiplying against B
// matrices.

template <typename OutputElTy, typename InputElTy, uint M, uint K,
          MatrixComponentType MatrixDT, MatrixScope Scope>
vector<OutputElTy, K> Multiply(vector<InputElTy, M>,
                               Matrix<MatrixDT, M, K, MatrixUse::B, Scope>);

template <typename OutputElTy, typename InputElTy, typename BiasElTy, uint M,
          uint K, MatrixComponentType MatrixDT, MatrixScope Scope>
vector<OutputElTy, K> MultiplyAdd(vector<InputElTy, M>,
                                  Matrix<MatrixDT, M, K, MatrixUse::B, Scope>,
                                  vector<BiasElTy, K>);

} // namespace linalg
} // namespace dx
```

### Example Usage: Wave Matrix

```c++
RWByteAddressBuffer B : register(u0);

void WaveMatrixExample() {
  using namespace dx::linalg;
  using MatrixATy =
      Matrix<MatrixComponentType::F16, 8, 32, MatrixUse::A, MatrixScope::Wave>;
  using MatrixBTy =
      Matrix<MatrixComponentType::F16, 32, 16, MatrixUse::B, MatrixScope::Wave>;
  using MatrixAccumTy = Matrix<MatrixComponentType::F16, 8, 16,
                               MatrixUse::Accumulator, MatrixScope::Wave>;
  using MatrixAccum32Ty = Matrix<MatrixComponentType::F32, 8, 16,
                                 MatrixUse::Accumulator, MatrixScope::Wave>;

  MatrixATy MatA = MatrixATy::Load(B, 0, 8 * 4, false);
  MatrixBTy MatB = MatrixBTy::Load(B, 0, 32 * 4, false);

  MatrixAccumTy Accum = Multiply(MatA, MatB);
  MatrixAccum32Ty Accum32 = Multiply<MatrixComponentType::F32>(MatA, MatB);
}
```

### Example Usage: Cooperative Vectors

```c++
RWByteAddressBuffer B : register(u0);

void CoopVec() {
  using namespace dx::linalg;
  using MatrixBTy =
      Matrix<MatrixComponentType::F16, 32, 16, MatrixUse::B, MatrixScope::Wave>;

  vector<float16_t, 32> Vec = (vector<float16_t, 32>)0;
  MatrixBTy MatB = MatrixBTy::Load(B, 0, 32 * 4, false);
  vector<float16_t, 16> Accum = Multiply<float16_t>(Vec, MatB);
}
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

The matrix use type parameter enables implementations to optimize the storage
and layout of the matrix prior to tensor operations. It may be expensive on some
hardware to translate between matrix uses, for that reason we capture the use in
the type and require explicit conversion in the HLSL API.

Throughout this document a matrix may be described as a matrix of it's use (e.g.
a matrix with `Use == Accumulator` is an _accumulator matrix_, while a matrix
with use `A` is an _A matrix_.)

#### Matrix Scope

The `Scope` parameter of an instance of a `linalg::Matrix` denotes the
uniformity scope of the matrix. The scope impacts which operations can be
performed on the matrix and may have performance implications depending on the
implementation.

There are three supported matrix scopes: `Thread`, `Wave`, and `ThreadGroup`.
* The `Thread` matrix scope denotes that a matrix's values may vary by thread,
  which requires that an implementation handle divergent matrix values.
* The `Wave` matrix scope denotes that a matrix's values are uniform across a
  wave, which allows an implementation to assume all instances of the matrix
  across a wave are identical.
* The `ThreadGroup` matrix scope denotes that a matrix's values are uniform
  across a thread group, which allows an implementation to assume all instances
  of the matrix across a thread group are identical.

Operations are categorized by their scope requirements. Some operations require
uniform scope matrices (`Wave` or`ThreadGroup`), while others can operate on
non-uniform (`Thread`) scope matrices. Operations that support non-uniform
scope also support uniform scopes.  There may be significant performance
benefits when using uniform scope matrices.

When using `ThreadGroup` scope matrices, explicit barriers are required only when
there are actual cross-thread dependencies, such as when multiple threads
contribute to building or modifying the matrix before it is used by other
threads. The matrix scope semantics handle most synchronization automatically,
eliminating the need for barriers between every matrix operation.

Throughout this document a matrix may be described as having a scope as
specified by the `Scope` parameter (e.g. a matrix with `Scope == Thread` is a
_matrix with thread scope_).

Matrix storage is always opaque, the `Scope` does not directly restrict how the
matrix is stored, it merely denotes allowed scopes of allowed data divergence.
A matrix with thread scope must behave as if each thread has a unique copy of
the matrix. An implementation may coalesce identical matrices across threads.

#### Matrix Storage

In HLSL, matrix objects are intangible objects so they do not have defined size
or memory layout. When in use, implementations are expected to distribute the
storage of matrices across the thread-local storage for all threads in a SIMD
unit. An implementation may also utilize caches or other memory regions as
appropriate. At the DXIL level a matrix is represented as a handle object.

An A matrix is a collection of per-thread vectors representing matrix rows,
while a B matrix is a collection of per-thread vectors representing matrix
columns.

An Accumulator matrix may be either an A matrix, or a B matrix, and it varies by
hardware implementation.

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
  ThreadGroup = 2,
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

#### New `hlsl` enable_if

```c++
namespace hlsl {
template <bool B, typename T> struct enable_if {};

template <typename T> struct enable_if<true, T> {
  using type = T;
};

} // namespace hlsl
```

This proposal depends on adding a new SFINAE construct `hlsl::enable_if` which
works just like `std::enable_if` in C++.

#### New hlsl type traits

```c++
namespace hlsl {

template <typename T> struct is_arithmetic {
  static const bool value = false;
};

#define __ARITHMETIC_TYPE(type)                                                \
  template <> struct is_arithmetic<type> {                                     \
    static const bool value = true;                                            \
  };

#if __HLSL_ENABLE_16_BIT
__ARITHMETIC_TYPE(uint16_t)
__ARITHMETIC_TYPE(int16_t)
#endif
__ARITHMETIC_TYPE(uint)
__ARITHMETIC_TYPE(int)
__ARITHMETIC_TYPE(uint64_t)
__ARITHMETIC_TYPE(int64_t)
__ARITHMETIC_TYPE(half)
__ARITHMETIC_TYPE(float)
__ARITHMETIC_TYPE(double)

} // namespace hlsl
```

This proposal depends on a new `is_arithmetic` type trait added to the `hlsl`
namespace.

#### dx::linalg::__detail type traits

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
Matrix Matrix::operator+=(T);
template <typename T>
  requires ArithmeticScalar<T>
Matrix Matrix::operator-=(T);
template <typename T>
  requires ArithmeticScalar<T>
Matrix Matrix::operator*=(T);
template <typename T>
  requires ArithmeticScalar<T>
Matrix Matrix::operator/=(T);
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
If the matrix is a `Wave` or `ThreadGroup` scope matrix, this operation shall behave equivalent
to:

```c++
Matrix::Splat(WaveReadLaneFirst(Val));
```

This operation may be called in divergent control flow when creating a thread
scope matrix, and must be called in uniform control flow when creating a wave
scope matrix.

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

This operation may be called in divergent control flow when loading a thread
scope matrix, and must be called in uniform control flow when loading a wave
scope matrix.

#### Matrix::FromThreadVectors

```c++
template <MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::A && Scope != MatrixScope::Thread &&
                              UseLocal == Use,
                          Matrix>::type
    FromThreadVectors(vector<ElementType, MScalars>);

template <MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::B && Scope != MatrixScope::Thread &&
                              UseLocal == Use,
                          Matrix>::type
    FromThreadVectors(vector<ElementType, NScalars>);
```

Produces a matrix from per-thread vectors. An A matrix is produced from
per-thread column vectors, while a B matrix is produced from per-thread row
vectors. The `FromThreadVectors` construction method is not available for
accumulator matrices which vary by hardware implementation.

When creating an A wave scope matrix, the N dimension must be less than or
equal to the wave size.  When creating an A thread group scope matrix, the N
dimension must be less than or equal to the thread group size.

When creating a B wave scope matrix, the M dimension must be less than or
equal to the wave size.  When creating a B thread group scope matrix, the M
dimension must be less than or equal to the thread group size.

Threads outside the matrix size are discarded.

Must be called from wave-uniform control flow.

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

This operation may be called in divergent control flow when storing a thread
scope matrix, and must be called in uniform control flow when storing a wave
scope matrix.

#### Matrix::GetThreadVector(uint)

```c++
template <MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::A && Scope != MatrixScope::Thread &&
                              UseLocal == Use,
                          vector<ElementType, MScalars>>::type
GetThreadVector(uint Index = 0);

template <MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::B && Scope != MatrixScope::Thread &&
                              UseLocal == Use,
                          vector<ElementType, NScalars>>::type
GetThreadVector(uint Index = 0);
```

Returns the underlying vector for the associated thread in the matrix. The
optional index is used when the matrix `K` dimension is larger than the wave
size to compute the starting offset (i.e. `(Index * WaveSize) + ThreadID`).

An A matrix produces a vector containing a column of a matrix, while a B matrix
produces a vector containing a row of the matrix. This method may not be used
on an Accumulator matrix because the matrix layout varies by hardware
implementation.

Threads which correspond to threads outside the matrix size will return a vector
with all elements zero initialized.

Must be called from wave-uniform control flow for a wave scope matrix and
thread group-uniform control flow for a thread group scope matrix..

#### Matrix::MultiplyAccumulate(Matrix, Matrix)

```c++
template <MatrixComponentType LHSTy, MatrixComponentType RHSTy, uint K,
          MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                             Scope != MatrixScope::Thread && UseLocal == Use,
                         void>::type
Matrix::MultiplyAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                           const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);
```

An accumulator matrix with wave or thread group scope has a method `MultiplyAccumulate` which
takes as parameters an M x K A matrix with the same scope and a K x N B matrix with
the same scope. The matrix arguments are multiplied against each other and added
back into the implicit object accumulator matrix.

Must be called from wave-uniform control flow.

#### Matrix::SumAccumulate(Matrix, Matrix)

```c++
template <MatrixComponentType LHSTy, MatrixComponentType RHSTy, uint K,
          MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                             Scope != MatrixScope::Thread && UseLocal == Use,
                         void>::type
Matrix::SumAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                      const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);
```

An accumulator matrix with wave or thread group scope has a method `SumAccumulate` which takes
as parameters an M x K A matrix with the same scope and a K x N B matrix with the same
scope. The matrix arguments are added together then added back into the implicit
object accumulator matrix.

Must be called from wave-uniform control flow.

#### Matrix::OuterProductAccumulate(vector, vector)

```c++
template <typename T, MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                         void>::type
Matrix::OuterProductAccumulate(const vector<T, M>, const vector<T, N>);
```

All accumulator matrix objects regardless of scope have a method
`OuterProductAccumulate` which takes an M-element vector and an N-element
vector. The operation performs an outer product of the two vectors to produce an
MxN matrix which is then added back into the implicit object accumulator
matrix.

#### Matrix::AccumulatorLayout()

```c++
MatrixUse linalg::AccumulatorLayout();
```

Returns the `MatrixUse` that identifies the hardware-dependent layout used by
Accumulator matrices. This can return `MatrixUse::A` or `MatrixUse::B`, and
should be evaluated by the driver compiler as a compile-time constant allowing
optimizing control flow and dead code elimination.

#### linalg::Multiply(Matrix, Matrix)

```c++
template <MatrixComponentType OutTy, MatrixComponentType ATy,
          MatrixComponentType BTy, uint M, uint N, uint K, MatrixScope Scope>
Matrix<OutTy, M, N, MatrixUse::Accumulator, Scope>
linalg::Multiply(const Matrix<T, M, K, MatrixUse::A, Scope>,
                 const Matrix<T, K, N, MatrixUse::B, Scope>);

template <MatrixComponentType T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::Accumulator, Scope>
linalg::Multiply(const Matrix<T, M, K, MatrixUse::A, Scope>,
                 const Matrix<T, K, N, MatrixUse::B, Scope>);
```

The `linalg::Multiply` function has two overloads that take an MxK `Wave`-scope
`A` matrix, and a KxN `Wave`-scope `B` matrix and yields an MxN `Wave`-scope
`Accumulator` matrix initialized with the product of the two input matrices. One

of the overloads infers the type of the output accumulator to match the input
matrices, the other overload takes a template parameter for the output matrix
type and takes arguments with potentially mismatched element types.

Must be called from wave-uniform control flow.

#### linalg::Multiply(vector, Matrix)

``` c++
template <typename OutputElTy, typename InputElTy, uint M, uint K,
          MatrixComponentType MatrixDT, MatrixScope Scope>
vector<OutputElTy, K>
    linalg::Multiply(vector<InputElTy, M>,
                     Matrix<MatrixDT, M, K, MatrixUse::B, Scope>);
```

The `linalg::Multiply` function has an overload that takes an `M`-element vector
and an MxK `B` matrix of any scope. The function returns a `K`-element vector.

#### linalg::MultiplyAdd(vector, Matrix, vector)

``` c++
template <typename OutputElTy, typename InputElTy, typename BiasElTy, uint M,
          uint K, MatrixComponentType MatrixDT, MatrixScope Scope>
vector<OutputElTy, K>
    linalg::MultiplyAdd(vector<InputElTy, M>,
                        Matrix<MatrixDT, M, K, MatrixUse::B, Scope>,
                        vector<BiasElTy, K>);
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
  ThreadGroup = 2,
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
matrix component's type, a type conversion is applied following the rules
documented in the [Conversions](#conversions) section.

```llvm
declare void @dx.op.castMatrix(
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix destination
  %dx.types.MatrixRef *  ; matrix source
  )
```

Converts the element and use type of the source matrix to the destination
matrix. The source matrix remains valid and unmodified after this operation is
applied. Validation shall enforce that both matrices have the same scope.

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
  immarg i32,            ; binary operation (DXILMatrixElementwiseOperation)
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
between opaque matrices and groupshared memory are defined in the
[Conversions](#conversions) section below.

```llvm
declare void @dx.op.matrixLoadFromThreads.v[NUM][TY](
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix
  < NUM x [Ty]>,         ; Vector
  )
```

Populates a matrix from per-thread vectors. For an A matrix the NUM corresponds
to the M dimension while for a B matrix it corresponds to the N dimension. The
NUM must match the matrix corresponding dimension, unless the element is a
packed data type in which case it must be the number of 32-bit unsigned integers
used to store M elements. This operation may not be used on Accumulator
matrices.

For an A matrix the N dimension must be less than or equal to the WaveSize. For
a B matrix the M dimension must be less than or equal to the WaveSize. Values
from additional threads are discarded.

The result of this operation is undefined if called from non-uniform control
flow.

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
declare < NUM x [Ty]> @dx.op.matrixExtractToThreads.v[NUM][TY](
  immarg i32,            ; opcode
  %dx.types.MatrixRef *, ; matrix
  i32,                   ; Index
  )
```

Extracts per-thread vectors from a matrix. For an A matrix the NUM corresponds
to the M dimension while for a B matrix it corresponds to the N dimension. The
NUM must match the matrix corresponding dimension, unless the element is a
packed data type in which case it must be the number of 32-bit unsigned integers
used to store M elements. This operation may not be used on Accumulator
matrices.

The Index argument specifies the starting row or column as a multiple of the
wave size. The resulting vector corresponds to the row or column numbered
`(Index * WaveSize) + ThreadID`.

Must be called from wave-uniform control flow.

```llvm
declare i32 @dx.op.matrixQueryAccumulatorLayout.v[NUM][TY](
  immarg i32,            ; opcode
  )
```

This opcode must be evaluated at driver compile time and replaced with the
appropriate architecture specific value denoting the layout of accumulator
matrices. A return value of `0` will denote that accumulator matrices are `A`
layout while a return value of `1` will denote that accumulator matrices are `B`
layout.

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
* All three matrices have the same scope (Wave or ThreadGroup)
* Matrix A's dimensions shall be M x K
* Matrix B's dimensions shall be K x N
* Matrix C's dimensions shall be M x N
* The element types are compatible

Must be called from wave-uniform control flow.

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

### Conversions

## Appendix 1: Outstanding Questions

* What is the exhaustive list of data types we need to support?
* What data type conversions do we need to support?
* Support for other number formats that aren't natively supported by HLSL?
* Do we need to specify a source/destination format for the data in the load and
  store operations that operate on descriptors or should we assume
  DXILMatrixComponentType?

## Appendix 2: HLSL Header

[Compiler Explorer](https://godbolt.org/z/br58c473W)
> Note: this mostly works with Clang, but has some issues to work out still.

```cpp
namespace hlsl {

template <typename T> struct is_arithmetic {
  static const bool value = false;
};

#define __ARITHMETIC_TYPE(type)                                                \
  template <> struct is_arithmetic<type> {                                     \
    static const bool value = true;                                            \
  };

#if __HLSL_ENABLE_16_BIT
__ARITHMETIC_TYPE(uint16_t)
__ARITHMETIC_TYPE(int16_t)
#endif
__ARITHMETIC_TYPE(uint)
__ARITHMETIC_TYPE(int)
__ARITHMETIC_TYPE(uint64_t)
__ARITHMETIC_TYPE(int64_t)
__ARITHMETIC_TYPE(half)
__ARITHMETIC_TYPE(float)
__ARITHMETIC_TYPE(double)

template <bool B, typename T> struct enable_if {};

template <typename T> struct enable_if<true, T> {
  using type = T;
};

} // namespace hlsl

namespace dx {

namespace linalg {

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

namespace __detail {
template <MatrixComponentType T> struct ComponentTypeTraits {
  using Type = uint;
  static const bool IsNativeScalar = false;
};

#define __MATRIX_SCALAR_COMPONENT_MAPPING(enum_val, type)                      \
  template <> struct ComponentTypeTraits<enum_val> {                           \
    using Type = type;                                                         \
    static const bool IsNativeScalar = true;                                   \
  };

#if __HLSL_ENABLE_16_BIT
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::I16, int16_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::U16, uint16_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::F16, float16_t)
#endif

__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::I32, int32_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::U32, uint32_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::F32, float)
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::I64, int64_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::U64, uint64_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(MatrixComponentType::F64, double)

} // namespace __detail

enum class MatrixUse {
  A = 0,
  B = 1,
  Accumulator = 2,
};

enum class MatrixScope {
  Thread = 0,
  Wave = 1,
  ThreadGroup = 2,
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
  using ElementType = typename __detail::ComponentTypeTraits<ComponentTy>::Type;
  // If this isn't a native scalar, we have an 8-bit type, so we have 4 elements
  // packed in each scalar value.
  static const uint ElementsPerScalar =
      __detail::ComponentTypeTraits<ComponentTy>::IsNativeScalar ? 1 : 4;
  // Computes the number of scalars actually stored in the matrix M dimension
  // accounting for packing.
  static const uint MScalars =
      (M + (ElementsPerScalar - 1)) / ElementsPerScalar;
  // Computes the number of scalars actually stored in the matrix N dimension
  // accounting for packing.
  static const uint NScalars =
      (N + (ElementsPerScalar - 1)) / ElementsPerScalar;

  template <MatrixComponentType NewCompTy, MatrixUse NewUse = Use>
  Matrix<NewCompTy, M, N, NewUse, Scope> cast();

  // Element-wise operations
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator+=(T);
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator-=(T);
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator*=(T);
  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  operator/=(T);

  // Apply a unary operation to each element.
  template <UnaryOperation Op> Matrix ApplyUnaryOperation();

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Splat(T Val);
  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ElementType));
  static Matrix Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ElementType));

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Load(/*groupshared*/ T Arr[], uint StartIdx, uint Stride, bool ColMajor);

  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::A && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           Matrix>::type
      FromThreadVectors(vector<ElementType, MScalars>);

  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::B && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           Matrix>::type
      FromThreadVectors(vector<ElementType, NScalars>);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             bool ColMajor, uint Align = sizeof(ElementType));

  template <typename T>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, void>::type
  Store(/*groupshared*/ T Arr[], uint StartIdx, uint Stride, bool ColMajor);

  // Extract the thread-specific vector.
  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::A && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           vector<ElementType, MScalars>>::type
  GetThreadVector(uint Index = 0);

  template <MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::B && Scope != MatrixScope::Thread &&
                               UseLocal == Use,
                           vector<ElementType, NScalars>>::type
  GetThreadVector(uint Index = 0);

  template <MatrixComponentType LHSTy, MatrixComponentType RHSTy, uint K,
            MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                               Scope != MatrixScope::Thread && UseLocal == Use,
                           void>::type
  MultiplyAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                     const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);

  template <MatrixComponentType LHSTy, MatrixComponentType RHSTy, uint K,
            MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                               Scope != MatrixScope::Thread && UseLocal == Use,
                           void>::type
  SumAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);

  // Cooperative Vector outer product accumulate.
  template <typename T, MatrixUse UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  OuterProductAccumulate(const vector<T, M>, const vector<T, N>);
};

MatrixUse AccumulatorLayout();

template <MatrixComponentType OutTy, MatrixComponentType ATy,
          MatrixComponentType BTy, uint M, uint N, uint K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::Wave>);

template <MatrixComponentType T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::Wave>);

template <MatrixComponentType OutTy, MatrixComponentType ATy,
          MatrixComponentType BTy, uint M, uint N, uint K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

template <MatrixComponentType T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

// Cooperative Vector Replacement API
// Cooperative Vector operates on per-thread vectors multiplying against B
// matrices.

template <typename OutputElTy, typename InputElTy, uint M, uint K,
          MatrixComponentType MatrixDT, MatrixScope Scope>
vector<OutputElTy, K> Multiply(vector<InputElTy, M>,
                               Matrix<MatrixDT, M, K, MatrixUse::B, Scope>);

template <typename OutputElTy, typename InputElTy, typename BiasElTy, uint M,
          uint K, MatrixComponentType MatrixDT, MatrixScope Scope>
vector<OutputElTy, K> MultiplyAdd(vector<InputElTy, M>,
                                  Matrix<MatrixDT, M, K, MatrixUse::B, Scope>,
                                  vector<BiasElTy, K>);

} // namespace linalg
} // namespace dx

RWByteAddressBuffer B : register(u0);

void WaveMatrixExample() {
  using namespace dx::linalg;
  using MatrixATy =
      Matrix<MatrixComponentType::F16, 8, 32, MatrixUse::A, MatrixScope::Wave>;
  using MatrixBTy =
      Matrix<MatrixComponentType::F16, 32, 16, MatrixUse::B, MatrixScope::Wave>;
  using MatrixAccumTy = Matrix<MatrixComponentType::F16, 8, 16,
                               MatrixUse::Accumulator, MatrixScope::Wave>;
  using MatrixAccum32Ty = Matrix<MatrixComponentType::F32, 8, 16,
                                 MatrixUse::Accumulator, MatrixScope::Wave>;

  MatrixATy MatA = MatrixATy::Load(B, 0, 8 * 4, false);
  MatrixBTy MatB = MatrixBTy::Load(B, 0, 32 * 4, false);

  MatrixAccumTy Accum = Multiply(MatA, MatB);
  MatrixAccum32Ty Accum32 = Multiply<MatrixComponentType::F32>(MatA, MatB);
}

void CoopVec() {
  using namespace dx::linalg;
  using MatrixBTy =
      Matrix<MatrixComponentType::F16, 32, 16, MatrixUse::B, MatrixScope::Wave>;

  vector<float16_t, 32> Vec = (vector<float16_t, 32>)0;
  MatrixBTy MatB = MatrixBTy::Load(B, 0, 32 * 4, false);
  vector<float16_t, 16> Accum = Multiply<float16_t>(Vec, MatB);
}
```


