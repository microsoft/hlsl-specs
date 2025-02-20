<!-- {% raw %} -->

* Proposal: [0029](0029-cooperative-vector.md)
* Author(s): [Anupama Chandrasekhar][anupamachandra]
* Sponsor: [Damyan Pepper][damyanp], [Greg Roth][pow2clk]
* Status: **Under Review**
* Planned Version: Shader Model 6.9


[anupamachandra]: https://github.com/anupamachandra
[damyanp]: https://github.com/damyanp
[pow2clk]: https://github.com/pow2clk

# HLSL Cooperative Vectors

## Introduction
In research and in industry, machine learning based approaches have made their way to mainstream, replacing/augmenting
traditional techniques. In graphics, neural network (NN) based rendering methods are gaining popularity over
traditional methods of image reconstruction, texture compression, material shading etc. Simultaneously, the increasing
use of GPUs for general purpose ML/DL means that GPU vendors continue to add more specialized hardware in GPUs to
accelerate neural network computations, like accelerating matrix operations. This specification introduces HLSL and DXIL intrinsics for vector-matrix operations that can accelerated by the underlying hardware.

## Motivation

Let's say, we have a typical shader for lighting computation. This is usually thousands of lines of computation, looping
over various materials, light sources etc. We want a way to replace these computations with a neural network like shown below.
Note that the NN simply replaces the computations in the original shader with no change to the rendering pipeline, like addition of a new shader stage.

**Original Shader**

``` 
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

``` 
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

Introduce new HLSL intrinsics to accelarate matrix-vector operations. In this specification we add four operations:

* **Matrix-Vector Multiply:** Multiply a matrix in memory and a vector parameter.
* **Matrix-Vector Multiply-Add:** Multiply a matrix in memory and a vector parameter and add a vector from memory.
* **Vector-Vector Outer Product and Accumulate:** Compute the outerproduct of two vectors.
* **Reduce and Accumulate:** Add elements of a vector atomically to the corresponding elements of an array in memory.


## Detailed design

### Intrinsics for Vector-Matrix Operations

**Matrix-Vector Multiply and Add Intrinsic**

Intrinsics for specifying a multiplication operation between a matrix(Dim: M * K) loaded from memory and aa vector(Dim: K), a
variant of this with an add, where a bias vector(Dim: K), loaded from memory, is added to the result vector(Dim: M) of the matrix-vector
multiply operation.

Note that the dimensions of the matrix are `M X K` versus `M x N`  usually found in linear algebra texbooks. This is to
futureproof for potential Matrix-Matrix operations in the future where the inputs could be `M X K` and `K x N` to
produce an `M X N` result matrix.

The `InputVector` is an HLSL vector and the `Matrix` and `BiasVector` are loaded from memory at specified offsets.

```
// Result = Matrix * InputVector + Bias
template<typename DESC, typename InputTy, typename ResultTy, uint InputComponents>
vector<ResultTy, DESC::M> VectorMatrixMulAdd(vector<InputTy, InputComponents>  InputVector,
                                                      (RW)ByteAddressBuffer             Matrix,
                                                      uint                              MatrixOffset,
                                                      uint                              MatrixStride,
                                                      (RW)ByteAddressBuffer             BiasVector,
                                                      uint                              BiasOffset);

// Result = Matrix * InputVector
template<typename DESC, typename InputTy, typename ResultTy, uint InputComponents>
vector<ResultTy, DESC::M> VectorMatrixMul(vector<InputTy, InputComponents> InputVector,
                                                   (RW)ByteAddressBuffer            Matrix,
                                                   uint                             MatrixOffset,
                                                   uint                             MatrixStride);

```

Note that the `InputVector` has a physical storage type `InputTy` and an interpretation type that specifies how it is
interpreted. Similarly,`Matrix` and `BiasVector` are loaded from a memory buffer and have interpretation parameters
that specify how the buffer elements are interpreted. See the section on Type Interpretation for more details.

