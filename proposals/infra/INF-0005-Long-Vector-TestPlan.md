# Test Plan

This test plan covers testing all HLSL intrinsics that can take long vectors as
parameters. And more specifically, it only covers testing scenarios which will
get coverage from a graphics driver supporting DXIL.

All tests are to be included in the HLK test binary which ships with the OS.
This test binary is only built in the OS repo and based off of the
ExecutionTests source code in the DXC repo. There is a script in the WinTools
repo which generates and annotates the HLK tests.

We break coverage down into five test categories:

1. Implement DXIL OpCode tests:
    * At the bottom of this document there is a table of all HLSL intrinsics and
    their mapped DXIL OpCodes as well as LLVM Instructions. For this first
    category we are concerned with getting coverage of each DXIL OpCode. In some
    cases there are multiple DXIL OpCodes listed. '[]' brackets are used to
    signify that the operator is only used in specific paths. Operators sharing
    the same brackets are in the same logic path. If an operator is not in
    brackets then it is used in all cases. Additonal opcodes are logic based,
    for example there may be an int and float specific opcode.

2. Implement LLVM Instruction tests:
    * These are the test cases for the LLVM Instructions listed in the in table
     at the bottom of this document.
    * Because we will use HLSL intrinsics to get coverage for the DXIL OpCode
       tests we speculate that we will get most of the coverage needed for the
       LLVM Instruction tests. After implementing the DXIL OpCode tests we
       should be able to do a coverage audit and ammend test cases, or write
       simple additional ones, as needed.
    * Just as in '1. Implement DXIL Intrinsic Tests' some cases have multiple
       instructions listed. '[]' brackets are used in the same manner. And there
       may also be multiple instructions.
    additional OpCodes/Instructions are logic based (i.e float or int specific).

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

