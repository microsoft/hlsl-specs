<!-- {% raw %} -->

# HLSL Vector Matrix Operations

## Instructions

- Proposal: [0031](0031-hlsl-vector-matrix-operations.md)
- Author(s): [Damyan Pepper][damyanp], [Chris Bieneman][llvm-beanz],
  [Anupama Chandrasekhar][anupamachandra]
- Sponsor: [Damyan Pepper][damyanp]
- Status: **Under Consideration**
- Planned Version: Shader Model 6.9

[damyanp]: https://github.com/damyanp[llvm-beanz]: https://github.com/llvm-beanz
[anupamachandra]: https://github.com/anupamachandra

## Introduction

This proposes a set of HLSL APIs that enable the use of the hardware-accelerated
vector/matrix operations described in [0029]. 

[0029]: 0029-cooperative-vector.md

## Motivation

Modern GPUs have dedicated silicon to accelerate matrix operations, but HLSL
doesn't provide a mechanism to easily utilize these units. Evaluation of
matrix-vector operations (multiply, muladd, accumulation) in HLSL was
previously scalarized at the DXIL level making it hard to employ these
specialized units. This proposal builds on the "Long vectors" feature described
in [0026], providing a mechanism to express matrix-vector ops in HLSL that can
be lowered to the DXIL ops described [0029], these primitives provide the right
level of abstraction for hardware acceleration.

[0026]: 0026-hlsl-long-vector-type.md

## Proposed solution

We introduce a the `dx.linalg` namespace that exposes functions for new
matrix-vector operations:

* **Matrix-Vector Multiply:** Multiply a matrix in memory and a vector
    parameter.
* **Matrix-Vector Multiply-Add:** Multiply a matrix in memory and a vector
    parameter and add a vector from memory.
* **Vector-Vector Outer Product and Accumulate:** Compute the outerproduct of
    two vectors and accumulate the result matrix atomically-elementwise in
    memory.
* **Reduce and Accumulate:** Accumulate elements of a vector
    atomically-elementwise to corresponding elements in memory.


## Detailed Design

### `dx.linalg.MatrixRef`

`MatrixRef` is a wrapper class that represents a Matrix stored in a
(RW)ByteAddressBuffer that also contains its type, dimension, layout, start
offset and stride.

#### Syntax

```c++ 
namespace dx {
namespace linalg {

template <TypeInterpretation Interpretation, uint M, uint K,
          MatrixLayout Layout>
class MatrixRef {
  RWByteAddressBuffer Buffer;
  uint Stride;
  uint StartOffset;
}

} // namespace linalg
} // namespace dx
```

> Note we need to support RWByteAddressBuffer and ByteAddressBuffer if we want
  to use MatrixRef for both Mul and OuterProductAccumulate. How do we do this?

#### Arguments

##### Template parameters

* **Interpretation**: This describes the type of the value in the buffer. See
    [Type Interpretation] section details.

* **M x K**: Matrix Dimension

* **Layout**: Specifies the layout of the matrix. See [Matrix Layouts] section
    for details.

##### Member Variables

The matrix is loaded from a raw buffer **Buffer**, starting at **StartOffset**.
For row-major and column-major layouts, **Stride** specifies the number of
bytes to go from one row/column to the next. For optimal layouts, **matrix
stride** is ignored. 

The base address of **Buffer** and the **StartOffset** must be 64 byte aligned.

The **Stride** must 16 byte aligned.

`dx::linalg::VectorRef`

`VectorRef` is a wrapper class that represents a vector stored in a
ByteAddressBuffer specfying its type and StartOffset.

>TODO: Needs a length/size parameter?

```c++ 
namespace dx {
namespace linalg {

template <TypeInterpretation Interpretation> class VectorRef {
  RWByteAddressBuffer Buffer;
  uint StartOffset;
}

} // namespace linalg
} // namespace dx

```

#### Arguments

##### Template Parameters

* **Interpretation**: This describes the type of the value in the buffer. See
    [Type Interpretation] section details.

##### Member Variables

The vector is loaded from a raw buffer **Buffer**, starting at **Start
Offset**.

The base address of **Buffer** and the **StartOffset** must be 64 byte aligned.

`dx.linalg.InterpretedVector`

`InterpretedVector` is a wrapper class that represents a native vector
`vector<T, N>` but with an interpretation type that determines the actual type
that vector will be interpreted as.

```c++ 
namespace dx { 
namespace linalg {

template<typename T, uint N, TypeInterpretation Interpretation> 
    class InterpretedVector { 
        vector<T, N> vec; }

} 
} 
```

#### Arguments

##### Template Parameters

* **T**: The vector **vec** 's declared type.
* **N**: The vector **vec** 's declared length.
* **Interpretation**: Allows functions operating on these vectors to interpret
    the vector as a type different from its declared type. Based on the value
    the type conversion maybe arithmetic or bitcast. See [Type Interpretation
    section] for more details. This interpreted type also determines the actual
    number of elements in the vector which might differ from **N** for packed
    types.

