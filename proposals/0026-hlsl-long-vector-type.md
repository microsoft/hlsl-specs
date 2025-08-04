<!-- {% raw %} -->

# HLSL Long Vectors

* Proposal: [0026](0026-hlsl-vector-type.md)
* Author(s): [Anupama Chandrasekhar](https://github.com/anupamachandra), [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Accepted**
* Planned Version: SM 6.9

## Introduction

HLSL has previously supported vectors of as many as four elements (int3, float4, etc.).
These are useful in a traditional graphics context for representation and manipulation of
 geometry and color information.
The evolution of HLSL as a more general purpose language targeting Graphics and Compute
 greatly benefit from longer vectors to fully represent these operations rather than to try to
 break them down into smaller constituent vectors.
This feature adds the ability to load, store, and perform elementwise operations on HLSL
 vectors longer than four elements.

## Motivation

The adoption of machine learning techniques expressed as vector-matrix operations
 require larger vector sizes to be representable in HLSL.
To take advantage of specialized hardware that can accelerate longer vector operations,
 these vectors need to be preserved in the exchange format as well.

## Proposed solution

Enable vectors of length between 5 and 1024 inclusive in HLSL using existing template-based vector declarations.
Such vectors will hereafter be referred to as "long vectors".
These will be supported for all elementwise intrinsics that take variable-length vector parameters.
For certain operations, these vectors will be represented as native vectors using
 [Dxil vectors](0030-dxil-vectors.md) and equivalent SPIR-V representations.

## Detailed design

### HLSL vectors

Currently HLSL allows declaring vectors using a templated representation:

```hlsl
vector<T, N> name;
```

`T` is any [scalar](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-scalar) type.
`N` is the number of components and must be a constant integer expression between 1 and 4 inclusive.
See the vector definition [documentation](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector) for more details.
This proposal adds support for long vectors of length greater than 4 by
 allowing `N` to be a constant integer expression greater than 4
 where previously such a declaration would produce an error.

The default behavior of HLSL vectors is preserved for backward compatibility, meaning, skipping the last parameter `N`
defaults to 4-component vectors and the use `vector name;` declares a 4-component float vector, etc. More examples
[here](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-vector).
Declarations of long vectors require the use of the template declaration.
Unlike vector sizes between 1 and 4, no shorthand declarations that concatenate
 the element type and number of elements (e.g. float2, double4) are allowed for long vectors.

#### Allowed Usage

The new vectors will be supported in all shader stages including Node shaders.

Long vectors can be:

* Elements of arrays, structs, StructuredBuffers, and ByteAddressBuffers.
* Parameters and return types of non-entry functions.
* Stored in groupshared memory.
* Static global variables.
* Local function scoped variables.

Long vectors are not permitted in:

* Resource types other than ByteAddressBuffer or StructuredBuffer.
* Any part of the shader's signature including entry function parameters and return types or
  user-defined struct parameters.
* Cbuffers or Tbuffers.
* A ray tracing `Parameter`, `Attributes`, or `Payload` parameter structures.
* A work graph record.

While this describes where long vectors can be used and later sections will describe how,
implementations may specify best practices in certain uses for optimal performance.

#### Constructing vectors

HLSL vectors can be constructed through initializer lists, constructor syntax initialization, or by assignment.
Vectors can be initialized and assigned from various casting operations including scalars, arrays, and initialization lists.
Initialization of vectors from vectors or initialization lists with fewer elements than the assigned vector are not allowed.
Long vectors will maintain equivalent casting abilities.

Examples:

```hlsl
vector<uint, 5> InitList = {1, 2, 3, 4, 5};
vector<uint, 6> Construct = vector<uint, 6>(6, 7, 8, 9, 0, 0);
uint4 initval = {0, 0, 0, 0};
vector<uint, 6> VecB = {1, 2, 3, 4, 5, 6};
vector<uint, 8> VecVec = {uint2(coord.xy), VecB};
vector<uint, 6> Assigned = VecB;
float Arr[5];
vector<float, 5> CastArr = (vector<float, 5>)Arr;
vector<float, 6> ArrScal = {Arr, 7.9};
vector<float, 10> ArrArr = {Arr, Arr};
vector<float, 15> Scal = 4.2;
```

#### Vectors in Raw Buffers

N-element vectors are loaded and stored from ByteAddressBuffers using the templated load and store methods
with a vector type of the required size as the template parameter and byte offset parameters.

```hlsl
RWByteAddressBuffer myBuffer;

vector<T, N> val = myBuffer.Load< vector<T, N> >(StartOffsetInBytes); 
myBuffer.Store< vector<T, N> >(StartoffsetInBytes + 100, val);

```

Long Vectors loaded from or stored to a Raw Buffer must comply with the alignment
rules of the underlying buffer. Therefore the offset used to `Load`/`Store` a vector
from/to a `ByteAddressBuffer` must be aligned to a multiple of the component type.
(EX: half -> 2 bytes, uint -> 4 bytes, int64 -> 8 bytes). Misaligned offsets result 
in undefined behavior.

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

Long vectors support the existing vector subscript operators `[]` to access the scalar element values.
They do not support any swizzle operations.

#### Operations on long vectors

Support all HLSL intrinsics that perform [elementwise calculations](0030-dxil-vectors.md#elementwise-intrinsics)
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
* Type Conversions: asdouble, asfloat, asfloat16, asint, asint16, asuint, asuint16

#### Disallowed vector intrinsics

* Only applicable to shorter vectors: AddUint64, D3DCOLORtoUBYTE4, cross, distance, dst, faceforward, length, normalize, reflect, refract, NonUniformResourceIndex
* Only useful for disallowed variables: EvaluateAttributeAtSample, EvaluateAttributeCentroid, EvaluateAttributeSnapped, GetAttributeAtVertex

### Interchange Format Additions

Long vectors can be represented in DXIL, SPIR-V or other interchange formats as scalarized elements or native vectors.
Representation of native vectors in DXIL depends on [dxil vectors](0030-dxil-vectors.md).

### Debug Support

First class debug support for HLSL vectors. Emit `llvm.dbg.declare` and `llvm.dbg.value` intrinsics that can be used by tools for better debugging experience.
These should enable tracking vectors through their scalarized and native vector usages.

### Diagnostic Changes

Error messages should be produced for use of long vectors in unsupported interfaces:

* Typed buffer element types.
* Parameters to the entry function.
* Return types from the entry function.
* Cbuffers blocks.
* Cbuffers global variables.
* Tbuffers.
* Work graph records.
* Mesh/amplification payload entry parameter structures.
* `Payload`, `Parameter`, and `Attributes` parameter user-defined structs used in
  `TraceRay()`, `CallShader()`, and `ReportHit()` ray tracing intrinsics.

Errors should also be produced when long vectors are used as parameters to intrinsics
 with vector parameters of variable length, but aren't permitted as listed in [Disallowed vector intrinsics](#disallowed-vector-intrinsics)
Attempting to use any swizzle member-style accessors on long vectors should produce an error.
Declaring vectors of length longer than 1024 should produce an error.

### Validation Changes

Validation should produce errors when a long vector is found in:

* The shader signature.
* A Cbuffer/Tbuffer.
* Work graph records.
* `Payload`, `Parameter`, and `Attributes` parameter user-defined structs used in
  `TraceRay()`, `CallShader()`, and `ReportHit()` ray tracing intrinsics.
* Metadata

Note that the disallowing long vectors in entry function signatures includes any user-defined structs
 used in mesh and ray tracing shaders.

Use of long vectors in unsupported intrinsics should produce validation errors.

### Device Capability

Devices that support Shader Model 6.9 will be required to fully support this feature.

## Testing

### Compilation Testing

#### Correct output testing

Verify that long vectors can be declared in all appropriate contexts:

* Local variables.
* Static global variables.
* Non-entry parameters.
* Non-entry return types.
* StructuredBuffer elements.
* Templated Load/Store methods on ByteAddressBuffers.
* As members of arrays and structs in any of the above contexts.

Verify that long vectors can be correctly initialized in all the forms listed in [Constructing vectors](#constructing-vectors).

Verify that long vectors in supported intrinsics produce appropriate outputs.
Supported intrinsic functions listed in [Allowed elementwise vector intrinsics](#allowed-elementwise-vector-intrinsics)
 may produce intrinsic calls with native vector parameters where available
 or scalarized parameters with individual scalar calls to the corresponding interchange format intrinsics.

Verify that long vector elements can be accessed using the subscript operation with static or dynamic indices.

Verify that long vectors of different sizes will reference different overloads of user and built-in functions.
Verify that template instantiation using long vectors correctly creates variants for the right sizes.

Verification of correct interchange format output depends on the implementation and representation.
Native vector DXIL intrinsics might be checked for as described in [Dxil vectors](0030-dxil-vectors.md)
 if native DXIL vector output is supported.
SPIR-V equivalent output should be checked as well.
Scalarized representations are also possible depending on the compilation implementation.

#### Invalid usage testing

Verify that long vectors produce compilation errors when:

* Declared in interfaces listed in [Diagnostic changes](#diagnostic-changes).
* Passed as parameters to any intrinsic functions listed in [Disallowed vector intrinsics](#disallowed-vector-intrinsics)
* All swizzle operations (e.g. `lvec.x`, `lvec.rg`, `lvec.wzyx`)
* Declaring a vector over the maximum size in any of the allowed contexts listed in [Allowed usage](#allowed-usage).

### Validation Testing

Verify that long vectors produce validation errors in:

* Each element of the shader signature.
* A cbuffer block struct.
* Work graphs record structs.
* The mesh/amplification entry `Payload` parameter struct.
* Each of the `Payload`, `Parameter`, `Attributes` parameter structs used in
  `TraceRay()`, `CallShader()`, and `ReportHit()`,
  and `anyhit`, `closesthit`, `miss`, `callable`, and `closesthit` entry functions.
* Any DXIL intrinsic that corresponds to the HLSL intrinsic functions listed in [Disallowed vector intrinsics](#disallowed-vector-intrinsics).
* Any metadata type.

### Execution Testing

Correct behavior for all of the intrinsics listed in [allowed elementwise vector intrinsics](#allowed-elementwise-vector-intrinsics)
 will be verified with execution tests that perform the operations on long vectors and confirm correct results
 for the given test values.
Where possible, these tests will be variations on existing tests for these
intrinsics. [Long-Vector-ExecutionTest-Plan](./infra/INF-0005-Long-Vector-ExecutionTest-Plan.md)

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

The restrictions outlined in [Allowed Usage](allowed-usage) were chosen because they weren't
 needed for the targeted applications, but are not inherently impossible.
They omitted out of unclear utility and to simplify the design.
There's nothing about those use cases that is inherently incompatible with long vectors
 and future work might consider relaxing those restrictions.

Swizzle operations were not supported because they are limited to the first four elements.
The names of the accessors (xyzw or rgba) are named according to the expected content of
 those vectors in a graphics context.
Since that intretation does not apply to longer vectors, it could be confusing.
The subscript access is flexible and generic and makes other accessors redundant.

## Open Issues

* Q: Is there a limit on the Number of Components in a vector?
  * A: 1024. It's big enough for known uses.
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
  * A: TBD. SPIR-V could be represented as an array of elements, scalarized to use scalars, or a new vector type.
* Q: should swizzle accessors be allowed for long vectors?
  * A: No. It doesn't make sense since they can't be used to access all elements
       and there's no way to create enough swizzle members to accommodate the longest allowed vector.

<!-- {% endraw %} -->