5. 'Creative' test cases:
  * Sizes around alignments and boundaries (details in [Vector Sizes to
    Test])[#vector-sizes-to-test].
  * Odd number of elements in vector
  * Anything else that comes up? TBD here.

# Buffer types to test
* Raw Buffers (ByteAddressBuffer)
* Structured Buffers (StructuredBuffer)
* Typed Buffers (Buffer\<T>)

# Vector element data types to test
Testing will cover the following vector element data types:
* bool, int16_t, uint16_t, int32_t, uint32_t, int64_t, uint64_t, float16_t,
float32_t, float64_t, packed_int16_t, and packed_uint16_t.

# Vector sizes and alignments to test

General sizes to test are in the range [5, 1024]. It is worth noting that the
[new form of rawBufferLoad](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0030-dxil-vectors.md#changes-to-dxil-intrinsics)
will be updated to vectorize sizes < 5. Sizes < 5 are assumed to be covered by
existing test collateral.  As part of this work we verify that assumption.

Some noteable test sizes:

* 128 bit boundaries : Memory access for Shader Model 5.0 and earlier operate on
128-bit slots aligned on 128-bit boundaries. An example is vector<half, 7>,
vector<half, 8> and vector<half, 9>. 112 bits, 128 bits, and 144 bits
respectively. This boundary will tested for with 32-bit and 64-bit sized values
as well.
* vector<TYPE, 5> : Testing one above previous vector limit.
* vector<TYPE, 16> : This size of 'vector' previously only appeared as matrices.
* vector<TYPE, 17> : Larger than any vector previously possible.
* vector<TYPE, 1024> : The new max size of a vector. 
* These sizes will be tested across [Vector element data types to test](#vector-element-data-types-to-test)

Some noteable alignment cases:
* Most GPUs operate on at least 32-bits at once, so waht happens if you use
  16-bit values and an odd number of elements. Could accesssing the last element
  expose issues where we could overwrite the next variable is it is assuming
  alignment?
* Additional interesting cases TBD.

# Implementation phases
Do the test work in two simple phases.

1. Implement and validate (locally against WARP) for all test categories.
2. HLK related work:
  * Add a SM 6.9 HLK requirement. Includes updating the HLK requirements doc.
  * Update mm_annotate_shader_op_arith_table.py to annotate the new test cases
  with HLK GUIDS and requirements
  * Add new tests to HLK playlist

# Test Case Implementation Priorities
The following cases have been identified as the most important to validate
first.

* The following tests will be implemented first:
* Initializing a vector with another.
* Multiply all components of a vector with a scalar value
* Add all components of a vector with a scalar value
* Clamp all components of a vector to the range [c, t]
* Component wise minimum between 2 vectors
* Component wise maximum between 2 vectors
* Component wise multiply between 2 vectors
* Component wise add between 2 vectors
* Subscript access, vec[i] = c

# Shipping
Note that because DXC and the Agility SDK are both undocked from Windows it is
our normal operating behavior for the HLK tests to become available with a later
TBD OS release. The good news is that this doesn't prevent the tests from being
available much earlier in the DXC repo. It just means that they are simply TAEF
tests in the DXC repo. An HLK test includes an extra level of infrastructure for
test gating, selection, and result submission for WHQL signing of drivers.

1. Tests will be shared privately with IHV's along with the latest DXC and
latest Agility SDK for tesing and validation. IHVs will also be able to build
and run the tests from the public DXC repo themselves. If needed Microsoft can
share further instructions when the tests are available.

2. The tests will ship with the HLK at a TBD date in a later OS release.

# New HLK Tests
All of the scripts and yaml files mentioned are part of the Microsoft WinTools
repo. mm_annotate_shader_op_arith_table.py will need to be updated to recognize
any new tests (not test cases) added. And additional GUIDs added for new tests.
mm_annotate_shader_op_arith_table.py is called by mm-hlk-update.py when
converting from ExecutionTests to the HLK 'DxilConf' tests. The aforementioned
*table.py script is run by Integration.HLKTestsUpdate.yaml

# Test Validation Requirements
The following statements must be true and validated for this work to be
considered completed.
* All new test cases pass when run locally against a WARP device
* All new test cases must verify applicable outputs for correctness.
* All new test cases are confirmed to be present in HLK Studio and selectable to
* be run when a target device satisfies the HLK ShaderModel 6.9 requirement.
* All new tests/test cases are added to the official WHQL HLK playlist for the
* OS release that the HLK tests will ship with.
* Tests will be annoated to show which DXIL OpCode, LLVM Instructions, and HLSL
  operators they are intended to get coverage for.

# Requirements
* Greg's long vector changes:
  [HLSL Long Vector
  Spec](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0026-hlsl-long-vector-type.md#allowed-elementwise-vector-intrinsics)

* WARP long vector support (D3D, Jesse Natalie). Needs Greg's Long Vector work.
   ETA of ~1 week to implement. This item is a bit of a chicken and egg in that
   in order to fully validate the new test cases we will need WARP support. But
   at the same time in order to fully validate the WARP implementation Jesse
   will need our tests. We will need to work with Jesse to share our tests to
   help validate his implementation work.

# Notes
* Private test binaries/collateral will be shared with IHVs for validation
   purposes. This will enable IHVs to verify long vector functionality without
   waiting for an OS/HLK release.

### HLSL-Operators
# HLSL Operators
These operators should generate LLVM instructions which use vectors.

Operator table from [Microsoft HLSL Operators](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-operators)
| Operator Name | Operator | Notes |
|-----------|--------------|----------|
Additive and Multiplicative Operators | +, -, *, /, % |
Array Operator | [i] | llvm:ExtractElementInst
Assignment Operators | =, +=, -=, *=, /=, %= |
Bitwise Operators | ~, <<, >>, &, \|, ^, <<=, >>=, &=, \|=, ^= | Only valid on
||| int and uint vectors
Boolean Math Operators | & &, ||, ?: |
Cast Operator | (type) | No direct operator, difference in GetElementPointer 
||| or load type
Comparison Operators| <, >, ==, !=, <=, >= |
Prefix or Postfix Operators| ++, -- |
Unary Operators | !, -, + |

# Mappings of HLSL Intrinsics to DXIL OpCodes or LLVM Instructions

## Trigonometry

| Intrinsic | DXIL OpCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| acos      | Acos | | |
| asin      | Asin | | |
| atan      | Atan | | |
| atan2     | Atan | FDiv, FAdd, FSub, FCmpOLT,
||| FCpmOEQ, FCmpOGE, FCmpOLT, And, Select | |
| cos       | Cos | | |
| cosh      | Hcos | | |
| degrees   | | FMul ||
| radians   | | FMul ||
| sin       | Sin | | |
| sinh      | Hsin | | |
| tan       | Tan | | |
| tanh      | Htan | | |

## Math

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| abs       | [Imax], [Fabs] |
| ceil      | Round_pi ||
| clamp     | FMax, FMin, [UMax, UMin] , [IMax, Imin] | |
| exp       | Exp | |
| exp2      | Exp | |
| floor     | Round_ni ||
| fma       | Fma | |
| fmod      | FAbs, Frc | FDiv, FNeg, FCmpOGE,
||| Select, FMul | |
| frac      | rc | |
| frexp     | | FCmpUNE, SExt, BitCast, And, Add,
||| AShr, SIToFP, Store, And, Or | |
| ldexp     | Exp | FMul |  |
| lerp      | | FSub, FMul, FAdd | |
| log       | Log | FMul | |
| log10     | Log | FMul | |
| log2      | Log | |
| mad       | IMad | |
| max       | IMax | |
| min       | IMin | |
| pow       | [Log, Exp] | [FMul] , [FDiv] ||
| rcp       | | FDiv | |
| round     | Round_ne ||
| rsqrt     | Rsqrt | |
| sign      | | ZExt, Sub, [ICmpSLT], [FCmpOLT] | |
| smoothstep| Saturate | FMul, FSub, FDiv ||
| sqrt      | Sqrt | |
| step      | | FCmpOLT, Select ||
| trunc     | Round_z | |

## Float Ops

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| f16tof32  | LegacyF16ToF32 | |
| f32tof16  | LegacyF32ToF16 | |
| isfinite  | IsFinite | |
| isinf     | IsInf | |
| isnan     | IsNan | |
| modf      | Round_z | FSub, Store | |

## Bitwise Ops
| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| saturate  | Saturate | |
| reversebits| Bfrev | |
| countbits | Countbits | |
| firstbithigh| FirstbitSHi | |
| firstbitlow| FirstbitLo | |

## Logic Ops

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| and       | | And, [ExtractElement, InsertElement] | |
| or        | | Or, [ExtractElement, InsertElement] | |
| select    | | Select, [ExtractElement, InsertElement] | |

## Reductions

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| all       | | [FCmpUNE], [ICmpNE] ,
||| [ExtractElement, And] |
| any       | | [FCmpUNE], [ICmpNE] ,
||| [ExtractElement, Or] | |
| clamp     | [UMax, UMin], [IMax, IMin] | |
| dot       | | ExtractElement, Mul | |


## Derivative and Quad Operations

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| ddx       | DerivCoarseX | |
| ddx_coarse| DerivCoarseX | |
| ddx_fine  | DerivFineX | |
| ddy       | DerivCoarseY | |
| ddy_coarse| DerivCoarseY | |
| ddy_fine  | DerivFineY | |
| fwidth    | QuadReadLaneAt | |
| QuadReadLaneAcrossX | QuadOp | |
| QuadReadLaneAcrossY | QuadOp | |
| QuadReadLaneAcrossDiagonal | QuadOp | |

## WaveOps

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| WaveActiveBitAnd | WaveActiveBit | |
| WaveActiveBitOr  | WaveActiveBit | |
| WaveActiveBitXor | WaveActiveBit | |
| WaveActiveProduct| WaveActiveOp | |
| WaveActiveSum    | WaveActiveOp | |
| WaveActiveMin    | WaveActiveOp | |
| WaveActiveMax    | WaveActiveOp | |
| WaveMultiPrefixBitAnd | WaveMultiPrefixOp | |
| WaveMultiPrefixBitOr  | WaveMultiPrefixOp | |
| WaveMultiPrefixBitXor | WaveMultiPrefixOp | |
| WaveMultiPrefixProduct| WaveMultiPrefixOp | |
| WaveMultiPrefixSum    | WaveMultiPrefixOp | |
| WavePrefixSum         | WavePrefixOp | |
| WavePrefixProduct     | WavePrefixOp | |
| WaveReadLaneAt        | WaveReadLaneAt | |
| WaveReadLaneFirst     | WaveReadLaneFirst | |

## Wave Reductions

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| WaveActiveAllEqual | WaveActiveAllEqual | |
| WaveMatch          | WaveMatch | |

## Type Casting Operations

| Intrinsic | DXIL OPCode | LLVM Instruction | Notes |
|-----------|--------------|----------|-----------|
| WaveActiveAllEqual | WaveActiveAllEqual | |
| WaveMatch          | WaveMatch | |
| asdouble           | MakeDouble | |
| asfloat            |  | BitCast |
| asfloat16          |  | BitCast |
| asint              |  | BitCast |
| asint16            |  | BitCast |
| asuint             | SplitDouble | |
| asuint16           | | BitCast |