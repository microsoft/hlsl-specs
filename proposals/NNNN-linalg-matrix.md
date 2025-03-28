<!-- {% raw %} -->

# Linear Algebra Matrix

* Proposal: [NNNN](NNNN-linalg-matrix.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: TBD
* Status: **Under Consideration**

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

## Proposed solution

Below is a proposed pseudo-HLSL API. The proposal uses C++20 concepts to
represent template type constraints so as to avoid needing SFINAE complications.

```c++
namespace hlsl {

template <class T>
concept ArithmeticScalar = std::is_arithmetic<T>::value;

namespace linalg {

template <typename ComponentTy, uint M, uint N>
  requires ArithmeticScalar<ComponentTy>
class Matrix {
  template <typename NewCompTy> Matrix<NewCompTy, M, N> cast();

  Matrix operator+(Matrix);
  Matrix operator-(Matrix);
  Matrix operator*(Matrix);
  Matrix operator/(Matrix);

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

  static Matrix Splat(ElTy Val);
  static Matrix Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ComponentTy));
  static Matrix Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
                     bool ColMajor, uint Align = sizeof(ComponentTy));

  static Matrix Load(groupshared ElTy Arr[], uint StartIdx, uint Stride,
                     bool ColMajor);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             bool ColMajor, uint Align = sizeof(ComponentTy));

  void Store(groupshared ElTy Arr[], uint StartIdx, uint Stride, bool ColMajor);

  void MultiplyAccumulate(const ref Matrix<T, N, M>);
  void SumAccumulate(const ref Matrix<T, N, M>);
};

template <typename T, uint M, uint N, uint K>
Matrix<T, M, N> Multiply(const ref Matrix<T, M, K>, const ref Matrix<T, K, N>);

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

<!-- {% endraw %} -->
