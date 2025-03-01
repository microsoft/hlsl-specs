<!-- {% raw %} -->

* Proposal: [0029](0029-cooperative-vector.md)
* Author(s): [Anupama Chandrasekhar][anupamachandra], [Damyan Pepper][damyanp],
             [Shashank Wadhwa][shashankw]
* Sponsor: [Damyan Pepper][damyanp], [Greg Roth][pow2clk]
* Status: **Under Review**
* Planned Version: Shader Model 6.9


[anupamachandra]: https://github.com/anupamachandra
[damyanp]: https://github.com/damyanp
[pow2clk]: https://github.com/pow2clk
[shashankw]: https://github.com/shashankw

# Cooperative Vectors

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
proposal \[TBD\].

[0026]: 0026-hlsl-long-vector-type.md
[0030]: 0030-dxil-vectors.md

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

Below shader is in HLSL-like psuedocode, to highlight the idea of what replacing physical computations with a neural network based evaluation looks like. The exact syntax for the new intrinsics is intentionally skipped to keep it simple, later sections contain examples with the correct syntax and sample descriptors.

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
    // the Matrix and Bias are trained offline and loaded to memory

    // layer0 = inputVector*inputMatrix + biasVector0
    // The matrix and bias are loaded from memory at offsets : moffset0 and boffset0
    vector<uint32_t, K> layer0 = MatrixVectorMulAdd(inputVector, inputMatrix0, moffset0, biasVector0, boffset0);
    layer0 = max(layer0,0); // Apply activation function

    // layer0 = inputVector*inputMatrix0 + biasVector0
    // The matrix and bias are loaded from memory at offsets : moffset1 and boffset1
    vector<uint32_t, K> layer1 = MatrixVectorMulAdd(layer0, inputMatrix0, moffset1, biasVector0, boffset1);
    layer1 = max(layer1,0); // Apply activation function

    // output = layer1*inputMatrix1 + biasVector1 
    vector<uint32_t, N> output = MatrixVectorMulAdd(layer1, inputMatrix1, biasVector1);

    output = exp(output); 
    
    color.r = output[0] * args.lightcolor; 
    color.g = output[1] * args.lightcolor; 
    color.b = output[2] * args.lightcolor; 
}

```


## Proposed solution

Introduce new DXIL operations to accelarate matrix-vector operations. In this
specification we add four operations:

* **Matrix-Vector Multiply:** Multiply a matrix in memory and a vector
    parameter.
* **Matrix-Vector Multiply-Add:** Multiply a matrix in memory and a vector
    parameter and add a vector from memory.
* **Vector-Vector Outer Product and Accumulate:** Compute the outerproduct of
    two vectors and accumulate the result matrix atomically-elementwise in
    memory.
* **Reduce and Accumulate:** Accumulate elements of a vector
    atomically-elementwise to corresponding elements in memory.


## Detailed design

### Matrix-Vector Multiply and Multiply-Add Operations

#### Opcodes

Different opcode values are used to differentiate between float, signed integer
and unsigned integer (in much the same way as `FMax`, `IMax` and `UMax` do.)

> The exact numeric values are TBD.  Here the values are shown as "offset from
> the first opcode value."

| Opcode | Name          | Description                                                           |
|--------|---------------|-----------------------------------------------------------------------|
| 0      | FMatVecMul    | Matrix-Vector multiply that returns a vector of floats                |
| 1      | FMatVecMulAdd | Matrix-Vector multiply-add that returns a vector of floats            |
| 2      | IMatVecMul    | Matrix-Vector multiply that returns a vector of signed integers       |
| 3      | IMatVecMulAdd | Matrix-Vector multiply-add that returns a vector of signed integers   |
| 4      | UMatVecMul    | Matrix-Vector multiply that returns a vector of unsigned integers     |
| 5      | UMatVecMulAdd | Matrix-Vector multiply-add that returns a vector of unsigned integers |


#### Syntax
 
``` llvm 
declare <[NUMo] x [TYo]> @dx.op.matvecmul.v[NUMo][TYo].v[NUMi][TYi](
    immarg i32        ; opcode
    <[NUMi] x [TYi]>, ; input vector
    immarg i32,       ; input interpretation
    %dx.types.Handle, ; matrix resource
    i32,              ; matrix offset
    immarg i32,       ; matrix interpretation
    immarg i32,       ; matrix M dimension    
    immarg i32,       ; matrix K dimension    
    immarg i32,       ; matrix layout
    immarg i1,        ; matrix transpose
    i32)              ; matrix stride

