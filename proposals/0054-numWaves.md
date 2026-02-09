
---
title: "0054 - numWaves shader intrinstic"
params:
  authors:
    - mafuller: Martin Fuller
  sponsors:
    - tbd: TBD
  status: Under Consideration
---

## Introduction

This proposal allows shaders to directly specify the number of waves launched 
to execute a thread group using a new 'numWaves' attribute. One of 'numWaves' 
of 'numThreads' must be specified, however these are mutually exclusive, the 
shader cannot specify both.

This facility is proposed for Compute and Amplification shaders only.

## Motivation

Specifying 'numWaves' has considerable benefits:
- It makes the 'wave specialisation' programming model (see 
  [GetGroupWaveIndex/GetGroupWaveCount](https://microsoft.github.io/hlsl-specs/proposals/0048-group-wave-index/)) 
  much more practical and easier for developers to adopt, since with 'numWaves', 
  you can easily code for a specific wave count and give different waves different
  tasks
- The front end compiler knows the value of GetGroupWaveCount, which is beneficial 
  because:
  - With 'numWaves' the front end compiler can make constant folding optimisations 
    with GetGroupWaveCount which may be reasonably missed with 'numThreads', i.e. 
    - With 'numThreads' the front end compiler does not know the value of 
      GetGroupWaveCount, meaning it cannot perform constant folding optimisations
    - The back end compiler may not duplicate optimisations the front end compiler 
      ordinarily performs, e.g. constant folding.
  - Arrays allocations, and particularly groupshared allocations can be sized by 
    GetGroupWaveCount, which is extremely beneficial for the 'wave specialisation' 
    programming model, sharing per wave data and minimising groupshared memory use.    
- The 'Wave specialisation' programming model can make data read/write more cache
  coherent with less atomic operations
  - Currently, typically a thread group will issue a single atomic per wave, and 
    append its outputs to a buffer, filtering out dead lanes
  - With wave specialisation, wave0 can sum the output count from all the waves in 
    its thread group, issue a single atomic and then assign each wave an offset with 
    which to write its outputs ([Example: Improved Memory Coherency Example with N Waves](#improved-memory-coherency-example-with-n-waves))
    - This improves data locality and cache coherency, since all outputs of a 
      thread group will be consecutive and not interleaved with outputs from other 
      thread groups. 
      - Typically the input is spatially coherent, e.g. a pixel grid, so this 
        improves spatial locality in the output buffers also
      - This may also improve lossless compression ratios, due to improved spatial 
        coherence, with less randomisation of interleaved output data
    - It reduces the total number of atomics
    - It improves determinism. Per-wave output is not randomly interleaved with 
      output from individual wave's in other thread groups. The order each thread
      groups writes its output is still non-deterministic, however the outputs 
      from all the waves within a thread group is now completely deterministic,   
- It allows tuning of the number of waves used in producer/consumer models, e.g. 
  Tasks Graphs, or the WaveExecuteActiveLanes proposal
  - It may be important for example to limit the number of cheap producer waves, 
    to provide additional compute resource for more expensive/longer running 
    consumer waves to execute concurrently
- It allows the programmer to iterate on work items, instead of issuing a thread 
  per item. 
  - This can be useful for background shaders, where it is desirable that these 
    take longer to complete but use less GPU resource, leaving more GPU resource 
    available for other critical path shaders.
- It allows the program to Dispatch based on wave size
  - This removes the requirement that shader using 'numWaves' and accomodating a 
    range of different wave sizes would need to feature a loop
  - It allows better fitting of the Dispatch size to the workload, minimising dead 
    lanes / wasted wave launch
    - For example, if the hardware wave size is 32, and the work size is 96, then 
      dispatching 3 waves results in zero dead lanes
    - Whereas with 'numThreads', the programmer might avoid using threads groups
      of less than 64 lanes, to make sure they efficiently utilise wave64 
      hardware for example. However dispatch(2,1,1) with an 64x1x1 TGS and wave32
      would results in 32 dead lanes in this use case.

## Proposed solution

For compute or amplification shaders the author can specify 'numWaves(X)' 
instead of 'numThreads(X,Y,Z)'. This launches X waves to execute the thread 
group. The number of threads per wave is determined by the hardware wave size.

If numWaves is specified, the following rules apply:
 - The shader must determine which work items each lane is to process by
   using SV_GroupID, GetGroupWaveIndex and WaveGetLaneIndex
 - The shader cannot use SV_DispatchThreadID, SV_GroupThreadID, SV_GroupIndex,
   these will result in a compiler error
 - Additionally specifying 'numThreads' will result in a compiler error
 - The backend compiler can fail compilation if it cannot honour the number 
   of required waves
   - This is similar to ERR_THREAD_GROUP_SIZE_INVALID when X * Y *Z cannot be 
     honored with 'numThreads'

To process work items, the shader will typically either:
 - Iterate over work items in a short loop
   - Typically numIterations = (WorkSizeInLanes / WaveCount) / WaveSize
     - Intentionally written this way, so the first division can be resolved by
       the front end compiler when using 'numWaves', the second divide by the 
       back end compiler, resulting in a single constant
   - numIterations is expected to be a low, single digit number
     - Especially for wave32 which is the most common wave size
 - Size the Dispatch based on the wave size 
   - The shader can use 'numWaves' and a range of wave sizes without having to 
     add a loop
   - It helps reduce dead lanes / wasted wave launch
   - The CPU needs to be able to query the wave size used in a PSO

### Single Wave Example
A compute shader to calculate the min/max depth for 8x8 tiles, using a single 
wave per thread group, thus avoiding any atomics or cross wave communication.

```HLSL
#define TILE_SIZE 8

[numWaves(1)]	  
[WaveSize(8, 64)]     // ranged size [8, 16, 32 or 64]
void ComputeMinMaxZ( uint2 tile : SV_GroupID )  
{
    float minZ = FLT_MAX, maxZ = -FLT_MAX;  

    uint laneIdx = WaveGetLaneIndex();
    uint2 coord = tile.xy * TILE_SIZE + uint2( laneIdx % TILE_SIZE, laneIdx / TILE_SIZE );    

    // numIterations will be w8(8), w16(4), w32(2), w64(1)
    // backend SC to pre-compute to single constant pls!
    uint numIterations = (TILE_SIZE * TILE_SIZE) / WaveGetLaneCount(); 

    for( uint i=0; i < numIterations; ++i ) {
         float z = Depth[ coord ];
         minZ = min( minZ, WaveActiveMin( z ) );
         maxZ = max( maxZ, WaveActiveMax( z ) );
         coord.y += WaveGetLaneCount() / TILE_SIZE;		
    }
    TileMinMaxDepthUAV[ tile.xy ] = (f32tof16( maxZ ) << 16) | f32tof16( minZ );
}
```

### Two Wave Example

A compute shader to calculate the min/max depth for 8x8 tiles, using two waves
per thread group and the 'wave specialisation' programming model to collate the 
result optimally with minimum groupshared use and no atomics.

```HLSL
#define TILE_SIZE 8

groupshared float g_wave1minZ; 
groupshared float g_wave1maxZ;

[numWaves(2)]	 
[WaveSize(8, 32)] 		   		 // ranged size [8, 16 or 32]
void ComputeMinMaxZ( uint2 tile : SV_GroupID ) 
{
    float minZ = FLT_MAX, maxZ = -FLT_MAX;  

    uint laneIdx = WaveGetLaneIndex();
    uint2 coord = tile.xy * TILE_SIZE + uint2( laneIdx % TILE_SIZE, laneIdx / TILE_SIZE );    
    // first wave does top half, second wave does bottom half
    coord.y = GetGroupWaveIndex() * (TILE_SIZE / GetGroupNumWaves()); 

    // numIterations will be w8(4), w16(2), w32(1)
    // front end compile can optimise the below since GetGroupNumWaves is known
    uint numIterations = (TILE_SIZE * TILE_SIZE) / GetGroupNumWaves(); 
    // back end compiler can resolve numIterations to a single constant
    numIterations /= WaveGetLaneCount(); 

    for( uint i=0; i < numIterations; ++i ) {
         float z = Depth[ coord ];
         minZ = min( minZ, WaveActiveMin( z ) );
         maxZ = max( maxZ, WaveActiveMax( z ) );
         coord.y += WaveGetLaneCount() / TILE_SIZE;		
    }
    // wave1 stores to LDS and retires, wave0 collates result and does write
    if( GetGroupWaveIndex() ) {
        g_wave1minZ = minZ;
        g_wave1maxZ = maxZ;
        return;
    }
    GroupMemoryBarrierWithGroupSync();

    minZ = min( minZ, g_wave1minZ );
    maxZ = max( maxZ, g_wave1maxZ );
    TileMinMaxDepthUAV[ tile.xy ] = (f32tof16( maxZ ) << 16) | f32tof16( minZ );
}
```

### Improved Memory Coherency Example 

Example showing all writes from a thread group being contiguous in memory, 
improving cache coherency and with a single per thread group atomic, instead 
of an atomic per wave.
This also improves determinism, since all outputs from a thread group are 
written contiguously, in a deterministic order, even though the order of 
thread groups writing is non-deterministic.

Group shared memory is sized for the number of waves in the thread group, 
which works because the number of waves is known to the front end compiler.

The Dispatch is sized for the wave size and 4x waves per thread group. Otherwise
this could be done with iteration, with a per iteration write to the UAVs.

Nearly all the below code may be considered wave invariant / scalar, and 
therefore may be considered practically 'free' on some hardware architectures.

```HLSL

// tile width is fixed, height is variable based on wave size
// the Dispatch to account for the variability in height based on querying the wave size of the PSO
#define TILE_WIDTH 16 

// used first to sum the number of outputs per wave, then as the per wave write offset
groupshared uint g_waveStore[ GetGroupNumWaves() - 1 ];

// ranged size [16, 32 or 64], each wave will process a height of 1, 2 or 4 pixels respectively, 
// meaning the threadgroup will process 16x4, 16x8 or 16x16 pixels depending on wave size
[numWaves(4)]	 
[WaveSize(16, 64)] 		        // ranged size [16, 32 or 64]                          
void Main( uint2 tile : SV_GroupID ) 
{
    // compute height processed by a wave and a thread group (constant to compiler)
    uint waveHeight = WaveGetLaneCount() / TILE_WIDTH;
    uint tileHeight = waveHeight * GroupGetWaveCount();
    
    // compute coordinate of tile 
    uint2 coord = tile.xy * uint2( TILE_WIDTH, tileHeight );

    // compute coordinate of wave
    coord.y += GroupGetWaveIndex() * waveHeight;

    // compute coordinate of lane
    coord += uint2( WaveGetLaneIndex() % TILE_WIDTH, WaveGetLaneIndex() / TILE_WIDTH );

    // do conditional filtering operation, could be anything
    bool exportData = ( GBuffer[ coord ] == <whatever> ) ? true : false;

    // sum the number of outputs to per wave groupshared memory
    uint count = WaveActiveCountBits( exportData ); 

    if( GroupGetWaveIndex() != 0 ) {
        g_waveStore[ GroupGetWaveIndex() - 1 ] = count;

        if( count == 0 )
            return;     // wave no longer needed, do not retire wave0 though!
    }
    GroupMemoryBarrierWithGroupSync();

    // wave0 sums the per-wave count and does a single atomic add to get the write offset for the entire thread group
    uint waveWriteOffset;
    if( GroupGetWaveIndex() == 0 ) {         
         uint threadGroupSum = count;
         for( uint j=0; j < GetGroupNumWaves() - 1; ++j )
             threadGroupSum += g_waveStore[j];
         
         AtomicAdd( CountBufferUAV[0], threadGroupSum, &waveWriteOffset );

         // compute per wave write offsets
         uint waveWriteOffsetItr = waveWriteOffset + count;   // wave0's section of the write buffer
         for( uint j=0; j < GetGroupNumWaves() - 1; ++j )  {
             uint waveCount = g_waveStore[j];
             g_waveStore[j] = waveWriteOffsetItr;             // wave's write offset into the write buffer
             waveWriteOffsetItr += waveCount;                 // wave's count
         }
    }
    GroupMemoryBarrierWithGroupSync();

    // all waves > 0 retrieve their write offset 
    if( GroupGetWaveIndex() != 0 ) 
         waveWriteOffset = g_waveStore[ GroupGetWaveIndex() - 1 ] ;

    uint threadWriteIndex = waveWriteOffset + WavePrefixCountBits( exportData );
    if( exportData ) 
        DataBufferUAV[ threadWriteIndex ] = (coord.x & 0xffff) | (coord.y << 16);
}
```

## Detailed design

### HLSL Additions

A new shader attribute 'numWaves(X)', where X is a integer and must be greater 
than zero, usable on Compute and Amplification shaders only. 
When 'numWaves' is used - 
- numThreads cannot be used
- Using SV_DispatchThreadID, SV_GroupThreadID, SV_GroupIndex is a compile error, 
  the program should use SV_GroupID, GetGroupWaveIndex and WaveGetLaneIndex instead 

### Amplification Shader Rasterization Order

Using 'numWaves' instead of 'numThreads' in an amplication shader does not change
the rasterization order. (which is only partial for AS)

### Derivatives

With 'numWaves' the shader must derive in software which work item(s) each lane
processes, using SV_GroupID, GetGroupWaveIndex and WaveGetLaneIndex.
It is still possible to use SM6.6 derivatives in this model and the QuadReadAccross 
intrinsics, providing the shader correctly arranges the work items per lane to the spec.
- [Spec](https://microsoft.github.io/DirectX-Specs/d3d/HLSL_SM_6_6_Derivatives.html)
- [Martin Fuller's blog with a shader for mapping lanes](https://martinfullerblog.wordpress.com/2023/02/01/compute-shader-thread-index-to-2d-coordinate)

### Interchange Format Additions

TBD, this is out of my knowledge area, but hopefully the sponsor can help here.

### Diagnostic Changes

New compile errors:
 - Using SV_DispatchThreadID, SV_GroupThreadID, SV_GroupIndex in a shader 
   using 'numWaves', the program should use SV_GroupID, GetGroupWaveIndex and 
   WaveGetLaneIndex instead
 - Using both 'numWaves' and 'numThreads' in the same shader
 - 'numWaves(X)', X must be an integer greater than zero
 - Requesting a number of waves which cannot be honoured by the backend compiler

### Runtime information

To enable the model where the Dispatch is sized based on wave size, the 
application needs to be able to query the wave size used in the PSO.
This requires that the driver commit to single wave size at compile time of 
the PSO. 
Some drivers may prefer to compile multiple versions of the shader with different 
wave sizes. The solution here is either to disallow this behaviour via a flag, 
or for the CPU to query the available sizes and select one at runtime. This 
proposal currently supports the former as it requires a far simpler API.

#### Runtime Additions

- A new flag D3D12_PIPELINE_STATE_FLAG_REPORT_WAVE_SIZE when set requires the 
  driver to commit to a single wave size at PSO creation time. 
  - If this flag is not set, the driver may compile multiple versions of the 
    shader with different wave sizes, and select one at runtime.
- A new flag D3D12_PIPELINE_STATE_HINT_PREFER_SMALL_WAVE_SIZE when set hints 
  to the driver to prefer a smaller wave sizes when compiling the PSO.
  - This flag may be useful for example if the shader expects to experience 
    significant divergence, or to more efficiently map to the workload size
- A new flag D3D12_PIPELINE_STATE_HINT_PREFER_LARGE_WAVE_SIZE when set hints 
  to the driver to prefer a larger wave size when compiling the PSO.
  - This flag may be useful for example if the shader benefits from cross lane
    intrinsics being wider, or to reduce atomic operations
- Extend D3D12_COMPUTE_PIPELINE_STATE_DESC with a 'CSWaveSize' field which is 
  filled out by the driver when the PSO is created
  - Non-zero if D3D12_PIPELINE_STATE_FLAG_REPORT_WAVE_SIZE is specified
  - Otherwise zero
- Ditto extend D3DX12_MESH_SHADER_PIPELINE_STATE_DESC with a 'ASWaveSize'
- For consistency, it may be desirable to report wave size for any shader type
  in all PSO state desc's.

#### Device Capability

It is very likely this feature can be implemented on older HW. 

Pre-requisites for this feature are:
- [Ranged wave size](https://microsoft.github.io/hlsl-specs/proposals/0013-wave-size-range/) 
  (already completed)
- [GroupWaveIndex](https://microsoft.github.io/hlsl-specs/proposals/0048-group-wave-index/),
  (accepted) which adds GetGroupWaveIndex and GetGroupWaveCount

GroupWaveIndex is currently slated for SM 6.10, so the shader version for this
feature needs to be at least 6.10.

## Testing

TBD