```
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

enum class DXILMatrixLayout : uint {
  RowMajor              = 0,
  ColumnMajor           = 1,
  InferencingOptimal    = 2,
  TrainingOptimal       = 3,
};

template<uint m, uint k, uint input_interp, uint matrix_interp, uint bias_interp, 
         uint layout, bool transpose>
struct VecMatOpDescriptor {
  static const uint M               = m;
  static const uint K               = k;
  static const uint Ii              = input_interp;
  static const uint Mi              = matrix_interp;
  static const uint Bi              = bias_interp;
  static const uint Layout          = layout;
  static const bool Transposed      = transpose;
};

// Result = Matrix * InputVector + Bias
template<typename DESC, typename InputTy, typename ResultTy, uint InputComponents>
vector<ResultTy, DESC::M> VectorMatrixMulAdd(vector<InputTy, InputComponents> InputVector,
                               (RW)ByteAddressBuffer Matrix,
                               uint MatrixOffset,
                               uint MatrixStride,
                               (RW)ByteAddressBuffer BiasVector,
                               uint BiasOffset);

// Result = Matrix * InputVector
template<typename DESC, typename InputTy, typename ResultTy, uint InputComponents>
vector<ResultTy, DESC::M> VectorMatrixMul(vector<InputTy, InputComponents> InputVector,
                             (RW)ByteAddressBuffer Matrix,
                             uint MatrixOffset,
                             uint MatrixStride);

```

