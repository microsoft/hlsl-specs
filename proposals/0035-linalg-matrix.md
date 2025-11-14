---
title: 0035 - Linear Algebra Matrix
params:
  authors:
  - llvm-beanz: Chris Bieneman
  - mapodaca-nv: Mike Apodaca
  status: Under Review
---

* Planned Version: SM 6.10

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

template <ComponentEnum ElementType, uint DimA> struct VectorRef {
  ByteAddressBuffer Buf;
  uint Offset;
};

template <typename T, int N, ComponentEnum DT> struct InterpretedVector {
  vector<T, N> Data;
  static const ComponentEnum Interpretation = DT;
  static const SIZE_TYPE Size =
      __detail::ComponentTypeTraits<DT>::ElementsPerScalar * N;
};

template <ComponentEnum DT, typename T, int N>
InterpretedVector<T, N, DT> MakeInterpretedVector(vector<T, N> Vec) {
  InterpretedVector<T, N, DT> IV = {Vec};
  return IV;
}

template <ComponentEnum ComponentTy, SIZE_TYPE M, SIZE_TYPE N,
          MatrixUseEnum Use, MatrixScopeEnum Scope>
class Matrix {
  using ElementType = typename __detail::ComponentTypeTraits<ComponentTy>::Type;
  // If this isn't a native scalar, we have an 8-bit type, so we have 4 elements
  // packed in each scalar value.
  static const uint ElementsPerScalar =
      __detail::ComponentTypeTraits<ComponentTy>::ElementsPerScalar;

  template <ComponentEnum NewCompTy, MatrixUseEnum NewUse = Use>
  Matrix<NewCompTy, M, N, NewUse, Scope> Cast();

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Splat(T Val);

  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  static Matrix Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                     MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Load(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
       MatrixLayoutEnum Layout);

  uint Length();

  uint2 GetCoordinate(uint);

  ElementType Get(uint);

  void Set(uint, ElementType);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  template <typename T, SIZE_TYPE Size>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value &&
                               (M * N / ElementsPerScalar >= Size),
                           void>::type
  Store(/*groupshared*/ T Arr[Size], uint StartIdx, uint Stride,
        MatrixLayoutEnum Layout);

  // Accumulate methods
  template <MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  Accumulate(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  template <typename T, MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value &&
                               Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  Accumulate(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
             MatrixLayoutEnum Layout);

  template <ComponentEnum LHSTy, ComponentEnum RHSTy, uint K,
            MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  MultiplyAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                     const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);

  template <ComponentEnum LHSTy, ComponentEnum RHSTy, uint K,
            MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  SumAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);
};

// Thread-scope Matrices are read-only. Using a template partial specialization
// for this simplifies the SFINAE-foo above.
template <ComponentEnum ComponentTy, SIZE_TYPE M, SIZE_TYPE N,
          MatrixUseEnum Use>
class Matrix<ComponentTy, M, N, Use, MatrixScope::Thread> {
  using ElementType = typename __detail::ComponentTypeTraits<ComponentTy>::Type;

  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  void Accumulate(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                  MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));
};

MatrixUseEnum AccumulatorLayout();

template <ComponentEnum OutTy, ComponentEnum ATy,
          ComponentEnum BTy, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::Wave>);

template <ComponentEnum T, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::Wave>);

template <ComponentEnum OutTy, ComponentEnum ATy,
          ComponentEnum BTy, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

template <ComponentEnum T, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

// Cooperative Vector Replacement API
// Cooperative Vector operates on per-thread vectors multiplying against B
// matrices with thread scope.

template <typename OutputElTy, typename InputElTy, SIZE_TYPE M, SIZE_TYPE K,
          ComponentEnum MatrixDT, MatrixScopeEnum Scope>
vector<OutputElTy, K> Multiply(vector<InputElTy, M>,
                               Matrix<MatrixDT, M, K, MatrixUse::B, Scope>);

template <typename OutputElTy, typename InputElTy, typename BiasElTy,
          SIZE_TYPE M, SIZE_TYPE K, ComponentEnum MatrixDT,
          MatrixScopeEnum Scope>
vector<OutputElTy, K> MultiplyAdd(vector<InputElTy, M>,
                                  Matrix<MatrixDT, M, K, MatrixUse::B, Scope>,
                                  vector<BiasElTy, K>);

template <typename OutputElTy, typename InputElTy,
          ComponentEnum InputInterp, typename BiasElTy, SIZE_TYPE M,
          SIZE_TYPE N, SIZE_TYPE K, ComponentEnum MatrixDT,
          MatrixScopeEnum Scope>
typename hlsl::enable_if<InterpretedVector<InputElTy, N, InputInterp>::Size ==
                             M,
                         vector<OutputElTy, K> >::type
    MultiplyAdd(InterpretedVector<InputElTy, N, InputInterp>,
                Matrix<MatrixDT, M, K, MatrixUse::B, Scope>,
                vector<BiasElTy, K>);

template <typename OutputElTy, typename InputElTy, ComponentEnum BiasElTy,
          SIZE_TYPE M, SIZE_TYPE K, ComponentEnum MatrixDT>
vector<OutputElTy, K>
    MultiplyAdd(vector<InputElTy, M>,
                Matrix<MatrixDT, M, K, MatrixUse::B, MatrixScope::Thread>,
                VectorRef<BiasElTy, K>);

template <typename OutputElTy, typename InputElTy,
          ComponentEnum InputInterp, ComponentEnum BiasElTy,
          SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K, ComponentEnum MatrixDT>
typename hlsl::enable_if<InterpretedVector<InputElTy, N, InputInterp>::Size ==
                             M,
                         vector<OutputElTy, K> >::type
    MultiplyAdd(InterpretedVector<InputElTy, N, InputInterp>,
                Matrix<MatrixDT, M, K, MatrixUse::B, MatrixScope::Thread>,
                VectorRef<BiasElTy, K>);

// Outer product functions
template <ComponentEnum OutTy, MatrixScopeEnum Scope, typename InputElTy,
          SIZE_TYPE M, SIZE_TYPE N>
Matrix<OutTy, M, N, MatrixUse::Accumulator, Scope>
    OuterProduct(vector<InputElTy, M>, vector<InputElTy, N>);

} // namespace linalg
} // namespace dx
```

### Example Usage: Wave Matrix

```c++
RWByteAddressBuffer B : register(u0);

