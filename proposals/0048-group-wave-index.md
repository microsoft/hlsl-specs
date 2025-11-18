---
title: "0048 - Group Wave Index"
params:
    authors:
    - MartinAtXbox: Martin Fuller
    - damyanp: Damyan Pepper
    - JoeCitizen: Jack Elliott
    sponsors:
    - JoeCitizen: Jack Elliott
    status: Under Consideration
---

* Planned Version: Shader Model 6.10
* Issues: [#645](https://github.com/microsoft/hlsl-specs/issues/645)

## Introduction

The proposal is for two new shader intrinsics:

* `WaveGetGroupIndex()`: returns the index of the wave in the thread group
* `WaveGetCount()`: returns the number of waves executing the thread group

## Motivation

Compute, Amplification and Mesh shader workloads consist of some number of 
thread groups, with each thread group containing some number of waves and there 
being a number of threads in the wave. Certain algorithms can be accelerated by
 specializing work done by individual waves in a thread group.

Currently, developers on PC cannot efficiently determine which wave they're in
within a thread group, nor can they determine how many waves are executing the
thread group without resorting to unsafe workarounds like
`uint groupWaveIndex = SVGroupIndex / WaveGetLaneCount()` and
`uint waveCount = (TGSize + WaveGetLaneCount() - 1) / WaveGetLaneCount()`,
which are not guaranteed to be correct across all hardware implementations and
thread group dimensions. This forces developers to either write divergent code
paths for different platforms or use slightly less efficient alternatives
involving atomic operations on thread local memory for example.

## Proposed solution

This proposal introduces two new intrinsic functions:

1. `WaveGetGroupIndex()`: Returns the index of the current wave within the 
   thread group. This value ranges from 0 to N-1, where N is the number of 
   waves in the thread group.
2. `WaveGetCount()`: Returns the number of waves executing the thread group.
   This value is at least `ceil(threadGroupSize / WaveGetLaneCount())` but may
   be larger if the implementation chooses to launch additional waves for
   hardware efficiency.

### Example Usage

```hlsl
#define TILE_SIZE 16

[numthreads(TILE_SIZE, TILE_SIZE, 1)]
void ComputeMinMaxZ(
    uint2 tileID : SV_GroupID)
{
    uint waveIndex = WaveGetGroupIndex();
    uint waveCount = WaveGetCount();
    
    float z = LoadDepth(tileID, waveIndex);
    float minZ = WaveActiveMin(z);
    float maxZ = WaveActiveMax(z);
    
    // Collaborate between waves using wave index
    if (waveIndex == 0)
    {
        // First wave performs final reduction
        GroupMemoryBarrierWithGroupSync();
        // ... combine results from all waves
    }
}
```

This solution enables:

1. **Wave-level collaboration**: Different waves within a thread group can
perform different tasks and coordinate their work efficiently.
2. **Portable code**: A single code path works across all wave sizes without
   conditionals on `WaveGetLaneCount()`.

## Detailed design

### HLSL Additions

#### Intrinsics

Two new intrinsics are added:

```hlsl
uint WaveGetGroupIndex();
uint WaveGetCount();
```

**`WaveGetGroupIndex()`**:
- Takes no parameters
- Returns a `uint` value representing the wave index [0, N-1]
- Can be called from anywhere within applicable shader entry points
- Returns a uniform value (same for all lanes in a wave)

**`WaveGetCount()`**:
- Takes no parameters
- Returns a `uint` value representing the total number of waves
- Can be called from anywhere within applicable shader entry points
- Returns a uniform value (same for all threads in the thread group)
- Value is guaranteed to be at least 
   `ceil(threadGroupSize / WaveGetLaneCount())`
- Implementation may return a larger value if additional waves are launched

#### Shader Stage Compatibility

Both `WaveGetGroupIndex` and `WaveGetCount` are valid in compute, mesh, and
amplification shaders. Using these intrinsics in any other shader stage will
result in a compilation error.

#### Value Ranges and Guarantees

**`WaveGetGroupIndex()`**:
- Returns a value in the range [0, N-1], where N is the total number of waves
  in the thread group
- N equals the value returned by `WaveGetCount()`
- All lanes within a wave return the same index value

**`WaveGetCount()`**:
- Returns the total number of waves N executing the thread group
- Guaranteed to be at least:
  ```hlsl
  N >= ceil((numthreads.x * numthreads.y * numthreads.z) / WaveGetLaneCount())
  ```
- Where `numthreads` is specified by the `[numthreads(x, y, z)]` attribute
- Implementation may launch additional waves beyond the minimum required, so N
  may be larger than the computed minimum
- All threads in the thread group (across all waves) return the same count value
- The value is consistent throughout the execution of the thread group

#### Wave Ordering and Launch Flexibility

The distribution of `WaveGetGroupIndex` values to threads is determined by the
implementation based on the shader and target hardware requirements. However,
the presence of `WaveGetGroupIndex` and `WaveGetCount` must not cause the
implementation to violate existing wave shape requirements such as SM 6.6's
requirement to have 4 consecutive threads form a 2x2 quad in cases where the 2D
thread group dimensions are divisible by 2.

Implementations have flexibility in determining `WaveGetCount()`:
- May launch exactly `ceil(threadGroupSize / waveSize)` waves (minimum required)
- May launch additional waves if beneficial for hardware efficiency or occupancy
- When additional waves are launched, those waves may have inactive lanes or may
  participate in work distribution as determined by the implementation
- The value returned by `WaveGetCount()` must account for all launched waves,
  including any additional ones

#### Source Code Compatibility

This feature is purely additive and has no impact on existing HLSL source code.
Existing shaders that do not use `WaveGetGroupIndex` or `WaveGetCount` are
unaffected.

### Interchange Format Additions

#### DXIL Additions

Two new DXIL operations are added:

```hlsl
uint dx.op.waveGetGroupIndex(i32)  ; returns the wave index within the group
uint dx.op.waveGetCount(i32)       ; returns the number of waves in the group
```

**`dx.op.waveGetGroupIndex`**:
- **Opcode**: (to be assigned during implementation)
- **Operand**: i32 opcode constant
- **Return Type**: i32 (unsigned)
- **Return Value**: The index of the current wave within the thread group
   [0, N-1]

**`dx.op.waveGetCount`**:
- **Opcode**: (to be assigned during implementation)
- **Operand**: i32 opcode constant
- **Return Type**: i32 (unsigned)
- **Return Value**: The total number of waves executing the thread group
- **Guarantee**: Value is at least `ceil(threadGroupSize / waveSize)`

Both operations are lowered to hardware-specific instructions during backend
compilation. The values are typically derived from hardware thread group and
wave information available in the shader execution environment.

#### Metadata

No new metadata is required. The use of `WaveGetGroupIndex` and `WaveGetCount`
is indicated by the presence of the respective `dx.op.*` operations in the
shader.

### Diagnostic Changes

#### New Errors

The following new compilation errors are introduced:

1. **Invalid Shader Stage**
   - Error: `error: WaveGetGroupIndex is only valid in compute, mesh, and 
   amplification shaders`
   - Occurs when: `WaveGetGroupIndex` is called in other shader stages
   - Error: `error: WaveGetCount is only valid in compute, mesh, and 
   amplification shaders`
   - Occurs when: `WaveGetCount` is called in other shader stages

#### Validation Changes

DXIL validation is updated to verify:

1. **Shader Model Check**: The `dx.op.waveGetGroupIndex` and
   `dx.op.waveGetCount` operations are only valid in Shader Model 6.10 or later.

2. **Shader Stage Check**: Both operations only appear in compute, amplification
   and mesh shaders.

3. **Well-formed Usage**: Both operations are called with the correct signature
   (single i32 opcode operand, returns i32).

### Runtime Additions

#### Runtime Information

No additional runtime information needs to be communicated beyond what is
already provided in the PSV0 (Pipeline State Validation) data. The runtime does
not need to know whether a shader uses `WaveGetGroupIndex` or `WaveGetCount`.

#### Device Capability

**Shader Model Requirement**: Shader Model 6.10 or later.

**Hardware Support**: As a required feature of SM 6.10, all devices supporting
this shader model must provide correct `WaveGetGroupIndex` and `WaveGetCount`
values.

**Interaction with Wave Size**:
- Works with fixed wave sizes (specified via `[WaveSize(N)]` attribute)
- Works with wave size ranges (specified via `[WaveSize(min, max)]` or
  `[WaveSize(min, max, preferred)]`)
- Works with hardware-default wave sizes

**Emulation**: 

Implementations could theoretically emulate this by using group shared memory
e.g:

```hlsl
groupshared uint g_waveId = 0;

...

uint groupWaveId = 0;
if(WaveIsFirstLane())
{
   InterlockedAdd(g_waveId, 1, groupWaveId);
}

groupWaveId = WaveReadLaneAt(groupWaveId, 0);
```

## Testing

### Compiler Testing

**DXIL Generation**:
- Verify that `WaveGetGroupIndex` generates the correct
  `dx.op.waveGetGroupIndex` operation call
- Verify that `WaveGetCount` generates the correct `dx.op.waveGetCount`
  operation call
- Test with various thread group sizes and wave size specifications
- Confirm correct behavior when combined with other wave intrinsics
- Verify both intrinsics can be used together in the same shader

### Diagnostic Testing

**Error Conditions**:
- Verify error when `WaveGetGroupIndex` is used in invalid shader stages
- Verify error when `WaveGetCount` is used in invalid shader stages
- Verify error in shader models earlier than 6.10

### Validation Testing

**DXIL Validator**:
- Confirm validation failure when either operation appears in invalid shader
  stages
- Confirm validation failure when either operation appears in pre-6.10 shader
  models
- Verify acceptance of valid usage patterns for both operations

### Execution Testing

**Correctness Tests**:
- Test with various thread group sizes: small (8), medium (256), large (1024)
- Test with different wave sizes: 4, 8, 16, 32, 64, 128
- Verify `WaveGetGroupIndex()` returns values in range [0, WaveGetCount()-1]
- Verify all lanes in a wave return the same `WaveGetGroupIndex()` value
- Verify all threads in a thread group return the same `WaveGetCount()` value

**Wave Count Guarantees**:
- Verify `WaveGetCount() >= ceil(threadGroupSize / WaveGetLaneCount())`
- Test that `WaveGetCount()` is consistent throughout thread group execution
- If implementation launches extra waves, verify indices cover the full range

**Wave Size Interaction**:
- Test with fixed wave sizes using `[WaveSize(N)]`
- Test with wave size ranges using `[WaveSize(min, max)]`
- Test with wave size ranges with preferred size
- Verify correct wave counts with all wave size configurations

**Multi-Wave Collaboration**:
- Test shaders where different waves perform different work
- Verify correct synchronization using `GroupMemoryBarrier` between waves
- Test scenarios with group shared memory accessed by different waves
- Test algorithms that iterate over all waves using `WaveGetCount()`
- Verify wave index uniqueness within a thread group

**Edge Cases**:
- Single wave per thread group (numthreads ≤ wave size, `WaveGetCount()` == 1)
- Maximum waves per thread group
- Non-power-of-2 thread group sizes
- 1D, 2D, and 3D thread group configurations
- Thread group sizes that are not exact multiples of wave size
