# Test Plan

All tests are to be included in the HLK test binary which ships with the OS.
This test binary is only built in the OS repo and based off of the 'ExecTests'
'ExecTests' source code in the DXC repo. There is a script in the WinTools repo
which generates and annotates the HLK tests.

There are three test categories we are concerned with:

1. Implement DXIL Intrinsic tests:
    - At the bottom of this document there is a table of all HLSL intrinsics and
    their mapped DXIL OpCodes. We just need coverage for each DXIL OpCode. If the
    DXIL OpCode column lists 'emulated' then this means that there are multiple
    LLVM/DXIL Ops used to compute the intrinsic. We will need to do an audit of
    them to confirm coverage of all vector ops.

2. Implement LLVM Native operation tests:
     - These are the test cases for the 'basic' HLSL operators listed in the HLSL
     operators table below.
     - We have added some test cases for these with the long vectors work, but we
     will want to make sure we add HLK coverage for all of these.

3. Standard loading and storing of long vectors
     - Ensure we have some basic tests doing standard loading/storing of long vectors.

# Vector Sizes to test

I don't think there are any particularly interesting vector sizes to test. So I
propose testing sizes of 5, 25, 100, 500. Sizes < 5 are assumed to already be
covered by existing test collateral. But, as part of this work we will verify that
assumption.

# Implementation phases
Do the test work in two simple phases.

1. Implement and validate (locally against WARP) the 3 test categories.
2. HLK related work:
     - Add a SM 6.9 HLK requirement. Includes updating the HLK requirements doc.
     - Update mm_annotate_shader_op_arith_table.py to annotate the new test cases
        with HLK GUIDS and requirements
     - Add new tests to HLK playlist

# Shipping
1. Tests will be shared privately with IHV's along with the latest DXC and
latest Agility SDK for tesing and validation.

2. The tests will ship with the HLK at a TBD date in a later OS release.

# New HLK Tests
mm_annotate_shader_op_arith_table.py (WinTools repo) will need to be updated to
recognize any new tests (not test cases) added. And additional GUIDs added for new
test cases. mm_annotate_shader_op_arith_table.py is called by mm-hlk-update.py when
converting from 'ExecTests' to the HLK 'DxilConf' tests. The aforementioned
*table.py script is run by Integration.HLKTestsUpdate.yaml

# Test Validation Requirements
The following statements must be true and validated for this work to be considered
completed.
 - All new test cases pass when run locally against a WARP device
 - All new test cases are confirmed to be lit up and available in the HLK when the
    target device reports support
 - All new tests/test cases are added to the HLK playlist

# Requirements
     - Greg's long vector changes. Check-in ETA of 3/7/25.
     - WARP long vector support (Jesse). Needs Greg's work, or a private WIP branch
        of Greg's work. ETA of ~1 week to implement.

# Notes
     - The 'ExecTests' (ExecutionTest.cpp) are used to generate the HLK tests (DxilConf
        tests)
     - Private test binaries/collateral will be shared with IHVs for validation
        purposes. This will enable IHVs to verify long vector functionality without
        waiting for an OS/HLK release.

# Open Questions
     - We speculate that the combiniation of test cases for HLSL operators and
     HLSL intrinsics which map to DXIL ops should get us all, or most of the
     coverage required for the 'emulated' intrinsics. But we should audit that.

# HLSL Operators
These operatores should generate LLVM native ops which use vectors.

| Operator Name | Operator | Notes |
|-----------|--------------|----------|
Additive and Multiplicative Operators | +, -, *, /, % |
Array Operator | [i] |
Assignment Operators | =, +=, -=, *=, /=, %= |
Binary Casts | C rules for float and int, C rules or HLSL intrinsics for bool |
Bitwise Operators | ~, <<, >>, &, \|, ^, <<=, >>=, &=, \|=, ^= | Only valid on int and uint vectors
Boolean Math Operators | & &, ||, ?: |
Cast Operator | (type) |
Comma Operator | , |
Comparison Operators| <, >, ==, !=, <=, >= |
Prefix or Postfix Operators| ++, -- |
Structure Operator | . |
Unary Operators | !, -, + |

# Mappings of HLSL intrinsics to DXIL opcodes or LLVM native operations

## Trigonometry

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|----------|
| acos      | DXIL::OpCode::Acos |  |
| asin      | DXIL::OpCode::Asin |  |
| atan      | DXIL::OpCode::Atan |  |
| atan2     | Emulated |            |
| cos       | DXIL::OpCode::Cos |   |
| cosh      | DXIL::OpCode::Hcos |  |
| degrees   | Emulated |            |
| radians   | Emulated |            |
| sin       | DXIL::OpCode::Sin |   |
| sinh      | DXIL::OpCode::Hsin |  |
| tan       | DXIL::OpCode::Tan |   |
| tanh      | DXIL::Opcode::Htan |  |

