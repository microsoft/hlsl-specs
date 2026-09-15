---
title: 0029 - Cooperative Vectors
params:
  authors:
  - anupamachandra: Anupama Chandrasekhar
  - damyanp: Damyan Pepper
  - shashankw: Shashank Wadhwa
  sponsors:
  - damyanp: Damyan Pepper
  - pow2clk: Greg Roth
  status: Rejected
---

> This has been superceded by [0035-linalg-matrix.md](0035-linalg-matrix.md)

 
* Planned Version: SM 6.9


[anupamachandra]: https://github.com/anupamachandra
[damyanp]: https://github.com/damyanp
[pow2clk]: https://github.com/pow2clk
[shashankw]: https://github.com/shashankw

 

Cooperative Vectors is the overall name for this feature, though it doesn't appear
in code other than feature tier/capability queries.

Many implementations implement matrix-matrix and matrix-vector operations by allowing
threads in a wave to cooperate under the hood while accessing the specialized hardware 
to achieve peak performance, hence these APIs that expose the acceleration hardware 
to HLSL users were put under the moniker **Cooperative/Wave**. But since this is an 
implementation detail below the level of abstraction of HLSL, the namespace 
**Linear Algebra** was chosen to categorize this set of operations.

E.g. `dx::linalg::` MatVec operations in HLSL, 
`D3D12_LINEAR_ALGEBRA_*` and `D3D12_LINEAR_ALGEBRA_MATRIX_VECTOR_*` in D3D API structs.

## Introduction

In research and in industry, machine learning based approaches have made their
way to mainstream, replacing/augmenting traditional techniques. In graphics,
neural network (NN) based rendering methods are gaining popularity over
traditional methods of image reconstruction, texture compression, material
shading etc. Simultaneously, the increasing use of GPUs for general purpose
ML/DL means that GPU vendors continue to add more specialized hardware in GPUs
to accelerate neural network computations, like accelerating matrix
operations.

This proposal introduces DXIL operations for vector-matrix operations that can
be accelerated by the underlying hardware, building on support for long vectors
described in proposals [0026] and [0030]. The high-level API is described in
proposal [0031].

[0026]: 0026-hlsl-long-vector-type.md
[0030]: 0030-dxil-vectors.md
[0031]: 0031-hlsl-vector-matrix-operations.md

## Motivation

Let's say, we have a typical shader for lighting computation. This is usually
thousands of lines of computation, looping over various materials, light
sources etc. We want a way to replace these computations with a neural network
like shown below. Note that the NN simply replaces the computations in the
original shader with no change to the rendering pipeline, like addition of a
new shader stage.

**Original Shader**

```c++ 
void ps_main(args) // args: texture, normal, position
{   
    PreProcessing(args);
    // Traditional Lighting Computations
    // typically 1000s of lines of code 
    ....
    ....
    ....
    
    color.r = output[0] * args.lightcolor; 
    color.g = output[1] * args.lightcolor; 
    color.b = output[2] * args.lightcolor; 
} 
```

**Neural Network based shader**

The shader below shows the idea of what replacing physical computations with a
neural network based evaluation looks like. Some details have been omitted, but
this should give a sense of how these new operations can be used.

> NOTE: see proposal [0031] for full details on the HLSL API.

```c++
ByteAddressBuffer inputMatrix0; // note read-only buffer
ByteAddressBuffer inputMatrix1; // note read-only buffer
ByteAddressBuffer biasVector0;  // note read-only buffer
ByteAddressBuffer biasVector1;  // note read-only buffer

void ps_main(args) // args: texture, normal, position
{   
    using namespace dx::linalg;

    PreProcessing(args);
    // Neural Network computes the output vector
    // using the same input args and trained data
    // in the form of matrices and bias vectors.

    // The input vector is computed from the shader input
    vector<uint32_t, INPUT_SIZE> inputVector = SomeFunction(args);

    // Below the physical calculations are replaced by NN evaluation
    // the Matrix and Bias are trained offline and loaded to memory

    // layer0 = inputVector*inputMatrix + biasVector0
    // The matrix and bias are loaded from memory at offsets : moffset0 and boffset0
    MatrixRef<DATA_TYPE_UINT32, N, INPUT_SIZE, MATRIX_LAYOUT_MUL_OPTIMAL> M0 = { inputMatrix0, moffset0, 0 }; 
    VectorRef<DATA_TYPE_UINT32> B0 = { biasVector0, boffset0 };

    vector<uint32_t, N> layer0 = MulAdd<uint32_t>(M0, MakeInterpretedVector<DATA_TYPE_UINT32>(inputVector), B0);
    layer0 = max(layer0,0); // Apply activation function

    // layer1 = inputVector*inputMatrix0 + biasVector0
    // The matrix and bias are loaded from memory at offsets : moffset1 and boffset1
    MatrixRef<DATA_TYPE_UINT32, N, N, MATRIX_LAYOUT_MUL_OPTIMAL> M1 = { inputMatrix0, moffset1, 0 };
    VectorRef<DATA_TYPE_UINT32> B1 = { biasVector0, boffset1 };
    vector<uint32_t, K> layer1 = MulAdd<uint32_t>(M1, MakeInterpretedVector<DATA_TYPE_UINT32>(layer0), B1);
    layer1 = max(layer1,0); // Apply activation function

    // output = layer1*inputMatrix1 + biasVector1 
    MatrixRef<DATA_TYPE_UINT32, OUTPUT_SIZE, N, MATRIX_LAYOUT_MUL_OPTIMAL> M2 = { inputMatrix1, 0, 0 };
    VectorRef<DATA_TYPE_UIN32> B2 = { biasVector1, 0 };
    vector<uint32_t, OUTPUT_SIZE> output = MulAdd<uint32_t>(M2, MakeInterpretedVector<DATA_TYPE_UINT32>(layer1), B2);

    output = exp(output); 
    
    color.r = output[0] * args.lightcolor; 
    color.g = output[1] * args.lightcolor; 
    color.b = output[2] * args.lightcolor; 
}

```


