
# Shader Execution Reordering (SER)

* Proposal: [NNNN](NNNN-shader-execution-reordering.md)
* Author(s): [Rasmus Barringer](https://github.com/rasmusnv), Robert Toth,
Michael Haidl, Simon Moll, Martin Stich
* Sponsor: [Tex Riddell](https://github.com/tex3d)
* Status: **Under Consideration**
* Impacted Projects: DXC

## Introduction

This proposal introduces `ReorderThread`, a built-in function for raygeneration shaders to
explicitly specify where and how shader execution coherence can be improved.
Additionally, `HitObject` is introduced to decouple traversal, intersection
testing and anyhit shading from closesthit and miss shading. Decoupling these
shader stages gives an increase in flexibility and enables `ReorderThread` to
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
`ReorderThread`,
that enables application-controlled reordering of work across the GPU for
improved execution and data coherence.
Additionally, the introduction of `HitObject` allows separation of traversal,
anyhit shading and intersection testing from closesthit and miss shading.

`HitObject` and `ReorderThread` can be combined to improve coherence for
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
`ReorderThread` and shader table-based closesthit and miss shading to be combined with
`RayQuery`.

The proposed extension to HLSL should be relatively straightforward to adopt by
current DXR implementations: `HitObject` merely decouples existing `TraceRay`
functionality into two distinct stages: the traversal stage and the shading
stage.
For SER's `ReorderThread`, the minimal allowed implementation is simply a
no-op, while implementations that already employ more sophisticated scheduling
strategies are likely able to reuse existing mechanisms to implement support
for SER. No DXR runtime changes are necessary, since the proposed extension to
the programming model is limited to HLSL and DXIL.

## Detailed Design

This section describes the HLSL additions for `HitObject` and `ReorderThread`
in detail.
The canonical use of these features involve changing a `TraceRay` call to the
following sequence:

```C++
HitObject Hit = HitObject::TraceRay( ..., Payload );
ReorderThread( Hit );
HitObject::Invoke( Hit, Payload );
```

This snippet traces a ray and stores the result of traversal, intersection
testing and anyhit shading in `Hit`. The call to `ReorderThread` improves
coherence based on the information inside the `Hit`. Closesthit or miss
shading is then invoked in a more coherent context.

Note that this is a very basic example. Among other things, it is possible to
query information about the hit to influence `ReorderThread` with additional
hints. See [Separation of ReorderThread and HitObject::Invoke](#separation-of-reorderthread-and-hitobjectinvoke)
for more elaborate examples.

### HitObject HLSL Additions

```C++
HitObject
```

The `HitObject` type encapsulates information about a hit or a miss. A
`HitObject` is constructed using `HitObject::TraceRay`,
`HitObject::FromRayQuery`, `HitObject::MakeMiss`, or `HitObject::MakeNop`. It
can be used to invoke closesthit or miss shading using `HitObject::Invoke`,
and to reorder threads for shading coherence with `ReorderThread`.

The `HitObject` has value semantics, so modifying one `HitObject` will not
impact any other `HitObject` in the shader. A shader can have any number of
active `HitObject`s at a time. Each `HitObject` will take up some hardware
resources to hold information related to the hit or miss, including ray,
intersection attributes and information about the shader to invoke. The size
of a `HitObject` is unspecified. As a consequence, `HitObject` cannot be
stored in structured buffers. Ray payload structs must not have members of
`HitObject` type. `HitObject` supports assignment (by-value copy) and can be
passed as arguments to and returned from local functions.

A `HitObject` is default-initialized to encode a NOP-HitObject (see `HitObject::MakeNop`).
A NOP-HitObject can be used with `HitObject::Invoke` and `ReorderThread` but
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
static HitObject HitObject::TraceRay(
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

An overload takes custom attributes associated with
COMMITTED_PROCEDURAL_PRIMITIVE_HIT. It is ok to always use the overload, even
for COMMITTED_TRIANGLE_HIT. For anything other than a procedural hit, the
specified attributes are ignored.

```C++
static HitObject HitObject::FromRayQuery(
    RayQuery Query);

template<attr_t>
static HitObject HitObject::FromRayQuery(
    RayQuery Query,
    attr_t CommittedCustomAttribs);
```

Parameter                           | Definition
---------                           | ----------
`Return: HitObject` | The `HitObject` that contains the result of the initialization operation.
`RayQuery Query` | RayQuery from which the hit is created.
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
static HitObject HitObject::MakeMiss(
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
certain scenarios when combined with `ReorderThread`, e.g., when a thread
wants to participate in reordering without executing a closesthit or miss
shader.

```C++
static HitObject HitObject::MakeNop();
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
static void HitObject::Invoke(
    HitObject Hit,
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
bool HitObject::IsMiss();
```

Returns `true` if the `HitObject` encodes a miss. If the `HitObject` encodes a
hit or is a NOP-HitObject, returns `false`.

---

#### HitObject::IsHit

```C++
bool HitObject::IsHit();
```

Returns `true` if the `HitObject` encodes a hit. If the `HitObject` encodes a
miss or is a NOP-HitObject, returns `false`.

---

#### HitObject::IsNop

```C++
bool HitObject::IsNop();
```

Returns `true` if the `HitObject` is a NOP-HitObject, otherwise returns
`false`.

---

#### HitObject::GetRayFlags

```C++
uint HitObject::GetRayFlags();
```

Returns the ray flags associated with the hit object.

Returns 0 if the `HitObject` is a NOP-HitObject.

---

#### HitObject::GetRayTMin

```C++
float HitObject::GetRayTMin();
```

Returns the parametric starting point for the ray associated with the hit
object.

Returns 0 if the `HitObject` is a NOP-HitObject.

---

#### HitObject::GetRayTCurrent

```C++
float HitObject::GetRayTCurrent();
```

Returns the parametric ending point for the ray associated with the hit
object. For a miss, the ending point indicates the maximum initially specified.

Returns 0 if the `HitObject` is a NOP-HitObject.

---

#### HitObject::GetWorldRayOrigin

```C++
float3 HitObject::GetWorldRayOrigin();
```

Returns the world-space origin for the ray associated with the hit object.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetWorldRayDirection

```C++
float3 HitObject::GetWorldRayDirection();
```

Returns the world-space direction for the ray associated with the hit object.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetObjectRayOrigin

```C++
float3 HitObject::GetObjectRayOrigin();
```

Returns the object-space origin for the ray associated with the hit object.

If the `HitObject` encodes a miss, returns the world ray origin.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetObjectRayDirection

```C++
float3 HitObject::GetObjectRayDirection();
```

Returns the object-space direction for the ray associated with the hit object.

If the `HitObject` encodes a miss, returns the world ray direction.

If the `HitObject` is a NOP-HitObject, all components of the returned `float3`
will be zero.

---

#### HitObject::GetObjectToWorld3x4

```C++
float3x4 HitObject::GetObjectToWorld3x4();
```

Returns a matrix for transforming from object-space to world-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetObjectToWorld4x3()` is the
matrix is transposed – use whichever is convenient.

---

#### HitObject::GetObjectToWorld4x3

```C++
float4x3 HitObject::GetObjectToWorld4x3();
```

Returns a matrix for transforming from object-space to world-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetObjectToWorld3x4()` is
the matrix is transposed – use whichever is convenient.

---

#### HitObject::GetWorldToObject3x4

```C++
float3x4 HitObject::GetWorldToObject3x4();
```

Returns a matrix for transforming from world-space to object-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetWorldToObject4x3()` is
the matrix is transposed – use whichever is convenient.

---

#### HitObject::GetWorldToObject4x3

```C++
float4x3 HitObject::GetWorldToObject4x3();
```

Returns a matrix for transforming from world-space to object-space.

Returns an identity matrix if the `HitObject` does not encode a hit.

The only difference between this and `HitObject::GetWorldToObject3x4()` is
the matrix is transposed – use whichever is convenient.

---

#### HitObject::GetInstanceIndex

```C++
uint HitObject::GetInstanceIndex();
```

Returns the instance index of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetInstanceID

```C++
uint HitObject::GetInstanceID();
```

Returns the instance ID of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetGeometryIndex

```C++
uint HitObject::GetGeometryIndex();
```

Returns the geometry index of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetPrimitiveIndex

```C++
uint HitObject::GetPrimitiveIndex();
```

Returns the primitive index of a hit.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetHitKind

```C++
uint HitObject::GetHitKind();
```

Returns the hit kind of a hit. See `HitKind` for definition of possible values.

Returns 0 if the `HitObject` does not encode a hit.

---

#### HitObject::GetAttributes

```C++
template<attr_t>
attr_t HitObject::GetAttributes();
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
uint HitObject::GetShaderTableIndex()
```

Returns the index used for shader table lookups. If the `HitObject` encodes a
hit, the index relates to the hit group table. If the `HitObject` encodes a
miss, the index relates to the miss table. If the `HitObject` is a
NOP-HitObject, or a `HitObject` constructed from a `RayQuery` without setting
a shader table index, the return value is zero.

---

#### HitObject::SetShaderTableIndex

```C++
void HitObject::SetShaderTableIndex(uint RecordIndex)
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
uint HitObject::LoadLocalRootTableConstant(uint RootConstantOffsetInBytes)
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

### ReorderThread HLSL Additions

`ReorderThread` provides an efficient way for the application to reorder work
across the physical threads running on the GPU in order to improve the
coherence and performance of subsequently executed code. The target ordering
is given by the arguments passed to `ReorderThread`. For example, the
application can pass a `HitObject`, indicating to the system that coherent
execution is desired with respect to a ray hit location in the scene.
Reordering based on a `HitObject` is particularly useful in situations with
highly incoherent hits, e.g., in path tracing applications.

`ReorderThread` is available only in shaders of type `raygeneration`.

This function introduces a [Reorder Point](#reorder-points).

#### Example 1

The following example shows a common pattern of combining `HitObject` and
`ReorderThread`:

```C++
// Trace a ray without invoking closesthit/miss shading.
HitObject hit = HitObject::TraceRay( ... );

// Reorder by hit point to increase coherence of subsequent shading.
ReorderThread( hit );

// Invoke shading.
HitObject::Invoke( hit, ... );
```

---

#### ReorderThread with HitObject

This variant of `ReorderThread` reorders calling threads based on the
information contained in a `HitObject`.

It is implementation defined which `HitObject` properties are taken into
account when defining the ordering. For example, an implementation may decide
to order threads with respect to their hit group index, hit locations in
3d-space, or other factors.

`ReorderThread` may access both information about the instance in the
acceleration structure as well as the shader record at the shader table
offset contained in the `HitObject`. The respective fields in the `HitObject`
must therefore represent valid instances and shader table offsets.
NOP-HitObjects is an exception, which do not contain information about a hit
or a miss, but are still legal inputs to `ReorderThread`. Similarly, a
`HitObject` constructed from a `RayQuery` but did not set a shader table
index is exempt from having a valid shader table record.

```C++
void ReorderThread( HitObject Hit );
```

Parameter                           | Definition
---------                           | ----------
`HitObject Hit` | `HitObject` that encapsulates the hit or miss according to which reordering should be performed.

---

#### ReorderThread with coherence hint

This variant of `ReorderThread` reorders threads based on a generic
user-provided hint. Similarity of hint values should indicate expected
similarity of subsequent work being performed by threads. The resolution of
the hint is implementation-specific. If an implementation cannot resolve all
values of `CoherenceHint`, it is free to ignore an arbitrary number of least
significant bits. The thread ordering resulting from this call may be
approximate.

```C++
void ReorderThread( uint CoherenceHint, uint NumCoherenceHintBitsFromLSB );
```

Parameter                           | Definition
---------                           | ----------
`uint CoherenceHint` | User-defined value that determines the desired ordering of a thread relative to others.
`uint NumCoherenceHintBitsFromLSB` | Indicates how many of the least significant bits in `CoherenceHint` the implementation should try to take into account. Applications should set this to the lowest value required to represent all possible values of `CoherenceHint` (at the given `ReorderThread` call site). All threads should provide the same value at a given call site to achieve best performance.

---

#### ReorderThread with HitObject and coherence hint

This variant of `ReorderThread` reorders threads based on the information
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
honors can be smaller in this overload of `ReorderThread` compared to the one
described in
[ReorderThread with coherence hint](#reorderthread-with-coherence-hint).

```C++
void ReorderThread( HitObject Hit,
                    uint CoherenceHint,
                    uint NumCoherenceHintBitsFromLSB );
```

Parameter                           | Definition
---------                           | ----------
`HitObject Hit` | `HitObject` that encapsulates the hit or miss according to which reordering should be performed.
`uint CoherenceHint` | User-defined value that determines the desired ordering of a thread relative to others.
`uint NumCoherenceHintBitsFromLSB` | Indicates how many of the least significant bits in `CoherenceHint` the implementation should try to take into account. Applications should set this to the lowest value required to represent all possible values of `CoherenceHint` (at the given `ReorderThread` call site). All threads should provide the same value at a given call site to achieve best performance.

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
    ReorderThread( hit, coherenceHints, 1 );

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
    HitObject hit;    // initialize to NOP-hitobject

    // Have threads conditionally participate in the next bounce depending on
    // loop iteration count and path throughput. Instead of having
    // non-participating threads break out of the loop here, we let them
    // participate in the reordering with a NOP-hitobject first.
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
    ReorderThread( hit );

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

A _reorder point_ is a point in the control flow of a shader or sequence of
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
- `ReorderThread`: the `ReorderThread` call site.

`ReorderThread` stands out as it explicitly separates reordering from a
transition between shader stages, thus, it allows applications to (carefully)
choose the most effective reorder locations given a specific workload. The
combination of `HitObject` and coherence hints provides additional control
over the reordering itself. These characteristics make `ReorderThread` a
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
are intended to be used in combination with `ReorderThread`.
The desired behavior, as communicated from a shader to the driver, is inferred
from the presence of `ReorderThread`.
If no `ReorderThread` call is made, it implies that the driver should minimize
its efforts to reorder for hit coherence.
Conversely, the existence of a `ReorderThread` call implies that more sophisticated
reordering will be beneficial, and that reordering conceptually occurs at the
`ReorderThread` call.
This describes the intended behavior communicated from an application, though
the actual behavior remains at the driver's discretion.
For example, an implementation may choose to defer the reordering operation
implied by `ReorderThread` to the next reorder point.

For performance reasons, it is crucial that the DXIL-generating compiler does
not move non-uniform resource access across reorder points in general, and across
`ReorderThread` in particular. It should be assumed that the shader will perform
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
        ReorderThread(coherenceCoord, 32);
    int B = WaveActiveBallot(true);
    return A - B;
}
```

In this example, a number of different things could happen:
- If the implementation does not honor `ReorderThread` at all, the function
will most likely return zero, as the set of threads before and after the
conditional reorder would be the same.
- If the implementation reorders threads invoking `ReorderThread` but does not
replace them, B will likely be less than A for threads not invoking
`ReorderThread`, while the reordered threads will likely resume execution with
a newly formed full wave, thereby obtaining `A <= B`.
- If the implementation replaces threads in a wave, the threads not
participating in the reorder may possibly be joined by more threads than were
removed from the wave, again observing `A <= B`.

---

### Memory coherence and visibility

Due to the existence of non-coherent caches on most modern GPUs, an
application must take special care when communicating information across
reorder points through memory (UAVs).

Specifically, if UAV stores or atomics are performed on one side of a reorder
point, and on the other side the data is read via non-atomic UAV reads, the
following is required:
- The UAV must be declared `[globallycoherent]`.
- The UAV writer must issue a `DeviceMemoryBarrier` between the write and the
reorder point.

## Separation of ReorderThread and HitObject::Invoke

`ReorderThread` and `HitObject::Invoke` are kept separate. It enables calling
`ReorderThread` without `HitObject::Invoke`, and `HitObject::Invoke` without
calling `ReorderThread`. These are valid use cases as reordering can be
beneficial even when shading happens inline in the raygeneration shader, and
reordering before a known to be coherent or cheap shader can be
counterproductive. For cases in which both is desired, keeping `ReorderThread`
and `HitObject::Invoke` separated is still beneficial as detailed below.

Common hit processing can happen in the raygeneration shader with the
additional efficiency gains of hit coherence. Benefits include:
- Logic otherwise duplicated can be hoisted into the raygeneration shader
without a loss of hit coherence. This can reduce instruction cache pressure
and reduce compile times.
- Logic between `ReorderThread` and `HitObject::Invoke` have access to the
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
`ReorderThread` naturally communicates a reorder point, when hit-coherent
execution starts and that it will persist after the call (until the next
reorder point). Reasoning about the execution and that it is hit-coherent is
not as obvious after a call to a hypothetical (fused)
`HitObject::ReorderAndInvoke`. Finally, tools can report live state across
`ReorderThread` and users can optimize live state across it. This is important
as live state across `ReorderThread` may be more expensive on some
architectures.

Some examples follow.

### Example: Common computations that rely on large raygeneration state

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
    ReorderThread( hit );

    IorData newEntry = LoadIorDataFromHit( hit );
    bool enter = hit.GetHitKind() == HIT_KIND_TRIANGLE_FRONT_FACE;

    payload.ior = UpdateIorList( newEntry, enter, iorList, iorListSize );

    HitObject::Invoke( hit, payload );
}
```

### Example: Do common computations with hit-coherence

```C++
hit = HitObject::TraceRay( ... );
ReorderThread( hit );

payload.giData = GlobalIlluminationCacheLookup( hit );

HitObject::Invoke( hit, payload );
```

### Example: Same surface shader but different behavior in the raygeneration shader

```C++
// Primary ray wants perfect shadows and does not need to reorder as it is
// coherent enough.
ray = GeneratePrimaryRay();
hit = HitObject::TraceRay( ... );
RayDesc shadowRay = SampleShadow( hit );
payload.shadowTerm = HitObject::TraceRay( shadowRay ).IsHit() ? 0.0f : 1.0f;
HitObject::Invoke( hit, payload );

// Secondary ray is incoherent but does not need perfect shadows.
ray = ContinuePath( payload );
hit = HitObject::TraceRay( ... );
ReorderThread( hit );
payload.shadowTerm = SampleShadowMap( hit );
HitObject::Invoke( hit, payload );
```

### Example: Unified shading

```C++
hit = HitObject::TraceRay( ... );

ReorderThread( hit );

// Do not call HitObject::Invoke. Shade in raygeneration.
```

### Example: Coherently break render loop on miss

Rationale: Executing the miss shader when not needed is unnecessarily
inefficient on some architectures.

```C++
for( ;; )
{
    hit = HitObject::TraceRay( ... );
    ReorderThread( hit );

    if( hit.IsMiss() )
        break;

    HitObject::Invoke( hit, payload );
}
```

### Example: Two-step shading, single reorder

```C++
hit = HitObject::TraceRay( ... );
ReorderThread( hit );

// Gather surface parameters into payload, e.g., compute normal and albedo
// based on surface-specific functions and/or textures.
HitObject::Invoke( hit, payload );

// Alter the hit object to point to a unified surface shader.
hit.SetShaderTableIndex( payload.surfaceShaderIdx );

// Invoke unified surface shading. We are already hit-coherent so not worth
// reordering again.
HitObject::Invoke( hit, payload );
```

### Example: Live state optimization

```C++
hit = HitObject::TraceRay( ... );

uint compressedNormal = CompressNormal( payload.normal );
ReorderThread( hit );
payload.normal = UncompressNormal( compressedNormal );

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
XXX + 6  | ReorderThread | Reorders the current thread. Optionally accepts a `HitObject` arg, or `undef`.
XXX + 7  | HitObject_IsMiss | Returns `true` if the `HitObject` represents a miss.
XXX + 8  | HitObject_IsHit | Returns `true` if the `HitObject` represents a hit.
XXX + 9  | HitObject_IsNop | Returns `true` if the `HitObject` is a Nop-HitObject.
XXX + 10 | HitObject_RayFlags | Returns the ray flags set in the HitObject.
XXX + 11 | HitObject_RayTMin | Returns the TMin value set in the HitObject.
XXX + 12 | HitObject_RayTCurrent | Returns the current T value set in the HitObject.
XXX + 13 | HitObject_WorldRayOrigin | Returns the ray origin in world space.
XXX + 14 | HitObject_WorldRayDirection | Returns the ray direction in world space.
XXX + 15 | HitObject_ObjectRayOrigin | Returns the ray origin in object space.
XXX + 16 | HitObject_ObjectRayDirection | Returns the ray direction in object space.
XXX + 17 | HitObject_ObjectToWorld3x4 | Returns the object to world space transformation matrix in 3x4 form.
XXX + 18 | HitObject_ObjectToWorld4x3 | Returns the object to world space transformation matrix in 4x3 form.
XXX + 19 | HitObject_WorldToObject3x4 | Returns the world to object space transformation matrix in 3x4 form.
XXX + 20 | HitObject_WorldToObject4x3 | Returns the world to object space transformation matrix in 4x3 form.
XXX + 21 | HitObject_GeometryIndex | Returns the geometry index committed on hit.
XXX + 22 | HitObject_InstanceIndex | Returns the instance index committed on hit.
XXX + 23 | HitObject_InstanceID | Returns the instance id committed on hit.
XXX + 24 | HitObject_PrimitiveIndex | Returns the primitive index committed on hit.
XXX + 25 | HitObject_HitKind | Returns the HitKind of the hit.
XXX + 26 | HitObject_ShaderTableIndex | Returns the shader table index set for this HitObject.
XXX + 27 | HitObject_SetShaderTableIndex | Returns a HitObject with updated shader table index.
XXX + 28 | HitObject_LoadLocalRootTableConstant | Returns the root table constant for this HitObject and offset.
XXX + 29 | HitObject_Attributes | Returns the attributes set for this HitObject.

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
- Validate that `opcode` equals `HitObject_TraceRay`.
- Validate the resource for `acceleration structure handle`.
- Validate the compatibility of type `PayloadT`.
- Validate that `payload` is a valid pointer.

Validation warnings:
- If `ray flags` is constant, validate the combination.
- If `instance inclusion mask` is constant, validate that no more than the 8 least significant bits are set.
- If `ray contribution to hit group index` is constant, validate that no more than the 4 least significant bits are set.
- If `multiplier for geometry contribution to hit group index` is constant, validate that no more than the 4 least significant bits are set.
- If `miss shader index` is constant, validate that no more than the 16 least significant bits are set.

#### HitObject_FromRayQuery

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_FromRayQuery(
    i32,                           ; opcode
    i32)                           ; ray query
    nounwind argmemonly

```
This is used for the HLSL overload of `HitObject::FromRayQuery` that only takes `RayQuery`.

Validation errors:
- Validate that `opcode` equals `HitObject_FromRayQuery`.
- Validate that `ray query` is a valid ray query handle.

#### HitObject_FromRayQueryWithAttrs

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_FromRayQuery.AttrT(
    i32,                           ; opcode
    i32,                           ; ray query
    AttrT*)                        ; attributes
    nounwind argmemonly
```
This is used for the HLSL overload of `HitObject::FromRayQuery` that takes `RayQuery` and the user-defined `Attribute` struct.
`AttrT` is the user-defined intersection attribute struct type. See `ReportHit` for definition.

Validation errors:
- Validate that `opcode` equals `HitObject_FromRayQueryWithAttrs`.
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

Validation errors:
- Validate that `opcode` equals `HitObject_MakeMiss`.

Validation warnings:
- If `ray flags` is constant, validate the combination.
- If `miss shader index` is constant, validate that no more than the 16 least significant bits are set.

#### HitObject_MakeNop

```DXIL
declare %dx.types.HitObject @dx.op.hitObject_MakeNop(
    i32)                           ; opcode
    nounwind readnone
```

Validation errors:
- Validate that `opcode` equals `HitObject_MakeNop`.

#### HitObject_Invoke

```DXIL
declare void @dx.op.hitObject_Invoke.PayloadT(
    i32,                           ; opcode
    %dx.types.HitObject,           ; hit object
    PayloadT*)                     ; payload
    nounwind
```

Validation errors:
- Validate that `opcode` equals `HitObject_Invoke`.
- Validate that `hit object` is not undef.
- Validate the compatibility of type `PayloadT`.
- Validate that `payload` is a valid pointer.

#### ReorderThread

Operation that reorders the current thread based on the supplied hints and
`HitObject`. The canonical lowering of the
HLSL intrinsic `ReorderThread( uint CoherenceHint, uint NumCoherenceHintBitsFromLSB )`
uses `undef` for the `HitObject` parameter.

```DXIL
declare void @dx.op.reorderThread(
    i32,                      ; opcode
    %dx.types.HitObject,      ; hit object
    i32,                      ; coherence hint
    i32)                      ; num coherence hint bits from LSB
    nounwind
```

Validation errors:
- Validate that `opcode` equals `ReorderThread`.
- Validate that `coherence hint` is not undef.
- Validate that `num coherence hint bits from LSB` is not undef.

Validation warnings:
- If `num coherence hint bits from LSB` is constant, validate that it is less than or equal to 32.

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
- Validate that `opcode` equals `HitObject_SetShaderTableIndex`.
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
- Validate that `opcode` equals `HitObject_LoadLocalRootTableConstant`.
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
- Validate that `opcode` equals `HitObject_Attributes`.
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
 HitObject_IsNop             | `i1`    | scalar | Returns `true` if the `HitObject` is a Nop-HitObject.
 HitObject_RayFlags          | `i32`   | scalar | Returns the ray flags set in the HitObject.
 HitObject_RayTMin           | `float` | scalar | Returns the TMin value set in the HitObject.
 HitObject_RayTCurrent       | `float` | scalar | Returns the current T value set in the HitObject.
 HitObject_WorldRayOrigin    | `float` | vector | Returns the ray origin in world space.
 HitObject_WorldRayDirection | `float` | vector | Returns the ray direction in world space.
 HitObject_ObjectRayOrigin   | `float` | vector | Returns the ray origin in object space.
 HitObject_ObjectRayDirection| `float` | vector | Returns the ray direction in object space.
 HitObject_ObjectToWorld3x4  | `float` | matrix | Returns the object to world space transformation matrix in 3x4 form.
 HitObject_ObjectToWorld4x3  | `float` | matrix | Returns the object to world space transformation matrix in 4x3 form.
 HitObject_WorldToObject3x4  | `float` | matrix | Returns the world to object space transformation matrix in 3x4 form.
 HitObject_WorldToObject4x3  | `float` | matrix | Returns the world to object space transformation matrix in 4x3 form.
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
- Validate that `opcode` is one of the supported opcodes in the table above.
- Validate that `hit object` is not undef.
- Validate that `index`, `row`, and `col` are constant and in a valid range.