void WaveMatrixExample() {
  using namespace dx::linalg;
  using MatrixATy =
      Matrix<ComponentType::F16, 8, 32, MatrixUse::A, MatrixScope::Wave>;
  using MatrixBTy =
      Matrix<ComponentType::F16, 32, 16, MatrixUse::B, MatrixScope::Wave>;
  using MatrixAccumTy = Matrix<ComponentType::F16, 8, 16,
                               MatrixUse::Accumulator, MatrixScope::Wave>;
  using MatrixAccum32Ty = Matrix<ComponentType::F32, 8, 16,
                                 MatrixUse::Accumulator, MatrixScope::Wave>;

  MatrixATy MatA = MatrixATy::Load(
      B, 0, /* Row stride = number of columns * element size */ 32 * 4,
      MatrixLayout::RowMajor);
  MatrixBTy MatB = MatrixBTy::Load(
      B, 0, /* Row stride = number of columns * element size */ 16 * 4,
      MatrixLayout::RowMajor);

  for (uint I = 0; I < MatB.Length(); ++I) {
    uint2 Pos = MatB.GetCoordinate(I);
    // Run `tanh` on all but the diagonal components for no reasonable reason.
    if (Pos.x != Pos.y) {
      float16_t Val = MatB.Get(I);
      MatB.Set(I, tanh(Val));
    }
  }

  MatrixAccumTy Accum = Multiply(MatA, MatB);
  MatrixAccum32Ty Accum32 = Multiply<ComponentType::F32>(MatA, MatB);
}
```

### Example Usage: Cooperative Vectors

```c++
ByteAddressBuffer B : register(t0);

void CoopVec() {
  using namespace dx::linalg;
  using MatrixBTy = Matrix<ComponentType::F16, 16, 16, MatrixUse::B,
                           MatrixScope::Thread>;

  vector<float16_t, 16> Vec = (vector<float16_t, 16>)0;
  MatrixBTy MatB = MatrixBTy::Load(
      MBuf, 0, /* Row stride = number of columns * element size */ 16 * 4,
      MatrixLayout::RowMajor);
  vector<float16_t, 16> Layer1 = Multiply<float16_t>(Vec, MatB);

  vector<float16_t, 16> NullBias = (vector<float16_t, 16>)0;
  vector<float16_t, 16> Layer2 = MultiplyAdd<float16_t>(Layer1, MatB, NullBias);

  VectorRef<ComponentType::F8_E4M3, 16> MemBias = {MBuf,
                                                         /*start offset*/ 4096};
  vector<float16_t, 16> Layer3 = MultiplyAdd<float16_t>(Layer2, MatB, MemBias);

  // Clang doesn't yet support packed types.
#ifdef __hlsl_dx_compiler
  vector<uint8_t4_packed, 4> SomeData = (vector<uint8_t4_packed, 4>)0;

  vector<float16_t, 16> Layer4 = MultiplyAdd<float16_t>(
      MakeInterpretedVector<ComponentType::F8_E4M3>(SomeData), MatB,
      MemBias);
  vector<float16_t, 16> Layer5 = MultiplyAdd<float16_t>(
      MakeInterpretedVector<ComponentType::F8_E4M3>(SomeData), MatB,
      NullBias);
#endif
}
```

### Example Usage: OuterProduct and Accumulate

```c++
RWByteAddressBuffer Buf : register(u1);