declare <[NUMo] x [TYo]> @dx.op.matvecmuladd.v[NUMo][TYo].v[NUMi][TYi](
    immarg i32        ; opcode
    <[NUMi] x [TYi]>, ; input vector
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
    immarg i32)       ; bias vector interpretation
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


##### Matrix

The matrix is loaded from a raw-buffer, **matrix resource**,  starting at
**matrix offset**. The **matrix interpretation** argument specifies the element
type of the matrix (see [Type Interpretations]), no conversion is performed.
The **matrix M dimension** and **matrix K dimension** arguments specify the
dimensions of the matrix. The**matrix layout** argument specifies the layout
of the matrix (see [Matrix Layouts]). If the **matrix transpose** is non-zero
then the matrix is transposed before performing the multiply (see
[Matrix Transpose]). For row-major and column-major layouts, **matrix
stride** specifies the number of bytes to go from one row/column to the next.
For optimal layouts, **matrix stride** is ignored. 

Only non-packed interpretations are valid for matrices.

The base address of **matrix resource** and **matrix offset** must be 64 byte
aligned.

The **matrix stride** is 16 byte aligned.

This operation doesn't perform bounds checking for matrix loads. If any part of
the matrix load is out of bounds then the entire operation is undefined.


##### Bias Vector

The bias vector is loaded from the raw-buffer, **bias vector resource**,
starting at **bias vector offset**. The **bias vector interpretation** argument
specifies the element type of the bias vector (see [Type Interpretations]), no
conversion is performed.

Only non-packed interpretations are valid for bias vectors.

The base address of **bias vector resource** and **bias vector offset** must be
64 byte aligned.

This operation doesn't perform bounds checking for bias loads. If any part of
the vector load is out of bounds then the entire operation is undefined.

#### Return Type

This operation returns a vector of size `NUMo` and contains elements of type
`TYo`. The result vector does not have an interpretation parameter, its type is
the declared type.


### Vector Outer Product

#### Syntax

``` llvm
declare void @dx.op.vecouterproductacc.v[M][TY].v[N][TY](
    immarg i32,       ; opcode 
    <[M] x [TY]>,     ; input vector 1
    <[N] x [TY]>,     ; input vector 2
    %dx.types.Handle, ; matrix resource
    i32,              ; matrix offset 
    i32,              ; matrix stride 
    immarg i32,       ; matrix interpretation 
    immarg i32)       ; matrix layout 
```

#### Overview

Computes the outer product between column vectors and an **M**x**N** matrix is
accumulated component-wise atomically (with device scope) in memory. 

``` 
ResultMatrix = InputVector1 * Transpose(InputVector2); 
```


#### Arguments

The two input vectors are specified via **input vector 1** and **input vector
2**.

