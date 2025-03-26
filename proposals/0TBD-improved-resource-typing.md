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

The `ResourceHeap` added in Shader Model 6.6 exposed a typeless, unsized heap
to shader authors which could be used to access any descriptor placed in the
heap through the client API.

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

typedef LinkedList RawConstantBuffer<RecursiveType>;

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

A new function is provided to quickly access multiple consecutive resources
in the resource heap by using composite types:

```hlsl
template <typename T>
T ResourceEntry(uint offset);
```

* `T` must be or only include resource types.
* `offset` is the base offset into the resource heap that resources should
  be read from.

If `T` is a single resource type, it is retrieved from the resource heap at
`offset`.
If `T` is an array or struct, the first element or member will be retrieved
from the resource heap at `offset`, and each subsequent element or member
will be accessed at an offset equal to the sum of `offset` and the offset of
all elements/members defined before it.

For example:

```hlsl
struct SomeResources {
	Texture2D	                    texture;
	RWStructuredBuffer<Texture2D>   bufferOfTextures;
};

SomeResources someResources = ResourceEntry(16);
```

This would be equivalent to:

```hlsl
SomeResources someResources;
someResources.texture = ResourceDescriptorHeap[16];
someResources.buffer = ResourceDescriptorHeap[17];
```

`offset` is the same index that would be provided to
`ResourceDescriptorHeap`, and each subsequent resource in `T` simply
increments the offset by 1.

In future, if non-homogenous descriptor sizes are advertised, as with
[VK_EXT_descriptor_buffer](https://docs.vulkan.org/features/latest/features/proposals/VK_EXT_descriptor_buffer.html),
`offset` could instead become a byte offset, enabling resources to be packed
much more tightly.


#### Open Issue: Should this replace the ResourceDescriptorHeap built-in?

If non-homogenous resource sizes are exposed to shaders,
`ResourceDescriptorHeap` poses a problem as it assumes uniform resource
sizes.
`ResourceEntry()` uses strong typing, so could seamlessly switch to byte
offsets on the user's behalf.
Supporting both models in the same shader is likely to be very messy.

As `ResourceEntry()` enables a superset of same functionality (the templated
type can just be a single resource type), and to avoid future
incompatibility, `ResourceDescriptorHeap` should be deprecated by this
proposal.


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
be interpreted as a Raw Buffer to be used in the shader.

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
	uint descriptorTableOffset;
    uint4 constants;
    RawConstantBuffer<...> buffer;
};

void main(RootData root : SV_Constants)
{
    DescriptorTableData descriptorTable = ResourceEntry(root.descriptorTableOffset);
}
```

In DirectX, this could be specified in the root signature as:

 * Binding 0 is a descriptor table
 * Binding 1 is 4 root constants
 * Binding 2 is a root descriptor CBV

In Vulkan this would map to push constants, where `buffer` maps to a
`VkDeviceAddress` value from a buffer.


#### Open Issue: Allow resource entries to be constructed in-place?

The above example shows the specification of a descriptor table from an index
in `SV_Constants`.
The manual step of construction is somewhat awkward, and it might make sense
to have a way to define those directly in storage.
Just specifying a structure would not be enough, as it would be treated as a
structure of multiple offsets, rather than a single offset to a contiguous
set of resources.

Something like the following might be desirable:

```hlsl
struct RootData {
	DescriptorTable<DescriptorTableData> descriptorTable;
    uint4 constants;
    RawConstantBuffer<...> buffer;
};
```

This would also allow applications to load/store descriptor table handles
directly in the same way as individual resource types.


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


### Raw Buffer types

In the above example, a root descriptor (in that case a CBV) is passed in.
When using a root descriptor in DirectX, these are mapped to buffers when
using registers.
However, declaring a standard buffer type directly here would result in the
assumption of a 32-bit index into the heap, not a 64-bit root descriptor VA.

New resource types are provided that can be declared to access a root
descriptor VA:

 * `RawConstantBuffer<typename T>`
 * `RawStructuredBuffer<typename T = float4, uint64_t Size = UINT64_MAX>`
 * `RawRWStructuredBuffer<typename T = float4, uint64_t Size = UINT64_MAX>`
 * `RawByteAddressBuffer<uint64_t Size = UINT64_MAX>`
 * `RawRWByteAddressBuffer<uint64_t Size = UINT64_MAX>`
 * `RawRasterizerOrderedBuffer<typename T = float4, uint64_t Size = UINT64_MAX>`
 * `RawRasterizerOrderedByteAddressBuffer<uint64_t Size = UINT64_MAX>`
 * `RawRaytracingAccelerationStructure`

These can be used in exactly the same way as their non-raw counterparts,
except that when declared in memory they correspond to a 64-bit GPU VA,
rather than a 32-bit heap index.

Raw structured and byte address buffers have an extra optional `Size`
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
    RawConstantBuffer<...> a;
    RawConstantBuffer<...> b;
    RawConstantBuffer<...> c;
};

struct RootData {
    RawConstantBuffer<MoreBuffers> buffer;
};

void main(RootData root : SV_Constants)
{
    uint value = root.buffer.a.value;
}
```

NOTE: This usage outside of root constants may require driver changes in
DirectX. Vulkan works out of the box with device addresses.


#### Open Issue: Why are raw buffer types separate from their counterparts?

Standard buffer types by this proposal are resources which live in the heap,
and are thus represented as a 32-bit index when read or written to memory.
Raw buffer types however, do not need to live in the heap, and are
represented as 64-bit pointers when accessed in external memory.
The only way to enable them to be the same type would impose heavy and
awkward restrictions on when and how they could be accessed in external
memory.
Having separate types feels like a cleaner compromise.

A future direction might be to deprecate non-raw buffers, but this proposal
aims to remain compatible with the existing DirectX API and, to a degree,
with existing shaders.


#### Open Issue: Raw resource construction

It would be useful to enable raw resources to be constructed from existing
heap resources of a matching type, possibly with an offset and reduced size
for non-constant buffer types.
This is not currently possible in any API, but if we could make it work it
would be one way to solve the "slice" problem, particularly if we enforce
that slices must be subsets of the original buffer.

That might look, for example, something like a new member functions for
buffers:

```hlsl
GetRaw();
GetRawSlice(uint offset);
GetRawSlice(uint offset, uint size);
```

The sum of `offset` and `size` must be less than or equal to the original
buffer's size.
The returned raw buffer would be identical to the original buffer resource,
except that it would now behave as a 64-bit pointer when accessed (including
OOB semantics), would be a potentially smaller range of data, and would no
longer be associated with the heap.


#### Open Issue: Pointer math

Currently there's no way to directly adjust the value of a pointer in a
shader legally, as aliasing is disallowed, and casting/construction of raw
resources is not supported.

It's unlikely we want this to change, but it might be useful considering that
an API to get subsets of raw buffers would solve this "safely".
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
