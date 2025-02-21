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

See [0029] for general background around the need for these new operations.

An HLSL API needs to be defined to expose these new operations in a way that:
* work well with existing HLSL APIs
* is expected to work well with future HLSL APIs in the same problem space
* can be implemented reasonably in DXC and cleanly in clang

This design builds on the "long vectors" feature described in [0026].

[0026]: 0026-hlsl-long-vector-type.md

## Proposed solution

First strawman:

```c++
ByteAddressBuffer inputMatrix0; 
ByteAddressBuffer inputMatrix1; 
ByteAddressBuffer biasVector0; 
ByteAddressBuffer biasVector1;

void ps_main(args) // args: texture, normal, position
{   
    PreProcessing(args);
    // Neural Network computes the output vector
    // using the same input args and trained data
    // in the form of matrices and bias vectors.

    // The input vector is computed from the shader input
    vector<uint32_t, M> inputVector = SomeFunction(args);

    // Below the physical calculations are replaced by NN evaluation
    // the Matrix and Bias are trained offline and loaded to memory.

    // layer0 = inputVector*inputMatrix + biasVector0
    // The matrix and bias are loaded from memory at offsets : moffset0 and boffset0

    dx::linalg::MatrixRef inMat0 = {inputMatrix0, moffset0};
    dx::linalg::VectorRef biasV0 = {biasVector0, boffset0};
    vector<uint32_t, K> layer0 = dx::linalg::MulAdd(inputVector, inMat0, biasV0);
    layer0 = max(layer0,0); // Apply activation function

    // layer0 = inputVector*inputMatrix0 + biasVector0
    // The matrix and bias are loaded from memory at offsets : moffset1 and boffset1

    dx::linalg::MatrixRef inMat1 = {inputMatrix1, moffset1};
    dx::linalg::VectorRef biasV1 = {biasVector1, boffset1};
    vector<uint32_t, K> layer1 = dx::linalg::MulAdd(layer0, inMat1, biasV1);
    layer1 = max(layer1,0); // Apply activation function

    // output = layer1*inputMatrix1 + biasVector1 
    vector<uint32_t, N> output = dx::linalg::MulAdd(layer1, inMat1, biasV1);

    output = exp(output); 

    color.r = output[0] * args.lightcolor; 
    color.g = output[1] * args.lightcolor; 
    color.b = output[2] * args.lightcolor; 
}
```

## Detailed design

TBD

## Alternatives considered (Optional)

TBD

## Acknowledgments (Optional)

TBD

<!-- {% endraw %} -->
