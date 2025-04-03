<!-- {% raw %} -->

# Typed resource heaps

* Proposal: [0TBD](0TBD-improved-resource-typing.md)
* Author(s): [Tobias Hector](https://github.com/tobski)
* Sponsor: Chris Bieneman
* Status: **Under Consideration**


## Introduction

This proposal adds a method to access the resource heap in HLSL with stronger
typing, and adds "bindless" methods of accessing root constants and shader
record data, fully removing the need to use descriptor tables.


## Motivation

The `ResourceDescriptorHeap` added in Shader Model 6.6 exposed a typeless,
unsized heap to shader authors which could be used to access any descriptor
placed in the heap through the client API.

While useful, without type information, it is incredibly difficult to
validate whether an application is doing what it's supposed to be doing, both
for debugging tools and for a shader author to reason about it in the first
place.

In addition to this, some APIs now provide methods to treat descriptors as
plain old data (POD), even interleaving descriptors and other POD types in
the heap. (E.g.
[PSSL](https://gdcvault.com/play/1024241/Higher-Res-Without-Sacrificing-Quality)
[see 11 minutes in].)

While regular POD types are currently off the table for DirectX 12 in its
current iteration of resource heaps, enabling stronger typing on the heap
would lay groundwork for exposing interleaved POD in future.

Notably, PSSL as linked above also enables resources to be accessed freely
from any source; allowing nested structures and arbitrary handling of data.
Until or unless hardware is modified to allow descriptors in arbitrary
memory, handling actual descriptors in this way is not possible portably.
However, it should be possible to better enable passing handles to the heap
around by modifying the type system to handle resources more consistently.


## Proposed solution

### Consistent Resource Type Handling

This change proposes that resource type declarations are _always_ considered
as 32-bit offsets into the heap, allowing them to be declared in arbitrary
external memory.
This includes storing them in buffers of indeterminate size, allowing fairly
arbitrary nesting of resource declarations.

Example declarations:

```hlsl
// A constant buffer containing other resource indices
// including a buffer that points to further resources.
struct SomeResources {
	Texture2D                       texture;
	RWStructuredBuffer<Texture2D>   bufferOfTextures;   // Can be written!
};

ConstantBuffer<SomeResources> someResources;
```

Declaring these is equivalent to declaring integer values and passing those
values to `ResourceDescriptorHeap` with the same resource type.
This serves primarily to make accessing the heap and reasoning about
descriptors in the heap easier, rather than passing loose integers around.

Samplers declarations work in the same way, but are offsets into the
`SamplerDescriptorHeap` instead.

The offset is the index that would be provided to `ResourceDescriptorHeap`.
If non-homogenous descriptors are advertised in future, the offset can
instead be treated as a byte offset.


#### Open Issue: Does this cause any incompatibility issues?

Switching out the type system like this will inevitably mean a lot of
codebase changes for the compiler.
It's entirely possible this means some existing behavior stops working which
some developer is relying on somewhere.
There needs to be at least some sort of large hammer switch for this behavior
change, as it's unlikely that any corner case behavior in the existing model
can be usefully ported over.


#### Open Issue: Recursive Nesting

The spec above allows nesting of buffer references within each other,
enabling some fairly powerful data structures to be constructed.
However, HLSL does not have the capability currently to express recursive
structures in the same way that you could do in most languages.

The cleanest fix from the user side would be to allow buffer typing to work
with forward declarations, similarly to pointer declarations.
E.g.:

```hlsl
struct RecursiveType;

typedef LinkedList ConstantBuffer<RecursiveType>;

struct RecursiveType {
    uint Data;
    LinkedList next;
};
```

However, the practicality of implementing this is unknown at the moment.
This could be made to work with the rest of this proposal as-is, but it
requires manually loading index values via `ResourceEntry`, which is
syntactically awkward.


#### Open Issue: Resource Registers

There's no real reason why a user couldn't continue to use resources declared
with register mappings alongside this proposal; and allowing this will enable
shaders to be more gradually transitioned to this new way of accessing
descriptors.
The only thing that may need to be restricted is mapping root data to
resources in the table, both to prevent aliasing with the new built-ins, and
because the mapped resources would not map to heap indices.


### Resource Entries

A new object is provided to quickly access multiple _consecutive_ resources
in the resource heap by using composite types:

```hlsl
template <typename T>
class ResourceEntry<T>;
```

This is treated in the same manner as resource types are in the prior
section, in that they are handled as a single underlying 32-bit offset into
the heap, and can be read and written as such.

However, unlike single resource types, `T` may be a composite object of
_multiple_ resource types, with the first struct member or array element
read from the underlying offset, and and each subsequent element or member
will be accessed at an offset equal to the sum of the base offset and the
relative offset of all elements/members defined before it.
This works with nested types just as well, in the case of a struct being
nested inside another struct or array, for example.

The `ResourceEntry` itself can be read and written, though its contents are
read-only, as the offsets are fixed from the base.
The contents may be written freely to other locations however.

For example:

```hlsl
struct Resources {
    Texture2D texture;
    Texture2D anotherTexture;
};

RWStructuredBuffer<ResourceEntry<Resources> >   resourceBuffer;

void main(...) {
    // Read a single index from the resource buffer;
    ResourceEntry<Resources> resources0 = resourceBuffer[0];
    
    // Can be accessed as a const version of its target type
    Resources someResources = resources0;
    
    // Can be stored as its own type
    resourceBuffer[1] = resources0;
        
    // Can access sub-parts of the ResourceEntry's structs as independent resources
    someResources.texture = resourceBuffer[1].anotherTexture;
    
    // **Cannot** store a variable of type T into a ResourceEntry with type T
    /* resourceBuffer[2] = someResources; */
    
    // **Cannot** write members/elements of a ResourceEntry; contents are read-only as offsets are fixed
    /* resourceBuffer[1].texture = resourceBuffer[1].anotherTexture; */
}
```

For the current DirectX12 interface where `ResourceDescriptorHeap` is a
homogenous array, the offset of every element/member of a ResourceEntry's
type can be treated as 1.

In future, if non-homogenous descriptor sizes are advertised, as with
[VK_EXT_descriptor_buffer](https://docs.vulkan.org/features/latest/features/proposals/VK_EXT_descriptor_buffer.html),
`offset` could instead become a byte offset, enabling resources to be packed
much more tightly.

When passing in a resource index from outside the shader, then that should
generally be declared as such in the shader; dynamic indices generated inside
the shader can be handled by specifying the base index as having an array
type.
For example:

```hlsl
ConstantBuffer<ResourceEntry<Texture2D[] > > textures;

void main(...)
{
    ...
    uint dynamicIndex = ...;
    Texture2D myDynamicTexture = textures[dynamicIndex];
}
```

However, there are cases where a developer may wish to pack the resource
index into other data, rather than consuming a full 32-bits for it.
Rather than having to fabricate an empty type and index into it in this case,
a constructor function is included:

```hlsl
ResourceEntry<T>(uint offset);
```

This allows the construction of `ResourceEntry` object from any arbitrary
integer the shader generates.

This would not drastically change the implementation complexity or expected
usage patterns; however shader authors are advised to avoid using this unless
they have a clear need to, as the added context of a resource handle is
useful for debugging and validation.



#### Open Issue: Could we avoid retyping all the resource handles by making use of ResourceEntry<T> instead?

The first part of this proposal suggested throwing away the existing (very
confusing) type handling of resource objects, and replacing it with
consistent handling of these types as 32-bit heap offsets.

This proposal still could work even if that overhaul does not occur, if
`ResourceEntry<T>`, where `T` is a single resource type, still works as
specified above.

The disadvantage of this is primarily semantic overhead, as nested resource
types would now need to be declared differently, with the extra
`ResourceEntry<T>` annotation between each nesting level. For example:

```hlsl
struct Resources {
    ResourceEntry<Texture2D> texture;
    ResourceEntry<Texture2D> anotherTexture;
};

RWStructuredBuffer<ResourceEntry<Resources> >   resourceBuffer;
```

There may also be a cognitive burden with developers expected to understand
two independent type systems, which will almost inevitably lead to errors.


#### Open Issue: Should this deprecate the ResourceDescriptorHeap built-in?

If non-homogenous resource sizes are exposed to shaders,
`ResourceDescriptorHeap` poses a problem as it assumes uniform resource
sizes.
`ResourceEntry<T>` uses strong typing, so could seamlessly switch to byte
offsets on the user's behalf.
Supporting both models in the same shader is likely to be very messy.

This also has similar problems with exposing a constructor for
ResourceEntry<T> types from an integer, in that there is no indication
of the meaning of the type until it is used.

For these reasons, the use of `ResourceDescriptorHeap` should be deprecated
as part of this proposal.


### Bindless Constants

Currently, accessing root constants or shader table entries must be done via
root signature mappings.
Two new System Value semantics are added that can be declared with inputs
to an entry point, avoiding root signature mappings:

* `SV_Constants`
* `SV_LocalConstants`

Both of these can be declared as composite types, and refer to either the
global root or local root data provided in the client API.

DirectX 12 does not distinguish root data as a homogenous array, instead
separating it into "root parameter indices" that define a set of up to 4
32-bit root constants, a 64-bit root descriptor, or a 32-bit descriptor
table, with a total maximum size of 256 bytes across all indices.
See https://learn.microsoft.com/en-us/windows/win32/direct3d12/root-signatures-overview#root-constants-descriptors-and-tables
for information on how this API works.
When consumed via `SV_Constants` in the shader, these are packed tightly, in
root parameter index order.
Root constants appear exactly as the data set by the application, descriptor
table entries become a 32-bit integer index into the resource heap, and
root descriptors are the 64-bit data passed in by the application, which can
be interpreted as a VA Buffer to be used in the shader.

For Vulkan `SV_Constants` maps directly to push constants.

As each shader table entry is simply a block of memory in both Vulkan and
DirectX, `SV_LocalConstants` is read as-is.
`SV_LocalConstants` is only available in shaders that can use local root data
(i.e. ray tracing and workgraphs).

Example usage of SV_Constants with resources:

```hlsl
struct DescriptorTableData {
    Texture2D<float4> a;
    Texture2D<float4> b;
    ConstantBuffer<Something> c;
    RWBuffer<float4> d;
    ...
};

struct RootData {
	ResourceEntry<DescriptorTableData> descriptorTable;
    uint4 constants;
    VAConstantBuffer<...> buffer;
};
```

In DirectX, this could be specified in the root signature as:

 * Binding 0 is a descriptor table
 * Binding 1 is 4 root constants
 * Binding 2 is a root descriptor CBV

In Vulkan this would map to push constants, where `buffer` maps to a
`VkDeviceAddress` value from a buffer.


#### Open Issue: Allow explicit offsets?

When defining a descriptor table, the offsets can be manually specified for
a subset of the entries, with other entries calculated manually, taking into
account any manually specified offsets as relevant.
It might be useful to have an attribute in resource entry structures
indicating this same functionality for compatibility reasons if nothing else.

For example:

```hlsl
struct DescriptorTableData {
    Texture2D<float4> a;
    Texture2D<float4> b;
    [[resourceoffset(16)]]
    ConstantBuffer<Something> c;
    RWBuffer<float4> d;
    ...
};
```

In this example the offset for `c` would be equal to 16, and `d` would take
an offset as the sum of 16 and the size of `c`.
It may also be beneficial to have a rolling offset variant, where the value
is added to the otherwise calculated offset.

Potentially this could be applicable to POD in regular structs as well, to
enable more control over struct padding.


### VA Buffer types

In the above example, a root descriptor (in that case a CBV) is passed in.
When using a root descriptor in DirectX, these are mapped to buffers when
using registers.
However, declaring a standard buffer type directly here would result in the
assumption of a 32-bit index into the heap, not a 64-bit root descriptor VA.

New resource types are provided that can be declared to access a root
descriptor VA:

 * `VAConstantBuffer<typename T>`
 * `VAStructuredBuffer<typename T = float4, uint64_t Size = UINT64_MAX>`
 * `VARWStructuredBuffer<typename T = float4, uint64_t Size = UINT64_MAX>`
 * `VAByteAddressBuffer<uint64_t Size = UINT64_MAX>`
 * `VARWByteAddressBuffer<uint64_t Size = UINT64_MAX>`
 * `VARasterizerOrderedBuffer<typename T = float4, uint64_t Size = UINT64_MAX>`
 * `VARasterizerOrderedByteAddressBuffer<uint64_t Size = UINT64_MAX>`
 * `VARaytracingAccelerationStructure`

These can be used in exactly the same way as their non-VA counterparts,
except that when declared in memory they correspond to a 64-bit GPU VA,
rather than a 32-bit heap index.

VA structured and byte address buffers have an extra optional `Size`
parameter to indicate the size of the buffer.
If this value is provided, accesses will be bounds checked against it,
providing zero values if the index is exceeded, and discarding writes.
Partial out of bounds conditions are treated as fully out of bounds.
The size of a constant buffer is implied from `T`, and acceleration
structures have no useful OOB behavior currently.

These can thus be declared in _any_ external memory, and used freely in the
same way as other resource types.
For example:

```hlsl
struct Data {
    uint value;
    float value2;
};

struct MoreBuffers {
    VAConstantBuffer<...> a;
    VAConstantBuffer<...> b;
    VAConstantBuffer<...> c;
};

struct RootData {
    VAConstantBuffer<MoreBuffers> buffer;
};

void main(RootData root : SV_Constants)
{
    uint value = root.buffer.a.value;
}
```

NOTE: This usage outside of root constants may require driver changes in
DirectX. Vulkan works out of the box with device addresses.


#### Open Issue: Should VA types with indeterminate size have a user-defined size?

Yes, no, and also maybe.

For code that has to go fast (which is usually every part of a shader), not
having bounds checks can be a performance win, so it's plausible that it
should be disabled for actual deployment.

For debugging, having a size is actually quite useful - because it lets the
debugger alert users to any OOB conditions that arise, which may cause errors
in the applications.

Having a size defined seems useful, but it might be beneficial to be able to
switch actual bounds checking on or off based on a build switch.
This shouldn't be something that necessarily has to be done when compiling
from HLSL, so needs some thought.
Having it fully dynamic likely wouldn't save much however, so it may be
desirable to ultimately have it under API control.


#### Open Issue: Should VA sizes be specified statically?

It's likely that at least some applications would want to provide the size
dynamically as an argument to the shader, so supplying this should absolutely
be possible.
However, this doesn't lend itself to being part of a static declaration in
constants or other memory.
The proposed slice API below would be one way to solve this, but if there's a
more reasonable way to set the initial size that would be useful.


#### Open Issue: Why are VA buffer types separate from their counterparts?

Standard buffer types by this proposal are resources which live in the heap,
and are thus represented as a 32-bit index when read or written to memory.
VA buffer types however, do not need to live in the heap, and are
represented as 64-bit pointers when accessed in external memory.
The only way to enable them to be the same type would impose heavy and
awkward restrictions on when and how they could be accessed in external
memory.
Having separate types feels like a cleaner compromise.

A future direction might be to deprecate non-VA buffers, but this proposal
aims to remain compatible with the existing DirectX API and, to a degree,
with existing shaders.


#### Open Issue: Slices

It would be useful to enable developers to get slices of an existing VA
resource for at least arrayed resources, such that subsets of the original
resource can be more tightly bounds checked at least during debugging.

That could look like the following additional members for arrayed resource
types:

```hlsl
T GetSlice(uint offset);
T GetSlice(uint offset, uint size);
```

The sum of `offset` and `size` must be less than or equal to the original
buffer's size.
The returned VA buffer would be identical to the original VA buffer resource,
except that it would be a smaller range of data.


#### Open Issue: VA resource construction

It would be useful to enable VA resources to be constructed from existing
heap resources of a matching type, possibly with an offset and reduced size
for non-constant buffer types.
This is not currently possible in any API, but if we could make it work it
would be one way to solve the "slice" problem, particularly if we enforce
that slices must be subsets of the original buffer.

That might look, for example, something like a new member functions for
non-VA buffer types:

```hlsl
T GetVAResource();
```

The returned VA buffer would be identical to the original buffer resource,
except that it would now behave as a 64-bit pointer when accessed (including
OOB semantics), and would no longer be associated with the heap.


#### Open Issue: Pointer math

Currently there's no way to directly adjust the value of a pointer in a
shader legally, as aliasing is disallowed, and casting/construction of VA
resources is not supported.

It's unlikely we want this to change, but it might be useful considering that
an API to get subsets of VA buffers would solve this "safely".
The previous issue suggests one such option.



## Detailed design

*The detailed design is not required until the feature is under review.*

This section should grow into a feature specification that will live in the
specifications directory once complete. Each feature will need different levels
of detail here, but some common things to think through are:

### HLSL Additions

* How is this feature represented in the grammar?
* How does it interact with different shader stages?
* How does it work interact other HLSL features (semantics, buffers, etc)?
* How does this interact with C++ features that aren't already in HLSL?
* Does this have implications for existing HLSL source code compatibility?

### Interchange Format Additions

* What DXIL changes does this change require?
* What Metadata changes does this require?
* How will SPIRV be supported?

### Diagnostic Changes

* What additional errors or warnings does this introduce?
* What existing errors or warnings does this remove?

#### Validation Changes

* What additional validation failures does this introduce?
* What existing validation failures does this remove?

### Runtime Additions

#### Runtime information

* What information does the compiler need to provide for the runtime and how?

#### Device Capability

* How does it interact with other Shader Model options?
* What shader model and/or optional feature is prerequisite for the bulk of
  this feature?
* What portions are only available if an existing or new optional feature
  is present?
* Can this feature be supported through emulation or some other means
  in older shader models?

## Testing

* How will correct codegen for DXIL/SPIRV be tested?
* How will the diagnostics be tested?
* How will validation errors be tested?
* How will validation of new DXIL elements be tested?
* How will the execution results be tested?


## Transition Strategy for Breaking Changes (Optional)

* Newly-introduced errors that cause existing shaders to newly produce errors
  fall into two categories:
  * Changes that produce errors from already broken shaders that previously
    worked due to a flaw in the compiler.
  * Changes that break previously valid shaders due to changes in what the compiler
    accepts related to this feature.
* It's not always obvious which category a new error falls into
* Trickier still are changes that alter codegen of existing shader code.

* If there are changes that will change how existing shaders compile,
  what transition support will we provide?
  * New compilation failures should have a clear error message and ideally a FIXIT
  * Changes in codegen should include a warning and possibly a rewriter
  * Errors that are produced for previously valid shader code would give ample
    notice to developers that the change is coming and might involve rollout stages

* Note that changes that allow shaders that failed to compile before to compile
  require testing that the code produced is appropriate, but they do not require
  any special transition support. In these cases, this section might be skipped.


## Alternatives considered (Optional)

If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing. Having these solutions and why they were rejected documented may save
trouble from those who might want to suggest feedback or additional features that
might build on this on. Even variations on the chosen solution can be interesting.


## Acknowledgments (Optional)

 - Chris Bieneman
 - Nicolai Haehnle
 - Alexander Johnston

<!-- {% endraw %} -->