The matrix is accumulated to the writeable raw-buffer specified by **matrix
resource**, with **matrix offset**, **matrix stride**, **matrix
interpretation** and **matrix layout** behaving as described [above]
(#matrix-vector-multiply-and-multiply-add-operations).

The base address of **matrix resource** and **matrix offset** must be 64 byte
aligned.

The **matrix stride** is 16 byte aligned.

Not all combinations of vector element type and matrix interpretations are
supported by all implementations. [CheckFeatureSupport] can be used to
determine which combinations are supported. A list of combinations that are
guaranteed to be supported on all implementations can be found in
[Minimum Support Set].


### Reduce Sum Accumulate

#### Syntax

``` llvm
declare void @dx.op.vecreducesumacc.v[NUM][TY](
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
by **output array resource** and **output array offset**.  The base address
and **output array offset** must be 64 byte aligned.

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

The various "interpretation" arguments specify a value from the following enum:

```c++
enum class DXILTypeInterpretation :uint {
  Float16               = 0,
  Float32               = 1,
  UnsignedInt8          = 2,
  UnsignedInt16         = 3,
  UnsignedInt32         = 4,
  SignedInt8            = 5,
  SignedInt16           = 6,
  SignedInt32           = 7,
  SignedInt8x4Packed    = 8,
  UnsignedInt8x4Packed  = 9,
  FloatE4M3             = 10,
  FloatE5M2             = 11,
  Unsupported           = 32
};
```

For matrices and vectors that are specified by resource handles and stored in
raw-buffers, the interpretation value directly specifies the element type.  It
is invalid to specify a packed interpretation in these cases.

For input vectors that come from variables there is a distinction between the
physical type and the logical type. The **input interpretation** argument for
these vectors describes how to convert from the physical to logical type. This
allows elements to be interpreted as types not natively supported by HLSL, e.g.
uint8/sint8. For packed interpretations, a single physical element can expand
into multiple logical elements.

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
; Using SignedInt8x4Packed input interpretation, each uint element (32-bit) in the 
; input vector will be interpreted as 4 int8 values.
;
; Note that TYi = i32 and NUMi = 8 (8 x 4 = 32 sint8 values ), and the result is a 
; 32-element vector.

%inputVector = <8 x i32> ...

%result = <32 x i32> call @dx.op.matvecmul.v[32][i32].v[8][i32](
     OPCODE,
     %inputVector,
     8,               ; input interpretation - SignedInt8x4Packed
     %matrixResource,
     0,               ; matrix offset
     5,               ; matrix interpretation - SignedInt8
     32,              ; matrix M dimension
     32,              ; matrix K dimension
     2,               ; matrix layout - InferencingOptimal
     0,               ; matrix transpose - false
     0)               ; matrix stride
```

Non-Packed Case:
``` llvm
; Using SignedInt8 input interpretation, each float element will be arithmetically
; converted to a sint8 value.

%inputVector = <32 x float> ...

%result = <64 x i32> call @dx.op.matvecmul.v[64][i32].v[32][float](
    OPCODE,
    %inputVector,
    5,               ; input interpretation - SignedInt8
    %matrixResource,
    0,               ; matrix offset
    5,               ; matrix interpretation - SignedInt8
    64,              ; matrix M dimension
    32,              ; matrix K dimension
    2,               ; matrix layout - InferencingOptimal
    0,               ; matrix transpose - false
    0)               ; matrix stride
```

#### Precision Requirements

The precision for intermediate operations is implementation dependent.

### Matrix Layouts

The **matrix layout** argument specifies a value from the following enum:

```c++
enum class DXILMatrixLayout : uint {
  RowMajor              = 0,
  ColumnMajor           = 1,
  InferencingOptimal    = 2,
  TrainingOptimal       = 3,
};
```

Optimal layouts are opaque implementation specific layouts, the D3D call
`CooperativeVectorConvertMatrix` can be used to convert the *Matrix* to an
optimal layout. Row-Major and Column-Major layouts are also supported.

 
### Matrix Transpose

The **matrix transpose** parameter indicates if the matrix is transposed before
performing the multiply. In linear algebra, the[transpose]
(https://en.wikipedia.org/wiki/Transpose) of a matrix is an operator which
flips a matrix over its diagonal; that is, it switches the row and column
indices of the matrix. 

Transposing is not supported for the RowMajor/ColumnMajor layouts. 

Not all component types support transposing. It is left to implementations to
define which types support matrix transposing. "TransposeSupported" flag from
the [CheckFeatureSupport] (#check-feature-support) struct is used to determine
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

Note: The enums and structs need to be updated from the coop_vec name, once a
new name for the feature is decided.

### Check Feature Support

This feature requires calling CheckFeatureSupport(). Additional D3D12_FEATURE
enum and corresponding D3D12_FEATURE_DATA* structs (listed below) are added to
enable discovering the Cooperative Vector tier along with the datatype and
interpretation combinations supported by new vector-matrix intrinsics.

```
typedef enum D3D12_FEATURE {
    ...
    // Contains cooperative vector tier.
    // NN tbd when implemented
    D3D12_FEATURE_D3D12_OPTIONSNN;
    D3D12_FEATURE_COOPERATIVE_VECTOR;
};

typedef enum D3D12_COOPERATIVE_VECTOR_DATATYPE {
    D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT16      = 0,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT32      = 1,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_UINT8        = 2,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_UINT16       = 3,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_UINT32       = 4,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_SINT8        = 5,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_SINT16       = 6,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_SINT32       = 7,    
    D3D12_COOPERATIVE_VECTOR_DATATYPE_SINT8_PACKED = 8,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_UINT8_PACKED = 9,
    D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT_E4M3   = 10,      // FP8: 1 sign bit, 4 exp bits, 3 mantissa bits
    D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT_E5M2   = 11       // FP8: 1 sign bit, 5 exp bits, 2 mantissa bits
};

typedef enum D3D12_COOPERATIVE_VECTOR_TIER
{
    D3D12_COOPERATIVE_VECTOR_TIER_NOT_SUPPORTED,    
    D3D12_COOPERATIVE_VECTOR_TIER_1_0
}

// This struct may be augmented with more capability bits
// as the feature develops
typedef struct D3D12_FEATURE_DATA_D3D12_OPTIONSNN // NN tbd when implemented
{
    Out D3D12_COOPERATIVE_VECTOR_TIER CooperativeVectorTier;
} D3D12_FEATURE_DATA_D3D12_OPTIONSNN;

// Used for VectorMatrixMulAdd intinsic
typedef struct D3D12_COOPERATIVE_VECTOR_PROPERTIES_INFERENCE
{
    D3D12_COOPERATIVE_VECTOR_DATATYPE InputType;
    D3D12_COOPERATIVE_VECTOR_DATATYPE InputInterpretation;
    D3D12_COOPERATIVE_VECTOR_DATATYPE MatrixInterpretation;
    D3D12_COOPERATIVE_VECTOR_DATATYPE BiasInterpretation;
    D3D12_COOPERATIVE_VECTOR_DATATYPE OutputType;
    BOOL                              TransposeSupported;
};

// Used for OuterProductAccumulate and ReduceSumAccumulate intrinsics
typedef struct D3D12_COOPERATIVE_VECTOR_PROPERTIES_TRAINING
{
    D3D12_COOPERATIVE_VECTOR_DATATYPE InputType;  
    D3D12_COOPERATIVE_VECTOR_DATATYPE AccumulationType;
};

typedef struct D3D12_FEATURE_DATA_COOPERATIVE_VECTOR
{    
    InOut UINT                                         VectorMatrixMulAddPropCount;
    Out D3D12_COOPERATIVE_VECTOR_PROPERTIES_INFERENCE* pVectorMatrixMulAddProperties;
    InOut UINT                                         OuterProductAccPropCount;
    Out D3D12_COOPERATIVE_VECTOR_PROPERTIES_TRAINING*  pOuterProductAccProperties;
    InOut UINT                                         ReduceSumAccPropCount;
    Out D3D12_COOPERATIVE_VECTOR_PROPERTIES_TRAINING*  pReduceSumAccProperties;
};

```

Support for the CooperativeVector feature is queried through
`CooperativeVectorTier`. User can also query properties supported for each
intrinsic in `D3D12_FEATURE_DATA_COOPERATIVE_VECTOR`. If pProperties is NULL
for any intrinsic, the count of available properties will be returned in
PropCount. Otherwise, PropCount must represent the size of the pProperties
array, which will be updated with the number of structures written to
pProperties upon return. If pProperties is non-NULL for any intrinsic but its
PropCount is less than the number of properties available for that intrinsic,
the operation fails and `E_INVALIDARG` is returned.

// XXX TODO: Add query for emulated types. For example E4M3 and E5M2 might not
be supported on certain h/w, but since these are in the minimum support set,
they need to be emulated, possibly using FP16. Add capability for the
application to query which types are natively supported and which ones are
emulated.

#### Minimum Support Set

Minimum set of properties that implementations are required to support for each
intrinsic are listed below.

##### For Matrix-Vector Multiply and Multiply-Add

Note that value of `TransposeSupported` is never guaranteed and needs to be
explicitly checked for the combinations below.


| InputType    | InputInterpretation | MatrixInterpretation | BiasInterpretation | OutputType |
|--------------|---------------------|----------------------|--------------------|------------|
| FP16         | FP16                | FP16                 | FP16               | FP16       |
| FP16         | E4M3                | E4M3                 | FP16               | FP16       |
| FP16         | E5M2                | E5M2                 | FP16               | FP16       |
| SINT8_PACKED | SINT8               | SINT8                | SINT32             | SINT32     |
| FP32         | SINT8               | SINT8                | SINT32             | SINT32     |


##### For OuterProductAccumulate

| InputType | AccumulationType |
|-----------|------------------|
| FP16      | FP16             |
| FP16      | FP32             |

##### For ReduceSumAccumulate

| InputType | AccumulationType |
|-----------|------------------|
| FP16      | FP16             |


#### Usage Example

```c++
// Check for CooperativeVector support and query properties for VectorMatrixMulAdd
D3D12_FEATURE_DATA_D3D12_OPTIONSNN CoopVecSupport = {};

d3d12Device->CheckFeatureSupport(D3D12_FEATURE_D3D12_OPTIONSNN, &CoopVecSupport, 
                                 sizeof(D3D12_FEATURE_DATA_D3D12_OPTIONSNN));

if (CoopVecSupport.CooperativeVectorTier == D3D12_COOPERATIVE_VECTOR_TIER_1_0) {
    // PropCounts to be filled by driver implementation
    D3D12_FEATURE_DATA_COOPERATIVE_VECTOR CoopVecProperties = {0, NULL, 0, NULL, 0, NULL};

    // CheckFeatureSupport returns the number of input combinations for inference intrinsic
    d3d12Device->CheckFeatureSupport(D3D12_FEATURE_COOPERATIVE_VECTOR, &CoopVecSupport, 
                                     sizeof(D3D12_FEATURE_COOPERATIVE_VECTOR));

    // Use VectorMatrixMulAddPropCount returned from the above 
    // CheckFeatureSupport call to query only VectorMatrixMulAddProperties
    UINT VectorMatrixMulAddPropCount = CoopVecSupport.VectorMatrixMulAddPropCount;
    std::vector<D3D12_COOPERATIVE_VECTOR_PROPERTIES_INFERENCE> properties(VectorMatrixMulAddPropCount);
    CoopVecSupport.pVectorMatrixMulAddProperties = properties.data();

    // CheckFeatureSupport returns the supported input combinations for the inference intrinsic
    d3d12Device->CheckFeatureSupport(D3D12_FEATURE_COOPERATIVE_VECTOR, &CoopVecSupport, 
                                    sizeof(D3D12_FEATURE_DATA_COOPERATIVE_VECTOR));
                                                                
    // Use VectorMatrixMulAdd shader with datatype and interpretation combination matching one of those returned.
    
} else {
    // Don't use Cooperative Vector
}
```

### Convert Matrix to desired layout and type

The weight and bias matrices used in the cooperative vector intrinsics are
(RW)ByteAddressBuffers with implementation specific alignment constraints and
performance characteristics. We introduce a driver side API to change the
layout and dataype of the weight matrix from and to any of the layouts in
`D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT` and datatypes in
`D3D12_COOPERATIVE_VECTOR_DATATYPE`.

```c++
enum D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT {
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_ROW_MAJOR,
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_COLUMN_MAJOR,
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_INFERENCING_OPTIMAL,
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_TRAINING_OPTIMAL
}
```

#### Query Destination Size

The destination buffer (to hold the matrix) size can be implementation
dependent. The API `GetCooperativeVectorMatrixConversionDestinationInfo` is
added to query the size of the destination buffer in the desired layout and
datatype. It takes a pointer to
`D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO` descriptor that provides
the inputs required to calculate the necessary size. The same descriptor,
updated with the calculated output size, is then passed to the conversion
API. 

```c++

// Descriptor to query the destination buffer size
typedef struct D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO { 
    UINT                                   DestSize;      // !< [out]Destination buffer size in bytes
                                                          // required for conversion 
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT DestLayout;    // !< [in] Is the layout the matrix is converted to
    UINT                                   DestStride;    // !< [in] Is the number of bytes between a consecutive 
                                                          // row or column (depending on DestLayout) of the 
                                                          // destination matrix if it is row-major or 
                                                          // column-major.
    UINT                                   NumRows;       // !< [in] Is the number of rows in the matrix. 
    UINT                                   NumColumns;    // !< [in] Is the number of columns in the matrix. 
    D3D12_COOPERATIVE_VECTOR_DATATYPE      DestDataType;  // !< [in] the type of a destination matrix element. 
};

// An API to return the number of bytes required in the destination buffer to
// store the result of conversion The size of the destination is a function of
// the destination layout information and does not depend on the source layout
// information.

void ID3D12Device::GetCooperativeVectorMatrixConversionDestinationInfo(
                        D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO* pDesc);

```

#### Conversion descriptors

After the size of the destination buffer is known, user can pass the
`D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO` descriptor along with
information of source layout and datatype in
`D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_SOURCE_INFO` and addresses of the
source and destination buffers to the layout and datatype conversion API.

```c++

// GPU VAs of source and destination buffers

typedef struct D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DATA {
    D3D12_GPU_VIRTUAL_ADDRESS               DestVA;               //!< [inout] GPU VA of destination 
                                                                  // buffer
    D3D12_GPU_VIRTUAL_ADDRESS               SrcVA;                //!< [in]    GPU VA of source 
                                                                  // buffer
};
 
// Source information descriptor. Destination information comes from 
// D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO

typedef struct D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_SRC_INFO {
    UINT                                    SrcSize;                // !< [in] Is the length in bytes of 
                                                                    // srcData    
    D3D12_COOPERATIVE_VECTOR_DATATYPE       SrcDataType;            // !< [in] Is the type of a 
                                                                    // source matrix 
                                                                    // element        
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT  SrcLayout;              // !< [in] Is the layout of the 
                                                                    // source matrix.
    UINT                                    SrcStride;              // !< [in] Is the number of bytes  
                                                                    // between a consecutive row or column 
                                                                    // (depending on srcLayout) 
                                                                    // of the source matrix, if it is row-major 
                                                                    // or column-major.   
};

// Descriptor passed to the conversion API
typedef struct D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_INFO {
    D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO      DestInfo;
    D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_SRC_INFO       SrcInfo;    
    D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DATA           DataDesc;   
};
```

#### Conversion APIs

New API is added to the ID3D12CommandList interface. Multiple conversions can be
done in a single call of the API. The number of descriptors pointed to by pDesc
is specified using descCount. If DestSize passed to this API is less than the
number of bytes returned in call to
`GetCooperativeVectorMatrixConversionDestinationInfo`, behavior is undefined.

```c++
// Converts source matrix to desired layout and datatype
void ID3D12CommandList::CooperativeVectorConvertMatrix(D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_INFO* pDesc,
                                                       UINT DescCount);

```

*Valid Usage:* 

* If SrcLayout is row-major or column-major, then SrcStride should be greater than the length of a row/column, and a
  multiple of the element size.
* If DestLayout is row-major or column-major, then DestStride should be greater than the length of a row/column, and a
  multiple of the element size.
* If SrcComponentType is not a supported MatrixInterpretation value as reported by CheckFeatureSupport() then
  SrcComponentType should be `D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT32`.
* If DestComponentType is not a supported MatrixInterpretation value as reported by CheckFeatureSupport() then
  DestComponentType should be `D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT32`.
* If SrcComponentType and DestComponentType are not equal, then one should be `D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT32`  or `D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT16` and the other should be a lower-precision floating-point type. 
* If DestComponentType is `D3D12_COOPERATIVE_VECTOR_DATATYPE_E4M3` or `D3D12_COOPERATIVE_VECTOR_DATATYPE_E5M2`, then DestLayout should be `D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_INFERENCING_OPTIMAL` or `D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_TRAINING_OPTIMAL`.


*Usage Example:*

```c++

D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_INFO infoDesc = 
{ 
    // DestInfo
    {
        0,                                                              // DestSize to be populated by 
                                                                        // driver implementation
        D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_INFERENCING_OPTIMAL,     // convert to inferencng optimal layout
        0,                                                              // stride is ignored since optimal layout 
                                                                        // is implementation dependent
        numRows,                                                        // number of rows in weight matrix to be 
                                                                        // converted
        numColumns,                                                     // number of columns in weight matrix to 
                                                                        // be converted
        D3D12_COOPERATIVE_VECTOR_DATATYPE_E4M3                          // convert to FP8 datatype
    },

    //SrcInfo
    {
        srcSize,                                                        // number of bytes of matrix in source 
                                                                        // layout and datatype
        D3D12_COOPERATIVE_VECTOR_DATATYPE_FLOAT32,                      // convert from float
        D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_ROW_MAJOR,               // convert from row major layout
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
pD3D12Device->GetCooperativeVectorMatrixConversionDestinationInfo(&infoDesc.DestInfo);

// After the size is known, initialize the DestVA. Offset the SrcVA with DestSize to get DestVA 
// (alignment requirements are ignored for simplicity)
infoDesc.DataDesc.DestVA = srcVA + infoDesc.DestInfo.DestSize;

// Perform the conversion
pD3D12CommandList->CooperativeVectorConvertMatrix(&infoDesc, 0);

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

## Open Issues

* Q: Type interpretations to use HLSL conversion rules of ML best practices?
* A: This spec uses the ML best practices like the SpirV spec. // TODO: get
  approval
* Q: More details on formats and their precision requirements
* A: Implementation Dependent
* Q: How do you handle cases where different implementations may not produce bit
  identical results?
* A: Some combination of exactly representable results/ epsilon ranges.
* Q: Using MatrixView and VectorView as a wrapper for the BAB containing the
  matrix/bias vectors and their corresponding interpretations.

## Acknowledgments

We would like to thank Jeff Bolz, Yury Uralsky, Patrick Neill and Tex Riddell
for their contributions to this proposal.

<!-- {% endraw %} -->