## Proposed solution

Introduce new DXIL operations to accelerate matrix-vector operations. In this
specification we add four operations:

* **Matrix-Vector Multiply:** Multiply a matrix in memory and a vector
    parameter.
* **Matrix-Vector Multiply-Add:** Multiply a matrix in memory and a vector
    parameter and add a vector from memory.
* **Vector-Vector Outer Product and Accumulate:** Compute the outer product of
    two vectors and accumulate the result matrix atomically-elementwise in
    memory.
* **Vector Accumulate:** Accumulate elements of a vector
    atomically-elementwise to corresponding elements in memory.


## Detailed design

### Matrix-Vector Multiply and Multiply-Add Operations

#### Syntax
 
``` llvm 
declare <[NUMo] x [TYo]> @dx.op.matvecmul.v[NUMo][TYo].v[NUMi][TYi](
    immarg i32        ; opcode
    <[NUMi] x [TYi]>, ; input vector
    immarg i1,        ; is input unsigned
    immarg i32,       ; input interpretation
    %dx.types.Handle, ; matrix resource
    i32,              ; matrix offset
    immarg i32,       ; matrix interpretation
    immarg i32,       ; matrix M dimension    
    immarg i32,       ; matrix K dimension    
    immarg i32,       ; matrix layout
    immarg i1,        ; matrix transpose
    i32,              ; matrix stride
    immarg i1)        ; is output unsigned

declare <[NUMo] x [TYo]> @dx.op.matvecmuladd.v[NUMo][TYo].v[NUMi][TYi](
    immarg i32        ; opcode
    <[NUMi] x [TYi]>, ; input vector
    immarg i1,        ; is input unsigned
    immarg i32,       ; input interpretation
    %dx.types.Handle, ; matrix resource
    i32,              ; matrix offset
    immarg i32,       ; matrix interpretation
    immarg i32,       ; matrix M dimension    
    immarg i32,       ; matrix K dimension    
    immarg i32,       ; matrix layout
    immarg i1,        ; matrix transpose
    i32,              ; matrix stride
    %dx.types.Handle, ; bias vector resource
    i32,              ; bias vector offset
    immarg i32,       ; bias vector interpretation
    immarg i1)        ; is output unsigned
```

#### Overview

The `@dx.op.matvecmul` operation multiplies a **MxK** dimension matrix and a
**K** sized input vector. The matrix is loaded from memory while the vector is
stored in a variable.

The `@dx.op.matvecmuladd` operation behaves as `@dx.op.matvecmul`, but also adds
an **M**-sized bias vector (loaded from memory) to the result.

> Note that the dimensions of the matrix are **M**x**K** versus the **M**x**N**
> usually found in linear algebra textbooks. This is to futureproof for
> potential matrix-matrix operations in the future where the inputs could be
> **M**x**K** and **K**x**N** to produce an **M**x**N** result matrix.

#### Arguments

##### Input Vector

The **input vector** is of size `NUMi` and contains elements of physical type
`TYi`. The **input interpretation** describes how to interpret the contents of
the vector. `NUMi` has a relationship with **K** as follows:

* for non-packed interpretations: `NUMi` equals **K**,
* for packed interpretations: `NUMi` equals the smallest number that can hold
  **K** values of the packed type.

Non-packed interpretations are standard types such as float16, uint etc.  Packed
types are types such as **SignedInt8x4Packed** where each 32-bit element of the
vector corresponds to four 8-bit signed integers. See [Type Interpretations]
for details.

The **is input unsigned** is a boolean value; `false` indicates that the input
vector is a float or signed integer, `true` indicates that the input vector is
an unsigned integer.


##### Matrix

The matrix is loaded from a read-only raw-buffer, **matrix resource**,  starting
at **matrix offset**. The **matrix interpretation** argument specifies the
element type of the matrix (see [Type Interpretations]), no conversion is
performed.

The **matrix M dimension** and **matrix K dimension** arguments specify the
dimensions of the matrix. The **matrix layout** argument specifies the layout
of the matrix (see [Matrix Layouts]). If the **matrix transpose** is non-zero
then the matrix is transposed before performing the multiply (see
[Matrix Transpose]). For row-major and column-major layouts, **matrix
stride** specifies the number of bytes to go from one row/column to the next.
For optimal layouts, **matrix stride** must be zero. 

Only non-packed interpretations are valid for matrices.

The base address of **matrix resource** and **matrix offset** must be 128-byte
aligned. Also note that the size of the underlying allocation is guaranteed to
be a multiple of 16 bytes ensuring that the 16 bytes access of the last
row/column of the matrix is valid memory. 

The **matrix stride** is 16-byte aligned.

