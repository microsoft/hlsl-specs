<!-- {% raw %} -->

# HLSL Long Vectors

* Proposal: [0026-HLSL-Vectors](0026-hlsl-vector-type.md)
* Author(s): [Anupama Chandrasekhar](https://github.com/anupamachandra), [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**

## Introduction

HLSL has previously supported vectors of as many as four elements (int3, float4, etc.).
These are useful in a traditional graphics context for representation and manipulation of
 geometry and color information.
The evolution of HLSL as a more general purpose language targeting Graphics and Compute
 greatly benefit from longer vectors to fully represent these operations rather than to try to
 break them down into smaller constituent vectors.
This feature adds the ability to load, store, and perform select operations on HLSL vectors longer than four elements.

## Motivation

The adoption of machine learning techniques expressed as vector-matrix operations
 require larger vector sizes to be representable in HLSL.
To take advantage of specialized hardware that can accelerate vector operations,
 these and other vector objects need to be preserved at the DXIL level.

## Proposed solution

Enable vectors of length between 4 and 128 inclusive in HLSL using existing template-based vector declarations.
Such vectors will hereafter be referred to as "long vectors".
These will be supported for all elementwise intrinsics that take variable-length vector parameters.
For certain operations, these vectors will be represented as native vectors using [dxil vectors](NNNN-dxil-vectors.md).

## Detailed design

### HLSL vectors

Currently HLSL allows declaring vectors using a templated representation:

```hlsl
vector<T, N> name;
```

`T` is any [scalar](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-scalar) type.
`N` is the number of components and must be an integer between 1 and 4 inclusive.
See the vector definition [documentation](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector) for more details.
This proposal adds support for long vectors of length greater than 4 by
 allowing `N` to be greater than 4 where previously such a declaration would produce an error.

The default behavior of HLSL vectors is preserved for backward compatibility, meaning, skipping the last parameter `N`
defaults to 4-component vectors and the use `vector name;` declares a 4-component float vector, etc. More examples
[here](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector).
Declarations of long vectors require the use of the template declaration.
Unlike vector sizes between 1 and 4, no shorthand declarations that concatenate
 the element type and number of elements (e.g. float2, double4) are allowed for long vectors.

The new vectors will be supported in all shader stages including Node shaders. There are no control flow or wave
uniformity requirements, but implementations may specify best practices in certain uses for optimal performance.

Long vectors can be:

* Elements of arrays, structs, StructuredBuffers, and ByteAddressBuffers.
* Parameters and return types of non-etry functions.
* Stored in groupshared memory.
* Static global varaibles.

Long vectors are not permitted in:

* Resource types other than ByteAddressBuffer or StructuredBuffer.
* Any element of the shader's signature including entry function parameters and return types.
* Cbuffers or tbuffers.

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

#### Vectors in Raw Buffers

N-element vectors are loaded and stored from ByteAddressBuffers using the templated load and store methods
with a vector type of the required size as the template parameter and byte offset parameters.

```hlsl
RWByteAddressBuffer myBuffer;

vector<T, N> val = myBuffer.Load< vector<T, N> >(StartOffsetInBytes); 
myBuffer.Store< vector<T, N> >(StartoffsetInBytes + 100, val);

```

StructuredBuffers with N-element vectors are declared using the template syntax
 with a long vector type as the template parameter.
N-element vectors are loaded and stored from ByteAddressBuffers using the templated load and store methods
with the element index parameters.

```hlsl
RWStructuredBuffer< vector<T, N> > myBuffer;

vector<T, N> val = myBuffer.Load(elementIndex); 
myBuffer.Store(elementIndex, val);

```

#### Accessing elements of long vectors

Long vectors support the existing vector subscript operators to return the scalar element values.
They do not support swizzle operations as they are limited to only the first four elements.

#### Operations on long vectors

Support all HLSL intrinsics that perform [elementwise calculations](NNNN-dxil-vectors.md#elementwise-intrinsics)
 that take parameters that could be long vectors and whose function doesn't limit them to shorter vectors.
These are operations that perform the same operation on an element regardless of its position in the vector
 except that the position indicates which element(s) of other vector parameters might be used in that calculation.

Refer to the HLSL spec for an exhaustive list of [Operators](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators) and [Intrinsics](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-intrinsic-functions).

#### Allowed elementwise vector intrinsics

* Trigonometry : acos, asin, atan, atan2, cos, cosh, degrees, radians, sin, sinh, tan, tanh
* Math: abs, ceil, clamp, exp, exp2, floor, fma, fmod, frac, frexp, ldexp, lerp, log, log10, log2, mad, max, min, pow, rcp, round, rsqrt, sign, smoothstep, sqrt, step, trunc
* Float Ops: f16tof32, f32tof16, isfinite, isinf, isnan, modf, saturate
* Bitwise Ops: reversebits, countbits, firstbithigh, firstbitlow
* Logic Ops: and, or, select
* Reductions: all, any, clamp, dot
* Quad Ops: ddx, ddx_coarse, ddx_fine, ddy, ddy_coarse, ddy_fine, fwidth, QuadReadLaneAt, QuadReadLaneAcrossX, QuadReadLaneAcrossY, QuadReadLaneAcrossDiagonal
* Wave Ops: WaveActiveBitAnd, WaveActiveBitOr, WaveActiveBitXor, WaveActiveProduct, WaveActiveSum, WaveActiveMin, WaveActiveMax, WaveMultiPrefixBitAnd, WaveMultiPrefixBitOr, WaveMultiPrefixBitXor, WaveMultiPrefixProduct, WaveMultiPrefixSum, WavePrefixSum, WavePrefixProduct, WaveReadLaneAt, WaveReadLaneFirst
* Wave Reductions: WaveActiveAllEqual, WaveMatch

#### Native vector intrinsics

Of the above list, the following will produce the appropriate unary, binary, or tertiary
 DXIL intrinsic that take native vector parameters:

* fma
* exp
* log
* tanh
* atan
* min
* max
* clamp
* step

#### Disallowed vector intrinsics

* Only applicable to for shorter vectors: AddUint64, asdouble, asfloat, asfloat16, asint, asint16, asuint, asuint16, D3DCOLORtoUBYTE4, cross, distance, dst, faceforward, length, normalize, reflect, refract, NonUniformResourceIndex
* Only useful for disallowed variables: EvaluateAttributeAtSample, EvaluateAttributeCentroid, EvaluateAttributeSnapped, GetAttributeAtVertex

### Debug Support

First class debug support for HLSL vectors. Emit `llvm.dbg.declare` and `llvm.dbg.value` intrinsics that can be used by tools for better debugging experience. Open Issue: Handle DXIL scalarized and vector paths.

### Diagnostic Changes

Error messages should be produced for use of long vectors in unsupported interfaces.

* The shader signature.
* A cbuffer/tbuffer.
* A work graph record.
* A mesh or ray tracing payload.

Errors should also be produced when long vectors are used as parameters to intrinsics
 with vector parameters of variable length, but aren't permitted as listed in [Disallowed vector intrinsics](#disallowed-vector-intrinsics)
Attempting to use any swizzle member-style accessors on long vectors should produce an error.
Declaring vectors of length longer than 128 should produce an error.

### Validation Changes

Validation should produce errors when a long vector is found in:

* The shader signature.
* A cbuffer/tbuffer.
* A work graph record.
* A mesh or ray tracing payload.

Use of long vectors in unsupported intrinsics should produce validation errors.

## Runtime Additions

Support for Long vectors requires dxil vector support as defined in [the specification](NNNN-dxil-vectors.md).

Use of long vectors in a shader should be indicated in DXIL with the corresponding
 shader model version and shader feature flag.

## Testing

### Compilation Testing

#### Correct output testing

Verify that long vectors can be declared in all appropriate contexts:

* local variables
* non-entry parameters
* non-entry return types
* StructuredBuffer elements
* Templated Load/Store methods on ByteAddressBuffers
* As members of arrays and structs in any of the above contexts

Verify that long vectors can be correctly initialized in all the forms listed in [Constructing vectors](constructing-vectors).

Verify that long vectors in supported intrinsics produce appropriate outputs.
For the intrinsic functions listed in [Native vector intrinsics](#native-vector-intrinsics),
 the generated DXIL intrinsic calls will have long vector parameters.
For other elementwise vector intrinsic functions listed in [Allowed elementwise vector intrinsics](#allowed-elementwise-vector-intrinsics),
 the generated DXIL should scalarize the parameters and produce scalar calls to the corresponding DXIL intrinsics.
Verify that long vector elements can be accessed using the subscript operation.

Verify that long vectors of different sizes will reference different overloads of user and built-in functions.
Verify that template instantiation using long vectors correctly creates variants for the right sizes.

#### Invalid usage testing

Verify that compilation errors are produced for long vectors used in:

* Entry function parameters
* Entry function returns
* Type buffer declarations
* Cbuffer blocks
* Cbuffer global variables
* Work graph records
* Mesh and ray tracing payloads
* Any intrinsic functions listed in [Disallowed vector intrinsics](#disallowed-vector-intrinsics)
* All swizzle operations (e.g. `lvec.x`, `lvec.rg`, `lvec.wzyx`)

### Validation Testing

Verify that Validation produces errors for any DXIL intrinsic that corresponds to the
 HLSL intrinsic functions listed in [Disallowed vector intrinsics](#disallowed-vector-intrinsics).
Verify that Validation produces errors for any DXIL intrinsic with native vector parameters
 that corresponds to the [allowed elementwise vector intrinsics](#allowed-elementwise-vector-intrinsics)
 and are not listed in [native vector intrinsics](#native-vector-intrinsics).

### Execution Testing

Correct behavior for all of the intrinsics listed in [allowed elementwise vector intrinsics](#allowed-elementwise-vector-intrinsics)
 will be verified with execution tests that perform the operations on long vectors and confirm correct results
 for the given test values.
Where possible, these tests will be variations on existing tests for these intrinsics.

## Alternatives considered

The original proposal introduced an opaque type to HLSL that could represent longer vectors.
This would have been used only for native vector operations.
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
  * A: 128. It's big enough for some known uses.
There aren't concrete reasons to restrict the vector length.
Having a limit facilitates testing and sets expectations for both hardware and software developers.

* Q: Usage restrictions
  * A: Long vectors may not form part of the shader signature.
       There are many restrictions on signature elements including bit fields that determine if they are fully written.
       By definition, these involve more interfaces that would require additional changes and testing.
* Q: Does this have implications for existing HLSL source code compatibility?
  * A: Existing HLSL code that makes no use of long vectors will have no semantic changes.
* Q: Should this change the default N = 4 for vectors?
  * A: No. While the default size of 4 is less intuitive in a world of larger vectors, existing code depends on this default, so it remains unchanged.
* Q: How will SPIR-V be supported?
  * A: TBD
* Q: should swizzle accessors be allowed for long vectors?
  * A: No. It doesn't make sense since they can't be used to access all elements
       and there's no way to create enough swizzle members to accommodate the longest allowed vector.
* Q: How should scalar groupshared arrays be loaded/stored into/out of long vectors.
  * A: After some consideration, we opted not to include explicit Load/Store operations for this function.
       There are at least a couple ways this could be resolved, and the preferred solution is outside the scope.

<!-- {% endraw %} -->