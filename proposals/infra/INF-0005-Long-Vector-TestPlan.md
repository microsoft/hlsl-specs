# Test Plan
There are three test categories we are concerned with:

1. DXIL Intrinsic tests: Go through the operators that support vectors and make a
    list of the DXIL ops used.
     - The table to reference for this is in HLOperationLower.cpp.
     - Many, if not all, of these probably have existing test cases that just need
        to be modified to use vectors
          - I think that the 'implementation' will largely be editing
             ShaderOpArithTable.xml, which is used to generate TAEF 'data driven'
             tests. Minor shader code updates and added input/output of vectors
     - Some tests may need to be duplicated for the vector variant of the test.
     - The tests cases in this category are any intrinsics in the below table that
        have a DXIL::OpCode::* in the DXIL OPCode column

2. LLVM Native operation tests
     - TBD: Where do we test these? Tex mentioned some existing tests but it sounds
        like we don't want to use those. And they aren't HLK tests anyways.
     - TODO: Discuss how we want to test ops that don't boil down to a single DXIL
        op. Still seems like something we should test in the HLK?

3. Standard loading and storing of long vectors
     - TODO: Do we have tests that do this today?

# Vector Sizes to test

I don't think there are any particularly interesting vector sizes to test. So I
propose testing sizes of 5, 25, 100, 500. Sizes < 5 are assumed to already be
covered by existing test collateral. But, as part of this work we will verify that
assumption.

# Phases
Do the test work in two simple phases.

1. Implement and validate (locally against WARP) the 3 test categories.
2. HLK related work:
     - Add a SM 6.9 HLK requirement. Includes updating the HLK requirements doc.
     - Update mm_annotate_shader_op_arith_table.py to annotate the new test cases
        with HLK GUIDS and requirements
     - Add new tests to HLK playlist
     - Note: Test binaries/collateral will be shared with IHVs for validation
        purposes.

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
     -

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