This operation doesn't perform bounds checking for matrix loads. If any part of
the matrix load is out of bounds then the entire matrix load will return zero.


##### Bias Vector

The bias vector is loaded from the read-only raw-buffer, **bias vector
resource**, starting at **bias vector offset**. The **bias vector
interpretation** argument specifies the element type of the bias vector (see
[Type Interpretations]), no conversion is performed.

Only non-packed interpretations are valid for bias vectors.

The base address of **bias vector resource** and **bias vector offset** must be
64-byte aligned.

This operation doesn't perform bounds checking for bias loads. If any part of
the vector load is out of bounds then the entire vector load will return zero.

#### Return Type

This operation returns a vector of size `NUMo` and contains elements of type
`TYo`. The result vector does not have an interpretation parameter, its type is
the declared type.

The **is output unsigned** is a boolean value; `false` indicates that the input
vector is a float or signed integer, `true` indicates that the input vector is
an unsigned integer.

#### Validation

* **input interpretation** must be a value corresponding to one of the following
  `ComponentType`s: `I16`, `U16`, `I32`, `U32`, `F16`, `F32`, `PackedS8x32`,
  `PackedU8x32`, `U8`, `I8`, `F8_E4M3`, `F8_E5M2`.
* **matrix interpretation** must be a value corresponding to one of the
  following `ComponentType`s: `I16`, `U16`, `I32`, `U32`, `F16`, `F32`, `U8`,
  `I8`, `F8_E4M3`, `F8_E5M2`, 
* **bias vector interpretation** must be a value corresponding to one of the
  following `ComponentType`s: `I16`, `U16`, `I32`, `U32`, `F16`, `F32`, `U8`,
  `I8`, `F8_E4M3`, `F8_E5M2`, 

### Vector-Vector Outer Product and Accumulate

#### Syntax

``` llvm
declare void @dx.op.outerproductaccumulate.v[M][TY].v[N][TY](
    immarg i32,       ; opcode 
    <[M] x [TY]>,     ; input vector 1
    <[N] x [TY]>,     ; input vector 2
    %dx.types.Handle, ; matrix resource
    i32,              ; matrix offset 
    immarg i32,       ; matrix interpretation 
    immarg i32,       ; matrix layout 
    i32)              ; matrix stride 
```

#### Overview

Computes the outer product between column vectors and an **M**x**N** matrix is
accumulated component-wise atomically (with device scope) in memory. 

``` 
ResultMatrix += InputVector1 * Transpose(InputVector2); 
```


#### Arguments

The two input vectors are specified via **input vector 1** and **input vector
2**.

