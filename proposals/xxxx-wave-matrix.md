<!-- {% raw %} -->

# Wave Matrix

* Proposal: [NNNN](NNNN-wave-matrix.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Greg Roth](https://github.com/pow2clk), [Tex Riddell](https://github.com/tex3d)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.9


## Introduction

This proposal adds HLSL support for a new DXIL feature WaveMatrix. The new data
types and operations add support for wave cooperative matrix multiplication and
accumulation. The underlying hardware and driver interfaces for this feature are
introduced in Shader Model 6.9.

## Motivation

GPUs have added dedicated hardware to support cooperative matrix multiplication
across SIMD lanes. This feature proposes adding new data types and built-in
functions to enable higher throughput matrix operations that fully utilize GPU
SIMD hardware.

These higher throughput matrix operations are required for optimal performance
of many machine learning and image processing workloads. Adding support to HLSL
will enable high-performance matrix operations across Shader Model 6.9 drivers
when hardware support is available.

## Proposed solution

WaveMatrix introduces new matrix templates to facilitate wave cooperative
operations:

```hlsl
// Matrix Depth (K) dimension is hardware dependent
// With TYPE_IN one of {float32_t, float16_t, uint8_t4_packed, int8_t4_packed}
WaveMatrixLeft  <TYPE_IN, M, N> ;             // M x K
WaveMatrixRight <TYPE_IN, M, N> ;             // K x N

// With TYPE_ACC one of {float32_t, float16_t, int32_t}
WaveMatrixAccumulator <TYPE_ACC, M, N> ;      // M x N
// WaveMatrixLeftColAcc and WaveMatrixRightRowAcc are provided support for
// quantization algorithms. See Zero Point section

// For accumulating columns from WaveMatrixLeft into a single column of sums
WaveMatrixLeftColAcc  <TYPE_ACC, M, N> ;      // M x 1

// For accumulating rows from WaveMatrixRight into a single row of sums
WaveMatrixRightRowAcc <TYPE_ACC, M, N> ;      // 1 x N
```

WaveMatrix accumulator object methods support operating on corresponding Left
and Right operands. Results of operations can be stored or accumulated back into
the accumulator. A simple example of multiplication is:

```hlsl
[numthreads(64,1,1)]
void main(uint3 GTID : SV_GroupThreadID, uint GIDX : SV_GroupIndex)
{
  WaveMatrixLeft<float, 16, 16> Left;
  WaveMatrixRight<float, 16, 16> Right;
  WaveMatrixAccumulator<float, 16, 16> Acc;

  Acc.Multiply(Left, Right); // Stores Left * Right into Acc
  Acc.MultiplyAccumulate(Left, Right); // Adds Left * Right to Acc
}
```

## Detailed design

### Reading This Spec

The next few sections include HLSL object definitions written in HLSL 2021
syntax and using inheritance to represent interface composition. The objects in
the `detail` namespace are not exposed in the HLSL runtime. They are provided
here to make the specification more concise to consume. Objects in no namespace
are exposed as public interfaces.

### WaveMatrix Matrix Objects

The code below approximately declares the base interface that WaveMatrix matrix
objects implement.

```c++
namespace detail {
template <typename ElTy, int NRows, int NCols>
class WaveMatrixBase {
  void Fill(ElTy Val);
  void Load(ByteAddressBuffer Res, uint StartOffset, uint Stride, bool ColMajor,
            uint Align = 0);
  void Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
            bool ColMajor, uint Align = sizeof(ElTy));

  void Load(groupshared ElTy Arr[], uint StartIdx, uint Stride, bool ColMajor);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             bool ColMajor, uint Align = sizeof(ElTy));

  void Store(groupshared ElTy Arr[], uint StartIdx, uint Stride, bool ColMajor);
};
} // namespace detail
```

The following sections will explain in detail what these methods do and what the
parameters represent.

#### WaveMatrix Fill

All WaveMatrix objects have a `Fill` method of the form `void Fill(ElTy Value)`
where `ElTy` is the element type.

The `Fill` method assigns the given Value to every element in the matrix or
matrix fragment. All wave threads must provide the same value or the result is
undefined. All WaveMatrix objects have the same `Fill` method with the same
behavior.


#### Loading and Storing WaveMatrix Matrix Objects

Values for WaveMatrix matrix objects can be loaded from and stored to
`[RW]ByteAddressBuffer` or `groupshared` array of type `ElTy`.

Loading from or storing to a `[RW]ByteAddressBuffer` takes a start offset in
bytes, row stride in bytes, and optional row alignment in bytes. Rows begin at
algined offsets from the `StartOffset` based on the `Stride` and `Alignment`
(`StartOffset + (RowIdx * [(Stride % Alignment) + Stride])`).

The `Alignment` must be at least `sizeof(ElTy)` otherwise the load behavior is
undefined.

Loading from or storing to a `groupshared` array takes the starting index, and
the row stride as a number of elements.

##### Orientation

When loading and storing WaveMatrix matrices a boolean parameter is provided to
indicate if the matrix being loaded or stored is column major. When false row
major orientation is assumed.

Matrices may be stored in row or column layout. Matrices are always loaded into
row-major orientation in memory for WaveMatrix objects. The `Load` and `Store`
methods perform matrix transposition when loading or storing column major
matrices.

##### Stride

When loading and storing from `groupshared` arrays, the stride is expressed in
number of elements, and signifies the number of elements between the first
element of each row for row major matrices or column for column major matrices.

When loading and storing from `[RW]ByteAddressBuffer` types, the stride is
expressed in bytes. The row stride must be a multiple of the size of the
element and greater than or equal to the size of the element multiplied by the
number of elements per row. Any value below the minimum legal values are
ignored. The behavior of row stride values that are not a multiple of element
stride is undefined.

#### WaveMatrix Left & Right

The code below approximately declares the base interface that WaveMatrixLeft and
WaveMatrixRight objects implement.

```c++
template <typename ElTy, int NRows, int NCols>
class WaveMatrixLeft : detail::WaveMatrixBase<ElTy, NRows, NCols> {
  uint MatrixDepth();
};

template <typename ElTy, int NRows, int NCols>
class WaveMatrixRight : detail::WaveMatrixBase<ElTy, NRows, NCols> {
  uint MatrixDepth();
};
```

`ElTy` must be either a 32 or 16 bit floating point type or an 8 bit packed
signed or unsigned integer type. `NRows` and `NCols` must be compile-time
constant expressions, and represent the number of rows and columns in the matrix
respectively.
 
##### WaveMatrix(Left|Right) MatrixDepth

The `MatrixDepth` method returns the hardware-dependent depth for the matrix
multiplication unit. The resulting value must be an multiple of 16.

### WaveMatrix Matrix Fragment Objects

The code below approximately declares the base interface that all WaveMatrix
fragment objects implement. A WaveMatrix fragment object stores a single row or
column of a WaveMatrix matrix.

```c++
namespace detail {
template <typename ElTy, int NRows, int NCols>
class WaveMatrixFragmentBase {
  void Fill(ElTy Val);

  void Load(ByteAddressBuffer Res, uint StartOffset, uint Stride,
            uint Align = 0);
  void Load(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
            uint Align = 0);

  void Load(groupshared ElTy Arr[], uint StartIdx, uint Stride);

  void Store(RWByteAddressBuffer Res, uint StartOffset, uint Stride,
             uint Align = 0);

  void Store(groupshared ElTy Arr[], uint StartIdx, uint Stride);
};
} // namespace detail
```

#### Loading and Storing WaveMatrix Fragment Objects

Values for WaveMatrix fragment objects can be loaded from and stored to
`[RW]ByteAddressBuffer` or `groupshared` array of type `ElTy`.

Loading from or storing to a `[RW]ByteAddressBuffer` takes a start offset in
bytes, element stride in bytes, and optional alignment in bytes. The alignment
must be at least `sizeof(ElTy)` otherwise the load behavior is undefined.

Loading from or storing to a `groupshared` array takes the starting index, and
the element stride as a number of elements.

##### Stride

When loading and storing from `groupshared` arrays, the stride is expressed in
number of elements.

When loading and storing from `[RW]ByteAddressBuffer` types the stride is
expressed in bytes and must be greater than or equal to the size of the element
type. Any value below the minimum legal values are ignored. The behavior of
stride values that are not a multiple of element size is undefined.

### WaveMatrix Accumulator Objects

The WaveMatrix Accumulator objects come in three forms which fall into two
categories: matrix accumulators and fragment accumulators. All accumulators
implement the interface below:

```c++
namespace detail {
template <typename ElTy, int NRows, int NCols, typename BaseT>
class WaveMatrixAccumulatorBase : BaseT<ElTy, NRows, NCols> {

  void ScalarMultiply(ElTy Value);
  void ScalarDivide(ElTy Value);
  void ScalarAdd(ElTy Value);
  void ScalarSubtract(ElTy Value);
};
} // namespace detail
```

Each of these operations performs the corresponding element-wise arithmetic
operation on the accumulator and the provided scalar value, storing the result
back into the accumulator.

### WaveMatrixAccumulator

```c++
namespace detail {
template <typename T>
struct is_8bit_packed_int_type =
    std::enable_if_t<(std::is_same<T, int8_t4_packed>::value ||
                      std::is_same<T, uint8_t4_packed>::value),
                     std::true_type>;

template <typename T> using is_8bit_packed_int_type = std::false_type;

template <typename T>
using is_32bit_int_type = std::enable_if_t<(std::is_same<T, int32_t>::value ||
                                             std::is_same<T, uint32_t>::value),
                                            std::true_type>;

template <typename T> using is_32bit_int_type = std::false_type;
} // namespace detail

template <typename ElTy, int NRows, int NCols>
class WaveMatrixAccumulator
    : WaveMatrixAccumulatorBase<ElTy, NRows, NCols, detail::WaveMatrixBase> {
  void Add(WaveMatrixLeftColAcc<ElTy, NRows, NCols> LeftMatrix);
  void Add(WaveMatrixRightRowAcc<ElTy, NRows, NCols> RightMatrix);
  void Add(WaveMatrixAccumulator<ElTy, NRows, NCols> Matrix);

  void Multiply(WaveMatrixLeft<ElTy, NRows, NCols> LHS,
                WaveMatrixRight<ElTy, NRows, NCols> RHS);
  void MultiplyAccumulate(WaveMatrixLeft<ElTy, NRows, NCols> LHS,
                          WaveMatrixRight<ElTy, NRows, NCols> RHS);

  template <typename MatElTy1, typename MatElTy2>
  std::enable_if_t<detail::is_32bit_int_type<ElTy> &&
                       detail::is_8bit_packed_int_type<MatElTy1> &&
                       detail::is_8bit_packed_int_type<MatElTy2>,
                   void>::type
  Multiply(WaveMatrixLeft<MatElTy1, NRows, NCols> LHS,
           WaveMatrixRight<MatElTy2, NRows, NCols> RHS);

  template <typename MatElTy1, typename MatElTy2>
  std::enable_if_t<detail::is_32bit_int_type<ElTy> &&
                       detail::is_8bit_packed_int_type<MatElTy1> &&
                       detail::is_8bit_packed_int_type<MatElTy2>,
                   void>::type
  MultiplyAccumulate(WaveMatrixLeft<MatElTy1, NRows, NCols> LHS,
                     WaveMatrixRight<MatElTy2, NRows, NCols> RHS);
};

```

#### Broadcast Add

The `WaveMatrixAccumulator::Add` methods perform an element-wise addition of an
accumulator matrix and the provided matrix or fragment accumulator.

If the argument is a fragment object, the `Add` method broadcasts the argument
accumulator up from an Mx1 or 1xN matrix to an MxN matrix then performs
element-wise addition.

#### WaveMatrixAccumulator::Multiply

The `WaveMatrixAccumulator::Multiply` method performs multiplication of the left
and right arguments and stores the result back into the `WaveMatrixAccumulator`.
This operation does not accumulate into the result, it overwrites the result.
This is a wave-level operation and cannot be used inside divergent control flow:
doing so results in undefined behavior.

For `Multiply` operations the matrix element types must match the accumulator
type unless the accumulator is a signed or unsigned 32-bit integer type. For
signed or unsigned 32-bit integer accumulators, signed or unsigned 8-bit packed
integers are also supported and can be mixed interchangeably.

#### WaveMatrixAccumulator::MultiplyAccumulate

The `WaveMatrixAccumulator::MultiplyAccumulate` method performs multiplication
of the left and right arguments and adds the result back into the
`WaveMatrixAccumulator`. This is a wave-level operation and cannot be used
inside divergent control flow: doing so results in undefined behavior.

For `MultiplyAccumulate` operations the matrix element types must match the
accumulator type unless the accumulator is a signed or unsigned 32-bit integer
type. For signed or unsigned 32-bit integer accumulators, signed or unsigned
8-bit packed integers are also supported and can be mixed interchangeably.

### WaveMatrix Fragment Accumulators

WaveMatrix intrinsics are defined to support quantization calculations.
Including calculating a sum for the rows of the left matrix and a sum of the
columns of the right matrix. The `WaveMatrixRightRowAcc` and
`WaveMatrixLeftColAcc` fragment accumulators perform this operation.

```c++
template <typename ElTy, int NRows, int NCols>
class WaveMatrixLeftColAcc
    : WaveMatrixAccumulatorBase<ElTy, NRows, NCols,
                                detail::WaveMatrixFragmentBase> {
  template <typename MatElTy>
  void SumAccumulate(WaveMatrixLeft<MatElTy, NRows, NCols> LeftMatrix);
};

template <typename ElTy, int NRows, int NCols>
class WaveMatrixRightRowAcc
    : WaveMatrixAccumulatorBase<ElTy, NRows, NCols,
                                detail::WaveMatrixFragmentBase> {
  void SumAccumulate(WaveMatrixRight<MatElTy, NRows, NCols> RightMatrix);
};
```

#### Wave Matrix Fragment SumAccumulate

The `SumAccumulate` methods accumulate the values of the argument matrix into
the WaveMatrix fragment accumulator. The fragment WaveMatrix must have the same
data type as the fragment accumulator.

This intrinsic is used to calculate
$(\sum_{i=0}^{K} A_{[x,i]})$ and $(\sum_{i=0}^{K} B_{[i,y]})$ from the
equation in the **Zero Point** section below.

For accumulating into a `WaveMatrixLeftColAcc`, this results in a row-wise sum
into the accumulator. For accumulating into a `WaveMatrixRightRowAcc`, this
results in a column-wise sum into the accumulator.

#### Zero Point

The following is the equation for matrix multiplication with zero point
adjustment included:

$C_{[x,y]} = (\sum_{i=0}^{K} A_{[x,i]} * B_{[i,y]}) - Z_a * (\sum_{i=0}^{K} B_{[i,y]}) - Z_b * (\sum_{i=0}^{K} A_{[x,i]}) + Z_a * Z_b * K$

$(\sum_{i=0}^{K} A_{[x,i]} * B_{[i,y]})$ is basic matrix multiplication.

$- Z_a * (\sum_{i=0}^{K} B_{[i,y]})$ is the zero point adjustment for matrix $A$

$- Z_b * (\sum_{i=0}^{K} A_{[x,i]})$ is the zero point adjustment for matrix $B$

$+ Z_a * Z_b * K$ is the static zero point adjustment for both matrix $A$ and $B$

$Z_*$ are constant zero points values

### DXIL Changes

### New DXIL Types

Wave Matrix adds a new opaque object type for interacting with Wave Matrix
objects.

```
%dx.types.waveMatrix = type { i8* }
```

Wave Matrix also adds a new property type for Wave Matrix objects.

```
%dx.types.waveMatProps = type { i8, i8, i32, i32 }
```
# New DXIL Opcodes

```
┌───────────────────────────────┬────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│             Name              │ opcode │                                                     IR Signature                                                      │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_Annotate            │ <TBD>  │void @dx.op.waveMatrix_Annotate(i32, %dx.types.waveMatrix*, %dx.types.waveMatProps)                                    │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_Depth               │ <TBD>  │i32 @dx.op.waveMatrix_Depth(i32, %dx.types.waveMatProps)                                                               │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_Fill                │ <TBD>  │void @dx.op.waveMatrix_Fill.<type>(i32, %dx.types.waveMatrix*, <type>)                                                 │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_LoadRawBuf          │ <TBD>  │void @dx.op.waveMatrix_LoadRawBuf(i32, %dx.types.waveMatrix*, %dx.types.Handle, i32, i32, i8, i1)                      │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_LoadGroupShared     │ <TBD>  │void @dx.op.waveMatrix_LoadGroupShared.<type>(i32, %dx.types.waveMatrix*, <type> addrspace(3)*, i32, i32, i1)          │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_StoreRawBuf         │ <TBD>  │void @dx.op.waveMatrix_StoreRawBuf(i32, %dx.types.waveMatrix*, %dx.types.Handle, i32, i32, i8, i1)                     │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_StoreGroupShared    │ <TBD>  │void @dx.op.waveMatrix_StoreGroupShared.<type>(i32, %dx.types.waveMatrix*, <type> addrspace(3)*, i32, i32, i1)         │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_Multiply            │ <TBD>  │void @dx.op.waveMatrix_Multiply(i32, %dx.types.waveMatrix*, %dx.types.waveMatrix*, %dx.types.waveMatrix*)              │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_MultiplyAccumulate  │ <TBD>  │void @dx.op.waveMatrix_Accumulate(i32, %dx.types.waveMatrix*, %dx.types.waveMatrix*)                                   │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_ScalarOp            │ <TBD>  │void @dx.op.waveMatrix_ScalarOp.<type>(i32, %dx.types.waveMatrix*, i8, <type>)                                         │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_SumAccumulate       │ <TBD>  │void @dx.op.waveMatrix_Accumulate(i32, %dx.types.waveMatrix*, %dx.types.waveMatrix*)                                   │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│waveMatrix_Add                 │ <TBD>  │void @dx.op.waveMatrix_Accumulate(i32, %dx.types.waveMatrix*, %dx.types.waveMatrix*)                                   │
└───────────────────────────────┴────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

## Acknowledgments

This spec was developed as an extensive collaboration between the Microsoft HLSL
and Direct3D teams and IHV partners.

Special thanks to:

Claire Andrews
Nick Feeney
Amar Patel
Tex Riddell
Greg Roth

<!-- {% endraw %} -->
