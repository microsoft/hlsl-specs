---
title: "NNNN - Group Wave Index"
params:
    authors:
    - MartinAtXbox: Martin Fuller
    - damyanp: Damyan Pepper
    - jackell: Jack Elliott
    sponsors:
    - damyanp: Damyan Pepper
    - jackell: Jack Elliott
    status: Under Consideration
---

* Planned Version: Shader Model 6.10
* Issues: [#645](https://github.com/microsoft/hlsl-specs/issues/645)

## Introduction

The proposal is for a new shader construct:

* `SV_GroupWaveIndex`: the index of the wave in the thread group

## Motivation

Compute, Amplification and Mesh shader workloads consist of some number of thread groups, with each
thread group containing some number of waves and there being a number of threads
in the wave. Certain algorithms can be accelerated by specializing work done by individual waves in a thread group.

Currently, developers on PC cannot efficiently determine which wave they're in
within a thread group without resorting to unsafe workarounds like
`uint groupWaveIndex = SVGroupIndex / WaveGetLaneCount()`, which is not guaranteed
to be correct across all hardware implementations and thread group dimensions. This forces developers to
either write divergent code paths for different platforms or use slightly less efficient
alternatives involving atomic operations on thread local memory for example.

## Proposed solution

This proposal introduces `SV_GroupWaveIndex`, a new system-value semantic that
provides the index of the current wave within the thread group. This value ranges
from 0 to N-1, where N is the number of waves in the thread group.

### Example Usage

```hlsl
#define TILE_SIZE 16

[numthreads(TILE_SIZE, TILE_SIZE, 1)]
void ComputeMinMaxZ(
    uint2 tileID : SV_GroupID,
    uint waveIndex : SV_GroupWaveIndex)
{
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

1. **Wave-level collaboration**: Different waves within a thread group can perform
   different tasks and coordinate their work efficiently.
2. **Single-wave specialization**: Shaders can optimize for the common case where
   a thread group contains exactly one wave.
3. **Portable code**: A single code path works across all wave sizes without
   conditionals on `WaveGetLaneCount()`.

## Detailed design

### HLSL Additions

#### Grammar

The `SV_GroupWaveIndex` semantic is added as a new system-value semantic:

```hlsl
SV_GroupWaveIndex : uint
```

This semantic can be applied to:
- Function parameters in applicable shader entry points
- Input structures for applicable shader entry points

#### Shader Stage Compatibility

`SV_GroupWaveIndex` is valid in compute, mesh, and amplification shaders. Using this semantic in
any other shader stage will result in a compilation error.

#### Type Requirements

The `SV_GroupWaveIndex` semantic must be applied to a `uint` type. Using it with
any other type will result in a compilation error.

#### Value Range

The value of `SV_GroupWaveIndex` is in the range [0, N-1], where N is the total
number of waves in the thread group. The number of waves N is determined by:

```hlsl
N = ceil((numthreads.x * numthreads.y * numthreads.z) / WaveSize)
```

Where `numthreads` is specified by the `[numthreads(x, y, z)]` attribute and
`WaveSize` is the actual wave size used for shader execution i.e. what is returned from `WaveGetLaneCount`.

#### Wave Ordering

The distribution of `SV_GroupWaveIndex` values to threads is up to the implementation on how best to launch waves for a given the shader and the target hardware requirements. However, the presence of `SV_GroupWaveIndex` must not cause the implementation to violate existing wave shape requirements such as SM 6.6's requirement to have 4 consecutive threads form a 2x2 quad in cases where the 2D thread group dimensions are divisible by 2.

#### Interaction with Other Semantics

`SV_GroupWaveIndex` can be freely combined with other compute shader semantics:
- `SV_GroupID`: The 3D index of the thread group
- `SV_GroupThreadID`: The 3D index of the thread within the group
- `SV_GroupIndex`: The flattened linear index of the thread within the group
- `SV_DispatchThreadID`: The global thread ID across the dispatch

Example:
```hlsl
[numthreads(256, 1, 1)]
void CSMain(
    uint3 groupID : SV_GroupID,
    uint3 groupThreadID : SV_GroupThreadID,
    uint groupIndex : SV_GroupIndex,
    uint waveIndex : SV_GroupWaveIndex)
{
    // All semantics can be used together
}
```

#### Source Code Compatibility

This feature is purely additive and has no impact on existing HLSL source code.
Existing shaders that do not use `SV_GroupWaveIndex` are unaffected.

### Interchange Format Additions

#### DXIL Additions

A new DXIL intrinsic is added to represent `SV_GroupWaveIndex`:

```hlsl
uint dx.op.groupWaveIndex(i32)  ; returns the wave index within the group
```

- **Opcode**: (to be assigned during implementation)
- **Operand**: i32 opcode constant
- **Return Type**: i32 (unsigned)
- **Return Value**: The index of the current wave within the thread group [0, N-1]

The intrinsic is lowered to hardware-specific instructions during backend
compilation. The value is typically derived from hardware thread group and wave
information available in the shader execution environment.

#### Metadata

No new metadata is required. The use of `SV_GroupWaveIndex` is indicated by the
presence of the `dx.op.groupWaveIndex` intrinsic in the shader.

### Diagnostic Changes

#### New Errors

The following new compilation errors are introduced:

1. **Invalid Shader Stage**
   - Error: `error: SV_GroupWaveIndex is only valid in compute, mesh, and amplification shaders`
   - Occurs when: `SV_GroupWaveIndex` is used in other shader stages

2. **Invalid Type**
   - Error: `error: SV_GroupWaveIndex must be applied to a 'uint' type`
   - Occurs when: The semantic is applied to a type other than `uint`

3. **Invalid Semantic Usage**
   - Error: `error: system-value semantics cannot be used as outputs`
   - Occurs when: `SV_GroupWaveIndex` is used on an output parameter or return value

#### Validation Changes

DXIL validation is updated to verify:

1. **Shader Model Check**: The `dx.op.groupWaveIndex` intrinsic is only valid
   in Shader Model 6.10 or later.

2. **Shader Stage Check**: The intrinsic only appears in compute, amplification and mesh shaders.

3. **Well-formed Usage**: The intrinsic is called with the correct signature
   (single i32 opcode operand, returns i32).

### Runtime Additions

#### Runtime Information

No additional runtime information needs to be communicated beyond what is already
provided in the PSV0 (Pipeline State Validation) data. The runtime does not need
to know whether a shader uses `SV_GroupWaveIndex`.

#### Device Capability

**Shader Model Requirement**: Shader Model 6.10 or later.

**Hardware Support**: As a required feature of SM 6.10, all devices supporting
this shader model must provide correct `SV_GroupWaveIndex` values.

**Interaction with Wave Size**:
- Works with fixed wave sizes (specified via `[WaveSize(N)]` attribute)
- Works with wave size ranges (specified via `[WaveSize(min, max)]` or
  `[WaveSize(min, max, preferred)]`)
- Works with hardware-default wave sizes

**Emulation**: 

Implementations could theoretically emulate this by using group shared memory e.g:

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
- Verify that `SV_GroupWaveIndex` generates the correct `dx.op.groupWaveIndex`
  intrinsic call
- Test with various thread group sizes and wave size specifications
- Confirm correct behavior when combined with other compute shader semantics

### Diagnostic Testing

**Error Conditions**:
- Verify error when used in invalid shader stages
- Verify error when applied to non-uint types (int, float, uint2, etc.)
- Verify error when used as an output semantic
- Verify error in shader models earlier than 6.10

### Validation Testing

**DXIL Validator**:
- Confirm validation failure when intrinsic appears in invalid shader stages
- Confirm validation failure when intrinsic appears in pre-6.10 shader models
- Verify acceptance of valid usage patterns

### Execution Testing

**Correctness Tests**:
- Test with various thread group sizes: small (8), medium (256), large (1024)
- Test with different wave sizes: 4, 8, 16, 32, 64, 128

**Wave Size Interaction**:
- Test with fixed wave sizes using `[WaveSize(N)]`
- Test with wave size ranges using `[WaveSize(min, max)]`
- Test with wave size ranges with preferred size

**Multi-Wave Collaboration**:
- Test shaders where different waves perform different work
- Verify correct synchronization using `GroupMemoryBarrier` between waves
- Test scenarios with group shared memory accessed by different waves

**Edge Cases**:
- Single wave per thread group (numthreads ≤ wave size)
- Maximum waves per thread group
- Non-power-of-2 thread group sizes
- 1D, 2D, and 3D thread group configurations