The matrix is accumulated to the writeable raw-buffer specified by **matrix
resource**, with **matrix offset**, **matrix interpretation**, **matrix
layout**, and **matrix stride** behaving as described 
[above](#matrix-vector-multiply-and-multiply-add-operations). 

Note that **matrix layout** must be `DXILMatrixLayout::OuterProductOptimal` for
this operation. **matrix stride** must be 0 (for optimal layouts).

The base address of **matrix resource** and **matrix offset** must be 128-byte
aligned. Also note that the size of the underlying allocation is guaranteed to
be a multiple of 16 bytes ensuring that the 16 bytes access of the last
row/column of the matrix is valid memory. Implementations may write to the
contents of the padding between the end of the matrix and the 16-byte boundary,
so developers should not use this padding space for anything else.

If any part of the matrix write is out-of-bounds, the whole operation is
skipped.

Not all combinations of vector element type and matrix interpretations are
supported by all implementations. [CheckFeatureSupport] can be used to
determine which combinations are supported. A list of combinations that are
guaranteed to be supported on all implementations can be found in
[Minimum Support Set].

#### Validation

* **matrix interpretation** must be a value corresponding to one of the
  following `ComponentType`s: `I16`, `U16`, `I32`, `U32`, `F16`, `F32`, `U8`,
  `I8`, `F8_E4M3`, `F8_E5M2`, 

* **matrix layout** must be `DXILMatrixLayout::OuterProductOptimal`


### Vector Accumulate

#### Syntax

``` llvm
declare void @dx.op.vectoraccumulate.v[NUM][TY](
    immarg i32,       ; opcode
    <[NUM] x [TY]>,   ; input vector
    %dx.types.Handle, ; output array resource 
    i32)              ; output array offset
```

#### Overview

Accumulates the components of a vector component-wise atomically (with device
scope) to the corresponding elements of an array in memory. See note in
[Atomic Operations].

#### Arguments

The input vector is specified by **input vector**, and has `NUM` elements of
type `TY`.

The output array is accumulated to the writeable raw-buffer resource specified
by **output array resource** and **output array offset**.  The base address and
**output array offset** must be 64-byte aligned.  Also note that the size of the
underlying allocation is guaranteed to be a multiple of 16 bytes, ensuring that
there is valid memory between the end of the array and the 16-byte boundary.
Implementations may write to the contents of the padding between the end of the
matrix and the 16-byte boundary, so developers should not use this padding space
for anything else.

If any part of the vector write is out-of-bounds, the whole operation is
skipped.

[CheckFeatureSupport] can be used to determine which vector element types can be
accumulated. A list of types that are guaranteed to be supported on all devices
can be found in [Minimum Support Set].


[Type Interpretations]: #type-interpretations
[Matrix Layouts]: #matrix-layouts
[Matrix Transpose]: #matrix-transpose
[Minimum Support Set]: #minimum-support-set
[CheckFeatureSupport]: #check-feature-support
[Atomic Operations]: #atomic-operations
[Precision Requirements]: #precision-requirements


### Type Interpretations

The `ComponentType` enum in `DxilConstants.h` is extended as shown below, with
four new 8-bit types:

```c++
enum class ComponentType : uint32_t {
  Invalid = 0,
  I1,
  I16, // = 2
  U16, // = 3
  I32, // = 4
  U32, // = 5
  I64,
  U64,
  F16, // = 8
  F32, // = 9
  F64,
  SNormF16,
  UNormF16,
  SNormF32,
  UNormF32,
  SNormF64,
  UNormF64,
  PackedS8x32, // = 17
  PackedU8x32, // = 18

  // BEGIN NEW FOR SM 6.9
  U8,      // = 19
  I8,      // = 20
  F8_E4M3, // = 21  
  F8_E5M2, // = 22
  // END     

  LastEntry
};
```

#### From-Register Interpretations

Input vectors stored in registers (eg `vector<float, 16>`) are interpreted
according to the Conversion Rules shown below.

For these vectors there is a distinction between the physical type and the
logical type. The **input interpretation** argument for these vectors describes
how to convert from the physical to logical type. This allows elements to be
interpreted as types not natively supported by HLSL, e.g. uint8/sint8. For
packed interpretations, a single physical element can expand into multiple
logical elements.

Implementations are expected to support the interpretations listed in [Minimum
Support Set], but may also report additional supported interpretations via
[CheckFeatureSupport].

The following `ComponentType`s are valid for use as input interpretations:
* `I16`
* `U16`
* `I32`
* `U32`
* `F16`
* `F32`
* `PackedS8x32`
* `PackedU8x32`
* `U8`
* `I8`
* `F8_E4M3`
* `F8_E5M2`


#### Memory Interpretations

Matrices and Vectors that are stored in raw-buffers and specified by resource
handles (eg the matrix and bias-vector arguments to dx.op.matvecmul) are
interpreted according to the Conversion Rules shown below.

Implementations are expected to support the interpretations listed in [Minimum
Support Set], but may also report additional supported interpretations via
[CheckFeatureSupport].

The following `ComponentType`s are valid for use as interpretations for matrices
or vectors stored in memory: 
* `I16`
* `U16`
* `I32`
* `U32`
* `F16`
* `F32`
* `U8`
* `I8`
* `F8_E4M3`
* `F8_E5M2`.


#### CheckFeatureSupport

[CheckFeatureSupport] can be used to determine what combinations of **TYi**,
**input interpretation**, **matrix interpretation**, **matrix transpose**,
**bias vector interpretation** and **TYo** are supported on a particular
implementation. A list of combinations that are guaranteed to be supported on
all implementations can be found in [Minimum Support Set]. Note that there is
no guaranteed support for **matrix tranpose**, and so it must always be
queried.

#### Conversion Rules

Non-"Packed" type interpretations are used to request arithmetic conversions.
Input type must be a 32-bit or 16-bit scalar integer or a 32-bit or 16-bit
float. Integer to integer conversion saturates, float to float conversion is
implementation dependent and preserves the value as accurately as possible.
Float to integer conversion is RTNE and saturating. Integer to float conversion
is RTNE.

> TODO: These rules make sense for NN applications but diverge from HLSL
> conversion rules
> [here](https://microsoft.github.io/hlsl-specs/specs/hlsl.html#Conv).

"Packed" type conversions are bitcasts to a smaller type. The declared input type must be 32-bit unsigned integer. 

> /// XXX TODO: Error handling for illegal conversions. 

Examples:

Packed Case:
``` llvm
; Using PackedS8x32 input interpretation, each uint element (32-bit) in the 
; input vector will be interpreted as 4 int8 values.
;
; Note that TYi = i32 and NUMi = 8 (8 x 4 = 32 sint8 values ), and the result is a 
; 32-element vector.

%inputVector = <8 x i32> ...

%result = <32 x i32> call @dx.op.matvecmul.v[32][i32].v[8][i32](
     OPCODE,
     %inputVector,
     16,              ; input interpretation - ComponentType::PackedS8x32
     false,           ; is input unsigned = false = signed
     %matrixResource,
     0,               ; matrix offset
     19,              ; matrix interpretation - ComponentType::I8
     32,              ; matrix M dimension
     32,              ; matrix K dimension
     2,               ; matrix layout - MulOptimal
     0,               ; matrix transpose - false
     0,               ; matrix stride
     0);              ; is output unsigned = false = signed
```

Non-Packed Case:
``` llvm
; Using I8 input interpretation, each float element will be arithmetically
; converted to a sint8 value.

%inputVector = <32 x float> ...

%result = <64 x i32> call @dx.op.matvecmul.v[64][i32].v[32][float](
    OPCODE,
    %inputVector,
    19,              ; input interpretation - ComponentType::I8
    0,               ; is input unsigned = false = signed
    %matrixResource,
    0,               ; matrix offset
    5,               ; matrix interpretation - ComponentType::I8
    64,              ; matrix M dimension
    32,              ; matrix K dimension
    2,               ; matrix layout - MulOptimal
    0,               ; matrix transpose - false
    0,               ; matrix stride
    0)               ; is output unsigned = false = signed
```

#### Precision Requirements

The precision for intermediate operations is implementation dependent.

### Matrix Layouts

The **matrix layout** argument specifies a value from the following enum:

```c++
enum class DXILMatrixLayout : uint {
  RowMajor              = 0,
  ColumnMajor           = 1,
  MulOptimal            = 2,
  OuterProductOptimal   = 3,
};
```

Optimal layouts are opaque implementation specific layouts, the D3D call
`ConvertLinearAlgebraMatrix` can be used to convert the *Matrix* to an optimal
layout. Row-Major and Column-Major layouts are also supported. **matrix
stride** must be zero for optimal layouts.

 
### Matrix Transpose

The **matrix transpose** parameter indicates if the matrix is transposed before
performing the multiply. In linear algebra, the
[transpose](https://en.wikipedia.org/wiki/Transpose) of a matrix is an operator
which flips a matrix over its diagonal; that is, it switches the row and column
indices of the matrix. 

Transposing is not supported for the RowMajor/ColumnMajor layouts. 

Not all component types support transposing. It is left to implementations to
define which types support matrix transposing. "TransposeSupported" flag from
the [CheckFeatureSupport](#check-feature-support) struct is used to determine
if a matrix transpose is supported. Note that even for the type/interpretation
combinations described in [Minimum Support Set], transpose support isn't
guaranteed and needs to be checked explicitly.

### Atomic Operations

Internally these may done component-wise or multiple components may be
accumulated in a single atomic, this is implementation dependent. In other
words, some implementations may use scalar atomics while others may use vector
atomics of an arbitrary size. Also, implementations may serialize per-component
atomic adds accross threads arbitrarily.

### Non-Uniform control flow

There are no requirements for fully occupied waves or uniform control flow while
using these intrinsics, this is to ensure wide usability across all shader
stages (compute, ray-tracing, pixel shader etc). It is possible that
implementations can enable fast paths by allowing vectors to cooperate behind
the scenes in cases with uniform paths, fully occupied waves and uniform values
for Matrix, Matrix Offset, Matrix Interpretation, Matrix Layout, Matrix Stride,
Matrix Transpose and Bias, Bias Offset, Bias Interpretation, but this is not a
requirement for functionality.

### Shader Stages

The vector-matrix intrinsics are expected to be supported in all shader stages.

### Diagnostic Changes

* Diagnostics for incorrect use of the new intrinsics.


### Validation Changes


#### D3D12 API Additions

### Check Feature Support

This feature requires calling CheckFeatureSupport(). Additional D3D12_FEATURE
enum and corresponding D3D12_FEATURE_DATA* structs (listed below) are added to
enable discovering the Cooperative Vector Tier along with the datatype and
interpretation combinations supported by new vector-matrix intrinsics.

```c++
typedef enum D3D12_FEATURE {
    ...
    // Contains Cooperative Vector tier.
    D3D12_FEATURE_D3D12_OPTIONS_EXPERIMENTAL;
    D3D12_FEATURE_COOPERATIVE_VECTOR;
};

// This is designed to match the ComponentType enum values but omits data 
// types that are not currently specified to work with this API. The names are chosen
// to more closely match those used by HLSL developers, as opposed to the ComponentType 
// names that align with LLVM IR.

typedef enum D3D12_LINEAR_ALGEBRA_DATATYPE {
  D3D12_LINEAR_ALGEBRA_DATATYPE_SINT16          =  2, // ComponentType::I16
  D3D12_LINEAR_ALGEBRA_DATATYPE_UINT16          =  3, // ComponentType::U16
  D3D12_LINEAR_ALGEBRA_DATATYPE_SINT32          =  4, // ComponentType::I32
  D3D12_LINEAR_ALGEBRA_DATATYPE_UINT32          =  5, // ComponentType::U32
  D3D12_LINEAR_ALGEBRA_DATATYPE_FLOAT16         =  8, // ComponentType::F16
  D3D12_LINEAR_ALGEBRA_DATATYPE_FLOAT32         =  9, // ComponentType::F32
  D3D12_LINEAR_ALGEBRA_DATATYPE_SINT8_T4_PACKED = 17, // ComponentType::PackedS8x32
  D3D12_LINEAR_ALGEBRA_DATATYPE_UINT8_T4_PACKED = 18, // ComponentType::PackedU8x32
  D3D12_LINEAR_ALGEBRA_DATATYPE_UINT8           = 19, // ComponentType::U8
  D3D12_LINEAR_ALGEBRA_DATATYPE_SINT8           = 20, // ComponentType::I8
  D3D12_LINEAR_ALGEBRA_DATATYPE_E4M3            = 21, // ComponentType::F8_E4M3 (1 sign, 4 exp, 3 mantissa bits)
  D3D12_LINEAR_ALGEBRA_DATATYPE_E5M2            = 22, // ComponentType::F8_E5M2 (1 sign, 5 exp, 2 mantissa bits)
};

typedef enum D3D12_COOPERATIVE_VECTOR_TIER
{
    D3D12_COOPERATIVE_VECTOR_TIER_NOT_SUPPORTED,    
    D3D12_COOPERATIVE_VECTOR_TIER_1_0,
    D3D12_COOPERATIVE_VECTOR_TIER_1_1
}

// This struct may be augmented with more capability bits
// as the feature develops
typedef struct D3D12_FEATURE_DATA_D3D12_OPTIONS_EXPERIMENTAL
{
    Out D3D12_COOPERATIVE_VECTOR_TIER CooperativeVectorTier;
} D3D12_FEATURE_DATA_D3D12_OPTIONS_EXPERIMENTAL;

// Used for MatrixVectorMulAdd intrinsic
typedef struct D3D12_COOPERATIVE_VECTOR_PROPERTIES_MUL
{
    D3D12_LINEAR_ALGEBRA_DATATYPE InputType;
    D3D12_LINEAR_ALGEBRA_DATATYPE InputInterpretation;
    D3D12_LINEAR_ALGEBRA_DATATYPE MatrixInterpretation;
    D3D12_LINEAR_ALGEBRA_DATATYPE BiasInterpretation;
    D3D12_LINEAR_ALGEBRA_DATATYPE OutputType;
    BOOL                          TransposeSupported;
};

// Used for OuterProductAccumulate and VectorAccumulate intrinsics
typedef struct D3D12_COOPERATIVE_VECTOR_PROPERTIES_ACCUMULATE
{
    D3D12_LINEAR_ALGEBRA_DATATYPE InputType;  
    D3D12_LINEAR_ALGEBRA_DATATYPE AccumulationType;
};

// CheckFeatureSupport data struct used with type D3D12_FEATURE_COOPERATIVE_VECTOR:
typedef struct D3D12_FEATURE_DATA_COOPERATIVE_VECTOR
{    
    InOut UINT                                          MatrixVectorMulAddPropCount;
    Out D3D12_COOPERATIVE_VECTOR_PROPERTIES_MUL*        pMatrixVectorMulAddProperties;
    InOut UINT                                          OuterProductAccumulatePropCount;
    Out D3D12_COOPERATIVE_VECTOR_PROPERTIES_ACCUMULATE* pOuterProductAccumulateProperties;
    InOut UINT                                          VectorAccumulatePropCount;
    Out D3D12_COOPERATIVE_VECTOR_PROPERTIES_ACCUMULATE* pVectorAccumulateProperties;
};

```

Support for the Cooperative Vector feature is queried through
`CooperativeVectorTier`. User can also query properties supported for each
intrinsic in `D3D12_FEATURE_DATA_COOPERATIVE_VECTOR`. If pProperties is NULL
for any intrinsic, the count of available properties will be returned in
PropCount. Otherwise, PropCount must represent the size of the pProperties
array, which will be updated with the number of structures written to
pProperties upon return. If pProperties is non-NULL for any intrinsic but its
PropCount is less than the number of properties available for that intrinsic,
the operation fails and `E_INVALIDARG` is returned.

>Note about emulation: For example E4M3 and E5M2 might not be supported natively
 on certain implementations, but since these are in the minimum support set,
 they need to be emulated, possibly using FP16. Emulation versus native support
 is an implementation detail specific to implementations and outside the scope
 of this specification document.

#### Support Tiers

**D3D12_COOPERATIVE_VECTOR_TIER_1_0**: Device supports *MatrixVectorMul*
  and *MatrixVectorMulAdd* intrinsics. `OuterProductAccumulatePropCount` and
  `VectorAccumulatePropCount` are 0 in this case.

**D3D12_COOPERATIVE_VECTOR_TIER_1_1**: Device supports previous
  tiers, *OuterProductAccumulate* and *VectorAccumulate* functions.

#### Minimum Support Set

Minimum set of properties that implementations are required to support for each
intrinsic are listed below.

##### For Matrix-Vector Multiply and Multiply-Add

Note that value of `TransposeSupported` is never guaranteed and needs to be
explicitly checked for the combinations below.


| InputType   | InputInterpretation | MatrixInterpretation | BiasInterpretation | OutputType |
|-------------|---------------------|----------------------|--------------------|------------|
| F16         | F16                 | F16                  | F16                | F16        |
| F16         | F8_E4M3             | F8_E4M3              | F16                | F16        |
| F16         | F8_E5M2             | F8_E5M2              | F16                | F16        |
| PackedS8x32 | PackedS8x32         | I8                   | I32                | I32        |
| U32         | PackedS8x32         | I8                   | I32                | I32        |
| F32         | I8                  | I8                   | I32                | I32        |

>Note: Only Optimal layouts can be used with for Float8(E4M3 and E5M2)
 `MatrixInterpretation`.

##### For OuterProductAccumulate

| InputType | AccumulationType |
|-----------|------------------|
| FP16      | FP16             |
| FP16      | FP32             |

##### For VectorAccumulate

| InputType | AccumulationType |
|-----------|------------------|
| FP16      | FP16             |


#### Usage Example

```c++
// Check for matrix vector support and query properties for MatrixVectorMulAdd
D3D12_FEATURE_DATA_D3D12_OPTIONS_EXPERIMENTAL TierSupport = {};

d3d12Device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONS_EXPERIMENTAL, &TierSupport, 
                                 sizeof(D3D12_FEATURE_DATA_D3D12_OPTIONS_EXPERIMENTAL));

if (TierSupport.CooperativeVectorTier >= D3D12_COOPERATIVE_VECTOR_TIER_1_0) {
    // PropCounts to be filled by driver implementation
    D3D12_FEATURE_DATA_COOPERATIVE_VECTOR CoopVecProperties = {0, NULL, 0, NULL, 0, NULL};

    // CheckFeatureSupport returns the number of input combinations for intrinsics
    d3d12Device->CheckFeatureSupport(D3D12_FEATURE_COOPERATIVE_VECTOR, &CoopVecProperties, 
                                     sizeof(D3D12_FEATURE_DATA_COOPERATIVE_VECTOR));

    // Use MatrixVectorMulAddPropCount returned from the above

    // Use CheckFeatureSupport call to query only MatrixVectorMulAddProperties
    UINT MatrixVectorMulAddPropCount = CoopVecProperties.MatrixVectorMulAddPropCount;
    std::vector<D3D12_COOPERATIVE_VECTOR_PROPERTIES_MUL> properties(MatrixVectorMulAddPropCount);
    CoopVecProperties.pMatrixVectorMulAddProperties = properties.data();

    // CheckFeatureSupport returns the supported input combinations for the mul intrinsics
    d3d12Device->CheckFeatureSupport(D3D12_FEATURE_COOPERATIVE_VECTOR, &CoopVecProperties, 
                                    sizeof(D3D12_FEATURE_DATA_COOPERATIVE_VECTOR));
                                                                
    // Use MatrixVectorMulAdd shader with datatype and interpretation
    // combination matching one of those returned.
    
} else {
    // Don't use Cooperative Vector ops
}
```

### Convert Matrix to desired layout and type

The weight and bias matrices used in the Linear Algebra intrinsics are
(RW)ByteAddressBuffers with implementation specific alignment constraints and
performance characteristics. We introduce a driver side API to change the
layout and dataype of the weight matrix from and to any of the layouts in
`D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT` and datatypes in
`D3D12_LINEAR_ALGEBRA_DATATYPE`.

```c++
enum D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT {
    D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_ROW_MAJOR,
    D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_COLUMN_MAJOR,
    D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_MUL_OPTIMAL,
    D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL
}
```

#### Query Destination Size

The destination buffer (to hold the matrix) size can be implementation
dependent. The API `GetLinearAlgebraMatrixConversionDestinationInfo` is
added to query the size of the destination buffer in the desired layout and
datatype. It takes a pointer to
`D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DEST_INFO` descriptor that provides
the inputs required to calculate the necessary size. The same descriptor,
updated with the calculated output size, is then passed to the conversion
API. 

The `DestSize` and `DestStride` must be a multiple of 16 bytes. The `DestVA`
must be 128-byte aligned.

```c++

// Descriptor to query the destination buffer size
typedef struct D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DEST_INFO { 
    UINT                                   DestSize;      // !< [out]Destination buffer size in bytes
                                                          // required for conversion 
    D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT     DestLayout;    // !< [in] Is the layout the matrix is converted to
    UINT                                   DestStride;    // !< [in] Is the number of bytes between a consecutive 
                                                          // row or column (depending on DestLayout) of the 
                                                          // destination matrix if it is row-major or 
                                                          // column-major.
    UINT                                   NumRows;       // !< [in] Is the number of rows in the matrix. 
    UINT                                   NumColumns;    // !< [in] Is the number of columns in the matrix. 
    D3D12_LINEAR_ALGEBRA_DATATYPE          DestDataType;  // !< [in] the type of a destination matrix element. 
};

// An API to return the number of bytes required in the destination buffer to
// store the result of conversion The size of the destination is a function of
// the destination layout information and does not depend on the source layout
// information.

void ID3D12DevicePreview::GetLinearAlgebraMatrixConversionDestinationInfo(
    D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DEST_INFO* pDesc);

```

#### Conversion descriptors

After the size of the destination buffer is known, user can pass the
`D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DEST_INFO` descriptor along with
information of source layout and datatype in
`D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_SOURCE_INFO` and addresses of the
source and destination buffers to the layout and datatype conversion API.

```c++

// GPU VAs of source and destination buffers

typedef struct D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DATA {
    D3D12_GPU_VIRTUAL_ADDRESS               DestVA;               //!< [inout] GPU VA of destination 
                                                                  // buffer
    D3D12_GPU_VIRTUAL_ADDRESS               SrcVA;                //!< [in]    GPU VA of source 
                                                                  // buffer
};
 
// Source information descriptor. Destination information comes from 
// D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DEST_INFO

typedef struct D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_SRC_INFO {
    UINT                                    SrcSize;                // !< [in] Is the length in bytes of 
                                                                    // srcData    
    D3D12_LINEAR_ALGEBRA_DATATYPE           SrcDataType;            // !< [in] Is the type of a 
                                                                    // source matrix 
                                                                    // element        
    D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT      SrcLayout;              // !< [in] Is the layout of the 
                                                                    // source matrix.
    UINT                                    SrcStride;              // !< [in] Is the number of bytes  
                                                                    // between a consecutive row or column 
                                                                    // (depending on srcLayout) 
                                                                    // of the source matrix, if it is row-major 
                                                                    // or column-major.   
};

// Descriptor passed to the conversion API
typedef struct D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_INFO {
    D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DEST_INFO      DestInfo;
    D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_SRC_INFO       SrcInfo;    
    D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_DATA           DataDesc;   
};
```

#### Conversion APIs

New API is added to the ID3D12CommandList interface. Multiple conversions can be
done in a single call of the API. The number of descriptors pointed to by pDesc
is specified using DescCount. If DestSize passed to this API is less than the
number of bytes returned in call to
`GetLinearAlgebraMatrixConversionDestinationInfo`, behavior is undefined.

```c++
// Converts source matrix to desired layout and datatype
void ID3D12GraphicsCommandListPreview::ConvertLinearAlgebraMatrix(
    D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_INFO* pDesc,
    UINT DescCount);

```

*Valid Usage:* 

* If SrcLayout is row-major or column-major, then SrcStride should be greater than the length of a row/column, and a
  multiple of the element size.
* If DestLayout is row-major or column-major, then DestStride should be greater than the length of a row/column, and a
  multiple of 16.
* If SrcComponentType is not a supported MatrixInterpretation value as reported by CheckFeatureSupport() then
  SrcComponentType should be `D3D12_LINEAR_ALGEBRA_DATATYPE_FLOAT32`.
* If DestComponentType is not a supported MatrixInterpretation value as reported by CheckFeatureSupport() then
  DestComponentType should be `D3D12_LINEAR_ALGEBRA_DATATYPE_FLOAT32`.
* If SrcComponentType and DestComponentType are not equal, then one should be `D3D12_LINEAR_ALGEBRA_DATATYPE_FLOAT32`  or `D3D12_LINEAR_ALGEBRA_DATATYPE_FLOAT16` and the other should be a lower-precision floating-point type. 
* If DestComponentType is `D3D12_LINEAR_ALGEBRA_DATATYPE_E4M3` or `D3D12_LINEAR_ALGEBRA_DATATYPE_E5M2`, then DestLayout should be `D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_MUL_OPTIMAL` or `D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_OUTER_PRODUCT_OPTIMAL`.

*CommandList interactions:*

- Synchronization around `ConvertLinearAlgebraMatrix` calls:
   - Legacy Barrier
     - Source buffer: Must be in `D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE` state
     - Dest buffer: Must be in `D3D12_RESOURCE_STATE_UNORDERED_ACCESS` state
     - UAV barrier synchronizes writes to the destination
   - Enhanced Barrier:
     - Source buffer access: `D3D12_BARRIER_ACCESS_SHADER_RESOURCE`
     - Dest buffer access: `D3D12_BARRIER_ACCESS_UNORDERED_ACCESS`
     - Sync point: `D3D12_BARRIER_SYNC_CONVERT_LINEAR_ALGEBRA_MATRIX`
 - Predication is supported
 - Available in Compute or Graphics CommandLists
 - Not supported in Bundles

*Usage Example:*

```c++

D3D12_LINEAR_ALGEBRA_MATRIX_CONVERSION_INFO infoDesc = 
{ 
    // DestInfo
    {
        0,                                                              // DestSize to be populated by 
                                                                        // driver implementation
        D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_MUL_OPTIMAL,                 // convert to mul optimal layout
        0,                                                              // stride is ignored since optimal layout 
                                                                        // is implementation dependent
        numRows,                                                        // number of rows in weight matrix to be 
                                                                        // converted
        numColumns,                                                     // number of columns in weight matrix to 
                                                                        // be converted
        D3D12_LINEAR_ALGEBRA_DATATYPE_E4M3                              // convert to FP8 datatype
    },

    //SrcInfo
    {
        srcSize,                                                        // number of bytes of matrix in source 
                                                                        // layout and datatype
        D3D12_LINEAR_ALGEBRA_DATATYPE_FLOAT32,                          // convert from float
        D3D12_LINEAR_ALGEBRA_MATRIX_LAYOUT_ROW_MAJOR,                   // convert from row major layout
        (numColumns * sizeof(float))                                    // row major stride without padding
    },

    //DataDesc
    {
        0,                                                              // dest buffer address not known yet. 
                                                                        // Will be intialized after destSize 
                                                                        // query
        srcVA                                                           // GPU VA of src buffer
    }                                              
}

// Query destSize
pD3D12Device->GetLinearAlgebraMatrixConversionDestinationInfo(&infoDesc.DestInfo);

// After the size is known, initialize the DestVA. Offset the SrcVA with DestSize to get DestVA 
// (alignment requirements are ignored for simplicity)
infoDesc.DataDesc.DestVA = srcVA + infoDesc.DestInfo.DestSize;

// Perform the conversion
pD3D12CommandList->ConvertLinearAlgebraMatrix(&infoDesc, 0);

```
### D3D12 DDI Additions

The DDIs for this feature are straightforward API mappings and have therefore
been excluded from this document.

## Testing

* How will validation of new DXIL elements be tested?
* A: *unit tests in dxc*
* How will the execution results be tested?
* A: *HLK tests*


## Alternatives considered

Our original proposal introduced an opaque Cooperative Vector type to HLSL to
limit the scope of the feature to small neural network evaluation and also
contain the scope for testing. But aligning with the long term roadmap of HLSL
to enable generic vectors, it makes sense to not introduce a new datatype but
use HLSL vectors.

Various combinations of enums for specifying interpretations were considered
with varying trade-offs of complexity versus typesafety and simplicity, before
deciding to extend the existing `ComponentType` enum.

## Acknowledgments

We would like to thank Jeff Bolz, Yury Uralsky, Patrick Neill, Tex Riddell and
Amar Patel for their contributions to this specification.


