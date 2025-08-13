# Long Vector Execution Test Plan

* Proposal: [0006](INF-0006-Long-Vector-ExecutionTest-Plan.md)
* Author(s): [Alex Sepkowski](https://github.com/alsepkow)
* Sponsor: [Alex Sepkowski](https://github.com/alsepkow)
* Status: **Accepted**
* Impacted Projects: DXC

## Introduction

This test plan covers testing all HLSL intrinsics that can take long vectors as
parameters. And more specifically, it only covers testing scenarios which will
get coverage from a graphics driver supporting DXIL.

These tests will verify that all DXIL opcodes and LLVM instructions which can be
reached using valid HLSL in SM 6.9 can compile, run, and produce correct output
when given long and native vector inputs. They will not verify that the
generated DXIL is vectorized.

All tests are to be included in the HLK test binary which ships with the OS.
This test binary is only built in the OS repo and based off of the
ExecutionTests source code in the DXC repo. There is a script in the WinTools
repo which generates and annotates the HLK tests.

We break coverage down into five test categories.

1. Implement DXIL OpCode tests:
    * At the bottom of this document there are [tables](#hlsl-operators)
      containing all HLSL operators (more on those in '3. HLSL Operator Tests')
      and HLSL intrinsics that can be used with long vectors. The HLSL
      intrinsics tables have a DXIL OpCode and LLVM instruction columns. These
      columns contain the intrinsic's mapped DXIL OpCodes as well as their
      LLVM instructions. All intrinsics have at least one DXIL OpCode or one
      LLVM instruction.

      Many intrinsics have trivial mappings. [Atan](#trigonometry) is an
      example of an intrinsic with a trivial mapping. Other intrinsics have
      multiple DXIL OpCodes. Some intrinsics will use all listed DXIL OpCodes
      and/or LLVM instructions, while others will have additional logic which
      determines which OpCodes/Instructions are used. If an intrinsic relies on
      additional logic to determine which OpCodes/Instructions are used then the
      OpCode/Instructions will be enclosed in '[]' brackets. The [sign](#math)
      intrinsic is an example of an intrinsic with additional logic. If an
      OpCode/Instruction is not enclosed in '[]' then it is used in all paths
      for that intrinsic.

2. Implement LLVM Instruction tests:
    * These are the test cases for the LLVM Instructions listed in the table
     at the bottom of this document.
    * Because we will use HLSL intrinsics to get coverage for the DXIL OpCode
       tests we speculate that we will get most of the coverage needed for the
       LLVM Instruction tests. After implementing the DXIL OpCode tests we
       should be able to do a coverage audit and ammend test cases, or write
       simple additional ones, as needed.
    * Just as in '1. Implement DXIL OpCode Tests' some cases have multiple
       instructions listed. '[]' brackets are used in the same manner. And there
       may also be multiple instructions.
    * Additional OpCodes/Instructions are logic based (i.e float or int specific).

3. HLSL Operator tests:
    * [HLSL Operators Table](#hlsl-operators) in this document lists the HLSL
      Operators which can take long vectors as arguments.
    * Many of these operators can and will get coverage by default in the DXIL
      OpCode tests. But we will audit coverage and ammend test case, or write
      simple additional ones, as needed.

4. Standard loading and storing of long vectors
    * These could be covered in test categories 1 and 2. But I propose we break
      out individual cases to ensure that we have more granular coverage.
    * Ensure we have some basic tests doing standard loading/storing of long
     vectors across [Buffer types to test](#buffer-types-to-test) and [Vector
     element data types to test](#vector-element-data-types-to-test).
    * Additionally, the above buffer types and data types should be tested by
      loading from a [ResourceDescriptorHeap](https://microsoft.github.io/DirectX-Specs/d3d/HLSL_SM_6_6_DynamicResources.html)

5. 'Creative' test cases:
    * Sizes around alignments and boundaries. See [Vector sizes and alignments](#vector-sizes-and-alignments-to-test)
    * Odd (non even) number of elements in vector. See [Test Sizes](#test-sizes)

## Buffer types to test

* Raw Buffers (Byte Address Buffers)
* Structured Buffers (StructuredBuffer\<T>)

## Vector element data types to test

Testing will cover the following vector element data types:

* bool, int16_t, uint16_t, int32_t, uint32_t, int64_t, uint64_t, float16_t,
float32_t, float64_t, packed_int16_t, and packed_uint16_t.

## Vector sizes and alignments to test

General sizes to test are in the range [3, 1024]. It is worth noting that the
[new form of rawBufferLoad](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0030-dxil-vectors.md#changes-to-dxil-intrinsics)
will be updated to vectorize sizes < 5.

## Test sizes

* vector<TYPE, 3> : Testing one below previous vector limit. Early testing found
  some issues here so it was added.
* vector<TYPE, 4> : Previous limit.
* vector<TYPE, 5> : Testing one above previous vector limit.
* vector<TYPE, 16> : This size of 'vector' previously only appeared as matrices.
* vector<TYPE, 17> : Larger than any vector previously possible.
* vector<TYPE, 35> : Arbitrarily picked.
* vector<TYPE, 100> : Arbitrarily picked.
* vector<TYPE, 256> : Arbitrarily picked.
* vector<TYPE, 1024> : The new max size of a vector.
* These sizes will be tested across [Vector element data types to test](#vector-element-data-types-to-test)

## Some noteable alignment cases

* 128 bit boundaries : Memory access for Shader Model 5.0 and earlier operate on
128-bit slots aligned on 128-bit boundaries. An example is vector<half, 7>,
vector<half, 8> and vector<half, 9>. 112 bits, 128 bits, and 144 bits
respectively. This boundary will tested for with 32-bit and 64-bit sized values
as well.

* Most GPUs operate on at least 32-bits at once, so what happens if you use
  16-bit values and an odd number of elements. Could accessing the last element
  expose issues where we could overwrite the next variable if it is assuming
  alignment?

## High level test design

1. The test will leverage the existing XML infrastructure currently used by the
   existing execution tests. There are two XML files. This general design
   pattern exists today in the execution tests.

   * 1st XML: Used to define shader source code and metadata about that shader
   code. This XML file is parsed using a private class. This private class helps
   facilitate creation of D3D resources and execution of the shader.
   * 2nd XML: Describes metadata about the specific test cases. Used by the
   TAEF infrastructure for [TAEF Data Driven
   Testing](https://learn.microsoft.com/en-us/windows-hardware/drivers/taef/data-driven-testing)
2. Test inputs will be hard coded in a c++ header file. This was chosen over
   definining inputs in the second XML as this is cleaner and easier to parse
   for different data types. This c++ header method also avoids needing to
   repeat the data set in the XML for each individual test cast. Inputs will use
   'value sets' which will typically be much smaller than the desired vector
   test size. Values will be repeated cyclically until the vector is full. For
   example, a value set `{1, 2, 3}` used to populate a `vector<int, 1024>` will
   produce the pattern `<1, 2, 3, 1, 2, 3, ...>`, repeating the sequence until
   all 1024 elements are filled. This approach provides predictable test data
   while keeping input definitions manageable.
3. Expected outputs are computed for each test case at run time.
4. All new long vector test code is factored out into its own files.

## Implementation phases

Do the test work in two simple phases.

1. Implement and validate (locally against WARP) for all test categories.
2. HLK related work:

* Add a SM 6.9 HLK requirement. Includes updating the HLK requirements doc.
* Update mm_annotate_shader_op_arith_table.py to annotate the new test cases
  with HLK GUIDS and requirements
* Add new tests to HLK playlist

## Shipping

Note that because DXC and the Agility SDK are both undocked from Windows it is
our normal operating behavior for the HLK tests to become available with a later
TBD OS release. The good news is that this doesn't prevent the tests from being
available much earlier in the DXC repo. It just means that they are simply TAEF
tests in the DXC repo. An HLK test includes an extra level of infrastructure for
test gating, selection, and result submission for WHQL signing of drivers.

1. Tests will be shared privately with IHVs along with the latest DXC and
latest Agility SDK for testing and validation. IHVs will also be able to build
and run the tests from the public DXC repo themselves. If needed Microsoft can
share further instructions when the tests are available.

2. The tests will ship with the HLK at a TBD date in a later OS release.

## Test Validation Requirements

The following statements must be true and validated for this work to be
considered completed.

* All new test cases pass when run locally against a WARP device
* All new test cases must verify applicable outputs for correctness.
* All new test cases are confirmed to be present in HLK Studio and selectable to
  be run when a target device satisfies the HLK ShaderModel 6.9 requirement.
* All new tests/test cases are added to the official WHQL HLK playlist for the
  OS release that the HLK tests will ship with.
* Tests will be annoated to show which DXIL OpCode, LLVM Instructions, and HLSL
  operators they are intended to get coverage for.

## Notes

* Private test binaries/collateral will be shared with IHVs for validation
   purposes. This will enable IHVs to verify long vector functionality without
   waiting for an OS/HLK release.

## HLSL-Operators
✅ - Means there was an explicit test case implemented for the intrinsic.
☑️ - Means the intrinsic gets coverage via other intrinsics. For example 'exp2'
just uses the DXIL Opcode for Exp. 

### HLSL Operators

These operators generate LLVM instructions which use vectors.

Operator table from [Microsoft HLSL Operators](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators)

| Completed | Operator Name | Operator | Notes |
|---|-----------|--------------|----------|
| ✅ | Addition | + | |
| ✅ | Subtraction | - | |
| ✅ | Multiplication | * | |
|   | Additive and Multiplicative Operators | +, -, *, /, % | |
|   | Array Operator | [i] | llvm:ExtractElementInst OR llvm:InsertElemtInst |
|   | Assignment Operators | =, +=, -=, *=, /=, %= | |
|   | Bitwise Operators | ~, <<, >>, &, \|, ^, <<=, >>=, &=, \|=, ^= | Only valid on int and uint vectors |
|   | Boolean Math Operators | & &, \|\| , ?: | |
|   | Cast Operator | (type) | No direct operator, difference in GetElementPointer  or load type |
|   | Comparison Operators | <, >, ==, !=, <=, >= | |
|   | Prefix or Postfix Operators | ++, -- | |
|   | Unary Operators | !, -, + | |

## Mappings of HLSL Intrinsics to DXIL OpCodes or LLVM Instructions

### Trigonometry

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
| ✅ | acos      | Acos | | Unary | range: -1 to 1 |
| ✅ | asin      | Asin | | Unary | range: -pi/2 to pi/2. Floating point types only. |
| ✅ | atan      | Atan | | Unary | range: -pi/2 to pi/2. |
| ✅ | cos       | Cos | | Unary | no range requirements. |
| ✅ | cosh      | Hcos | | Unary | no range requirements. |
| ✅ | sin       | Sin | | Unary | no range requirements. |
| ✅ | sinh      | Hsin | | Unary | no range requirements. |
| ✅ | tan       | Tan | | Unary | no range requirements. |
| ✅ | tanh      | Htan | | Unary | no range requirements. |
| ✅ | atan2     | Atan | FDiv, FAdd, FSub, FCmpOLT, FCmpOEQ, FCmpOGE, FCmpOLT, And, Select | Unary | Not required. |

### Math

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
| ✅ | abs       | [Imax], [Fabs] | | Unary | Imax for ints. Fabs for floats. |
| ✅ | ceil      | Round_pi | | Unary | |
| ✅ | exp       | Exp | | Unary | |
| ✅ | floor     | Round_ni | | Unary | |
|   | fma       | Fma | | Ternary | All three inputs are of the same type. Any inputs that are long vectors must have the same number of dimensions. |
| ✅ | frac      | rc | | Unary | |
|   | frexp     | | FCmpUNE, SExt, BitCast, And, Add, AShr, SIToFP, Store, And, Or | Unary | Has a return value in addition to an output parameter. |
| ☑️ | ldexp     | Exp | FMul | Binary | Not required. Covered by floating point multiplication and exp. |
| ☑️ | lerp      | | FSub, FMul, FAdd | Ternary | Not required. FSub, FMul, and FAdd are all well covered. |
| ✅ | log       | Log | FMul | Unary | All three inputs are of the same type. Any inputs that are long vectors must have the same number of dimensions. |
|   | mad       | IMad | | Ternary | |
| ✅ | max       | IMax | | Binary | |
| ✅ | min       | IMin | | Binary | |
| ☑️ | pow       | [Log, Exp] | [FMul] , [FDiv] | Binary | Not required. Ops well covered by other tests. |
| ☑️ | rcp       | | FDiv | Unary | Not required. Covered by floating point division. |
| ✅ | round     | Round_ne | | Unary | |
| ✅ | rsqrt     | Rsqrt | | Unary | |
| ✅ | sign      | | ZExt, Sub, [ICmpSLT], [FCmpOLT] | Unary | |
|   | smoothstep| Saturate | FMul, FSub, FDiv | Ternary | |
| ✅ | sqrt      | Sqrt | | Unary | |
| ☑️ | step      | | FCmpOLT, Select | Binary | Not required. FCmpOLT covered by atan2 and sign. Select covered by explicit select test. |
| ✅ | trunc     | Round_z | | Unary | |
| ☑️ | clamp     | FMax, FMin, [UMax, UMin] , [IMax, Imin] | | Ternary | Not required. Covered by min and max. |
| ☑️ | exp2      | Exp | | Unary | Not required. Covered by exp. |
| ☑️ | log10     | Log | FMul | Unary | Not required. Covered by log.|
| ☑️ | log2      | Log | | Unary | Not required. Covered by log.|

### Float Ops

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
|   | f16tof32  | LegacyF16ToF32 | | | Unary |
|   | f32tof16  | LegacyF32ToF16 | | | Unary |
|   | isfinite  | IsFinite | | | Unary |
|   | isinf     | IsInf | | | Unary |
|   | isnan     | IsNan | | | Unary |
|   | modf      | Round_z | FSub, Store | Has a return value and an ouput value. | Unary |
|   | fmod      | FAbs, Frc | FDiv, FNeg, FCmpOGE, Select, FMul | | Binary |

### Bitwise Ops

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
|   | saturate  | Saturate | | | Unary |
|   | reversebits| Bfrev | | | Unary |
|   | countbits | Countbits | | | Unary |
|   | firstbithigh| FirstbitSHi | | | Unary |
|   | firstbitlow| FirstbitLo | | | Unary |

### Logic Ops

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
|   | select    | | Select, [ExtractElement, InsertElement] | | Ternary |
|   | and       | | And, [ExtractElement, InsertElement] | Not required. Covered by select. | Binary |
|   | or        | | Or, [ExtractElement, InsertElement] | Not required. Covered by select. | Binary |

### Reductions

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
|   | all       | | [FCmpUNE], [ICmpNE] , [ExtractElement, And] | | Unary |
|   | any       | | [FCmpUNE], [ICmpNE] , [ExtractElement, Or] | | Unary |
|   | dot       | | ExtractElement, Mul | | Binary |

### Derivative and Quad Operations

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
|   | ddx       | DerivCoarseX | | | Unary |
|   | ddx_fine  | DerivFineX | | | Unary |
|   | ddy       | DerivCoarseY | | | Unary |
|   | ddy_fine  | DerivFineY | | | Unary |
|   | fwidth    | QuadReadLaneAt | | | Unary |
|   | QuadReadLaneAcrossX | QuadOp | | | Unary |
|   | QuadReadLaneAcrossY | QuadOp | | Uses different QuadOp parameters leading to different behavior. | Unary |
|   | QuadReadLaneAcrossDiagonal | QuadOp | | Uses different QuadOp parameters leading to different behavior. | Unary |
|   | ddx_coarse| DerivCoarseX | | Not required. Covered by ddx | Unary |
|   | ddy_coarse| DerivCoarseY | | Not requried. Covered by ddy | Unary |

### WaveOps

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
|   | WaveActiveBitAnd      | WaveActiveBit | | | Binary |
|   | WaveActiveBitOr       | WaveActiveBit | | | Binary |
|   | WaveActiveBitXor      | WaveActiveBit | | | Binary |
|   | WaveActiveProduct     | WaveActiveOp | | | Binary |
|   | WaveActiveSum         | WaveActiveOp | | | Binary |
|   | WaveActiveMin         | WaveActiveOp | | | Binary |
|   | WaveActiveMax         | WaveActiveOp | | | Binary |
|   | WaveMultiPrefixBitAnd | WaveMultiPrefixOp | | | Binary |
|   | WaveMultiPrefixBitOr  | WaveMultiPrefixOp | | | Binary |
|   | WaveMultiPrefixBitXor | WaveMultiPrefixOp | | | Binary |
|   | WaveMultiPrefixProduct| WaveMultiPrefixOp | | | Binary |
|   | WaveMultiPrefixSum    | WaveMultiPrefixOp | | | Binary |
|   | WavePrefixSum         | WavePrefixOp | | | Binary |
|   | WavePrefixProduct     | WavePrefixOp | | | Binary |
|   | WaveReadLaneAt        | WaveReadLaneAt | | | Binary |
|   | WaveReadLaneFirst     | WaveReadLaneFirst | | | Unary |
|   | WaveActiveAllEqual    | WaveActiveAllEqual | | | Unary |
|   | WaveMatch             | WaveMatch | | | Unary |

### Type Casting Operations

| Completed  | Intrinsic | DXIL OpCode | LLVM Instruction | Basic Op Type | Notes |
|---|-----------|--------------|------------------|----------------|-----------|
| ✅ | asdouble           | MakeDouble  | | | Binary |
| ✅ | asfloat            | | BitCast | | Unary |
| ✅ | asfloat16          | | BitCast | | Unary |
| ✅ | asint              | | BitCast | | Unary |
| ✅ | asint16            | | BitCast | | Unary |
| ✅ | asuint (from double) | SplitDouble | Returns void. Has two output arguments. | Converts double to two uints | Binary |
| ✅ | asuint (bitcast)     | | BitCast | Bitcast from float/int to uint | Unary |
| ✅ | asuint16           | | BitCast | | Unary |
