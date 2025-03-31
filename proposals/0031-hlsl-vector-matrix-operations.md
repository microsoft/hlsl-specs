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
vector/matrix operations described in [0029].

[0029]: 0029-cooperative-vector.md

## Motivation

Modern GPUs have dedicated silicon to accelerate matrix operations, but HLSL
doesn't provide a mechanism to easily utilize these units. Evaluation of
matrix-vector operations (multiply, muladd, accumulation) in HLSL was previously
scalarized at the DXIL level making it hard to employ these specialized units.
This proposal builds on the "Long vectors" feature described in [0026],
providing a mechanism to express matrix-vector ops in HLSL that can be lowered
to the DXIL ops described [0029], these primitives provide the right level of
abstraction for hardware acceleration.

An HLSL API needs to be defined to expose these new operations in a way that:
* works well with existing HLSL APIs
* is expected to work well with future HLSL APIs in the same problem space
* can be implemented reasonably in DXC and cleanly in clang

[0026]: 0026-hlsl-long-vector-type.md

## Proposed solution

This API will be implemented using HLSL code.  The exact mechanism for getting
this code into a developer's shader is TBD, but implementations have a few
possible options, including:

* Developers must explicitly #include a header file
* The compiler force-includes the header file
* The compiler force-includes a precompiled version of the header file

The header-implementation accesses the DXIL operations described in [0029] by
calling low-level builtins. These builtins should be considered implementation
details and users should not call them directly. However, since they are a part
of the implementation plan for the first implementation of this API they are
described [below](#builtins).

Since this API is currently only supported by DirectX, all the new types /
methods described in it are placed in the `dx` namespace. Within this namespace,
a `linalg` namespace is also added to group together types and methods related
to linear algebra.

Throughout this API, template parameters are used to store values that must be
known at compile time, while member variables or function arguments are used to
store values that may only be determined at runtime.

This API defines the following supporting types:

* `struct dx::linalg::MatrixRef`
  * Reference to a matrix stored in a ByteAddressBuffer.   
* `struct dx::linalg::RWMatrixRef`
  * Reference to a matrix stored in a RWByteAddressBuffer.
* `struct dx::linalg::VectorRef`
  * Reference to a vector stored in a ByteAddressBuffer.
* `struct dx::linalg::RWVectorRef`
  * Reference to a vector stored in a RWByteAddressBuffer.
* `struct dx::linalg::Vector`
  * Wrapper around a vector, allowing the elements of the vector to be
    reinterpreted in various ways.
* `enum dx::linalg::DataType`
  * Enum describing various data types that can be used to applied to matrices
    and vectors.
* `enum dx::linalg::MatrixLayout`
  * Enum describing the possible layouts for a matrix in memory.

This API defines the following functions:

* `dx::linalg::Mul`
  * Multiply a matrix in memory by a vector parameter.
* `dx::linalg::MulAdd`
  * Multiply a matrix in memory by a vector parameter, and add a vector from
    memory.
* `dx::linalg::OuterProductAccumulate`
  * Compute the outer product of two vectors and accumulate the result matrix
    atomically-elementwise in memory.
* `dx::linalg::VectorAccumulate`
  * Accumulate elements of a vector atomically-elementwise to corresponding
    elements in memory.
* `dx::linalg::InterpretedVector`
  * Convenience function to construct a `Vector` inline while inferring various
    template parameters.


These are all described in more detail below, but the follow code example gives
a flavor of how these work together:

```c++
ByteAddressBuffer model;

vector<float, 3> ApplyNeuralMaterial(vector<half, 8> inputVector) {
  using namespace dx::linalg;

  MatrixRef<
      DATA_TYPE_E4M3, 32, 8,
      MATRIX_LAYOUT_INFERENCING_OPTIMAL>
      matrix0 = {model, 0, 0};

  VectorRef<DATA_TYPE_FLOAT16> biasVector0 = {model, 1024};

  MatrixRef<
      DATA_TYPE_E4M3,
      32, 32, MATRIX_LAYOUT_INFERENCING_OPTIMAL>
      matrix1 = {model, 2048, 0};

  VectorRef<DATA_TYPE_FLOAT16> biasVector1 = {model, 3072};

  MatrixRef<
      DATA_TYPE_E4M3,
      3, 32, MATRIX_LAYOUT_INFERENCING_OPTIMAL>
      matrix2 = {model, 4096, 0};

  VectorRef<DATA_TYPE_FLOAT16> biasVector2 = {model, 5120};

  vector<half, 32> layer0 = MulAdd<half>(
      matrix0,
      InterpretedVector<DATA_TYPE_E4M3>(inputVector),
      biasVector0);
  layer0 = max(layer0, 0);

  vector<half, 32> layer1 = MulAdd<half>(
      matrix1,
      InterpretedVector<DATA_TYPE_E4M3>(layer0),
      biasVector1);
  layer1 = max(layer1, 0);

  vector<float, 3> output = MulAdd<float>(
      matrix2,
      InterpretedVector<DATA_TYPE_E4M3>(layer1),
      biasVector2);
  output = exp(output);

  return output;
}
```

## Detailed design

TBD

### Builtins

Although these "builtins" are not intended to be part of the HLSL language, and
no promises are made that these will continue to be available over time, this
proposal describes an implementation in terms of builtins such as this. For
this reason it is useful to have them described here as a reference point.

Each builtin corresponds to one of the operations described in [0029].

```c++
namespace dx {
namespace linalg {
namespace details {

// dx.op.matvecmul
template <typename TYo, int NUMo, typename TYi, int NUMi, typename RES>
void __builtin_MatVecMul(out vector<TYo, NUMo> OutputVector,
                         bool IsOutputUnsigned, vector<TYi, NUMi> InputVector,
                         bool IsInputUnsigned, uint InputVectorInterpretation,
                         RES MatrixResource, uint MatrixStartOffset,
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
                                      DataType MatrixInterpretation,
                                      MatrixLayout Layout, uint MatrixStride);

// dx.op.vectoraccumulate
template <typename TY, int NUM, typename RES>
void __builtin_VectorAccumulate(vector<TY, NUM> InputVector,
                                RES OutputArrayResource,
                                uint OutputArrayOffset);

} // namespace details
} // namespace linalg
} // namespace dx

```

## Alternatives considered (Optional)

TBD

## Acknowledgments (Optional)

We would like to thank Jeff Bolz for his contribution to this spec.

<!-- {% endraw %} -->
