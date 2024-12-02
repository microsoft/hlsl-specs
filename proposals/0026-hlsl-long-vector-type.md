<!-- {% raw %} -->

# HLSL Long Vectors

* Proposal: [0026-HLSL-Vectors](0026-hlsl-vector-type.md)
* Author(s): [Anupama Chandrasekhar](https://github.com/anupamachandra), [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**

## Introduction

HLSL has supported vectors in a limited capacity (int3, float4, etc.).
These are scalarized in DXIL.
While they are useful in a traditional graphics context,
 small vectors do not scale well with the evolution of HLSL as a more general purpose language targeting Graphics and Compute.
Notably, the adoption of machine learning techniques expressed as vector-matrix operations require larger vector sizes to be representable in HLSL.
To take advantage of specialized hardware that can accelerate vector operations,
 these and other vector objects need to be preserved at the DXIL level.

## Proposed solution

Enable vectors of length greater than 4 in HLSL using existing template-based vector declarations.
Preserve the vector type in DXIL.

## Detailed design

### HLSL vectors

Currently HLSL allows declaring vectors using a templated representation:

```hlsl
vector<T, N> name;
```

`T` is any [scalar](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-scalar) type.
`N` is the number of components and must be an integer between 1 and 4 inclusive.
See the vector definition [documentation](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector) for more details.
This proposal adds support for vectors of length greater than 4.

The default behavior of HLSL vectors is preserved for backward compatibility, meaning, skipping the last parameter `N`
defaults to 4-component vectors and the use `vector name;` declares a 4-component float vector, etc. More examples
[here](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector).
Declarations of vectors longer than 4 require the use of the template declaration.
Unlike vector sizes between 1 and 4, no shorthand declarations are provided.

The new vectors will be supported in all shader stages including Node shaders. There are no control flow or wave
uniformity requirements, but implementations may specify best practices in certain uses for optimal performance.

Restrictions on the uses of vectors with N > 4:

* Vectors with length greater than 4 are not permitted inside a `struct`.
* Vectors with length greater than 4 are not permitted as shader input/output parameters.

#### Constructing vectors

HLSL vectors can be constructed through initializer lists, constructor syntax initialization, or by assignment.

Examples:

``` hlsl
vector<uint, 5> vecA = {1, 2, 3, 4, 5};
vector<uint, 6> vecB = vector<uint, 6>(6, 7, 8, 9, 0, 0);
uint4 initval = {0, 0, 0, 0};
vector<uint, 8> vecC = {uint2(coord.xy), vecB};
vector<uint, 6> vecD = vecB;
```

#### Load and Store vectors from Buffers/Arrays

For loading and storing N-dimensional vectors from ByteAddressBuffers we use the templated load and store methods
by providing a vector type of the required size as the template parameter.

```hlsl
// Load/Store from [RW]ByteAddressBuffers
RWByteAddressBuffer myBuffer;

vector<T, N> val = myBuffer.Load< vector<T, N> >(uint StartOffsetInBytes);
myBuffer.Store< vector<T, N> >(uint StartoffsetInBytes, vector<T, N> stVec);

// Load/Store from groupshared arrays
groupshared T inputArray[512];
groupshared T outputArray[512];

Load(vector<T,N> ldVec, groupshared inputArray, uint offsetInBytes);
Store(vector<T,N> stVec, groupshared outputArray, uint offsetInBytes);
```

#### Operations on vectors

Support all HLSL intrinsics that are important as activation functions:

* fma
* exp
* log
* tanh
* atan
* min
* max
* clamp
* step

Eventually support all HLSL operators and math intrinsics that are currently enabled for vectors.

Refer to the HLSL spec for an exhaustive list of [Operators](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators) and [Intrinsics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-intrinsic-functions).

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

The original proposal introduced an opaque type to HLSL that could represent longer vectors.
This would have been used only for cooperative vector operations.
This would have limited the scope of the feature to small neural network evaluation and also contain the scope for testing some.

Representing vectors used in neural networks as LLVM vectors also allows leveraging existing optimizations.
This direction also aligns with the long term roadmap of HLSL to enable generic vectors.
Since the new data type would have required extensive testing as well,
the testing burden saved may not have been substantial.
Since these vectors are to be added eventually anyway, the testing serves multiple purposes.
It makes sense to not introduce a new datatype but use HLSL vectors,
even if the initial implementation only exposes partial functionality.

## Open Issues

* Q: Is there a limit on the Number of Components in a vector?
  * A: Chose a number based on precedents set by other languages. Support atleast 128.
* Q: Usage restrictions
  * A: General vectors (N > 4) are not permitted inside structs.
* Q: Does this have implications for existing HLSL source code compatibility?
  * A: No, existing HLSL code is unaffected by this change.
* Q: Should this change the default N = 4 for vectors?
  * A: No. While the default size of 4 is less intuitive in a world of larger vectors, existing code depends on this default, so it remains unchanged.
* Q: How will SPIRV be supported?
  * A: TBD
* Q: Under what conditions do HLSL vectors remain as vectors and when do they get scalarized in DXIL?
  * A: UNRESOLVED
* Q: Can all implementations support vector DXIL?
  * A: Feature check?

## Acknowledgments

<!-- {% endraw %} -->