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

Today HLSL (DXIL) validation enforces a fixed upper limit of 32 KB
of group shared memory per thread group for compute, mesh, and amplification
shaders. Modern GPU architectures often expose substantially larger physically
available shared memory, and practical algorithms (e.g. large tile / cluster
culling, large matrix manipulation, software raster bins, wave-cooperative BVH
traversal, etc.) are constrained by the fixed specification limit rather than
hardware reality.

This proposal introduces a device-dependent maximum group shared memory limit
for Shader Model 6.10+, together with a way for shader authors to declare the
maximum amount of group shared memory their shader will ever use so that they
can guarantee portability across a target device set.

## Motivation

Goals:
* Allow hardware to expose a larger per-thread-group group shared memory
capacity.
* Provide a compile-time author-declared upper bound to ensure predictable
portability.
* Maintain safety: runtime validators must still reject shaders whose static
allocation exceeds the hardware or declared limits.
* Remain source-compatible with existing shaders (no behavior change if they do
nothing).

## Proposed Solution

Introduce two core pieces:

1. A runtime API query returning `MaxGroupSharedMemoryPerGroup` (in bytes).
    - This will return a minimum value of 32,768 i.e the default for SM 6.9 and
    prior
    - There is no defined maximum value.
    - Values must be 4 byte aligned.
2. A new optional entry-point attribute allowing a shader author to declare the
*guaranteed maximum* group shared usage the shader intends to stay under: 
   `[GroupSharedLimit(<bytes>)]`. This value is a compile-time
   constant positive integer. The purpose of this is to provide a measure of
   safety for the shader author to ensure their group shared memory usage 
   doesn't exceed hardware capability of their minimum spec.

No change is proposed to how static `groupshared` objects are declared; sizes
remain compile-time constants.

### Examples
#### Example 1: `GroupSharedLimit` declared but not exceeded
```hlsl
groupshared uint g_BigScratch1[ 16384 ];

[numthreads(128,1,1)]
// Author intends to remain portable to devices with>= 64 KB
[GroupSharedLimit(65536)]
void CSMain(uint3 dtid : SV_DispatchThreadID)
{
    g_BigScratch1[dtid.x] = ...
}
```
In this example the shader declares a maximum of 64k group shared memory usage
and it's static usage does not exceed that therefore no errors are generated.

#### Example 2: `GroupSharedLimit` declared but exceeded

```hlsl
// 64 KB + 4 Bytes FAIL (GroupSharedLimit Exceeded)
groupshared uint g_BigScratch2[ 16385 ];

[numthreads(128,1,1)]
 // Author intends to remain portable to devices with >= 64 KB
[GroupSharedLimit(65536)]
void CSMain(uint3 dtid : SV_DispatchThreadID)
{
    g_BigScratch2[dtid.x] = ...
}
```
This shader declares a maximum of 64k group shared memory but it's actual usage
is 4 bytes larger than that which results in a compiler error.

#### Example 2: `GroupSharedLimit` undeclared and original limit exceeded
```hlsl
// 64 KB FAIL. (no GroupSharedLimit -> fallback to 32k limit)
groupshared uint g_BigScratch3[ 16384 ];  

[numthreads(128,1,1)]
void CSMain(uint3 dtid : SV_DispatchThreadID)
{
    g_BigScratch3[dtid.x] = ...
}
```
This shader does not make use of `GroupSharedLimit` therefore the SM6.10 and
prior limit of 32k is applied and a compiler error is generated because it's
actual usage exceeds that.

## Detailed Design

### Runtime Validation
* If `GroupSharedLimit` is omitted, validation will fall back to the original
32k limit. The error message will be update to indicate that the limit may be
raised with the caveat that hardware support must be checked.
* If `GroupSharedLimit` is present, HLSL validation will ensure the actual
static usage is less than that limit. While a shader may pass validation and
compile successfully the runtime may reject it if the shared memory usage is
greater than the device can support.
* The compiler MUST still compute precise static usage and emit it for
validation.

### HLSL Additions

#### Attribute

```hlsl
[GroupSharedLimit(<bytes>)]
```

Rules:
* `<bytes>`: positive, compile-time constant `uint` literal / constexpr; must
be a multiple of 4.
* At most one `GroupSharedLimit` attribute per entry point; duplicates are an
error.
* Applies only to compute, mesh, amplification shaders.
* The attribute does NOT itself reserve memory; it constrains static usage.
i.e. the calculated shared memory usage of the shader must always be <= this
value.

#### Interaction With Existing Constructs
* Existing `groupshared` declarations unchanged.
* Wave / subgroup operations unaffected.

### Diagnostic Changes

New compile-time errors:
- `GroupSharedLimit attribute requires a positive compile-time integer
argument`.
- `GroupSharedLimit attribute argument must be a multiple of 4`.
- `Duplicate GroupSharedLimit attribute on entry point`.
- `GroupSharedLimit attribute not allowed on this shader stage`
(non compute/mesh/amplification).
- `groupshared static usage (<bytes>) exceeds declared GroupSharedLimit
(<limit>)`.

Validator / pipeline creation errors:
- `groupshared static usage (<bytes>) exceeds device capacity (<capacity>)`.

### Validation Changes

Validator must:
* Sum byte sizes of all groupshared globals (respect alignment / padding like
today).
* Check attribute presence & argument correctness.
* Ensure intrinsic appears only in compute/mesh/amplification and SM >= 6.10.
* Emit / retain static usage metadata (existing) for runtime comparison against
device capability.

### Runtime Additions

#### Capability Bit / Query

Add a new feature query (illustrative naming):
* D3D12: `D3D12_FEATURE_DATA_D3D12_OPTIONS_XX::MaxGroupSharedMemoryPerGroup`
    - Value declares the maximum group shared memory in bytes per thread group
    - Must be >= 32,768 and 4 byte aligned

#### Pipeline Compilation / Load
* Runtime compares shader static usage versus device capacity.
* Failure path mirrors existing shader model mismatch failures.

### Device Capability

* When targeting Shader Model 6.10 drivers must return a value for
`MaxGroupSharedMemoryPerGroup` greater than or equal to 32,768.

## Testing

Testing matrix axes:
* Stages: compute, mesh, amplification.
* Capacities: 0 - 32 KB, 48 KB, 64 KB, 96 KB, 128 KB.
* Attribute: absent vs present (below, equal, above static usage; above
capacity).

## Alternatives Considered

| Alternative | Rationale for Rejection |
|-------------|-------------------------|
| Increase static limit > 32k to something larger. | What value to pick? What about when hardware advances past that? |