<!-- {% raw %} -->

* Proposal: [0026-HLSL-Vectors](0026-hlsl-vector-type.md)
* Author(s): [Anupama Chandrasekhar](https://github.com/anupamachandra)
* Sponsor: [Damyan Pepper](https://github.com/damyanp)
* Status: **Under Consideration**

# HLSL Vectors

## Introduction

HLSL has supported vectors in a limited capacity (int3, float4, etc.), and these are scalarized in DXIL; small vectors while useful in a traditional graphics context do not scale well with the evolution on HLSL as a more general purpose language targetting Graphics and Compute. Notably, with the ubiquitous adoption of machine learning techniques which often get expressed as vector-matrix operations, there is a need for supporting larger vector sizes in HLSL and preserving these vector objects at the DXIL level to take advantage of specialized hardware that can accelerate vector operations.

## Proposed solution

Enable vectors of longer length in HLSL and preserve the vector type in DXIL.

## Detailed design

### HLSL vectors `vector<T, N>`

Currently HLSL allows `vector<T, N> name;` where `T` is any [scalar](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-scalar) type and `N`, number of
components, is a positive integer less than or equal to 4. See current definition [here](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector). 
This proposal extends this support to longer vectors (beyond 4). 

The default behavior of HLSL vectors is preserved for backward compatibility, meaning, skipping the last parameter `N`
defaults to 4-component vectors and the use `vector name;` declares a 4-component float vector, etc. More examples
[here](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector).

The new vectors will be supported in all shader stages including Node shaders. There are no control flow or wave
uniformity requirements, but implementations may specify best practices in certain uses for optimal performance. 

**Restrictions on the uses of vectors with N > 4** 

* Vectors with length greater than 4 are not permitted inside a `struct`.
* Vectors with length greater than 4 are not permitted as shader input/output parameters.

**Constructing vectors**

HLSL vectors can be constructed through initializer lists and constructor syntax initializing or by assignment.

Examples:

``` 
vector<uint, 5> vecA = {1, 2, 3, 4, 5}; 
vector<uint, 6> vecB = vector<uint, 6>(6, 7, 8, 9, 0, 0);
uint4 initval = {0, 0, 0, 0};
vector<uint, 8> vecC = {uint2(coord.xy), vecB};
vector<uint, 6> vecD = vecB;
```

**Load and Store vectors from Buffers/Arrays**

For loading and storing N-dimensional vectors from ByteAddressBuffers we use the `LoadN` and `StoreN` methods, extending
the existing Load/Store, Load2/Store2, Load3/Store3 and Load4/Store4 methods.

``` 
// Load/Store from [RW]ByteAddressBuffers
RWByteAddressBuffer myBuffer;

vector<uint, N> val = myBuffer.LoadN(uint StartOffsetInBytes); 
myBuffer.StoreN<T>(uint StartoffsetInBytes, vector<T, N> stVec);

// Load/Store from groupshared arrays
groupshared T inputArray[512];
groupshared T outputArray[512];

Load(vector<T,N> ldVec, groupshared inputArray, uint offsetInBytes);
Store(vector<T,N> stVec, groupshared outputArray, uint offsetInBytes);
```

**Operations on vectors** 

Support all HLSL intrinsics that are important as activation functions: fma, exp, log, tanh, atan, min, max, clamp, and
step. Eventually support all HLSL operators and math intrinsics that are currently enabled for vectors.

Refer to the HLSL spec for an exhaustive list of [Operators](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators) and [Intrinsics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-intrinsic-functions).

Note: Additionally any mathematical operations missing from the above list but needed as activation functions for neural
network computations will be added.

### Debug Support
First class debug support for HLSL vectors. Emit `llvm.dbg.declare` and `llvm.dbg.value` intrinsics that can be used by tools for better debugging experience. Open Issue: Handle DXIL scalarized and vector paths. 


### Diagnostic Changes

* Additional error messages for illegal or unsupported use of arbitrary length vectors.
* Remove current bound checks (N <= 4) for vector size in supported cases, both HLSL and DXIL.


### Validation Changes

* What additional validation failures does this introduce?
*Illegal uses of vectors should produce errors*
* What existing validation failures does this remove?
*Allow legal uses of vectors with number of components greater than 4*

## D3D12 API Additions

TODO: Possible checks for DXIL vector support and tiered support.

## Check Feature Support

Open Issue: Can implementations support vector DXIL?

### Minimum Support Set


## Testing

* How will correct codegen for DXIL/SPIRV be tested?
* How will the diagnostics be tested?
* How will validation errors be tested?
* How will validation of new DXIL elements be tested?
* A: *unit tests in dxc*
* How will the execution results be tested?
* A: *HLK tests*


## Alternatives considered

Our original proposal introduced an opaque Cooperative Vector type to HLSL to limit the scope of the feature to small
neural network evaluation and also contain the scope for testing. But aligning with the long term roadmap of HLSL to
enable generic vectors, it makes sense to not introduce a new datatype but use HLSL vectors, even if the initial
implementation only exposes partial functionality.

## Open Issues
* Q: Is there a limit on the Number of Components in a vector?
* A: Chose a number based on precedents set by other languages. Support atleast 128.
* Q: Usage restrictions
* A: *General vectors (N > 4) are not permitted inside structs.*
* Q: Does this have implications for existing HLSL source code compatibility?
* A: *No, existing HLSL code is unaffected by this change.*
* A: *Change the default N = 4 for vectors? Will affect existing shaders.*
* Q: How will SPIRV be supported?
* A: 
* Q: When do HLSL vectors remain as vectors and when do they get scalarized in DXIL?
* A: 
* Q: Can all implementations support vector DXIL?
* A: Feature check?

## Acknowledgments


<!-- {% endraw %} -->