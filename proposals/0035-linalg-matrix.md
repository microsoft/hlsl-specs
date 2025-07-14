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
  negate,
  abs,
  sin,
  cos,
  tan,
  // What elementwise unary operations make sense?
};

template <typename ComponentTy, uint M, uint N, MatrixUse Use,
          MatrixScope Scope>
  requires ArithmeticScalar<ComponentTy>
class Matrix {
  template <typename NewCompTy, MatrixUse NewUse = Use>
  Matrix<NewCompTy, M, N, NewUse, Scope> cast();

  // Element-wise arithmetic operations.
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
  Matrix unaryOperation(UnaryOperation Op);

  static Matrix Splat(ComponentTy Val);
  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ComponentTy));
  static Matrix Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ComponentTy));

  static Matrix Load(/*groupshared*/ ComponentTy Arr[], uint StartIdx,
                     uint Stride, bool ColMajor);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             bool ColMajor, uint Align = sizeof(ComponentTy));

  void Store(/*groupshared*/ ComponentTy Arr[], uint StartIdx, uint Stride,
             bool ColMajor);

  template <typename T>
    requires ArithmeticScalar<T>
  std::enable_if_t<Use == MatrixUse::Accumulator, void>
  MultiplyAccumulate(const Matrix<T, N, M, MatrixUse::A, Scope>,
                     const Matrix<T, N, M, MatrixUse::B, Scope>);

  template <typename T>
    requires ArithmeticScalar<T>
  std::enable_if_t<Use == MatrixUse::Accumulator, void>
  SumAccumulate(const Matrix<T, N, M, MatrixUse::A, Scope>,
                const Matrix<T, N, M, MatrixUse::B, Scope>);

  // Cooperative Vector outer product accumulate.
  template <typename T>
  std::enable_if_t<Use == MatrixUse::Accumulator, void>
  OuterProductAccumulate(const vector<T, M> &, const vector<T, N>);
};

template <typename T, uint M, uint N, uint K, MatrixScope Scope>
Matrix<T, M, N, MatrixUse::A, Scope>
Multiply(const Matrix<T, M, K, MatrixUse::A, Scope>,
         const Matrix<T, K, N, MatrixUse::B, Scope>);

// HLSL 202y+ with global operator overloading these become viable.
template <typename T, uint M, uint N, uint K, MatrixScope Scope>
Matrix<T, M, N, MatrixUse::Accumulator, Scope>
operator+(const Matrix<T, M, K, MatrixUse::A, Scope>,
          const Matrix<T, K, N, MatrixUse::B, Scope>);

template <typename T, uint M, uint N, uint K, MatrixScope Scope>
Matrix<T, M, N, MatrixUse::Accumulator, Scope>
operator-(const Matrix<T, M, K, MatrixUse::A, Scope>,
          const Matrix<T, K, N, MatrixUse::B, Scope>);

template <typename T, uint M, uint N, uint K, MatrixScope Scope>
Matrix<T, M, N, MatrixUse::Accumulator, Scope>
operator*(const Matrix<T, M, K, MatrixUse::A, Scope>,
          const Matrix<T, K, N, MatrixUse::B, Scope>);

template <typename T, uint M, uint N, uint K, MatrixScope Scope>
Matrix<T, M, N, MatrixUse::Accumulator, Scope>
operator/(const Matrix<T, M, K, MatrixUse::A, Scope>,
          const Matrix<T, K, N, MatrixUse::B, Scope>);

// Cooperative Vector Replacement API
// Cooperative Vector operates on per-thread vectors multiplying against B
// matrices.

template <typename OutputElTy, typename InputElTy, uint M, uint N, uint K,
          typename MatrixBufferTy, typename InputDT, typename MatrixDT,
          uint MatrixM, uint MatrixK, MatrixScope Scope, bool MatrixTranspose>
vector<OutputElTy, M>
Multiply(vector<InputElTy, N> InputVector,
         Matrix<MatrixDT, M, K, MatrixUse::B, Scope> Matrix);

template <typename OutputElTy, typename InputElTy, typename BiasElTy, uint M,
          uint N, uint K, typename MatrixBufferTy, typename InputDT,
          typename MatrixDT, uint MatrixM, uint MatrixK, MatrixScope Scope,
          bool MatrixTranspose>
vector<OutputElTy, M>
MultiplyAdd(vector<InputElTy, N> InputVector,
            Matrix<MatrixDT, M, K, MatrixUse::B, Scope> Matrix,
            vector<BiasElTy, M> BiasVector);

} // namespace linalg
} // namespace hlsl
```

## Detailed design

## Outstanding Questions

* Do we need a "scope" parameter or is it reasonable to assume Subgroup scope
  for all operations at least for an initial feature?
* Do we need the usage to be part of the type?
  * Vulkan has a "use" template parameter, which serves a similar purpose to the
    D3D WaveMatrix "Left" and "Right" types. The compiler should be able to
    detect the usage and introduce memory shuffling automatically (with
    potential performance impact).
* Do we need element-wise accessors? The Vulkan extension doesn't support
  element manipulations, but this has been identified as an important feature?
* What will the DXIL representation look like?
  * This will be addressed in a separate proposal.
* Support for packed types?
* Support for other number formats that aren't natively supported by HLSL?

<!-- {% endraw %} -->
