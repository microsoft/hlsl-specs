---
title: "NNNN - Variable Group Shared Memory"
params:
  authors:
  - jackell: Jack Elliott
  sponsors:
  - jackell: Jack Elliott
  status: Under Consideration
---

* Planned Version: Shader Model 6.10
* Issues: (TBD)

## Introduction

Today HLSL (DXIL) validation enforces a fixed upper limit (historically 32 KB)
of group shared (a.k.a. thread group shared / LDS / shared) memory per thread
group for compute, mesh, and amplification shaders. Modern GPU architectures
often expose substantially larger physically available shared memory, and
practical algorithms (e.g. large tile / cluster culling, work graph staging,
software raster bins, wave-cooperative BVH traversal, advanced GI probes) are
constrained by the fixed specification limit rather than hardware reality.

This proposal introduces a device-dependent maximum group shared memory limit
for Shader Model 6.10+, together with a way for shader authors to declare the
maximum amount of group shared memory their shader will ever use so that they
can guarantee portability across a target device set.

## Motivation

Goals:
* Allow hardware to expose a (potentially larger) per-thread-group group shared memory capacity.
* Provide a compile-time author-declared upper bound to ensure predictable portability.
* Maintain safety: runtime validators must still reject shaders whose static allocation exceeds
  the hardware or declared limits.
* Remain source-compatible with existing shaders (no behavior change if they do nothing).

## Proposed Solution

Introduce two core pieces:

1. A runtime API query returning `MaxGroupSharedMemoryPerGroup` (in bytes).
    - This will return a minimum value of 32,768 i.e the maximum for SM 6.9 and prior
    - There is no defined maximum value.
    - Values must be 4 byte aligned.
2. A new optional entry-point attribute allowing a shader author to declare the *guaranteed maximum*
   group shared usage the shader intends to stay under: `[GroupSharedLimit(<bytes>)]`. This value is a compile-time
   constant positive integer. The purpose of this is to provide a measure of safety
   for the shader author to ensure their group shared memory usage doesn't exceed
   hardware capability of their minimum spec.

No change is proposed to how static `groupshared` objects are declared; sizes remain compile-time
constants.

### Example

```hlsl
[numthreads(128,1,1)]
[GroupSharedLimit(65536)] // Author intends to remain portable to devices with >= 64 KB
void CSMain(uint3 dtid : SV_DispatchThreadID)
{
    // 64 KB O.K.
    groupshared uint bigScratch[ 65536 ];
}

[numthreads(128,1,1)]
[GroupSharedLimit(65536)] // Author intends to remain portable to devices with >= 64 KB
void CSMain(uint3 dtid : SV_DispatchThreadID)
{
    // 64 KB + 4 Bytes FAIL (GroupSharedLimit Exceeded)
    groupshared uint bigScratch[ 65537 ];
}

[numthreads(128,1,1)]
void CSMain(uint3 dtid : SV_DispatchThreadID)
{
    // 64 KB + 4 Bytes O.K. (no GroupSharedLimit, could still fail runtime lowering)
    groupshared uint bigScratch[ 65537 ];  
}
```

## Detailed Design

### Runtime Validation
* If `GroupSharedLimit` is omitted and the compiled HLSL shader requires more group shared memory
than is supported by the device then the runtime will reject the shader at pipeline creation time.
Similarly, if `GroupSharedLimit` was declared and HLSL validation passed the resulting shader will
still need to pass the runtime device limit check.
* The compiler MUST still compute precise static usage and emit it for validation.

### HLSL Additions

#### Attribute

```hlsl
[GroupSharedLimit(<bytes>)]
```

Rules:
* `<bytes>`: positive, compile-time constant `uint` literal / constexpr; must be a multiple of 4.
* At most one `GroupSharedLimit` attribute per entry point; duplicates are an error.
* Applies only to compute, mesh, amplification shaders.
* The attribute does NOT itself reserve memory; it constrains static usage.
i.e. the calculated shared memory usage of the shader must always be <= this value.

#### Interaction With Existing Constructs
* Existing `groupshared` declarations unchanged.
* Wave / subgroup operations unaffected.

### Diagnostic Changes

New compile-time errors:
- `GroupSharedLimit attribute requires a positive compile-time integer argument`.
- `GroupSharedLimit attribute argument must be a multiple of 4`.
- `Duplicate GroupSharedLimit attribute on entry point`.
- `GroupSharedLimit attribute not allowed on this shader stage` (non compute/mesh/amplification).
- `groupshared static usage (<bytes>) exceeds declared GroupSharedLimit (<limit>)`.

Validator / pipeline creation errors:
- `groupshared static usage (<bytes>) exceeds device capacity (<capacity>)`.

### Validation Changes

Validator must:
* Sum byte sizes of all groupshared globals (respect alignment / padding like today).
* Check attribute presence & argument correctness.
* Ensure intrinsic appears only in compute/mesh/amplification and SM >= 6.10.
* Emit / retain static usage metadata (existing) for runtime comparison against device capability.

### Runtime Additions

#### Capability Bit / Query

Add a new feature query (illustrative naming):
* D3D12: `D3D12_FEATURE_DATA_D3D12_OPTIONS_XX::MaxGroupSharedMemoryPerGroup`
    - Value declares the maximum group shared memory in bytes per thread group
    - Must be >= 32,768

#### Pipeline Compilation / Load
* Runtime compares shader static usage versus device capacity.
* Failure path mirrors existing shader model mismatch failures.

### Device Capability

* When targeting Shader Model 6.10 drivers must return a value for `MaxGroupSharedMemoryPerGroup`
greater than or equal to 32,768.

## Testing

Testing matrix axes:
* Stages: compute, mesh, amplification.
* Capacities: 0 - 32 KB, 48 KB, 64 KB, 96 KB, 128 KB.
* Attribute: absent vs present (below, equal, above static usage; above capacity).

## Alternatives Considered

| Alternative | Rationale for Rejection |
|-------------|-------------------------|
| Increase static limit from 32k to something larger. | What value to pick? What about when hardware advances past that? |