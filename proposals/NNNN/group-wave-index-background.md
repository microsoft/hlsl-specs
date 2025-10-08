# D3D12 Group Wave Index <!-- omit in TOC -->

Martin Fuller -- <martin@xbox.com>

---

# Contents <!-- omit in TOC -->

- [Proposal Summary](#proposal-summary)
- [Use Cases](#use-cases)
- [Problem with the Current Model](#problem-with-the-current-model)
- [Example 1 -- N Waves per Thread Group with N equals 1 specialization](#example-1----n-waves-per-thread-group-with-n-equals-1-specialization)
  - [Omitting GroupWaveCount equals 1 Specialization](#omitting-groupwavecount-equals-1-specialization)
- [Example 2 -- 4x border loads](#example-2----4x-border-loads)
- [Testing](#testing)


---

# Proposal Summary

The proposal is for two new compute shader variables:

1.  `GroupGetWaveCount()`: the number of waves in a thread group

2.  `SV_GroupWaveIndex`: The index of the wave in the thread group
    `0...GroupGetWaveCount()-1`

These variables could be mutually exclusive with `SV_DispatchThreadID` and
`SV_GroupThreadID`. That is trying to use either of these with
`SV_GroupWaveIndex` would result in a shader compilation error. This might
ease IHV concerns with these new variables.

In this 'low level' mode, the work item for each lane is always derived
by the shader author from `SV_GroupID`/`SV_GroupIndex`, `SV_GroupWaveIndex`
and `WaveGetLaneIndex()` only.

`GroupGetWaveCount()` must be considered a compile time constant, which can
be used both for dead code elimination and array sizes.

It is highly desirable for debug/testing purposes to be able to emulate
different wave widths, see testing section.

---

# Use Cases

`SV_GroupWaveIndex` and `GroupGetWaveCount()` enable:

1.  Greater collaboration of work between waves without having to go
    'off-chip', involving atomic operations, and pre-memset of UAVs.

2.  Different waves to perform different tasks

3.  Single wave specialization

I have been using this on Xbox to achieve good performance wins, however
my implementation of `SV_GroupWaveIndex` is not considered safe on PC

```C++
SV_GroupWaveIndex = WaveReadFirstLane(SV_GroupIndex) / WaveGetLaneCount();
```

---

# Problem with the Current Model

Frequently we see titles are exploiting the efficiency of wave wide
intrinsics on PC, but do provide divergent code for console where the
wave width is known and fixed. The problem lighting up these
optimizations to PC is the programming model.

The moment I find I have to write in HLSL

```C++
    if ( WaveGetLaneCount() == <whatever> )
```

I'm in trouble. Conditionals on lane count are fraught with problems.
How many wave counts do I have to support? How do I test these? What are
the future compat concerns? 64, 32, 16, 8, 4, 2, 1? The maintenance
implications here are terrible. The net result is that code is generally
diverged between an optimal solution for console, and PC using
non-optimal code, often with more atomics etc..

Writing a shader that deals in N waves per thread group is a far better
model, with the option if I want to of specializing on single waves.
That is, I need only 1 code path for any wave width, but I might decide
to add a specialization when N == 1. Or the shader compiler may be able
to produce this specialization automatically

---

# Example 1 -- N Waves per Thread Group with N equals 1 specialization

Hi-Z or light tile min/max calculation. Simple min/max operation of a
16x16 screen space tile. TGS of 16x16, and using wave32 = 8 waves per
group.

1.  I declare a group shared array, one element per wave in the thread
    group

2.  Each wave does a `WaveActiveMin`/`Max` and thread 0 writes the result to
    group shared memory

3.  All waves except wave 0 retire

4.  Wave 0 loops `0..GroupGetWaveCount()-1`, taking the min/max of all group
    shared values, and makes a single write to a UAV

In fact, the group shared values only needs to be 7 elements large,
since Wave0 does not need to write its values to groupshared and read
them back.

Here is the code I really want to write. Featuring both single wave
specialization, and on-chip collaboration between different waves:

```C++
#define TILE_SIZE 16

[numthreads (TILE_SIZE, TILE_SIZE, 1)]
void ComputeMinMaxZ(
    uint2 tileID: SV_GroupID, 
    uint waveIndex : SV_GroupWaveIndex)
{
    uint2 coord - GetLaneCoord2DSquare(tileID, TILE_SIZE, waveIndex, GroupGetWaveCount());
    float z = Depth[coord];           // vector
    float minZ = WaveActiveMin(z);    // uniform
    float maxZ = WaveActiveMax(z);    // uniform

    // Ideally we could test this code path by artifically restricting the wave width
    if constexpr (GroupGetWaveCount() > 1)
    {
        // locally declared ideally
        groupshared float g_minZ[GroupGetWaveCount() - 1];
        groupshared float g_maxZ[GroupGetWaveCount() - 1];

        if (waveIndex < GroupGetWaveCount() - 1)
        {
            g_minZ[waveIndex] = minZ;
            g_maxZ[waveIndex] = maxZ;
            return;
        }
        // only the last wave is left at this point, we simply need to wait for all other waves to
        // write their min/max and retire before the last wave continues
        GroupMemoryBarrierWithGroupSync();

        // the one remaining wave didn't write to grouped shared RAM, so it updates its min/max with the
        // values from the other waves

        // could use minZ = min(minZ, WaveActiveMin(g_minZ[laneIndex])); however this requires
        // care that numWaves < WaveGetLaneCount(), which is fine, but another code path to test.
        // WaveActiveMin/Max are sometimes implemeneted as a parallel reduction taking ~6 instructions
        // each, so iteration is probably faster for the iteration count we expect, wave32 or wave64
        // potentially some GPU's could execute this loop using uniform instructions only
        for (uint i = 0; i < GroupGetWaveCount() - 1; ++i)
        {
            // this is all uniform, though some Hw will have to use vector instructions (inc XBox)
            // this is good to encourage IHVs to give us more uniform ops! ;)
            minZ = min(minZ, g_minZ[i]));
            maxZ = max(maxZ, g_maxZ[i]));
        }
    }
    // only one wave will ever get here

    // This is a uniform store of two uniform values. The SC may on some HW decide its better to use
    // the vector pipeline and insert an if(laneIndex == 0). Again, more opportunity for future HW
    TileMinMaxDepthUAV[tileID.xy] = (f32tof16(maxZ) << 16) | f32tof16(minZ);
}
```

---

## Omitting GroupWaveCount equals 1 Specialization

Looking at the above code example again, if the specialization for `N ==
1` was omitted by the shader author, it is easy to imagine that the
shader compiler could eliminate all the group shared memory itself on a
machine where `GroupGetWaveCount() == 1`, and arrive at the same optimum
specialization.

---

# Example 2 -- 4x border loads

Any sort of kernel run over an image. I load 18x18 tile of pixels to
process with 3x3 kernel. With a TGS of 16x16, and using wave32 = 8 waves
per group.

1.  Waves 0..3 load a different border each to group shared memory

2.  All 8 waves load 1/8 of the interior pixels to group shared memory

3.  GroupSync

4.  Process

With wave32, wave 4..7's have no border to load. These waves are issued
later, but typically arrive at the group sync first.

With wave64, there are only 4 waves, so each loads a 17 pixel border

With wave16 or lower, the border functions which load 17 pixels have to
loop. So the border load functions should be written as a loop that only
executes 1x time on wave32 or wider.

The interesting thing about this shader is it has 4 code paths to load
the 4 borders, what happens if you have less than 4 waves? The shader
author should use the following function to decide if a given wave index
should load a border (modulo).

```C++
bool ShouldWaveDoWork(
    uint groupWaveIndex, 
    uint modulo)
{
    return (groupWaveIndex & (GroupGetWaveCount() - 1)) == 
           (modulo & (GroupGetWaveCount() - 1));
}
```

The above function returns the following results for modulo 0..3

1.  8 waves - only waves 0..3 obtain a single true result, for a
    different border each 0..3. Waves 4..7 never obtain a true result

2.  4 waves - only waves 0..3 obtain a single true result, for a
    different border each 0..3.

3.  2 waves - waves 0..1 obtain two true results each, wave 0 loads
    borders 0,2, wave 1 loads border 1,3

4.  1 wave - loads all 4x borders

The function is of course resolves to a trivial number of instructions,
especially given that modulo (0..3) and `GroupGetWaveCount()` will be
compile time constants. We have a single bitwise AND, compare and
branch, and these are scalar ops.

---

# Testing

Titles could test out specializations in the code by altering their
thread group size to match or deviate from the native machine width.
However it would also be highly desirable to be able to test with wave
widths that are different to the native machine width. This could be
done in a number of ways including:

1.  Testing a width smaller than the native width, either by

    a.  Artificially turning off 50%, 75% etc.. of the lanes

    b.  The GPU runs virtual waves with the laneIndex partitioned, e.g.
        for a wave128 pretending to be a wave64

        i.  Runs with only lanes 0..63 active = waveIndex0

        ii. Runs again with only lanes 64..127 = waveIndex1

        iii. That is WaveGetLaneIndex() returns 0..63 for real lane
             indices 64..127 when running waveIndex1

2.  Testing a width larger than the native width

    a.  Emulate by running two or more waves with hidden group shared
        memory to allow wave intrinsics to run wider than a real wave

Likely this emulation would only be enabled in non-retail driver modes.