*InputVector* is the vector operand of the matrix-vector mul/mul-add operation. *InputTy* is the physical storage type
 of the elements of the vector, which might vary from the actual type that the elements of the vector are interpreted
 as, *InputInptretation* from *DESC*. *InputComponents* is the number of components in the input vector, which equals
 the matrix dimension *K* for a non-packed type and for a packed type, equals the least number that can hold *K* values
 of the packed type. Where, packed type, refers to types like `SignedInt8x4Packed` where each 32-bit element of the
 vector corresponds to four 8-bit signed integers; Unpacked types are the standard types like float16, uint etc. The
 elements of the *InputVector* are converted to type specified by *DESC: Ii* present in, if it is legal. More details
 in the [Type Interpretations](#type-interpretations) section.

*Matrix* is loaded starting from a byte offset *MatrixOffset* from the start of Buffer, and raw data is loaded according
 to the type interpretation parameter *DESC: Mi*. *DESC: MxK* is the dimension of the matrix. No conversion is
 performed. The *MatrixOffset* and the base address of the Matrix buffer must be 64B aligned. The *DESC: Layout* of the
 matrix is one of the enum values *DXILMatrixLayout* listed above.

*MatrixStride*, for RowMajor or ColumnMajor layouts, is the number of bytes to go from one row/column to the next. For
 optimal layouts, *MatrixStride* is ignored.

*BiasVector*, the bias vector, is loaded starting from a byte offset of *BiasOffset* from the start of the array, and
 raw data is loaded according to the type interpretation parameter *DESC: Bi*. *M* consecutive elements are loaded. No
 conversion is performed. The *BiasOffset* and the base address of the BiasVector buffer must be 64B aligned.

 **VecMatOpDescriptor Parameters** 

 The *VecMatOpDescriptor* describes the interpretation of the Input, Matrix and Bias elements. Bias interpretation
 applies only for the *VectorMatrixMulAdd* operation and is ignored for *VectorMatrixMul* operation. 

*Ii* Input Interpretation, *Mi* MatrixInterpretation and *Bi* BiasInterpretation define what type the respective objects
 will be interpreted as. These values are constrained by the combinations allowed by the device, *Matrix* and *Bias*
 are typeless buffers and their respective interpretations determine the types. See [Type Interpretations]
 (#type-interpretations) section for more details.


*Mi* and *Bi* determines the type of the Weight Matrix and Bias Vector elements.

For the unpacked case, *M x K* is the dimension of the Matrix, *M* is the size of the result vector, *K* is the size of
the input vector. For the packed case, the number of components in the input vector must large enough to hold the *K*
packed components.

*Layout* is an enum value, `DXILMatrixLayout`. Optimal layouts are opaque implementation specific layouts, the D3D call
 `CooperativeVectorConvertMatrix` can be used to convert the *Matrix* to an optimal layout. Row-Major and Column-Major
 layouts are also supported.

The *Transposed* parameter indicates if the *Matrix* is transposed before performing the multiply. In linear algebra,
the[transpose](https://en.wikipedia.org/wiki/Transpose) of a matrix is an operator which flips a matrix over its
diagonal; that is, it switches the row and column indices of the matrix. Transposing is not supported for the
RowMajor/ColumnMajor layouts. Not all component types support transposing. It is left to implementations to define
which types support matrix transposing. "TransposeSupported" flag from the [CheckFeatureSupport]
(#check-feature-support) struct is used to determine if a matrix transpose is supported. Note that even for the
type/interpretation combinations with guaranteed [support](#minimum-support-set), transpose support isn't guaranteed
and needs to be checked explicitly.

**Type Interpretations**

The types of *InputVector*, *Matrix* and *BiasVector* are all determined by their respective interpretation parameters.
For the Matrix and BiasVector which are stored in (RW)ByteAddressBuffers, this is straightforward: the *M*
and *K* *VecMatOpDescriptor* parameters describe the dimensions of the *Matrix*/*BiasVector*, these are loaded from the
offsets *MatrixOffset* and *Biasoffset* respectively and the *Mi* and *Bi* parameters which
are *DXILTypeInterpretation* enums specify the element type.

*InputVector* is an HLSL vectors of a given type *InputTy* . However, the type that the elements of this vector are
 interpreted as in the matrix-vector operation is specified by the *InputInterpretation* parameter. The reason is that
 the interpretation parameter allows the elements to be interpreted as types not natively supported by HLSL, e.g.
 uint8/sint8. 

The legal conversions from the declared *InputType* to *InputInterpretation: Ii* and the
corresponding *MatrixInterpretation: Mi* and *BiasInterpretation: Bi* are implementation dependent and can be queried.
See[CheckFeatureSupport](#check-feature-support) section for details. An exception to this rule is the set of
combinations guaranteed to be supported on all devices supporting this feature. See [Minimum Support Set]
(#minimum-support-set).  Note that *Transposed* is always queried.

Non-"Packed" type interpretations are used to request arithmetic conversions. Input type must be a 32-bit or 16-bit
scalar integer or a 32-bit or 16-bit float. Integer to integer conversion saturates, float to float conversion is
implementation dependent and preserves the value as accurately as possible. Float to integer conversion is RTNE and
saturating. Integer to float conversion is RTNE.

/// XXX TODO: These rules make sense for NN applications but diverge from HLSL conversion rules [here]
    (https://microsoft.github.io/hlsl-specs/specs/hlsl.html#Conv).

"Packed" type conversions are bitcasts to a smaller type. The declared input type must be 32-bit unsigned integer. 

/// XXX TODO: Error handling for illegal conversions. 

Examples:

Packed Case:
```
// Declare an input vector
vector<uint, 8> ipVector;

// Set interpretation value to DXILCoopVectorTypeInterpretation::SignedInt8x4Packed
// Each uint element (32-bit) in the input vector, ipVector, will be interpreted as 4 int8 values in the VectorMatrixMul intrinsic. 
// Note that InputTy = uint and InputComponents = 8 (8 x 4 = 32 sint8 values )
VecMatOpDescriptor<32 /*M*/, 
                   32 /*K*/, 
                   DXILTypeInterpretation::SignedInt8x4Packed /*InputInterpretation*/, 
                   DXILTypeInterpretation::SignedInt8 /*MatrixInterpretation*/,
                   DXILTypeInterpretation::Unsupported /*BiasInterpretation*/, 
                   DXILMatrixLayout::InferencingOptimal /*Layout*/,
                   false /*Transpose*/> desc;

vector<int, 32> resultVector; //Note that the ResultComponents equals M(32)
// Matrix is a ByteAddressBuffer
resultVector = VectorMatrixMul(ipVector, Matrix, 0/*MatrixOffset*/, 0/*MatrixStride*/);

```

Non-Packed Case:
```
// Declare an input vector
vector<float, 32> ipVector;

// Set interpretation value to DXILCoopVectorTypeInterpretation::SignedInt8x4Packed
// Each float element of the input vector, ipVector, will be arithmetically converted to a sint8 value in the VectorMatrixMul intrinsic. 
VecMatOpDescriptor<64 /*M*/, 
                   32 /*K*/, 
                   DXILTypeInterpretation::SignedInt8 /*InputInterpretation*/, 
                   DXILTypeInterpretation::SignedInt8 /*MatrixInterpretation*/,
                   DXILTypeInterpretation::SignedInt8 /*BiasInterpretation*/, 
                   DXILMatrixLayout::InferencingOptimal /*Layout*/,
                   false /*Transpose*/> desc;

vector<int, 64> resultVector; // Note that the ResultComponents equals M(64)

// Matrix and Bias are ByteAddressBuffers
resultVector = VectorMatrixMul(ipVector, Matrix, 0/*MatrixOffset*/, 0/*MatrixStride*/, Bias, 0/*BiasStride*/);

```


**Vector Outer Product**

Computes the outer product between column vectors and an *MxN Matrix* is accumulated atomically (with device scope) in memory. The device should be queried in `CheckFeatureSupport` to determine type of InputVector supported and the corresponding Accumulation type.
An exception to this rule is the set of combinations guaranteed to be supported on all devices supporting the cooperative vector feature. See [here](#minimum-support-set).

``` 
ResultMatrix = InputVector1 * Transpose(InputVector2); 
```


```
template<uint matrix_interp, uint layout>
struct OuterProductAccDescriptor{
  static const uint Mi     = matrix_interp;
  static const uint Layout = layout;
};

template<typename DESC, typename T, uint M, uint N>
void OuterProductAccumulate(vector<T, M> InputVector1,
                            vector<T, N> InputVector2,
                            RWByteAddressBuffer ResultMatrix,
                            uint ResultMatrixOffset,
                            uint ResultMatrixStride);
```

*InputVector1* is an M component vector of type T.

*InputVector2* is an N component vector of type T.

*ResultMatrix* is the resulting *MxN* matrix accumulated atomically (with device scope) in memory
 (RWByteAddressBuffer) at offset *ResultMatrixOffset*. The base address and *ResultMatrixOffset* of the Matrix buffer
 must be 64B aligned.

*ResultMatrixStride* for RowMajor or ColumnMajor layouts, is the number of bytes to go from one row/column to the next.
 For optimal lyouts, stride is ignored.

 **OuterProductAccDescriptor Parameters**

 *Mi* determines the type of the Result Matrix. See [Type Interpretations](#type-interpretations) section for more
  details.

 *Layout* is an enum value, `DXILMatrixLayout`. Optimal layouts are opaque implementation specific layouts, the D3D call
  `CooperativeVectorConvertMatrix` can be used to convert the *Matrix* to an optimal layout. Row-Major and Column-Major
  layouts are also supported.

The device should be queried in [Check Feature Support](#check-feature-support) to determine datatypes of InputVector
supported along with the AccumulationType. An exception to this rule is the set of combinations guaranteed to be
supported on all devices supporting this feature. See [Minimum Support Set](#minimum-support-set).


**Reduce Sum Accumulate**

Accumulates the components of a vector atomically (with device scope) to the corresponding elements of an array in
memory.

```
template<typename T, uint M>
void ReduceSumAccumulate(vector<T, M> InputVector,
                         RWByteAddressBuffer Buf,
                         uint BufOffset);

```

*InputVector* is an M component vector of type T.

*Buf* is the array into which the *InputVector* is accummulated. The base address and *BufOffset* of the buffer
 must be 64B aligned.

*BufOffset* is the offset to the first element of the array to which the *InputVector* is accummulated. It is 64B aligned.

The device should be queried in [Check Feature Support](#check-feature-support) to determine datatypes of InputVector supported along
with the AccumulationType. An exception to this rule is the set of combinations guaranteed to be supported on all
devices supporting this feature. See [Minimum Support Set](#minimum-support-set).

### Example HLSL Shader

// XXX TODO

### Interchange Format Additions

**Vector Matrix Multiply(Add)**

*HLSL*

``` 
template<typename DESC, typename InputTy, typename ResultTy, uint InputComponents>
vector<ResultTy, DESC::M> VectorMatrixMulAdd(vector<InputTy, InputComponents> InputVector,
                                                      (RW)ByteAddressBuffer Matrix,
                                                      uint MatrixOffset,
                                                      uint MatrixStride,
                                                      (RW)ByteAddressBuffer BiasVector,
                                                      uint BiasOffset);

```

*DXIL*

``` 
<n1 x ty1> @dx.op.vecmatmul.v<n1><ty1>.v<n2<ty2>(i32 opcode, 
                                                 <n2 x ty2> %ipVec, 
                                                 i32 inputInterpretation, 
                                                 %dx.types.Handle %matrix, 
                                                 i32 %matrixoffset, 
                                                 i32 matrixInterpretation, 
                                                 i32 matrixMdim,
                                                 i32 matrixKdim, 
                                                 i32 matrixLayout, 
                                                 i32 matrixTranspose, 
                                                 i32 matrixStride
                                                 i1 isResultSigned); 
```

**Outer Product Accumulate**

*HLSL*

``` 
template<typename DESC, typename T, uint M, uint N>
void OuterProductAccumulate(vector<T, M> InputVector1,
                            vector<T, N> InputVector2,
                            RWByteAddressBuffer ResultMatrix,
                            uint ResultMatrixOffset,
                            uint ResultMatrixStride);

```

*DXIL*

``` 
void @dx.op.vecouterproductacc.v<n1><ty>.v<n2<ty>(i32 opcode, <n1 x ty> %ipVec1, 
                                                  <n2 x ty> %ipVec2, 
                                                  %dx.types.Handle %matrix, 
                                                  i32 %matrixoffset, 
                                                  i32 %matrixstride,
                                                  i32 matrixInterpretation, 
                                                  i32 matrixLayout); 
```


**Reduce Sum Accumulate**

*HLSL*

```
void ReduceSumAccumulate(vector<T, M> InputVector,
                         RWByteAddressBuffer Buf,
                         uint BufOffset);

```

*DXIL*
```
void @dx.op.vecreducesumacc.v<n><ty>(i32 opcode, 
                                     <n x ty> %ipVec, 
                                     %dx.types.Handle %buf, 
                                     i32 %bufoffset); 
```

### Non-Uniform control flow

There are no requirements for fully occupied waves or uniform control flow while using these intrinsics, this is to
ensure wide usability across all shader stages (compute, ray-tracing, pixel shader etc). It is possible that
implementations can enable fast paths by allowing vectors to cooperate behind the scenes in cases with uniform paths,
fully occupied waves and uniform values for Matrix, Matrix Offset, Matrix Interpretation, Matrix Layout, Matrix Stride,
Matrix Transpose and Bias, Bias Offset, Bias Interpretation, but this is not a requirement for functionality.

### Shade Stages

The vector-matrix intrinsics are expected to be supported in all shader stages.

// XXX TODO: Add query to determine which shader stages support these intrinsics.

### Diagnostic Changes

* Diagnostics for incorrect use of the new intrinsics.


#### Validation Changes


### D3D12 API Additions

Note: The enums and structs need to be updated from the coop_vec name, once a new name for the feature is decided.

#### Check Feature Support

This feature requires calling CheckFeatureSupport(). Additional D3D12_FEATURE enum and corresponding D3D12_FEATURE_DATA* structs (listed below) are added to enable discovering the Cooperative Vector tier along with the datatype and interpretation combinations supported by new vector-matrix intrinsics.

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

Support for the CooperativeVector feature is queried through `CooperativeVectorTier`. 
User can also query properties supported for each intrinsic in `D3D12_FEATURE_DATA_COOPERATIVE_VECTOR`. 
If pProperties is NULL for any intrinsic, the count of available properties will be returned in PropCount. 
Otherwise, PropCount must represent the size of the pProperties array, which will be updated with the number of structures written to pProperties upon return. 
If pProperties is non-NULL for any intrinsic but its PropCount is less than the number of properties available for that intrinsic, the operation fails and `E_INVALIDARG` is returned.

// XXX TODO: Add query for emulated types. For example E4M3 and E5M2 might not be supported on certain h/w, but since these are in the minimum support set, they need to be emulated, possibly using FP16. Add capability for the application to query which types are natively supported and which ones are emulated.

### Minimum Support Set

Minimum set of properties that implementations are required to support for each intrinsic are listed below.

#### For VectorMatrixMulAdd

Note that value of `TransposeSupported` is never guaranteed and needs to be explicitly checked for the combinations below.

```
| InputType    | InputInterpretation | MatrixInterpretation | BiasInterpretation | OutputType |
|--------------|---------------------|----------------------|--------------------|------------|
| FP16         | FP16                | FP16                 | FP16               | FP16       |
| FP16         | E4M3                | E4M3                 | FP16               | FP16       |
| FP16         | E5M2                | E5M2                 | FP16               | FP16       |
| SINT8_PACKED | SINT8               | SINT8                | SINT32             | SINT32     |
| FP32         | SINT8               | SINT8                | SINT32             | SINT32     |
```

#### For OuterProductAccumulate

```
| InputType | AccumulationType |
|-----------|------------------|
| FP16      | FP16             |
| FP16      | FP32             |
```

#### For ReduceSumAccumulate

```
| InputType | AccumulationType |
|-----------|------------------|
| FP16      | FP16             |
```

**Usage Example:**

```
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

    // Use VectorMatrixMulAddPropCount returned from the above CheckFeatureSupport call to query only VectorMatrixMulAddProperties
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

The weight and bias matrices used in the cooperative vector intrinsics are (RW)ByteAddressBuffers with implementation
specific alignment constraints and performance characteristics. We introduce a driver side API to change the layout and
dataype of the weight matrix from and to any of the layouts in `D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT` and datatypes in
`D3D12_COOPERATIVE_VECTOR_DATATYPE`.

```
typedef enum D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT {
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_ROW_MAJOR,
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_COLUMN_MAJOR,
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_INFERENCING_OPTIMAL,
    D3D12_COOPERATIVE_VECTOR_MATRIX_LAYOUT_TRAINING_OPTIMAL
}
```

#### Query Destination Size

The destination buffer (to hold the matrix) size can be implementation dependent. The API `GetCooperativeVectorMatrixConversionDestinationInfo` is added to query the size of the destination buffer in the desired layout and datatype. It takes a pointer to `D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO` descriptor that provides the inputs required to calculate the necessary size. The same descriptor, updated with the calculated output size, is then passed to the conversion API. 

```

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

// An API to return the number of bytes required in the destination buffer to store the result of conversion
// The size of the destination is a function of the destination layout information and does not depend on the
// source layout information.

void ID3D12Device::GetCooperativeVectorMatrixConversionDestinationInfo(
                        D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO* pDesc);

```

#### Conversion descriptors

After the size of the destination buffer is known, user can pass the `D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_DEST_INFO` descriptor along with information of source layout and datatype in `D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_SOURCE_INFO` and addresses of the source and destination buffers to the layout and datatype conversion API.

```

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

New API is added to the ID3D12CommandList interface. Multiple conversions can be done in a single call of the API. The number of descriptors pointed to by pDesc is specified using descCount. If DestSize passed to this API is less than the number of bytes returned in call to `GetCooperativeVectorMatrixConversionDestinationInfo`, behavior is undefined.

```
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

```

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
The DDIs for this feature are straightforward API mappings and have therefore been excluded from this document.

## Testing

* How will validation of new DXIL elements be tested?
* A: *unit tests in dxc*
* How will the execution results be tested?
* A: *HLK tests*


## Alternatives considered

Our original proposal introduced an opaque Cooperative Vector type to HLSL to limit the scope of the feature to small
neural network evaluation and also contain the scope for testing. But aligning with the long term roadmap of HLSL to
enable generic vectors, it makes sense to not introduce a new datatype but use HLSL vectors.

## Open Issues
* Q: Type interpretations to use HLSL conversion rules of ML best practices?
* A: This spec uses the ML best practices like the SpirV spec. // TODO: get approval
* Q: The supported types might sometimes need to be emulated as some hardware might not support it.
* A: Add a query to check which types are native versus emulated
* Q: More details on formats and their precision requirements
* A:
* Q: How do you handle cases where different implementations may not produce bit identical results?
* A: Some combination of exactly representable results/ epsilon ranges.
* Q: Programming guidance about divergence
* A: While there are no uniformily constraints while using these intrinisics, best perfomance might be implementation specific, likely requiring uniform control flow.
* Q: Using MatrixView and VectorView as a wrapper for the BAB containing the matrix/bias vectors and their corresponding interpretations.
* Q: Rename to MatrixVectorMul(Add) to make the left multiply explicit

## Acknowledgments
Would like to thank Jeff Bolz and Shashank Wadhwa for their contributions.

<!-- {% endraw %} -->