void OuterProdAccum() {
  using namespace dx::linalg;
  using MatrixAccumTy = Matrix<ComponentType::F16, 16, 8,
                               MatrixUse::Accumulator, MatrixScope::Thread>;

  vector<float16_t, 16> VecA = (vector<float16_t, 16>)0;
  vector<float16_t, 8> VecB = (vector<float16_t, 8>)0;
  MatrixAccumTy MatAcc =
      OuterProduct<ComponentType::F16, MatrixScope::Thread>(VecA, VecB);

  MatAcc.Accumulate(Buf, 0, 0, MatrixLayout::OuterProductOptimal);
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

The following table summarizes the operations supported for each matrix scope:

| Operation | Thread Scope | Wave Scope | ThreadGroup Scope |
|-----------|--------------|------------|-------------------|
| `Matrix::Cast()` | ✗ | ✓ | ✓ |
| `Matrix::Length()` | ✗ | ✓ | ✓ |
| `Matrix::GetCoordinate(uint)` | ✗ | ✓ | ✓ |
| `Matrix::Get(uint)` | ✗ | ✓ | ✓ |
| `Matrix::Set(uint, T)` | ✗ | ✓ | ✓ |
| `Matrix::Splat()` | ✗ | ✓ | ✓ |
| `Matrix::Load(ByteAddressBuffer)` | ✓ | ✓ | ✓ |
| `Matrix::Load(RWByteAddressBuffer)` | ✗ | ✓ | ✓ |
| `Matrix::Load(groupshared)` | ✗ | ✓ | ✓ |
| `Matrix::Store(RWByteAddressBuffer)` | ✗ | ✓ | ✓ |
| `Matrix::Store(groupshared)` | ✗ | ✓ | ✓ |
| `Matrix::Accumulate(RWByteAddressBuffer)` | ✓ | ✓ | ✓ |
| `Matrix::Accumulate(groupshared)` | ✗ | ✓ | ✓ |
| `Matrix::MultiplyAccumulate()` | ✗ | ✓ | ✓ |
| `Matrix::SumAccumulate()` | ✗ | ✓ | ✓ |
| `linalg::Multiply(Matrix, Matrix)` | ✗ | ✓ | ✓ |
| `linalg::Multiply(vector, Matrix)` | ✓ | ✗ | ✗ |
| `linalg::MultiplyAdd(vector, Matrix, vector)` | ✓ | ✗ | ✗ |
| `linalg::OuterProduct(vector, vector)` | ✓ | ✓ | ✓ |

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

#### Restrictions on Dimensions

The HLSL API will enforce restrictions on the `K` dimension as found in the
formula: `MxK * KxN = MxN`

This restriction impacts the number of rows in an A matrix, and columns in a B
matrix, but has no impact on an accumulator matrix.

The minimum and maximum `K` dimension for Wave and Thread scope matrices is tied
to the the minimum and maximum wave size, while the minimum and maximum `K`
dimension for ThreadGroup matrices is tied to the thread group size.


| Matrix Scope | Scalar element dimensions     |
| ------------ | ----------------------------- |
| Thread       | Powers of two between [4,128] |
| Wave         | Powers of two between [4,128] |
| ThreadGroup  | [1,1024]                      |

Sizes for matrices of packed data types are 4 times the valid size for a scalar
element.

Not all hardware is required to support all possible dimensions for thread and
wave scope matrices, or all possible element types. The shader compiler will
encode the dimensions and input and output data types used by each shader in the
[Pipeline State Validation metadata](#pipeline-state-validation-metadata).

### HLSL API Documentation

#### HLSL Enumerations
```c++
struct ComponentType {
  enum ComponentEnum {
    Invalid = 0,
    I1 = 1,
    I8 = 2,
    U8 = 3,
    I16 = 4,
    U16 = 5,
    I32 = 6,
    U32 = 7,
    I64 = 8,
    U64 = 9,
    F16 = 10,
    F32 = 11,
    F64 = 12,
    SNormF16 = 13,
    UNormF16 = 14,
    SNormF32 = 15,
    UNormF32 = 16,
    SNormF64 = 17,
    UNormF64 = 18,
    F8_E4M3 = 19,
    F8_E5M2 = 20,
  };
};
using ComponentEnum = ComponentType::ComponentEnum;

struct MatrixUse {
  enum MatrixUseEnum {
    A = 0,
    B = 1,
    Accumulator = 2,
  };
};
using MatrixUseEnum = MatrixUse::MatrixUseEnum;

struct MatrixScope {
  enum MatrixScopeEnum {
    Thread = 0,
    Wave = 1,
    ThreadGroup = 2,
  };
};
using MatrixScopeEnum = MatrixScope::MatrixScopeEnum;

struct MatrixLayout {
  enum MatrixLayoutEnum {
    RowMajor = 0,
    ColMajor = 1,
    MulOptimal = 2,
    OuterProductOptimal = 3,
  };
};
using MatrixLayoutEnum = MatrixLayout::MatrixLayoutEnum;
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
template <ComponentEnum T> struct ComponentTypeTraits {
  using Type = uint;
  static const bool IsNativeScalar = false;
  static const uint ElementsPerScalar = 4;
};

#define __MATRIX_SCALAR_COMPONENT_MAPPING(enum_val, type)                      \
  template <> struct ComponentTypeTraits<enum_val> {                           \
    using Type = type;                                                         \
    static const bool IsNativeScalar = true;                                   \
    static const uint ElementsPerScalar = 1;                                   \
  };

#if __HLSL_ENABLE_16_BIT
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::I16, int16_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::U16, uint16_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::F16, float16_t)
#endif

__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::I32, int32_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::U32, uint32_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::F32, float)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::I64, int64_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::U64, uint64_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::F64, double)

} // namespace __detail
```

The `linalg::__detail::ComponentTypeTraits` struct is provided as an
implementation detail to enable mapping `ComponentType` values to their
native HLSL element types and differentiating between types that have native
scalar support.

#### Matrix::Cast

```c++
template <ComponentType NewCompTy, MatrixUse NewUse = Use>
Matrix<NewCompTy, M, N, NewUse, Scope> Matrix::Cast();
```

Requires `Wave` or `ThreadGroup` scope input and output matrices.

The `Matrix::Cast()` function supports casting component types and matrix `Use`.
Must be called from uniform control flow on scope-uniform matrices.

#### Matrix::Splat(T)


```c++
template <typename T>
static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
Matrix::Splat(T Val);
```

Requires `Wave` or `ThreadGroup` scope matrix output.

Constructs a matrix filled with the provided value casted to the element type.
This operation shall behave equivalent to:

```c++
Matrix::Splat(WaveReadLaneFirst(Val));
```

#### Matrix::Load

```c++
static Matrix Matrix::Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                           MatrixLayoutEnum Layout,
                           uint Align = sizeof(ElementType));

// Not available on Thread scope matrices.
static Matrix Matrix::Load(RWByteAddressBuffer Res, uint StartOffset,
                           uint Stride, MatrixLayoutEnum Layout,
                           uint Align = sizeof(ElementType));

// Not available on Thread scope matrices.
template <typename T>
static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
Matrix::Load(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
             MatrixLayoutEnum Layout);
```

The following table specifies the valid values for the `Layout` parameter
given the `Load` method type and matrix scope.  All other combinations are
unsupported:

| Operation                         | Matrix Scope          | Matrix Layout          |
|-----------------------------------|-----------------------|------------------------|
| `Matrix::Load(ByteAddressBuffer)` | `Thread`              | any                    |
| `Matrix::Load(*)`                 | `Wave`, `ThreadGroup` | `RowMajor`, `ColMajor` |

The matrix `Load` methods create a new matrix of the specified dimensions and
fill the matrix by reading data from the supplied source. Thread scope matrices
can only be read from `ByteAddressBuffer` objects. Wave scope matrices can be
read from `[RW]ByteAddressBuffer` objects or `groupshared` arrays. When read
from `[RW]ByteAddressBuffer` objects the data is assumed to already be in the
expected target data format. When read from `groupshared` memory, the data may
be in any arithmetic or packed data type. If the type mismatches the target data
type of the matrix a data conversion is applied on load.

This operation may be called in divergent control flow when loading a thread
scope matrix, and must be called in uniform control flow when loading a wave
scope matrix.

#### Matrix::Length

```c++
uint Matrix::Length();
```

Requires `Wave` or `ThreadGroup` scope matrix.

Returns the number of matrix components accessible to the current thread. If the
matrix's elements are stored in a packed type `Length` will return the number of
packed elements (e.g. if a thread has 8 accessible elements of `int8` type which
are packed into 2 `int8_t4_packed`, `Length` will return 2). The mapping and
distribution of threads to matrix elements is opaque and
implementation-specific. The value returned by `Length` may be different for
each thread. The sum of the values returned by `Length` across all threads must
be greater than or equal to the total number of matrix elements. Some
implementations may map multiple threads to the same matrix element. Therefore,
developers should take this into consideration when programming side-effects,
such as atomic operations and/or UAV writes, within user-defined matrix
operations.

May be called from non-uniform control flow. However, given the above rules,
calling `Length` from divergent threads may result in unpredictable behavior.
For example, the number of matrix elements accessible to each thread will be
inconsistent across different implementations.

#### Matrix::GetCoordinate

```c++
uint2 Matrix::GetCoordinate(uint);
```

Requires `Wave` or `ThreadGroup` scope matrix.

Converts a specified index into row and column coordinates. The valid range of
`Index` is `[0, Length()-1]`. If the value of `Index` is out of
range, then the result value is `UINT32_MAX.xx`. The mapping of indices to
matrix coordinates is implementation-specific.

#### Matrix::Get

```c++
ElementType Matrix::Get(uint);
```

Requires `Wave` or `ThreadGroup` scope matrix.

Retrieves the value of a matrix component at the specified index.  The valid
range of `Index` is `[0, Length()-1]`. If the value of `Index` is out of range,
then the result value zero casted to the `ElementType`.

#### Matrix::Set

```c++
void Matrix::Set(uint, ElementType);
```

Requires `Wave` or `ThreadGroup` scope matrix.

Sets the value of a matrix component at the specified index.  The valid
range of `Index` is `[0, Length()-1]`.  If the value of `Index` is out of range,
then the operation is a no-op.

#### Matrix::Store

```c++
void Matrix::Store(
    RWByteAddressBuffer Res, uint StartOffset, uint Stride, MatrixLayout Layout,
    uint Align = sizeof(__detail::ComponentTypeTraits<ComponentTy>::Type));

template <typename T, SIZE_TYPE Size>
typename hlsl::enable_if<hlsl::is_arithmetic<T>::value &&
                             (M * N / ElementsPerScalar >= Size),
                         void>::type
Matrix::Store(/*groupshared*/ T Arr[Size], uint StartIdx, uint Stride,
              MatrixLayout Layout);
```

The following table specifies the valid values for the `Layout` parameter
given the `Store` method type and matrix scope.  All other combinations are
unsupported:

| Operation          | Matrix Scope          | Matrix Layout          |
|--------------------|-----------------------|------------------------|
| `Matrix::Store(*)` | `Wave`, `ThreadGroup` | `RowMajor`, `ColMajor` |

The matrix `Store` methods store the matrix data to a target
`RWByteAddressBuffer` or `groupshared` array. When storing to
`RWByteAddressBuffer` objects the data is stored in the component type of the
matrix object. When storing to `groupshared` memory, the matrix component data
is converted to the target arithmetic or packed data type if the data types do
not match.

#### Matrix::Accumulate

```c++
template <MatrixScope ScopeLocal = Scope>
typename hlsl::enable_if<Use == MatrixUse::Accumulator && ScopeLocal == Scope,
                         void>::type
Matrix::Accumulate(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                   MatrixLayout Layout, uint Align = sizeof(ElementType));

template <typename T, MatrixUse UseLocal = Use>
typename hlsl::enable_if<hlsl::is_arithmetic<T>::value &&
                             Use == MatrixUse::Accumulator &&
                             Scope != MatrixScope::Thread && UseLocal == Use,
                         void>::type
Matrix::Accumulate(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
                   MatrixLayout Layout);
```

The following table specifies the valid values for the `Layout` parameter
given the `Accumulate` method type and matrix scope.  All other combinations
are unsupported:

| Operation                                 | Matrix Scope          | Matrix Layout          |
|-------------------------------------------|-----------------------|------------------------|
| `Matrix::Accumulate(RWByteAddressBuffer)` | `Thread`              | `OuterProductOptimal`  |
| `Matrix::Accumulate(*)`                   | `Wave`, `ThreadGroup` | `RowMajor`, `ColMajor` |

When used with `Wave` and `ThreadGroup` matrices this must be called from
uniform control flow on uniform matrices.

The matrix `Accumulate` methods add the matrix data to a target
`RWByteAddressBuffer` or `groupshared` array. These methods are only available
for matrices with `MatrixUse::Accumulator`. The `RWByteAddressBuffer` overload
works with all matrix scopes, while the `groupshared` overload only works with
`Wave` scope matrices. When accumulating to `RWByteAddressBuffer` objects the
data is added in the component type of the matrix object. When accumulating to
`groupshared` memory, the matrix component data is converted to the target
arithmetic or packed data type if the data types do not match.

#### Matrix::MultiplyAccumulate(Matrix, Matrix)

```c++
template <ComponentType LHSTy, ComponentType RHSTy, uint K,
          MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                             Scope != MatrixScope::Thread && UseLocal == Use,
                         void>::type
Matrix::MultiplyAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                           const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);
```

Requires `Wave` or `ThreadGroup` scope matrix, and must be called from uniform
control flow on uniform matrices.

An accumulator matrix with wave or thread group scope has a method `MultiplyAccumulate` which
takes as parameters an M x K A matrix with the same scope and a K x N B matrix with
the same scope. The matrix arguments are multiplied against each other and added
back into the implicit object accumulator matrix.

#### Matrix::SumAccumulate(Matrix, Matrix)

```c++
template <ComponentType LHSTy, ComponentType RHSTy, uint K,
          MatrixUse UseLocal = Use>
typename hlsl::enable_if<Use == MatrixUse::Accumulator &&
                             Scope != MatrixScope::Thread && UseLocal == Use,
                         void>::type
Matrix::SumAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                      const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);
```

Requires `Wave` or `ThreadGroup` scope matrix, and must be called from uniform
control flow on uniform matrices.

An accumulator matrix with wave or thread group scope has a method `SumAccumulate` which takes
as parameters an M x K A matrix with the same scope and a K x N B matrix with the same
scope. The matrix arguments are added together then added back into the implicit
object accumulator matrix.

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
template <ComponentType OutTy, ComponentType ATy,
          ComponentType BTy, uint M, uint N, uint K, MatrixScope Scope>
Matrix<OutTy, M, N, MatrixUse::Accumulator, Scope>
linalg::Multiply(const Matrix<T, M, K, MatrixUse::A, Scope>,
                 const Matrix<T, K, N, MatrixUse::B, Scope>);

template <ComponentType T, uint M, uint N, uint K>
Matrix<T, M, N, MatrixUse::Accumulator, Scope>
linalg::Multiply(const Matrix<T, M, K, MatrixUse::A, Scope>,
                 const Matrix<T, K, N, MatrixUse::B, Scope>);
```

Requires `Wave` or `ThreadGroup` scope matrix inputs and output, and must be
called from uniform control flow on uniform matrices.

The `linalg::Multiply` function has two overloads that take an MxK `Wave`-scope
`A` matrix, and a KxN `Wave`-scope `B` matrix and yields an MxN `Wave`-scope
`Accumulator` matrix initialized with the product of the two input matrices. One

of the overloads infers the type of the output accumulator to match the input
matrices, the other overload takes a template parameter for the output matrix
type and takes arguments with potentially mismatched element types.

#### linalg::Multiply(vector, Matrix)

``` c++
template <typename OutputElTy, typename InputElTy, uint M, uint K,
          ComponentType MatrixDT>
vector<OutputElTy, K>
    linalg::Multiply(vector<InputElTy, M>,
                     Matrix<MatrixDT, M, K, MatrixUse::B, MatrixScope::Thread>);
```

Requires `Thread` scope matrix input, may be called from divergent control flow.

The `linalg::Multiply` function has an overload that takes an `M`-element vector
and an MxK `B` matrix with `Thread` scope. The function returns a `K`-element
vector.

#### linalg::OuterProduct(vector, vector)

```c++
template <ComponentType OutTy, MatrixScope Scope, typename InputElTy,
          uint M, uint N>
Matrix<OutTy, M, N, MatrixUse::Accumulator, Scope>
    linalg::OuterProduct(vector<InputElTy, M>, vector<InputElTy, N>);
```

The `linalg::OuterProduct` function has two overloads that take an M-element vector
and an N-element vector and yield an MxN `Accumulator` matrix with the specified
scope initialized with the outer product of the two input vectors. One overload
infers the type of the output accumulator to match the input vector element type,
the other overload takes a template parameter for the output matrix element type.
All matrix scopes are allowed for the output matrix.

#### linalg::MultiplyAdd(vector, Matrix, vector)

``` c++
template <typename OutputElTy, typename InputElTy, typename BiasElTy, uint M,
          uint K, ComponentType MatrixDT>
vector<OutputElTy, K>
    linalg::MultiplyAdd(vector<InputElTy, M>,
                        Matrix<MatrixDT, M, K, MatrixUse::B, MatrixScope::Thread>,
                        vector<BiasElTy, K>);
```

Requires `Thread` scope matrix input, may be called from divergent control flow.

The `linalg::MultiplyAdd` function has an overload that takes an `M`-element, an
MxK `B` matrix with `Thread` scope, and a `K`-element vector. The operation
multiplies the `M`-element vector by the matrix then adds the `K`-element vector
producing a result `K`-element vector.

### DXIL Types

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

enum class DXILComponentType {
  Invalid = 0,
  I1 = 1,
  I8 = 2,
  U8 = 3,
  I16 = 4,
  U16 = 5,
  I32 = 6,
  U32 = 7,
  I64 = 8,
  U64 = 9,
  F16 = 10,
  F32 = 11,
  F64 = 12,
  SNormF16 = 13,
  UNormF16 = 14,
  SNormF32 = 15,
  UNormF32 = 16,
  SNormF64 = 17,
  UNormF64 = 18,
  F8_E4M3 = 19,
  F8_E5M2 = 20,
}
```

This feature also adds a matrix ref that serves as an opaque type handle to the
implementation's representation of the matrix and a properties struct that
represents other attributes of the created matrix.


```llvm
  %dx.types.MatrixRef     = type { i8 * }

  %dx.types.MatrixProperties = type {
  i8,  ; DXILComponentType
  i32, ; M Dimension
  i32, ; N Dimension
  i8,  ; DXILMatrixUse
  i8,  ; DXILMatrixScope
  }

```

### DXIL Operations

```llvm
declare %dx.types.MatrixRef @dx.op.createMatrix(
  immarg i32  ; opcode
  )
```

Creates a new uninitialized matrix handle.

```llvm
declare %dx.types.MatrixRef @dx.op.annotateMatrix(
  immarg i32,                ; opcode
  %dx.types.MatrixRef,       ; Matrix being annotated
  %dx.types.MatrixProperties ; Struct containing annotation info
  )
```

Defines a matrix as having the specified component type, dimensions, use, and
scope.

```llvm
declare @dx.op.fillMatrix.[TY](
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  [Ty]                   ; fill value
  )
```

Fills a matrix with a scalar value. The scalar's type does not need to match the
matrix component's type, a type conversion is applied following the rules
documented in the [Conversions](#conversions) section.

```llvm
declare void @dx.op.castMatrix(
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix destination
  %dx.types.MatrixRef    ; matrix source
  )
```

Converts the element and use type of the source matrix to the destination
matrix. The source matrix remains valid and unmodified after this operation is
applied. Validation shall enforce that both matrices have the same scope.

```llvm
declare void @dx.op.matrixLoadFromDescriptor(
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  %dx.types.Handle,      ; ByteAddressBuffer
  i32,                   ; Offset
  i32,                   ; Stride
  i32,                   ; matrix layout
  )
```

Populates a matrix with data from a [RW]ByteAddressBuffer. This operation must
observe [bounds checking behavior](#bounds-checking-behavior) described below.

> Question: Do we need to specify a source format for the data or should we
> assume DXILComponentType?

Validation rules will enforce that:
* `Layout` is `RowMajor` or `ColMajor` for matrix with `MatrixScope` of `Wave`
  or `ThreadGroup`
* `Stride` is `0` if the `Layout` is not `RowMajor` or `ColMajor`

```llvm
declare void @dx.op.matrixLoadFromMemory.p[Ty](
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  [Ty] * addrspace(4),   ; groupshared T[M * N]
  i32,                   ; Offset
  i32,                   ; Stride
  i32,                   ; matrix layout
  )
```

Populates a matrix with data from a `groupshared` array. Data conversions
between opaque matrices and groupshared memory are defined in the
[Conversions](#conversions) section below.

```llvm
declare i32 @dx.op.matrixLength(
  immarg i32,           ; opcode
  %dx.types.MatrixRef   ; matrix
  )
```

Returns the number of elements stored in thread-local storage on the active
thread for the provided matrix.

```llvm
declare <2 x i32> @dx.op.matrixGetCoordinate(
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  i32                    ; thread-local index
  )
```

Returns a two element vector containing the column and row of the matrix that
the thread-local index corresponds to.

```llvm
declare [Ty] @dx.op.matrixGetElement.[Ty](
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  i32                    ; thread-local index
  )
```

Gets the element of the matrix corresponding to the thread local index provided.
If the index is out of range for the values stored in this thread the result is
0.

```llvm
declare void @dx.op.matrixSetElement.[Ty](
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  i32,                   ; thread-local index
  [Ty]                   ; value
  )
```

Sets the element of the matrix corresponding to the thread local index provided
to the value provided. If the index is out of range for the values stored in
this thread the result is a no-op.

```llvm
declare void @dx.op.matrixStoreToDescriptor(
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  %dx.types.Handle,      ; ByteAddressBuffer
  i32,                   ; Offset
  i32,                   ; Stride
  i32,                   ; matrix layout
  )
```

Store a matrix to a RWByteAddressBuffer at a specified offset. This operation
must observe [bounds checking behavior](#bounds-checking-behavior) described
below.

Validation rules will enforce that:
* `Layout` is `RowMajor` or `ColMajor`

```llvm
declare void @dx.op.matrixStoreToMemory.p[Ty](
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  [Ty] *,                ; groupshared T[M * N]
  i32,                   ; Offset
  i32,                   ; Stride
  i32,                   ; matrix layout
  )
```

Store a matrix to groupshared memory. Data conversions between opaque matrices
and groupshared memory are defined in the [Conversions](#conversions) section
below.

The validator will ensure that the group shared target memory is large enough
for the write.

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
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix A
  %dx.types.MatrixRef,   ; matrix B
  %dx.types.MatrixRef    ; matrix C
  )
```

Three opcodes are available for this operation class:
* Matrix Matrix Multiply: `C = A * B`
* Matrix Matrix Multiply with Accumulation: `C += A * B`
* Matrix Matrix Addition with Accumulation: `C += A + B`

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
  immarg i32,           ; opcode
  <[NUMi] x [TYi]>,     ; input vector
  immarg i32,           ; input interpretation type (DXILComponentType)
  %dx.types.MatrixRef   ; matrix A
)
```

This operation implements a row-vector multiplication against a `B` matrix of
`Thread` scope.

Validation will enforce that:
* The input vector length matches the `M` matrix dimension
* The matrix A is a `B` matrix of `Thread` scope

``` llvm
declare <[NUMo] x [TYo]> @dx.op.matvecmuladd.v[NUMo][TYo].v[NUMi][TYi].v[NUMo][TYb](
  immarg i32,            ; opcode
  <[NUMi] x [TYi]>,      ; input vector
  immarg i32,            ; input interpretation type (DXILComponentType)
  %dx.types.MatrixRef,   ; matrix A
  <[NUMo] x [TYb]>,      ; bias vector
  immarg i32             ; bias interpretation type (DXILComponentType)
)
```

This operation implements a row-vector multiplication against a `B` matrix of
`Thread` scope with a bias vector added to the result.

Validation will enforce that:
* The input vector length matches the `M` matrix dimension
* The bias vector length matches the `N` matrix dimension
* The matrix A is a `B` matrix of `Thread` scope

```llvm
declare void @dx.op.matrixAccumulateToDescriptor(
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  %dx.types.Handle,      ; RWByteAddressBuffer
  i32,                   ; Offset
  i32,                   ; Stride
  i32                    ; matrix layout
  )
```

Accumulates a matrix to a RWByteAddressBuffer at a specified offset. This
operation is only available for matrices with `MatrixUse::Accumulator`. The
matrix data is added to the existing data in the buffer. The matrix component
data is converted to the target arithmetic or packed data type if the data types
do not match, then added to the existing data in memory. This operation must
observe [bounds checking behavior](#bounds-checking-behavior) described below.

Validation rules will enforce that:
* `Layout` is `OuterProductOptimal` for matrix with `MatrixScope` of `Thread`
* `Layout` is `RowMajor` or `ColMajor` for matrix with `MatrixScope` of `Wave`
  or `ThreadGroup`
* `Stride` is `0` if the `Layout` is not `RowMajor` or `ColMajor`

```llvm
declare void @dx.op.matrixAccumulateToMemory.p[Ty](
  immarg i32,            ; opcode
  %dx.types.MatrixRef,   ; matrix
  [Ty] *,                ; groupshared T[M * N]
  i32,                   ; Offset
  i32,                   ; Stride
  i32                    ; matrix layout
  )
```

Accumulates a matrix to groupshared memory. This operation is only available for
matrices with `MatrixUse::Accumulator` and `Wave` or `ThreadGroup` scope. Data
conversions between opaque matrices and groupshared memory are defined in the
[Conversions](#conversions) section below.

The validator will ensure that the group shared target memory is large enough
for the write.

```llvm
declare %dx.types.MatrixRef @dx.op.matrixOuterProduct.v[M][TY].v[N][TY](
  immarg i32,            ; opcode
  immarg i32,            ; component type (DXILComponentType)
  immarg i32,            ; M dimension
  immarg i32,            ; N dimension
  immarg i32,            ; matrix Scope (DXILMatrixScope)
  <[M] x [Ty]>,          ; vector A
  <[N] x [Ty]>           ; vector B
  )
```

Creates a new MxN accumulator matrix initialized with the outer product of the
two input vectors. The matrix scope can be `Thread`, `Wave`, or `ThreadGroup`.
The element type of the output matrix matches the element type of the input
vectors.

#### Bounds Checking Behavior

The `@dx.op.matrixLoadFromDescriptor` operation loads data from a descriptor.
For load operations a default element value of zero casted to the element type
is substituted for out of bounds reads. An implementation may either perform
bounds checking on the full bounds of the load initializing the full matrix to
the default element value if any element is out of bounds, or it may perform
per-element bounds checking initializing only the out of bounds elements to the
default value.

The `@dx.op.matrixStoreToDescriptor` and `@dx.op.matrixAccumulateToDescriptor`
operations write data to a descriptor. Writes to out of bounds memory are a
no-op. An implementation may either perform bounds checking on the full bounds
of the store converting the whole store to a no-op if any elelemt is out of
bounds, or it may perform per-element bounds checking only converting the out of
bounds stores to no-ops.

> Note: bounds checking is not required for reads and writes to root descriptors
> as D3D does not attach dimensions to root descriptors.

#### Pipeline State Validation Metadata

Shader Model 6.10 will introduce a version 4 of the Pipeline
State Validation RuntimeInfo structure. A new 32-bit unsigned integer
`LinalgMatrixUses` will count the number of `MatrixUse` objects appended after
the signature output vectors (presently the last data at the end of `PSV0` for
version 3).

The `MatrixUse` object is defined:

```c
struct MatrixUse {
  uint32_t Dimensions[3]; // M, N, K
  uint8_t Scope;
  uint8_t OperandType;
  uint8_t ResultType;
  uint8_t RESERVED; // unused but reserved for padding/alignment.
  uint32_t Flags; // do we need this?
};
```

This object will encode each matrix shape and element type as used by the DXIL
operations in the `matrixOp` and `matvecmuladd` opcode classes.

The Scope field will encode one of the values defined in the [`DXILMatrixScope`
enumeration](#dxil-enumerations).

The `OperandType` and `ResultType` fields will encode one of the values defined
in the [`DXILComponentType` enumeration](#dxil-enumerations).

> Open questions:
> 1) Do we need the M and N dimensions or just the K dimension?
> 2) Do we need both operand types, or should we expect the operands to be the
>    same type?
> 3) What flags do we need?

### Conversions

## Appendix 1: Outstanding Questions

* What is the exhaustive list of data types we need to support?
* What data type conversions do we need to support?
* Support for other number formats that aren't natively supported by HLSL?
* Do we need to specify a source/destination format for the data in the load and
  store operations that operate on descriptors or should we assume
  DXILComponentType?


## Appendix 2: HLSL Header

[Compiler Explorer](https://godbolt.org/z/W5a7zbPr3)
> Note: this mostly works with Clang, but has some issues to work out still.

```cpp
namespace hlsl {

#ifdef __hlsl_dx_compiler
#define SIZE_TYPE int
#else
#define SIZE_TYPE uint
#endif

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

struct ComponentType {
  enum ComponentEnum {
    Invalid = 0,
    I1 = 1,
    I8 = 2,
    U8 = 3,
    I16 = 4,
    U16 = 5,
    I32 = 6,
    U32 = 7,
    I64 = 8,
    U64 = 9,
    F16 = 10,
    F32 = 11,
    F64 = 12,
    SNormF16 = 13,
    UNormF16 = 14,
    SNormF32 = 15,
    UNormF32 = 16,
    SNormF64 = 17,
    UNormF64 = 18,
    F8_E4M3 = 19,
    F8_E5M2 = 20,
  };
};
using ComponentEnum = ComponentType::ComponentEnum;

struct MatrixUse {
  enum MatrixUseEnum {
    A = 0,
    B = 1,
    Accumulator = 2,
  };
};
using MatrixUseEnum = MatrixUse::MatrixUseEnum;

struct MatrixScope {
  enum MatrixScopeEnum {
    Thread = 0,
    Wave = 1,
    ThreadGroup = 2,
  };
};
using MatrixScopeEnum = MatrixScope::MatrixScopeEnum;

struct MatrixLayout {
  enum MatrixLayoutEnum {
    RowMajor = 0,
    ColMajor = 1,
    MulOptimal = 2,
    OuterProductOptimal = 3,
  };
};
using MatrixLayoutEnum = MatrixLayout::MatrixLayoutEnum;

namespace __detail {
template <ComponentEnum T> struct ComponentTypeTraits {
  using Type = uint;
  static const bool IsNativeScalar = false;
  static const uint ElementsPerScalar = 4;
};

#define __MATRIX_SCALAR_COMPONENT_MAPPING(enum_val, type)                      \
  template <> struct ComponentTypeTraits<enum_val> {                           \
    using Type = type;                                                         \
    static const bool IsNativeScalar = true;                                   \
    static const uint ElementsPerScalar = 1;                                   \
  };

#if __HLSL_ENABLE_16_BIT
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::I16, int16_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::U16, uint16_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::F16, float16_t)
#endif

__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::I32, int32_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::U32, uint32_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::F32, float)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::I64, int64_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::U64, uint64_t)
__MATRIX_SCALAR_COMPONENT_MAPPING(ComponentType::F64, double)

} // namespace __detail

template <ComponentEnum ElementType, uint DimA> struct VectorRef {
  ByteAddressBuffer Buf;
  uint Offset;
};

template <typename T, int N, ComponentEnum DT> struct InterpretedVector {
  vector<T, N> Data;
  static const ComponentEnum Interpretation = DT;
  static const SIZE_TYPE Size =
      __detail::ComponentTypeTraits<DT>::ElementsPerScalar * N;
};

template <ComponentEnum DT, typename T, int N>
InterpretedVector<T, N, DT> MakeInterpretedVector(vector<T, N> Vec) {
  InterpretedVector<T, N, DT> IV = {Vec};
  return IV;
}

template <ComponentEnum ComponentTy, SIZE_TYPE M, SIZE_TYPE N,
          MatrixUseEnum Use, MatrixScopeEnum Scope>
class Matrix {
  using ElementType = typename __detail::ComponentTypeTraits<ComponentTy>::Type;
  // If this isn't a native scalar, we have an 8-bit type, so we have 4 elements
  // packed in each scalar value.
  static const uint ElementsPerScalar =
      __detail::ComponentTypeTraits<ComponentTy>::ElementsPerScalar;

  template <ComponentEnum NewCompTy, MatrixUseEnum NewUse = Use>
  Matrix<NewCompTy, M, N, NewUse, Scope> Cast();

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Splat(T Val);

  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  static Matrix Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                     MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  template <typename T>
  static typename hlsl::enable_if<hlsl::is_arithmetic<T>::value, Matrix>::type
  Load(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
       MatrixLayoutEnum Layout);

  uint Length();

  uint2 GetCoordinate(uint);

  ElementType Get(uint);

  void Set(uint, ElementType);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  template <typename T, SIZE_TYPE Size>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value &&
                               (M * N / ElementsPerScalar >= Size),
                           void>::type
  Store(/*groupshared*/ T Arr[Size], uint StartIdx, uint Stride,
        MatrixLayoutEnum Layout);

  // Accumulate methods
  template <MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  Accumulate(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  template <typename T, MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<hlsl::is_arithmetic<T>::value &&
                               Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  Accumulate(/*groupshared*/ T Arr[], uint StartIdx, uint Stride,
             MatrixLayoutEnum Layout);

  template <ComponentEnum LHSTy, ComponentEnum RHSTy, uint K,
            MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  MultiplyAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                     const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);

  template <ComponentEnum LHSTy, ComponentEnum RHSTy, uint K,
            MatrixUseEnum UseLocal = Use>
  typename hlsl::enable_if<Use == MatrixUse::Accumulator && UseLocal == Use,
                           void>::type
  SumAccumulate(const Matrix<LHSTy, M, K, MatrixUse::A, Scope>,
                const Matrix<RHSTy, K, N, MatrixUse::B, Scope>);
};

// Thread-scope Matrices are read-only. Using a template partial specialization
// for this simplifies the SFINAE-foo above.
template <ComponentEnum ComponentTy, SIZE_TYPE M, SIZE_TYPE N,
          MatrixUseEnum Use>
class Matrix<ComponentTy, M, N, Use, MatrixScope::Thread> {
  using ElementType = typename __detail::ComponentTypeTraits<ComponentTy>::Type;

  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));

  void Accumulate(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                  MatrixLayoutEnum Layout, uint Align = sizeof(ElementType));
};

MatrixUseEnum AccumulatorLayout();

template <ComponentEnum OutTy, ComponentEnum ATy, ComponentEnum BTy,
          SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::Wave>);

template <ComponentEnum T, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::Wave>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::Wave>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::Wave>);

template <ComponentEnum OutTy, ComponentEnum ATy, ComponentEnum BTy,
          SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<OutTy, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<ATy, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<BTy, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

template <ComponentEnum T, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K>
Matrix<T, M, N, MatrixUse::Accumulator, MatrixScope::ThreadGroup>
Multiply(const Matrix<T, M, K, MatrixUse::A, MatrixScope::ThreadGroup>,
         const Matrix<T, K, N, MatrixUse::B, MatrixScope::ThreadGroup>);

// Cooperative Vector Replacement API
// Cooperative Vector operates on per-thread vectors multiplying against B
// matrices with thread scope.

template <typename OutputElTy, typename InputElTy, SIZE_TYPE M, SIZE_TYPE K,
          ComponentEnum MatrixDT, MatrixScopeEnum Scope>
vector<OutputElTy, K> Multiply(vector<InputElTy, M>,
                               Matrix<MatrixDT, M, K, MatrixUse::B, Scope>);

template <typename OutputElTy, typename InputElTy, typename BiasElTy,
          SIZE_TYPE M, SIZE_TYPE K, ComponentEnum MatrixDT,
          MatrixScopeEnum Scope>
vector<OutputElTy, K> MultiplyAdd(vector<InputElTy, M>,
                                  Matrix<MatrixDT, M, K, MatrixUse::B, Scope>,
                                  vector<BiasElTy, K>);

template <typename OutputElTy, typename InputElTy, ComponentEnum InputInterp,
          typename BiasElTy, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K,
          ComponentEnum MatrixDT, MatrixScopeEnum Scope>
typename hlsl::enable_if<InterpretedVector<InputElTy, N, InputInterp>::Size ==
                             M,
                         vector<OutputElTy, K> >::type
    MultiplyAdd(InterpretedVector<InputElTy, N, InputInterp>,
                Matrix<MatrixDT, M, K, MatrixUse::B, Scope>,
                vector<BiasElTy, K>);

template <typename OutputElTy, typename InputElTy, ComponentEnum BiasElTy,
          SIZE_TYPE M, SIZE_TYPE K, ComponentEnum MatrixDT>
vector<OutputElTy, K>
    MultiplyAdd(vector<InputElTy, M>,
                Matrix<MatrixDT, M, K, MatrixUse::B, MatrixScope::Thread>,
                VectorRef<BiasElTy, K>);

template <typename OutputElTy, typename InputElTy, ComponentEnum InputInterp,
          ComponentEnum BiasElTy, SIZE_TYPE M, SIZE_TYPE N, SIZE_TYPE K,
          ComponentEnum MatrixDT>
typename hlsl::enable_if<InterpretedVector<InputElTy, N, InputInterp>::Size ==
                             M,
                         vector<OutputElTy, K> >::type
    MultiplyAdd(InterpretedVector<InputElTy, N, InputInterp>,
                Matrix<MatrixDT, M, K, MatrixUse::B, MatrixScope::Thread>,
                VectorRef<BiasElTy, K>);

// Outer product functions
template <ComponentEnum OutTy, MatrixScopeEnum Scope, typename InputElTy,
          SIZE_TYPE M, SIZE_TYPE N>
Matrix<OutTy, M, N, MatrixUse::Accumulator, Scope>
    OuterProduct(vector<InputElTy, M>, vector<InputElTy, N>);

} // namespace linalg
} // namespace dx

RWByteAddressBuffer B : register(u0);

void WaveMatrixExample() {
  using namespace dx::linalg;
  using MatrixATy =
      Matrix<ComponentType::F16, 8, 32, MatrixUse::A, MatrixScope::Wave>;
  using MatrixBTy =
      Matrix<ComponentType::F16, 32, 16, MatrixUse::B, MatrixScope::Wave>;
  using MatrixAccumTy = Matrix<ComponentType::F16, 8, 16,
                               MatrixUse::Accumulator, MatrixScope::Wave>;
  using MatrixAccum32Ty = Matrix<ComponentType::F32, 8, 16,
                                 MatrixUse::Accumulator, MatrixScope::Wave>;

  MatrixATy MatA = MatrixATy::Load(
      B, 0, /* Row stride = number of columns * element size */ 32 * 4,
      MatrixLayout::RowMajor);
  MatrixBTy MatB = MatrixBTy::Load(
      B, 0, /* Row stride = number of columns * element size */ 16 * 4,
      MatrixLayout::RowMajor);

  for (uint I = 0; I < MatB.Length(); ++I) {
    uint2 Pos = MatB.GetCoordinate(I);
    // Run `tanh` on all but the diagonal components for no reasonable reason.
    if (Pos.x != Pos.y) {
      float16_t Val = MatB.Get(I);
      MatB.Set(I, tanh(Val));
    }
  }

  MatrixAccumTy Accum = Multiply(MatA, MatB);
  MatrixAccum32Ty Accum32 = Multiply<ComponentType::F32>(MatA, MatB);
}

ByteAddressBuffer MBuf : register(t0);

void CoopVec() {
  using namespace dx::linalg;
  using MatrixBTy =
      Matrix<ComponentType::F16, 16, 16, MatrixUse::B, MatrixScope::Thread>;

  vector<float16_t, 16> Vec = (vector<float16_t, 16>)0;
  MatrixBTy MatB = MatrixBTy::Load(
      MBuf, 0, /* Row stride = number of columns * element size */ 16 * 4,
      MatrixLayout::RowMajor);
  vector<float16_t, 16> Layer1 = Multiply<float16_t>(Vec, MatB);

  vector<float16_t, 16> NullBias = (vector<float16_t, 16>)0;
  vector<float16_t, 16> Layer2 = MultiplyAdd<float16_t>(Layer1, MatB, NullBias);

  VectorRef<ComponentType::F8_E4M3, 16> MemBias = {MBuf,
                                                   /*start offset*/ 4096};
  vector<float16_t, 16> Layer3 = MultiplyAdd<float16_t>(Layer2, MatB, MemBias);

  // Clang doesn't yet support packed types.
#ifdef __hlsl_dx_compiler
  vector<uint8_t4_packed, 4> SomeData = (vector<uint8_t4_packed, 4>)0;

  vector<float16_t, 16> Layer4 = MultiplyAdd<float16_t>(
      MakeInterpretedVector<ComponentType::F8_E4M3>(SomeData), MatB, MemBias);
  vector<float16_t, 16> Layer5 = MultiplyAdd<float16_t>(
      MakeInterpretedVector<ComponentType::F8_E4M3>(SomeData), MatB, NullBias);
#endif
}

RWByteAddressBuffer Buf : register(u1);

void OuterProdAccum() {
  using namespace dx::linalg;
  using MatrixAccumTy = Matrix<ComponentType::F16, 16, 8,
                               MatrixUse::Accumulator, MatrixScope::Thread>;

  vector<float16_t, 16> VecA = (vector<float16_t, 16>)0;
  vector<float16_t, 8> VecB = (vector<float16_t, 8>)0;
  MatrixAccumTy MatAcc =
      OuterProduct<ComponentType::F16, MatrixScope::Thread>(VecA, VecB);

  MatAcc.Accumulate(Buf, 0, 0, MatrixLayout::OuterProductOptimal);
}
```