##### Member Variables
 
 A native vector **vec** of type **T** and size **N**.

 ### Functions

`dx::linalg::Mul` and `dx::linalg::MulAdd`

The `dx::linalg::Mul` function multiplies matrix and a input vector. The matrix
is loaded from memory while the vector is stored in a variable.

The `dx::linalg::MulAdd` operation behaves as `dx::linalg::Mul`, but also adds
an bias vector (loaded from memory) to the result.

#### Syntax

```c++ 
namespace dx { 
namespace linalg {

template <TypeInterpretation matrixInterpretation, uint M, uint K, MatrixLayout
layout, typename InputType, uint InputNumcomp, TypeInterpretation
InputInterpretation, typename ResultType, bool MatrixNeedsTranspose>
vector<ResultType, M> Mul(MatrixRef<matrixInterpretation, M, N, layout>
WeightMatrix, InterpretedVector<InputType, InputNumComp, InputInterpretation>
InputVector); } }

```

```c++ 
namespace dx { 
namespace linalg {

template <TypeInterpretation matrixInterpretation, uint M, uint K, MatrixLayout
layout, TypeInterpretation biasVectorInterpretation, typename InputType, uint
InputNumcomp, TypeInterpretation InputInterpretation, typename ResultType>
vector<ResultType, M> MulAdd(MatrixRef<matrixInterpretation, M, N,
layout> WeightMatrix, InterpretedVector<InputType, InputNumComp,
InputInterpretation> InputVector, VectorRef<BiasInterpretation> BiasVector);

} 
} 
```

#### Arguments

* **WeightMatrix**: is the Matrix multiplicand loaded from a raw buffer.

* **InputVector**: is the vector multiplicand.

* **BiasVector**: add the result of the matrix-vector multiply to a vector
    loaded from a raw buffer. 


`dx::linalg::OuterProductAccumulate`

#### Syntax

```c++ 
namespace dx { 
namespace linalg {

template <typename T, uint M, uint N, MatrixLayout layout, TypeInterpretation
interpretation> 
void OuterProductAccumulate(vector<T, M> inputVector1,
        vector<T, N> inputVector2, MatrixRef<interpretation, M, N, layout>
        AccMatrix); 
} 
}

```

#### Arguments

`dx::linalg::VectorAccumulate`

#### Syntax

```c++ 
namespace dx { 
namespace linalg {

template <typename T, uint N> 
void VectorAccumulate(vector<T, N> inputVector,
        RWByteAddressBuffer Buffer, uint StartOffset);

} 
} 
```

#### Arguments

### Type Interpretation

> To be filled

### Matrix Layout

> To be filled

First strawman:

> To be fixed

First strawman:

```c++ 

ByteAddressBuffer inputMatrix0; 
ByteAddressBuffer inputMatrix1; 
ByteAddressBuffer biasVector0; 
ByteAddressBuffer biasVector1;

void ps_main(args) // args: texture, normal, position{   PreProcessing(args);
    // Neural Network computes the output vector using the same input args and
    // trained data in the form of matrices and bias vectors.

    // The input vector is computed from the shader input
    vector<uint32_t, M> inputVector = SomeFunction(args);

    // Below the physical calculations are replaced by NN evaluation the Matrix
    // and Bias are trained offline and loaded to memory.

    // layer0 = inputVector*inputMatrix + biasVector0 The matrix and bias are
    // loaded from memory at offsets : moffset0 and boffset0

    dx::linalg::MatrixRef inMat0 = {inputMatrix0, moffset0};
    dx::linalg::VectorRef biasV0 = {biasVector0, boffset0}; vector<uint32_t, K>
    layer0 = dx::linalg::MulAdd(inputVector, inMat0, biasV0); layer0 = max
    (layer0,0); // Apply activation function

    // layer0 = inputVector*inputMatrix0 + biasVector0 The matrix and bias are
    // loaded from memory at offsets : moffset1 and boffset1

    dx::linalg::MatrixRef inMat1 = {inputMatrix1, moffset1};
    dx::linalg::VectorRef biasV1 = {biasVector1, boffset1}; vector<uint32_t, K>
    layer1 = dx::linalg::MulAdd(layer0, inMat1, biasV1); layer1 = max
    (layer1,0); // Apply activation function

    // output = layer1*inputMatrix1 + biasVector1 
    vector<uint32_t, N> output = dx::linalg::MulAdd(layer1, inMat1, biasV1);

    output = exp(output); 

    color.r = output[0] * args.lightcolor; color.g = output
    [1] * args.lightcolor; color.b = output[2] * args.lightcolor; } ```

## Alternatives considered (Optional)

TBD

## Acknowledgments (Optional)

We would like to thank Jeff Bolz for his contribution to this spec.

<!-- {% endraw %} -->
