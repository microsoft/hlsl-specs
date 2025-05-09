
# Shader Execution Reordering (SER)

* Proposal: [0027](0027-shader-execution-reordering.md)
* Author(s): [Rasmus Barringer](https://github.com/rasmusnv), Robert Toth,
Michael Haidl, Simon Moll, Martin Stich
* Sponsor: [Tex Riddell](https://github.com/tex3d)
* Status: **Under Consideration**
* Impacted Projects: DXC

## Introduction

This proposal introduces `MaybeReorderThread`, a built-in function for raygeneration shaders to
explicitly specify where and how shader execution coherence can be improved.
Additionally, `HitObject` is introduced to decouple traversal, intersection
testing and anyhit shading from closesthit and miss shading. Decoupling these
shader stages gives an increase in flexibility and enables `MaybeReorderThread` to
improve coherence for closesthit and miss shading, as well as subsequent operations.

## Motivation

Many raytracing workloads suffer from divergent shader execution and divergent
data access because of their stochastic nature. Improving coherence with
high-level application-side logic has many drawbacks, both in terms of
achievable performance (compared to a hardware-assisted implementation) and
developer effort. The DXR API already allows implementations to dynamically
schedule shading work triggered by `TraceRay` and `CallShader`, but does not
offer a way for the application to control that scheduling in any way.

Furthermore, the current fused nature of `TraceRay` with its combined
execution of traversal, intersection testing, anyhit shading and closesthit or
miss shading imposes various restrictions on the programming model that, again,
can increase the amount of developer effort and decrease performance. One
aspect is that common code, e.g., vertex fetch and interpolation, must be
duplicated in all closesthit shaders. This can cause more code to be generated,
which is particularly problematic in a divergent execution environment.
Furthermore, `TraceRay`'s nature requires that simple visibility rays
unnecessarily execute hit shaders in order to access basic information about
the hit which must be transferred back to the caller through the payload.

## Proposed Solution

Shader Execution Reordering (SER) introduces a new HLSL built-in intrinsic,
`MaybeReorderThread`,
that enables application-controlled reordering of work across the GPU for
improved execution and data coherence.
Additionally, the introduction of `HitObject` allows separation of traversal,
anyhit shading and intersection testing from closesthit and miss shading.

`HitObject` and `MaybeReorderThread` can be combined to improve coherence for
closesthit and miss shader execution in a controlled manner.
Applications can control coherence based on hit properties,
ray generation state, ray payload, or any combination thereof. Applications can
maximize performance by considering coherence for both hit and miss shading as
well as subsequent control flow and data access patterns inside the
raygeneration shader.

`HitObject` improves the flexibility of the ray tracing pipeline in general.
First, common code, such as vertex fetch and interpolation, must no longer be
duplicated in all closesthit shaders. Common code can simply be part of the
raygeneration shader and execute before closesthit shading. Second, simple
visibility rays no longer have to invoke hit shaders in order to access basic
information about the hit, such as the distance to the closest hit. Finally,
`HitObject` can be constructed from a `RayQuery`, which enables
`MaybeReorderThread` and shader table-based closesthit and miss shading to be combined with
`RayQuery`.

The proposed extension to HLSL should be relatively straightforward to adopt by
current DXR implementations: `HitObject` merely decouples existing `TraceRay`
functionality into two distinct stages: the traversal stage and the shading
stage.
For SER's `MaybeReorderThread`, the minimal allowed implementation is simply a
no-op, while implementations that already employ more sophisticated scheduling
strategies are likely able to reuse existing mechanisms to implement support
for SER. No DXR runtime changes are necessary, since the proposed extension to
the programming model is limited to HLSL and DXIL.

Note that all new SER types and intrinsics are added to `namespace dx` in
accordance with the [Fast-Track Process for HLSL
Extensions](https://github.com/microsoft/hlsl-specs/blob/main/docs/Process.md#fast-track-for-extensions).
For the sake of legibility, this document only qualifies the namespace
explicitly in [HitObject HLSL Additions](#hitobject-hlsl-additions) when SER
additions are formally specified. An implicit `using namespace dx` is assumed
in the rest of this specification.

## Detailed Design

This section describes the HLSL additions for `HitObject` and `MaybeReorderThread`
in detail.
The canonical use of these features involve changing a `TraceRay` call to the
following sequence that is functionally equivalent:

```C++
HitObject Hit = HitObject::TraceRay( ..., Payload );
MaybeReorderThread( Hit );
HitObject::Invoke( Hit, Payload );
```

This snippet traces a ray and stores the result of traversal, intersection
testing and anyhit shading in `Hit`. The call to `MaybeReorderThread` improves
coherence based on the information inside the `Hit`. Closesthit or miss
shading is then invoked in a more coherent context.

Note that this is a very basic example. Among other things, it is possible to
query information about the hit to influence `MaybeReorderThread` with additional
hints. See [Separation of MaybeReorderThread and HitObject::Invoke](#separation-of-MaybeReorderThread-and-hitobjectinvoke)
for more elaborate examples.

`TraceRay` returning a `HitObject` can be called on its own as well without
calling `ReorderThread` or `Invoke`.  The caller might just want a `HitObject` 
without caring about thread reordering or Closesthit or miss shading. 
This is discussed in [Device Support](#device-support), in particular
the implication given that SER is required as part of Shader Model 6.9 for 
raytracing capable devices: Even for devices that only trivially support SER 
by doing nothing on `ReorderThread` must also support `Invoke` not being called,
essentially a new capability to skip final shading not available before.

### HitObject HLSL Additions

```C++
namespace dx {
  HitObject
}
```

The `HitObject` type encapsulates information about a hit or a miss. A
`HitObject` is constructed using `HitObject::TraceRay`,
`HitObject::FromRayQuery`, `HitObject::MakeMiss`, or `HitObject::MakeNop`. It
can be used to invoke closesthit or miss shading using `HitObject::Invoke`,
and to reorder threads for shading coherence with `MaybeReorderThread`.

The `HitObject` has value semantics, so modifying one `HitObject` will not
impact any other `HitObject` in the shader. A shader can have any number of
active `HitObject`s at a time. Each `HitObject` will take up some hardware
resources to hold information related to the hit or miss, including ray,
intersection attributes and information about the shader to invoke. The size
of a `HitObject` is unspecified, and thus considered intangible. As a
consequence, `HitObject` cannot be stored in memory buffers, in groupshared
memory, in ray payloads, or in intersection attributes. `HitObject` supports
assignment (by-value copy) and can be passed as arguments to and returned from
local inlined functions.

A `HitObject` is default-initialized to encode a NOP-HitObject (see `HitObject::MakeNop`).
A NOP-HitObject can be used with `HitObject::Invoke` and `MaybeReorderThread` but
does not call shaders or provide additional information for reordering.
Most accessors will return zero-initialized values for a NOP-HitObject.

### Valid Shader Stages

The `HitObject` type and related functions are available only in the following
shader stages: `raygeneration`, `closesthit`, `miss` (the shader stages that
may call `TraceRay`).

---

#### HitObject::TraceRay

Executes traversal (including anyhit and intersection shaders) and returns the
resulting hit or miss information as a `HitObject`. Unlike `TraceRay`, this
does not execute closesthit or miss shaders. The resulting payload is not part
of the `HitObject`. See
[Interaction with Payload Access Qualifiers](#interaction-with-payload-access-qualifiers)
for details.

```C++
template<payload_t>
static dx::HitObject dx::HitObject::TraceRay(
    RaytracingAccelerationStructure AccelerationStructure,
    uint RayFlags,
    uint InstanceInclusionMask,
    uint RayContributionToHitGroupIndex,
    uint MultiplierForGeometryContributionToHitGroupIndex,
    uint MissShaderIndex,
    RayDesc Ray,
    inout payload_t Payload);
```

See `TraceRay` for parameter definitions.

The returned `HitObject` will always encode a hit or a miss, i.e., it will
never be a NOP-HitObject.

`HitObject::TraceRay` must not be invoked if the maximum trace recursion depth
has been reached.

This function introduces [Reorder Points](#reorder-points).

---

#### HitObject::FromRayQuery

Construct a `HitObject` representing the committed hit in a `RayQuery`. It is
not bound to a shader table record and behaves as a NOP-HitObject if invoked.
It can be used for reordering based on hit information.
If no hit is committed in the RayQuery,
the HitObject returned is a NOP-HitObject. A shader table record can be assigned
separately, which in turn allows invoking a shader.

An overload takes a user-defined hit kind and custom attributes associated with
COMMITTED_PROCEDURAL_PRIMITIVE_HIT.
It is ok to always use the overload, even for COMMITTED_TRIANGLE_HIT. For anything
other than a procedural hit, the specified hit kind and attributes are ignored.

```C++
static dx::HitObject dx::HitObject::FromRayQuery(
    RayQuery Query);

template<attr_t>
static dx::HitObject dx::HitObject::FromRayQuery(
    RayQuery Query,
    uint CommittedCustomHitKind,
    attr_t CommittedCustomAttribs);
```

Parameter                           | Definition
---------                           | ----------
`Return: HitObject` | The `HitObject` that contains the result of the initialization operation.
`RayQuery Query` | RayQuery from which the hit is created.
`uint CommittedCustomHitKind` | See the `HitKind` parameter of `ReportHit` for definition.
`attr_t CommittedCustomAttribs` | See the `Attributes` parameter of `ReportHit` for definition. If a closesthit shader is invoked from this `HitObject`, `attr_t` must match the attribute type of the closesthit shader.

The size of `attr_t` must not exceed `MaxAttributeSizeInBytes` specified in the `D3D12_RAYTRACING_SHADER_CONFIG`.

---

#### HitObject::MakeMiss

Construct a `HitObject` representing a miss without tracing a ray. It is
legal to construct a `HitObject` that differs from the result that would be
obtained by passing the same parameters to `HitObject::TraceRay`, e.g.,
constructing a miss for a ray that would have hit some geometry if it were
traced.

```C++
static dx::HitObject dx::HitObject::MakeMiss(
    uint RayFlags,
    uint MissShaderIndex,
    RayDesc Ray);
```

Parameter                           | Definition
---------                           | ----------
`Return: HitObject` | The `HitObject` that contains the result of the initialization operation.
`uint RayFlags` | Valid combination of Ray flags as specified by `TraceRay`. Only defined ray flags are propagated by the system.
`uint MissShaderIndex` | The miss shader index, used to calculate the address of the shader table record. The miss shader index must reference a valid shader table record. Only the least significant 16 bits of this value are used.

---

#### HitObject::MakeNop

Construct a NOP-HitObject that represents neither a hit nor a miss. This is
the same as a default-initialized `HitObject`. NOP-HitObjects can be useful in
certain scenarios when combined with `MaybeReorderThread`, e.g., when a thread
wants to participate in reordering without executing a closesthit or miss
shader.

```C++
static dx::HitObject dx::HitObject::MakeNop();
```

Parameter                           | Definition
---------                           | ----------
`Return: HitObject` | The `HitObject` initialized to a NOP-HitObject.

---

#### HitObject::Invoke

Execute closesthit or miss shading for the hit or miss encapsulated in a
`HitObject`. The `HitObject` fully determines the system values accessible
from the closesthit or miss shader.
A NOP-HitObject or a `HitObject` constructed from a `RayQuery` without
setting a shader table index will not invoke a shader and is effectively
ignored.

The `HitObject::Invoke` call counts towards the trace recursion depth. It must
not be invoked if the maximum trace recursion depth has already been reached.
It is legal to call `Invoke` with the same `HitObject` multiple times. The
`HitObject` is not modified by `Invoke`.

This function introduces [Reorder Points](#reorder-points), also in cases
where no shader is invoked.

```C++
template<payload_t>
static void dx::HitObject::Invoke(
    dx::HitObject Hit,
    inout payload_t Payload);
```

Parameter                           | Definition
---------                           | ----------
`HitObject Hit` | `HitObject` that encapsulates information about the closesthit or miss shader to be executed. If the `HitObject` is a NOP-HitObject or a `HitObject` constructed from a `RayQuery` without setting a shader table index, then neither a closeshit nor a miss shader will be executed.
`payload_t Payload` | The ray payload. `payload_t` must match the type expected by the shader being invoked. See [Interaction With Payload Access Qualifiers](#interaction-with-payload-access-qualifiers) for details.

> It is legal to call `HitObject::TraceRay` with a different payload type than
> a subsequent `HitObject::Invoke`. One use case for this is a pipeline with
> anyhit shaders that require only a small payload, combined with closesthit
> shaders that read inputs from a large payload.  Payload Access Qualifiers
> can express this situation, but don't allow for as much optimization as
> using two different payloads with `HitObject` does. That is because anyhit
> would have to preserve the fields read by closesthit, unnecessarily
> increasing register pressure on anyhit. Note that allowing different payload
> types within a hit group is not a spec change, because payload compatibility
> matters at runtime, not compile time. That is, at runtime, the payload type
> passed to the calling `TraceRay`/`HitObject::TraceRay`/`HitObject::Invoke`
> must match the payload type of the _invoked_ shaders (only). With the
> introduction of `HitObject`, it can now be desirable for applications to
> create hit groups where the payload type in anyhit differs from the payload
> type in closesthit, whereas without `HitObject` this was merely legal but
> not particularly useful.

---

#### HitObject::IsMiss

```C++
bool dx::HitObject::IsMiss();
```

Returns `true` if the `HitObject` encodes a miss. If the `HitObject` encodes a
hit or is a NOP-HitObject, returns `false`.

---

#### HitObject::IsHit

```C++
bool dx::HitObject::IsHit();
```

Returns `true` if the `HitObject` encodes a hit. If the `HitObject` encodes a
miss or is a NOP-HitObject, returns `false`.

---

#### HitObject::IsNop

```C++
bool dx::HitObject::IsNop();
```

Returns `true` if the `HitObject` is a NOP-HitObject, otherwise returns
`false`.

---

#### HitObject::GetRayFlags

```C++
uint dx::HitObject::GetRayFlags();
```

Returns the ray flags associated with the hit object.

Returns 0 if the `HitObject` is a NOP-HitObject.

---

#### HitObject::GetRayTMin

```C++
float dx::HitObject::GetRayTMin();
```

Returns the parametric starting point for the ray associated with the hit
object.

Returns 0 if the `HitObject` is a NOP-HitObject.

---

#### HitObject::GetRayTCurrent

```C++
float dx::HitObject::GetRayTCurrent();
```

Returns the parametric ending point for the ray associated with the hit
object. For a miss, the ending point indicates the maximum initially specified.

Returns 0 if the `HitObject` is a NOP-HitObject.

---

#### HitObject::GetWorldRayOrigin

```C++
float3 dx::HitObject::GetWorldRayOrigin();
```

Returns the world-space origin for the ray associated with the hit object.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetWorldRayDirection

```C++
float3 dx::HitObject::GetWorldRayDirection();
```

Returns the world-space direction for the ray associated with the hit object.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetObjectRayOrigin

```C++
float3 dx::HitObject::GetObjectRayOrigin();
```

Returns the object-space origin for the ray associated with the hit object.

If the `HitObject` encodes a miss, returns the world ray origin.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetObjectRayDirection

```C++
float3 dx::HitObject::GetObjectRayDirection();
```

Returns the object-space direction for the ray associated with the hit object.

If the `HitObject` encodes a miss, returns the world ray direction.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetObjectToWorld3x4

```C++
float3x4 dx::HitObject::GetObjectToWorld3x4();
```

Returns a matrix for transforming from object-space to world-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetObjectToWorld4x3()` is the
matrix is transposed – use whichever is convenient.

---

#### HitObject::GetObjectToWorld4x3

```C++
float4x3 dx::HitObject::GetObjectToWorld4x3();
```

Returns a matrix for transforming from object-space to world-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetObjectToWorld3x4()` is
the matrix is transposed – use whichever is convenient.

---

#### HitObject::GetWorldToObject3x4

```C++
float3x4 dx::HitObject::GetWorldToObject3x4();
```

Returns a matrix for transforming from world-space to object-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetWorldToObject4x3()` is
the matrix is transposed – use whichever is convenient.

---

#### HitObject::GetWorldToObject4x3

```C++
float4x3 dx::HitObject::GetWorldToObject4x3();
```

Returns a matrix for transforming from world-space to object-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetWorldToObject3x4()` is
the matrix is transposed – use whichever is convenient.

---

#### HitObject::GetInstanceIndex

```C++
uint dx::HitObject::GetInstanceIndex();
```

Returns the instance index of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetInstanceID

```C++
uint dx::HitObject::GetInstanceID();
```

Returns the instance ID of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetGeometryIndex

```C++
uint dx::HitObject::GetGeometryIndex();
```

Returns the geometry index of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetPrimitiveIndex

```C++
uint dx::HitObject::GetPrimitiveIndex();
```

Returns the primitive index of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetHitKind

```C++
uint dx::HitObject::GetHitKind();
```

Returns the hit kind of a hit. See `HitKind` for definition of possible values.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetAttributes

```C++
template<attr_t>
attr_t dx::HitObject::GetAttributes();
```

Returns the attributes of a hit. `attr_t` must match the committed
attributes’ type regardless of whether they were committed by an intersection
shader, fixed function logic, or using `HitObject::FromRayQuery`.

If the `HitObject` does not encode a hit, the returned value will be
zero-initialized. The size of `attr_t` must not exceed
`MaxAttributeSizeInBytes` specified in the `D3D12_RAYTRACING_SHADER_CONFIG`.

---

#### HitObject::GetShaderTableIndex

```C++
uint dx::HitObject::GetShaderTableIndex()
```

Returns the index used for shader table lookups. If the `HitObject` encodes a
hit, the index relates to the hit group table. If the `HitObject` encodes a
miss, the index relates to the miss table. If the `HitObject` is a
NOP-HitObject, or a `HitObject` constructed from a `RayQuery` without setting
a shader table index, the return value is zero.

---

#### HitObject::SetShaderTableIndex

```C++
void dx::HitObject::SetShaderTableIndex(uint RecordIndex)
```

Sets the index used for shader table lookups.

Parameter                           | Definition
---------                           | ----------
`uint RecordIndex` | The index into the hit or miss shader table. If the `HitObject` is a NOP-HitObject, the value is ignored.

> If the `HitObject` encodes a hit, the index relates to the hit group table and only the bottom 28 bits are used:

```C++
HitGroupRecordAddress =
    D3D12_DISPATCH_RAYS_DESC.HitGroupTable.StartAddress + // from: DispatchRays()
    D3D12_DISPATCH_RAYS_DESC.HitGroupTable.StrideInBytes * // from: DispatchRays()
    HitGroupRecordIndex; // from shader: HitObject::SetShaderTableIndex(RecordIndex)
```

> If the `HitObject` encodes a miss, the index relates to the miss table and only the least significant 16 bits are used:

```C++
MissRecordAddress =
    D3D12_DISPATCH_RAYS_DESC.MissShaderTable.StartAddress + // from: DispatchRays()
    D3D12_DISPATCH_RAYS_DESC.MissShaderTable.StrideInBytes * // from: DispatchRays()
    MissRecordIndex; // from shader: HitObject::SetShaderTableIndex(RecordIndex)
```

---

#### HitObject::LoadLocalRootTableConstant

```C++
uint dx::HitObject::LoadLocalRootTableConstant(uint RootConstantOffsetInBytes)
```

Load a local root table constant from the shader table. The offset is
specified from the start of the local root table arguments, after the shader
identifier. This function is particularly convenient for applications to
"peek" at material properties or flags stored in the shader table and use
that information to augment reordering decisions before invoking a hit shader.

`RootConstantOffsetInBytes` must be a multiple of 4.

If the `HitObject` is a NOP-HitObject or a `HitObject` constructed from a
`RayQuery` without setting a shader table index, the return value is zero.

---

#### Interaction with Payload Access Qualifiers

Payload Access Qualifiers (PAQs) describe how information flows between
shader stages in `TraceRay`:

```C++
caller -> anyhit -> (closesthit|miss) -> caller
           ^  |
           |__|
```

With `HitObject`, control is returned to the caller after
`HitObject::TraceRay` completed and hence caller is inserted between anyhit
and (closesthit|miss).

The flow for `HitObject::TraceRay` is:

```C++
caller -> anyhit -> caller
           ^  |
           |__|
```

The flow for `HitObject::Invoke` is:

```C++
caller -> (closesthit|miss) -> caller
```

To allow interchangeability of payload types between `TraceRay` and the new
execution model introduced with `HitObject::TraceRay`/`HitObject::Invoke`,
the following additional PAQ rules apply:

- At the call to `HitObject::TraceRay`, any field declared as `read(miss)` or
`read(closesthit)` is treated as `read(caller)`
- At the call to `HitObject::Invoke`, any field declared as `write(anyhit)`
is treated as `write(caller)`

### MaybeReorderThread HLSL Additions

`MaybeReorderThread` provides an efficient way for the application to reorder work
across the physical threads running on the GPU in order to improve the
coherence and performance of subsequently executed code. The target ordering
is given by the arguments passed to `MaybeReorderThread`. For example, the
application can pass a `HitObject`, indicating to the system that coherent
execution is desired with respect to a ray hit location in the scene.
Reordering based on a `HitObject` is particularly useful in situations with
highly incoherent hits, e.g., in path tracing applications.

`MaybeReorderThread` is available only in shaders of type `raygeneration`.

This function introduces a [Reorder Point](#reorder-points).

#### Example 1

The following example shows a common pattern of combining `HitObject` and
`MaybeReorderThread`:

```C++
// Trace a ray without invoking closesthit/miss shading.
HitObject hit = HitObject::TraceRay( ... );

// Reorder by hit point to increase coherence of subsequent shading.
MaybeReorderThread( hit );

// Invoke shading.
HitObject::Invoke( hit, ... );
```

---

#### MaybeReorderThread with HitObject

This variant of `MaybeReorderThread` reorders calling threads based on the
information contained in a `HitObject`.

It is implementation defined which `HitObject` properties are taken into
account when defining the ordering. For example, an implementation may decide
to order threads with respect to their hit group index, hit locations in
3d-space, or other factors.

`MaybeReorderThread` may access both information about the instance in the
acceleration structure as well as the shader record at the shader table
offset contained in the `HitObject`. The respective fields in the `HitObject`
must therefore represent valid instances and shader table offsets.
NOP-HitObjects is an exception, which do not contain information about a hit
or a miss, but are still legal inputs to `MaybeReorderThread`. Similarly, a
`HitObject` constructed from a `RayQuery` but did not set a shader table
index is exempt from having a valid shader table record.

```C++
void dx::MaybeReorderThread(dx::HitObject Hit);
```

Parameter                           | Definition
---------                           | ----------
`HitObject Hit` | `HitObject` that encapsulates the hit or miss according to which reordering should be performed.

---

#### MaybeReorderThread with coherence hint

This variant of `MaybeReorderThread` reorders threads based on a generic
user-provided hint. Similarity of hint values should indicate expected
similarity of subsequent work being performed by threads. More significant
bits of the hint value are more important than less significant bits for
determining coherency. Specific scheduling behavior may vary by
implementation. The resolution of
the hint is implementation-specific. If an implementation cannot resolve all
values of `CoherenceHint`, it is free to ignore an arbitrary number of least
significant bits. The thread ordering resulting from this call may be
approximate.

```C++
void dx::MaybeReorderThread(uint CoherenceHint, uint NumCoherenceHintBitsFromLSB);
```

Parameter                           | Definition
---------                           | ----------
`uint CoherenceHint` | User-defined value that determines the desired ordering of a thread relative to others.
`uint NumCoherenceHintBitsFromLSB` | Indicates how many of the least significant bits in `CoherenceHint` the implementation should try to take into account. Applications should set this to the lowest value required to represent all possible values of `CoherenceHint` (at the given `MaybeReorderThread` call site). All threads should provide the same value at a given call site to achieve best performance.

---

#### MaybeReorderThread with HitObject and coherence hint

This variant of `MaybeReorderThread` reorders threads based on the information
contained in a `HitObject`, supplemented by additional information expressed
as a user-defined hint. The user-provided hint should mainly map properties
that an implementation cannot infer from the `HitObject` itself. This can
represent material- or other application-specific behavior. Examples include
stochastic behavior such as loop termination by russian roulette in path
tracing, or a material specific trait that is handled in a branch within a
closeshit shader.

An implementation should attempt to group threads both by information in the
`HitObject` and by information in the coherence hint. The details of how this
information is combined for reordering is implementation specific, but
implementations should generally prioritize the hit group specified in the
`HitObject` higher than the coherence hint. This lets applications use the
coherence hint to reduce divergence from important branches within closesthit
shaders, like the aforementioned material traits.

Note that the number of coherence hint bits that the implementation actually
honors can be smaller in this overload of `MaybeReorderThread` compared to the one
described in
[MaybeReorderThread with coherence hint](#MaybeReorderThread-with-coherence-hint).

```C++
void dx::MaybeReorderThread(
    dx::HitObject Hit,
    uint CoherenceHint,
    uint NumCoherenceHintBitsFromLSB);
```

Parameter                           | Definition
---------                           | ----------
`HitObject Hit` | `HitObject` that encapsulates the hit or miss according to which reordering should be performed.
`uint CoherenceHint` | User-defined value that determines the desired ordering of a thread relative to others.
`uint NumCoherenceHintBitsFromLSB` | Indicates how many of the least significant bits in `CoherenceHint` the implementation should try to take into account. Applications should set this to the lowest value required to represent all possible values of `CoherenceHint` (at the given `MaybeReorderThread` call site). All threads should provide the same value at a given call site to achieve best performance.

---

#### Example 2

The following pseudocode shows an example of reordering with coherence hints
as it might be used in a simple path tracer.

```C++
for( int bounceCount=0; ; bounceCount++ )
{
    // Trace the next ray
    HitObject hit = HitObject::TraceRay( ray, payload, ... );

    // Assume per-geometry albedo information is stored in the Shader Table
    float albedo = asfloat( hit.LoadLocalRootTableConstant(0) );

    // Use the albedo information and current bounce count to estimate whether
    // we're likely to exit the loop after shading the current hit, and turn
    // that estimate into a coherence hint for reordering. Note that whether
    // this estimate is correct or not only affects performance, not
    // correctness.
    bool probablyFinished = russianRoulette(albedo)
                            || bounceCount >= maxBounces;
    uint coherenceHints = probablyFinished ? 1 : 0;

    // Reorder based on the hit, while taking into account how likely we are to
    // exit the loop this round.
    MaybeReorderThread( hit, coherenceHints, 1 );

    // Invoke shading for the current hit. Due to the reordering performed
    // above, this will have increased coherence.
    HitObject::Invoke( hit, payload );

    // Test whether the loop should actually exit, or whether we should compute
    // the next light bounce.
    if( payload.needsNextBounce && bounceCount < maxBounces )
        ray = sampleNextBounce( ... );
    else
        break;
}
```

#### Example 3

The following pseudocode shows another example of reordering used in the
context of path tracing with a slightly different loop structure. In this
case, NOP-HitObject are used in reordering to ensure coherent execution not
only of shaders, but also of the code after the loop.


```C++
for( int bounceCount=0; ; bounceCount++ )
{
    HitObject hit;    // initialize to NOP-HitObject

    // Have threads conditionally participate in the next bounce depending on
    // loop iteration count and path throughput. Instead of having
    // non-participating threads break out of the loop here, we let them
    // participate in the reordering with a NOP-HitObject first.
    // This will cause them to be grouped together and execute the work after
    // the loop with higher coherence. Note that the values of 'bounceCount'
    // might differ between threads in a wave, because reordering may group
    // threads from different iteration counts together if their hit locations
    // are similar.
    if( bounceCount < MaxBounces && throughput > ThroughputThreshold )
    {
        // Trace the next ray
        hit = HitObject::TraceRay( ray, payload, ... );
    }

    // Reorder based on the ray hit. Some of the hit objects may be NOPs; these
    // will be grouped together. Note that ordering by the type of hitobject
    // (hit,miss,nop) can be expected to take precedence over ordering by the
    // shader ID represented by the hitobject. This is as opposed to coherence
    // hint bits, which have lower priority than the shader ID during
    // reordering.
    MaybeReorderThread( hit );

    // Now that we've reordered, break non-participating threads out of the
    // loop.
    if( hit.IsNop() )
        break;

    // Execute shading and update path throughput.
    HitObject::Invoke( hit, payload );
    throughput *= payload.brdfValue;
}

// Assume significant work here that benefits from waves breaking out of the
// loop coherently.
<...>
```

---

## Reorder points

The existing DXR API define _repacking points_ at `TraceRay` and `CallShader`.
This proposal aims to formalize the concept and suggests renaming them to _reorder points_.

A reorder point is a point in the control flow of a shader or sequence of
shaders where the system may arbitrarily change the physical arrangement of
threads executing on the GPU, usually with the goal of increasing coherence.
That is, the system may choose to migrate thread contexts that arrive at a
reorder point to different processors, different waves or groups, or indices
within waves or groups. Such migrations can be visible to the application if
the application queries certain system state, such as group or thread IDs,
wave lane indices, ballots, etc.

The existing DXR API has reorder points due to `TraceRay` and `CallShader`.
The _Shader Execution Reordering_ specification adds several new reorder
points. The following is a comprehensive list of existing and newly added
reorder points:

- `TraceRay`: transitions to and from `anyhit`, `intersection`, `closesthit`,
and `miss` shaders. In the case of multiple `anyhit` or `intersection` shader
invocations, each shader stage transition is a separate reorder point.
- `CallShader`: transitions to and from the `callable` shader.
- `HitObject::TraceRay`: transitions to and from `anyhit` and `intersection`
shaders. In the case of multiple `anyhit` or `intersection` shader
invocations, each shader stage transition is a separate reorder point.
- `HitObject::Invoke`: transitions to and from `closeshit` and `miss` shaders.
Constitutes a reorder point even in cases where no shader is invoked.
- `MaybeReorderThread`: the `MaybeReorderThread` call site.

`MaybeReorderThread` stands out as it explicitly separates reordering from a
transition between shader stages, thus, it allows applications to (carefully)
choose the most effective reorder locations given a specific workload. The
combination of `HitObject` and coherence hints provides additional control
over the reordering itself. These characteristics make `MaybeReorderThread` a
versatile tool for improving performance in a variety of workloads that suffer
from divergent execution or data access.

Similar to `TraceRay` and `CallShader`, the behavior of the actual reorder
operation at any reorder point is implementation specific. An implementation
may, for instance, not reorder at all, reorder within some local domain
(threads on a local processor), reorder only within a certain time window,
reorder globally across the entire GPU and the entire dispatch, or any
variation thereof. The general target is for implementations to make a _best
effort_ to extract as much coherence as possible, while keeping the overhead
of reordering low enough to be practical for use in typical raytracing
scenarios.

While it is understood that reordering at `TraceRay` and `CallShader` is done
at the discretion of the driver, `HitObject::TraceRay` and `HitObject::Invoke`
are intended to be used in conjunction with `MaybeReorderThread`.
Reordering at `HitObject::TraceRay` and `HitObject::Invoke` is permitted but the
driver should minimize its efforts to reorder for hit coherence and instead
prioritize reordering through `MaybeReorderThread`.

Some implementations may achieve best performance when `HitObject::TraceRay`,
`MaybeReorderThread`, and `HitObject::Invoke` are called back-to-back.
This case is semantically equivalent to DXR 1.0 `TraceRay` but with defined
reordering characteristics.
The back-to-back combination of `MaybeReorderThread` and `HitObject::Invoke` may
similarly see a performance benefit on some implementations.

For performance reasons, it is crucial that the DXIL-generating compiler does
not move non-uniform resource access across reorder points in general, and across
`MaybeReorderThread` in particular. It should be assumed that the shader will perform
the access where coherence is maximized.

---

### Divergence behavior

An implementation may only reorder threads whose control flow arrives at a
reorder point. Threads that do not arrive at a reorder point are guaranteed to
not migrate, even if neighboring threads in the same wave do migrate.

From the physical wave's point of view, an implementation may remove, replace,
or do nothing with threads that arrive at a reorder point. It is also legal for
an implementation to replace threads that were inactive at the start of the
wave or those that exited the shader during execution, as long as any remaining
thread reach a reorder point. This may indirectly affect threads that
conditionally did not invoke a reorder point, as illustrated in the following
code snippet:

```C++
int MyFunc(int coherenceCoord)
{
    int A = WaveActiveBallot(true);
    if (WaveIsFirstLane())
        MaybeReorderThread(coherenceCoord, 32);
    int B = WaveActiveBallot(true);
    return A - B;
}
```

In this example, a number of different things could happen:
- If the implementation does not honor `MaybeReorderThread` at all, the function
will most likely return zero, as the set of threads before and after the
conditional reorder would be the same.
- If the implementation reorders threads invoking `MaybeReorderThread` but does not
replace them, B will likely be less than A for threads not invoking
`MaybeReorderThread`, while the reordered threads will likely resume execution with
a newly formed full wave, thereby obtaining `A <= B`.
- If the implementation replaces threads in a wave, the threads not
participating in the reorder may possibly be joined by more threads than were
removed from the wave, again observing `A <= B`.

---

### Memory coherence and visibility

Due to the existence of non-coherent caches on most modern GPUs, an
application must take special care when communicating information across
reorder points through memory (UAVs). This proposal introduces a new
coherence scope for communication between reorder points within the same
dispatch index. The following additions are made:
- A new `[reordercoherent]` storage class for UAVs.
- A new `REORDER_SCOPE = 0x8` member in the `SEMANTIC_FLAG` enum for use in barriers.

Specifically, if UAV stores or atomics are performed on one side of a
reorder point, and on the other side the data is read via non-atomic
UAV reads, the following steps are required:
1. The UAV must be declared `[reordercoherent]`.
2. The UAV writer must issue a `Barrier(UAV_MEMORY, REORDER_SCOPE)` between the write and the reorder point.

Note that these steps are required to ensure coherence across any reorder point.
For example, between a write performed before `MaybeReorderThread` or `TraceRay` and a
subsequent read in the same shader, or between shader stages (such as data written
in the closesthit shader and read in the raygeneration shader).

When communicating both between threads with different dispatch index and
across reorder points the reorder coherence scope is insufficient.
Instead, global coherency can be utilized as follows:
1. The UAV must be declared `[globallycoherent]`.
2. The UAV writer must issue a `DeviceMemoryBarrier` between the write and the
reorder point.

## Separation of MaybeReorderThread and HitObject::Invoke

`MaybeReorderThread` and `HitObject::Invoke` are kept separate. It enables calling
`MaybeReorderThread` without `HitObject::Invoke`, and `HitObject::Invoke` without
calling `MaybeReorderThread`. These are valid use cases as reordering can be
beneficial even when shading happens inline in the raygeneration shader, and
reordering before a known to be coherent or cheap shader can be
counterproductive. For cases in which both is desired, keeping `MaybeReorderThread`
and `HitObject::Invoke` separated is still beneficial as detailed below.

Common hit processing can happen in the raygeneration shader with the
additional efficiency gains of hit coherence. Benefits include:
- Logic otherwise duplicated can be hoisted into the raygeneration shader
without a loss of hit coherence. This can reduce instruction cache pressure
and reduce compile times.
- Logic between `MaybeReorderThread` and `HitObject::Invoke` have access to the
full state of the raygeneration shader. It can access a large material stack
keeping track of surface boundaries, for example. This is difficult or
impossible to communicate through the payload.
- Modularity between the shader stages is improved by allowing hit shading to
focus on surface logic. Different raygeneration shaders, and different call
sites within a raygeneration shader, may want to vary how common logic is
implemented. E.g., on first bounce a shadow ray may be fired after performing
common light sampling. On a second bounce a shadow map lookup may be enough.

In addition to the above, API complexity is reduced by only having separate
calls, as opposed to both separate calls and a fused variant. Further,
`MaybeReorderThread` naturally communicates a reorder point, when hit-coherent
execution starts and that it will persist after the call (until the next
reorder point). Reasoning about the execution and that it is hit-coherent is
not as obvious after a call to a hypothetical (fused)
`HitObject::ReorderAndInvoke`. Finally, tools can report live state across
`MaybeReorderThread` and users can optimize live state across it. This is important
as live state across `MaybeReorderThread` may be more expensive on some
architectures.

Some examples follow.

### Example: Common computations that rely on large raygeneration state

In this example, a large number of surface events are tracked in the ray generation shader.
Only the result is communicated to the invoked shader via the payload.

```C++
struct IorData
{
    float ior;
    uint id;
};

IorData iorList[16];
uint iorListSize = 0;

for( ... )
{
    HitObject hit = HitObject::TraceRay( ... );
    MaybeReorderThread( hit );

    IorData newEntry = LoadIorDataFromHit( hit );
    bool enter = hit.GetHitKind() == HIT_KIND_TRIANGLE_FRONT_FACE;

    payload.ior = UpdateIorList( newEntry, enter, iorList, iorListSize );

    HitObject::Invoke( hit, payload );
}
```

### Example: Do common computations with hit-coherence

In this example, common code runs in the raygeneration shader, after
the thread has been reordered for hit coherence.

```C++
hit = HitObject::TraceRay( ... );
MaybeReorderThread( hit );

payload.giData = GlobalIlluminationCacheLookup( hit );

HitObject::Invoke( hit, payload );
```

### Example: Same surface shader but different behavior in the raygeneration shader

This example demonstrates varying reordering behavior and shadow logic, despite
using the same shader code.

```C++
// Primary ray wants perfect shadows and does not need to explicitly
// reorder for hit coherence as it is coherent enough.
ray = GeneratePrimaryRay();
hit = HitObject::TraceRay( ... );
// NOTE: Although MaybeReorderThread is not explicitly invoked here,
// reordering can still occur at any reorder point based on
// driver-specific decisions.
RayDesc shadowRay = SampleShadow( hit );
payload.shadowTerm = HitObject::TraceRay( shadowRay ).IsHit() ? 0.0f : 1.0f;
HitObject::Invoke( hit, payload );

// Secondary ray is incoherent but does not need perfect shadows.
ray = ContinuePath( payload );
hit = HitObject::TraceRay( ... );
MaybeReorderThread( hit );
payload.shadowTerm = SampleShadowMap( hit );
HitObject::Invoke( hit, payload );
```

### Example: Unified shading

No hit shader is invoked in this example; however, reordering can still
improve data coherence.

```C++
hit = HitObject::TraceRay( ... );

MaybeReorderThread( hit );

// Do not call HitObject::Invoke. Shade in raygeneration.
```

### Example: Coherently break render loop on miss

Executing the miss shader when not needed is unnecessarily inefficient
on some architectures. In this example, miss shader execution is skipped.

Note that behavior can vary. Other architectures may have better efficiency
when `HitObject::TraceRay`, `MaybeReorderThread` and `HitObject::Invoke` are
called back-to-back (see [Reorder Points](#reorder-points)).

```C++
for( ;; )
{
    hit = HitObject::TraceRay( ... );
    MaybeReorderThread( hit );

    if( hit.IsMiss() )
        break;

    HitObject::Invoke( hit, payload );
}
```

### Example: Two-step shading, single reorder

In this example, shading is performed in two steps.
The first step gathers material information, while the second step dispatches a common surface shader.
This approach can help reduce shader permutations.

```C++
hit = HitObject::TraceRay( ... );
MaybeReorderThread( hit );

// Gather surface parameters into payload, e.g., compute normal and albedo
// based on surface-specific functions and/or textures.
HitObject::Invoke( hit, payload );

// Alter the hit object to point to a unified surface shader.
hit.SetShaderTableIndex( payload.surfaceShaderIdx );

// Invoke unified surface shading. We are already hit-coherent so it is not
// worth explicitly reordering again.
// Reordering may still occur at any reorder point based on driver-specific
// decisions.
HitObject::Invoke( hit, payload );
```

### Example: Live state optimization

In this example, logic is added to compress and uncompress part of the
payload across `MaybeReorderThread`.
This can make sense if live state is more expensive across `MaybeReorderThread`.

Some implementations may favor cases where `HitObject::TraceRay`, `MaybeReorderThread`
and `HitObject::Invoke` are called back-to-back (see [Reorder Points](#reorder-points)),
so performance profiling is necessary.

```C++
hit = HitObject::TraceRay( ... );

uint compressedNormal = CompressNormal( payload.normal );
MaybeReorderThread( hit );
payload.normal = UncompressNormal( compressedNormal );

HitObject::Invoke( hit, payload );
```

### Example: Back-to-back calls

This example demonstrates the back-to-back arrangement of `HitObject::TraceRay`,
`MaybeReorderThread`, and `HitObject::Invoke`.
For some architectures, this arrangement is the most efficient, as it can be
recognized as a single reorder point, reducing call overhead
(see [Reorder Points](#reorder-points)).
Additional logic between these calls should only be added when necessary.

```C++
hit = HitObject::TraceRay( ... );
MaybeReorderThread( hit );
HitObject::Invoke( hit, payload );
```

## DXIL specification

The DXIL specification follows directly from the
[detailed HLSL design](#detailed-design).
The concept of a `HitObject` is represented by the DXIL type
`dx.types.HitObject`:

```DXIL
%dx.types.HitObject = type { i8 * }
```

Central to `dx.types.HitObject` is its value semantics;
an assignment is a copy.
As the size of `dx.types.HitObject` is unknown at the DXIL level, the driver
compiler will employ type replacement early in the lowering process. This is
analogous to how `dx.types.Handle` is lowered.
The DXIL-generating compiler will guarantee that the type is
trivially replaceable, e.g., prevent SROA from splitting up the type.

All intrinsics take `dx.types.HitObject` by value. Any intrinsic that produces
a new `HitObject` will return a new `dx.types.HitObject` value.
Intrinsics that modify a `HitObject` take the `dx.types.HitObject` by value and return a modified `dx.types.HitObject` value.

### New operations

| Opcode | Opcode name | Description
|:---    |:---         |:---
XXX      | HitObject_TraceRay | Analogous to TraceRay but without invoking CH/MS and returns the intermediate state as a `HitObject`.
XXX + 1  | HitObject_FromRayQuery | Creates a new `HitObject` representing a committed hit from a `RayQuery`.
XXX + 2  | HitObject_FromRayQueryWithAttrs | Creates a new `HitObject` representing a committed hit from a `RayQuery` and committed attributes.
XXX + 3  | HitObject_MakeMiss | Creates a new `HitObject` representing a miss.
XXX + 4  | HitObject_MakeNop | Creates an empty nop `HitObject`.
XXX + 5  | HitObject_Invoke | Represents the invocation of the CH/MS shader represented by the `HitObject`.
XXX + 6  | MaybeReorderThread | Reorders the current thread. Optionally accepts a `HitObject` arg, or `undef`.
XXX + 7  | HitObject_IsMiss | Returns `true` if the `HitObject` represents a miss.
XXX + 8  | HitObject_IsHit | Returns `true` if the `HitObject` represents a hit.
XXX + 9  | HitObject_IsNop | Returns `true` if the `HitObject` is a NOP-HitObject.
XXX + 10 | HitObject_RayFlags | Returns the ray flags set in the HitObject.
XXX + 11 | HitObject_RayTMin | Returns the TMin value set in the HitObject.
XXX + 12 | HitObject_RayTCurrent | Returns the current T value set in the HitObject.
XXX + 13 | HitObject_WorldRayOrigin | Returns the ray origin in world space.
XXX + 14 | HitObject_WorldRayDirection | Returns the ray direction in world space.
XXX + 15 | HitObject_ObjectRayOrigin | Returns the ray origin in object space.
XXX + 16 | HitObject_ObjectRayDirection | Returns the ray direction in object space.
XXX + 17 | HitObject_ObjectToWorld3x4 | Returns the object to world space transformation matrix in 3x4 form.
XXX + 18 | HitObject_WorldToObject3x4 | Returns the world to object space transformation matrix in 3x4 form.
XXX + 19 | HitObject_GeometryIndex | Returns the geometry index committed on hit.
XXX + 20 | HitObject_InstanceIndex | Returns the instance index committed on hit.
XXX + 21 | HitObject_InstanceID | Returns the instance id committed on hit.
XXX + 22 | HitObject_PrimitiveIndex | Returns the primitive index committed on hit.
XXX + 23 | HitObject_HitKind | Returns the HitKind of the hit.
XXX + 24 | HitObject_ShaderTableIndex | Returns the shader table index set for this HitObject.
XXX + 25 | HitObject_SetShaderTableIndex | Returns a HitObject with updated shader table index.
XXX + 26 | HitObject_LoadLocalRootTableConstant | Returns the root table constant for this HitObject and offset.
XXX + 27 | HitObject_Attributes | Returns the attributes set for this HitObject.

#### HitObject_TraceRay

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_TraceRay.PayloadT(
    i32,              ; opcode
    %dx.types.Handle, ; acceleration structure handle
    i32,              ; ray flags
    i32,              ; instance inclusion mask
    i32,              ; ray contribution to hit group index
    i32,              ; multiplier for geometry contribution to hit group index
    i32,              ; miss shader index
    float,            ; ray origin x
    float,            ; ray origin y
    float,            ; ray origin z
    float,            : tMin
    float,            ; ray direction x
    float,            ; ray direction y
    float,            ; ray direction z
    float,            ; tMax
    PayloadT*)        ; payload
    nounwind
```

Validation errors:
- Validate the resource for `acceleration structure handle`.
- Validate the compatibility of type `PayloadT`.
- Validate that `payload` is a valid pointer.

#### HitObject_FromRayQuery

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_FromRayQuery(
    i32,                           ; opcode
    i32)                           ; ray query
    nounwind argmemonly

```
This is used for the HLSL overload of `HitObject::FromRayQuery` that only takes `RayQuery`.

Validation errors:
- Validate that `ray query` is a valid ray query handle.

#### HitObject_FromRayQueryWithAttrs

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_FromRayQueryWithAttrs.AttrT(
    i32,                           ; opcode
    i32,                           ; ray query
    i32,                           ; hit kind
    AttrT*)                        ; attributes
    nounwind argmemonly
```
This is used for the HLSL overload of `HitObject::FromRayQuery` that takes `RayQuery`, a user-defined hit kind, and `Attribute` struct.
`AttrT` is the user-defined intersection attribute struct type. See `ReportHit` for definition.

Validation errors:
- Validate that `ray query` is a valid ray query handle.
- Validate the compatibility of type `AttrT`.
- Validate that `attributes` is a valid pointer.

#### HitObject_MakeMiss

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_MakeMiss(
    i32,                           ; opcode
    i32,                           ; ray flags
    i32,                           ; miss shader index
    float,                         ; ray origin x
    float,                         ; ray origin y
    float,                         ; ray origin z
    float,                         : tMin
    float,                         ; ray direction x
    float,                         ; ray direction y
    float,                         ; ray direction z
    float)                         : tMax
    nounwind readnone
```

#### HitObject_MakeNop

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_MakeNop(
    i32)                           ; opcode
    nounwind readnone
```

#### HitObject_Invoke

```DXIL
declare void @dx.op.hitObject_Invoke.PayloadT(
    i32,                           ; opcode
    %dx.types.HitObject,           ; hit object
    PayloadT*)                     ; payload
    nounwind
```

Validation errors:
- Validate that `hit object` is not undef.
- Validate the compatibility of type `PayloadT`.
- Validate that `payload` is a valid pointer.

#### MaybeReorderThread

Operation that reorders the current thread based on the supplied hints and
`HitObject`. The HLSL overload without `HitObject` is lowered to the same intrinsic
with a NOP-HitObject (`HitObject_MakeNop`). The HLSL overload without coherence
hints is lowered by specifying `0` for `number of coherence hint bits from LSB`.

```DXIL
declare void @dx.op.MaybeReorderThread(
    i32,                      ; opcode
    %dx.types.HitObject,      ; hit object
    i32,                      ; coherence hint
    i32)                      ; num coherence hint bits from LSB
    nounwind
```

Validation errors:
- Validate that `coherence hint` is not `undef` if `num coherence hint bits from LSB` is nonzero.
- Validate that `hit object` is not `undef`.
- Validate that `num coherence hint bits from LSB` is not `undef`.

#### HitObject_SetShaderTableIndex

Returns a HitObject with updated shader table index.

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_SetShaderTableIndex(
    i32,                           ; opcode
    %dx.types.HitObject,           ; hit object
    i32)                           ; record index
    nounwind readnone
```

Validation errors:
- Validate that `hit object` is not undef.
- Validate that `record index` is not undef.

#### HitObject_LoadLocalRootTableConstant

Returns the root table constant for this HitObject and offset.

```DXIL
declare i32 @dx.op.hitObject_LoadLocalRootTableConstant(
    i32,                           ; opcode
    %dx.types.HitObject,           ; hit object
    i32)                           ; offset
    nounwind readonly
```

Validation errors:
- Validate that `hit object` is not undef.
- Validate that `offset` is not undef.

#### HitObject_Attributes

Copies the attributes set for this HitObject to the provided buffer.

```DXIL
declare void @dx.op.hitObject_Attributes.AttrT(
    i32,                           ; opcode
    %dx.types.HitObject,           ; hit object
    AttrT*)                        ; attributes
    nounwind argmemonly
```

`AttrT` is the user-defined intersection attribute struct type. See `ReportHit` for definition.

Validation errors:
- Validate that `hit object` is not undef.
- Validate the compatibility of type `AttrT`.
- Validate that `attributes` is a valid pointer.

#### Generic State Value getters

State value getters return scalar, vector or matrix values dependent on the provided opcode.
Scalar getters use the `hitobject_StateScalar` dxil intrinsic and the return type is the state value type.
Vector getters use the `hitobject_StateVector` dxil intrinsic and the return type is the vector element type.
Matrix getters use the `hitobject_StateMatrix` dxil intrinsic and the return type is the matrix element type.

 Opcode Name          | Return Type | Category  | Description
:------------         |:----------- |:--------- |:-----------
 HitObject_IsMiss            | `i1`    | scalar | Returns `true` if the `HitObject` represents a miss.
 HitObject_IsHit             | `i1`    | scalar | Returns `true` if the `HitObject` represents a hit.
 HitObject_IsNop             | `i1`    | scalar | Returns `true` if the `HitObject` is a NOP-HitObject.
 HitObject_RayFlags          | `i32`   | scalar | Returns the ray flags set in the HitObject.
 HitObject_RayTMin           | `float` | scalar | Returns the TMin value set in the HitObject.
 HitObject_RayTCurrent       | `float` | scalar | Returns the current T value set in the HitObject.
 HitObject_WorldRayOrigin    | `float` | vector | Returns the ray origin in world space.
 HitObject_WorldRayDirection | `float` | vector | Returns the ray direction in world space.
 HitObject_ObjectRayOrigin   | `float` | vector | Returns the ray origin in object space.
 HitObject_ObjectRayDirection| `float` | vector | Returns the ray direction in object space.
 HitObject_ObjectToWorld3x4  | `float` | matrix | Returns the object to world space transformation matrix in 3x4 form.
 HitObject_WorldToObject3x4  | `float` | matrix | Returns the world to object space transformation matrix in 3x4 form.
 HitObject_GeometryIndex     | `i32`   | scalar | Returns the geometry index committed on hit.
 HitObject_InstanceIndex     | `i32`   | scalar | Returns the instance index committed on hit.
 HitObject_InstanceID        | `i32`   | scalar | Returns the instance id committed on hit.
 HitObject_PrimitiveIndex    | `i32`   | scalar | Returns the primitive index committed on hit.
 HitObject_HitKind           | `i32`   | scalar | Returns the HitKind of the hit.
 HitObject_ShaderTableIndex  | `i32`   | scalar | Returns the shader table index set for this HitObject.


```DXIL
declare T @dx.op.hitObject_StateScalar.T(
    i32,                      ; opcode
    %dx.types.HitObject)      ; hit object
    nounwind readnone
```
The overload `T` is a valid return type as listed above.

```DXIL
declare float @dx.op.hitObject_StateVector.f32(
    i32,                      ; opcode
    %dx.types.HitObject,      ; hit object
    i32)                      ; index
    nounwind readnone
```
```DXIL
declare float @dx.op.hitObject_StateMatrix.f32(
    i32,                      ; opcode
    %dx.types.HitObject,      ; hit object
    i32,                      ; row
    i32)                      ; column
    nounwind readnone
```

Validation errors:
- Validate that `hit object` is not undef.
- Validate that `index`, `row`, and `col` are constant and in a valid range.

### Encoding of `reordercoherent`

[Memory Coherence And Visibility](#memory-coherence-and-visibility) introduces the `reordercoherent` HLSL attribute for UAVs.
This new resource attribute is encoded in DXIL in the following way:

A new tag is added to the resource extended property tags:
```cpp
   static const unsigned kDxilAtomic64UseTag = 3;
+  static const unsigned kDxilReorderCoherentTag = 4;
```
The tag carries an `i1` value that indicates whether the resource is reordercoherent. The resource is not reordercoherent when the tag is absent.

A flag is added to the Dxil Library Runtime Data (RDAT):
```cpp
   RDAT_ENUM_VALUE(Atomics64Use,             1 << 4)
+  RDAT_ENUM_VALUE(UAVReorderCoherent,       1 << 5)
```

A new field is added to `DxilResourceProperties`:
```cpp
   // BYTE 2
-  uint8_t Reserved2;
+  uint8_t ReorderCoherent : 1;
+  uint8_t Reserved2 : 7;
```

## Device Support

Devices that support Shader Model 6.9 and raytracing must support the 
Shader Execution Reordering HLSL methods in this spec. This doesn't mean 
all devices must support performing thread reordering - it is valid for 
an implementation to do nothing there.  Applications write one codebase 
using SER, and devices that can take advantage will, and other devices 
will just behave as if no reordering happened.

To help applications understand if the device actually does reordering,
D3D12 exposes a device capability indicating it that can be queried via
`CheckFeatureSupport()`:

```C++
// OPTIONSNN - NN TBD when this is added to D3D12
typedef struct D3D12_FEATURE_DATA_D3D12_OPTIONSNN
{
    ...
    _Out_ BOOL ShaderExecutionReorderingActuallyReorders;
    ...
} D3D12_FEATURE_DATA_D3D12_OPTIONSNN;
```

e.g.:

```C++
D3D12_FEATURE_DATA_D3D12_OPTIONSNN Options; // NN TBD when implemented
VERIFY_SUCCEEDED(pDevice->CheckFeatureSupport(
    D3D12_FEATURE_D3D12_OPTIONSNN, &Options, sizeof(Options)));
if (!Options.ShaderExecutionReorderingActuallyReorders) {
    // Maybe app wants to do it's own manuall sorting.
    // Or maybe a developer just wants to double check what's happening
    // on a given device during development.
}
```
 
Even on devices that don't do reordering, the `HitObject` portion 
of SER can be useful.

For instance, suppose an app wants to trace a ray, potentially including AnyHit 
shader invocations, and just wants the final T value without running
the ClosestHit shader (even if it happens to exist in the HitGroup).

The app can call `TraceRay()` returning a `HitObject`, call
`GetRayTCurrent()` on the `HitObject` to get the `T` value and be done.
Not calling `Invoke()`, skips `ClosestHit`/`Miss` invocation, and this 
works on any device with Shader Model 6.9 support.

The app might still want to call `ReorderThread()` after `TraceRay()` 
if the subsequent work could benefit, as illustrated in the Unified 
Shading example above.  And devices that can't reorder would just 
ignore the `ReorderThread()` call.