## Math

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|----------|
| mod       | Emulated |              |
| abs       | DXIL::OpCode::Imax |    |
| ceil      | DXIL::OpCode::Round_pi ||
| clamp     | DXIL::OpCode::UMax, UMin \ DXIL::OpCode::FMax/Fmin \ DXIL::OpCode::IMax/Imin ||
| exp       | DXIL:OpCode::Exp |      |
| exp2      | DXIL::OpCode::Exp |     |
| floor     | DXIL::OpCode::Round_ni ||
| fma       | DXIL::OpCode::Fma |     |
| fmod      | Emulated |              |
| frac      | DXIL::OpCode::Frc |     |
| frexp     | Emulated |              |
| ldexp     | Emulated: CreateFMul |  |
| lerp      | Emulated: CreateFAdd |  |
| log       | Emulated: CreateFMul |  |
| log10     | Emulated: CreateFMul |  |
| log2      | DXIL::OpCode::Log |     |
| mad       | DXIL::OpCode::IMad |    |
| max       | DXIL::OpCode::IMax |    |
| min       | DXIL::OpCode::IMin |    |
| pow       | Emulated: CreateFMul or CreateFDiv ||
| rcp       | Emulated: CreateFDiv |  |
| round     | DXIL::OpCode::Round_ne ||
| rsqrt     | DXIL::OpCode::Rsqrt |   |
| sign      | Emulated: CreateSub |   |
| smoothstep| Emulated: CreateFMul, CreateFSub ||
| sqrt      | DXIL::OpCode::Sqrt |    |
| step      | Emulated: CreateSelect ||
| trunc     | DXIL::OpCode::Round_z | |

## Float Ops

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-----------|
| f16tof32  | DXIL::OpCode::LegacyF16ToF32 | |
| f32tof16  | DXIL::OpCode::LegacyF32ToF16 | |
| isfinite  | DXIL::OpCode::IsFinite | |
| isinf     | DXIL::OpCode::IsInf | |
| isnan     | DXIL::OpCode::IsNan | |
| modf      | Emulated | |

## Bitwise Ops
| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-------------|
| saturate  | DXIL::OpCode::Saturate | |
| reversebits| DXIL::OpCode::Bfrev | |
| countbits | DXIL::OpCode::Countbits | |
| firstbithigh| DXIL::OpCode::FirstbitSHi | |
| firstbitlow| DXIL::OpCode::FirstbitLo | |

## Logic Ops

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-----------|
| and       | Emulated | |
| or        | Emulated | |
| select    | Emulated | |

## Reductions

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-----------|
| all       | Emulated | |
| any       | Emulated | |
| clamp     | Emulated | |
| dot       | Emulated | |

## Derivative and Quad Operations

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-----------|
| ddx       | DXIL::OpCode::DerivCoarseX | |
| ddx_coarse| DXIL::OpCode::DerivCoarseX | |
| ddx_fine  | DXIL::OpCode::DerivFineX | |
| ddy       | DXIL::OpCode::DerivCoarseY | |
| ddy_coarse| DXIL::OpCode::DerivCoarseY | |
| ddy_fine  | DXIL::OpCode::DerivFineY | |
| fwidth    | DXIL::OpCode::QuadReadLaneAt | |
| QuadReadLaneAcrossX | DXIL::OpCode::QuadOp | |
| QuadReadLaneAcrossY | DXIL::OpCode::QuadOp | |
| QuadReadLaneAcrossDiagonal | DXIL::OpCode::QuadOp | |

## WaveOps

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-------------|
| WaveActiveBitAnd | DXIL::OpCode::WaveActiveBit | |
| WaveActiveBitOr  | DXIL::OpCode::WaveActiveBit | |
| WaveActiveBitXor | DXIL::OpCode::WaveActiveBit | |
| WaveActiveProduct| DXIL::OpCode::WaveActiveOp | |
| WaveActiveSum    | DXIL::OpCode::WaveActiveOp | |
| WaveActiveMin    | DXIL::OpCode::WaveActiveOp | |
| WaveActiveMax    | DXIL::OpCode::WaveActiveOp | |
| WaveMultiPrefixBitAnd | DXIL::OpCode::WaveMultiPrefixOp | |
| WaveMultiPrefixBitOr  | DXIL::OpCode::WaveMultiPrefixOp | |
| WaveMultiPrefixBitXor | DXIL::OpCode::WaveMultiPrefixOp | |
| WaveMultiPrefixProduct| DXIL::OpCode::WaveMultiPrefixOp | |
| WaveMultiPrefixSum    | DXIL::OpCode::WaveMultiPrefixOp | |
| WavePrefixSum         | DXIL::OpCode::WavePrefixOp | |
| WavePrefixProduct     | DXIL::OpCode::WavePrefixOp | |
| WaveReadLaneAt        | DXIL::OpCode::WaveReadLaneAt | |
| WaveReadLaneFirst     | DXIL::OpCode::WaveReadLaneFirst | |

## Wave Reductions

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-------------|
| WaveActiveAllEqual | DXIL::OpCode::WaveActiveAllEqual | |
| WaveMatch          | DXIL::OpCode::WaveMatch | |

## Type Casting Operations

| Intrinsic | DXIL OPCode | Notes |
|-----------|--------------|-----------|
| WaveActiveAllEqual | DXIL::OpCode::WaveActiveAllEqual | |
| WaveMatch          | DXIL::OpCode::WaveMatch | |
| asdouble           | DXIL::OpCode::MakeDouble | |
| asfloat            | Emulated | |
| asfloat16          | Emulated | |
| asint              | Emulated | |
| asint16            | Emulated | |
| asuint             | DXIL::OpCode::SplitDouble | |
| asuint16           | Emulated | |