<!-- {% raw %} -->

# Add shader name to Pipeline State Validation data (PSV0)

* Proposal: [0012](0012-psv0-entry-name.md)
* Author(s): [Tex Riddell](https://github.com/tex3d)
* Sponsor: [Tex Riddell](https://github.com/tex3d)
* Status: **Under Consideration**
* Planned Version: SM 6.8, validator version 1.8
* PRs:
  [#5946](https://github.com/microsoft/DirectXShaderCompiler/pull/5946)
* Issues:
  [#5944](https://github.com/microsoft/DirectXShaderCompiler/issues/5944)

## Introduction

In an upcoming feature, the D3D12 runtime needs to know the entry function name
for non-library shaders, in order to import shaders into state objects, and
construct graphics or compute programs referring to them by name.  The `PSV0`
part of a DxilContainer encodes information for the D3D12 runtime so it can
construct and validate state objects without parsing llvm bitcode.  This
proposes to add the entry function name to the existing `PSV0` container part.

## Motivation

In an upcoming feature, the D3D12 runtime needs to know the entry
function name for non-library shaders in order to import shaders into
collections, and construct graphics or compute programs using them.

DXIL libraries encode information about entry functions and exports, among
other facts the runtime needs, in the Runtime Data `RDAT` part.
However, non-library targets, such as `vs_6_7`, `cs_6_0`, and so on, do not
use the `RDAT` part to describe data for the runtime.  Instead, for historical
reasons, they use several different parts to describe information about the
shader that the runtime needs for pipeline construction and validation.
There is an optional part holding a root signature, up to three parts for I/O
signatures, and a `PSV0` (`PipelineStateValidation`) part that encodes all
additional information for the runtime.

None of these parts included for non-library shaders currently capture the name
of the entry function inside the DXIL part data. This name is available in
the encoded llvm bitcode, but the runtime is unable to parse bitcode.
Enabling the runtime to parse LLVM bitcode would add dependencies,
and require parsing a large amount of unnecessary data.

## Proposed solution

The `PSV0` part has a string table, and a versioning convention that allows
backward and forward compatibility when adding new data.
Adding a new structure version with a field for the entry name which is an
offset into the string table accommodates the need to surface
information for the D3D12 runtime to access.

Adding this information will not impact an older runtime's ability to read the
`PSV0` data in the container.  If the new runtime is reading an older version
of the `PSV0` data, the name will simply appear to be unset.  If the name is
unset, the runtime can fall back to default behavior, which limits the state
object API usage scenarios.

When a new compiler and validator are used to compile an
application's shaders, these shaders will still be compatible with older
pipeline API and runtime versions while including the additional information
that makes them convenient to use in the new state object API.

## Detailed design

This section contains some of the details describing the data layout of PSV0.
For brevity this spec does not specify unrelated parts of the PSV0 format.
Notable omissions are the `PSVSignatureElement` and `PSVResourceBindInfo` record
structure and the shader-stage specific info structures contained in the
`PSVRuntimeInfo0` shader info union.  The contents of these structures are not
relevant to this proposal.

### PSV0 data layout

The data layout for `PSV0` is described with pseudo-code
[here](https://github.com/microsoft/DirectXShaderCompiler/blob/e496555aae0c9efdc67430994055a8077a8b86cc/include/dxc/DxilContainer/DxilPipelineStateValidation.h#L821).
Like all other DxilContainer parts, values in `PSV0` are little-endian.

The basic layout of PSV0 starts with a PSVRuntimeInfo structure size, used for
versioning, then the `PSVRuntimeInfo` structure, followed by additional data
sections depending on state in the `PSVRuntimeInfo` structure.

The `PSVRuntimeInfo` structure contains the constant-sized information
describing the shader for runtime validation purposes.  It is versioned in a
manner where each subsequent version simply adds to the structure, increasing
its size.  Each version must begin and end on a 4-byte aligned boundary.  This
structure contains unions, where the active member of a union depends on some
other state.  All unused areas of a record are zero-filled, this includes
unused space in a union, unused fields outside a union.

The following tables describe `PSVRuntimeInfo` structure layouts by version.
Offset and Size are in bytes.  Offset starts from the beginning of the struct,
not including the structure size at the beginning of the PSV0 data.  The
Availability column identifies when the described value at this location is
interpreted in this way (this may overlap other fields in the case of unions).
The Dependency column identifies additional data in a later section that may be
indicated by this value.

#### PSVRuntimeInfo Version 0

`PSVRuntimeInfo0`, size: `24 bytes`:

| Offset | Size | Field | Availability | Dependency | Description |
|-|-|-|-|-|-|
| 0 | 16 | `union { ... }` | union member depends on shader type decoded from the `ProgramVersion` in the `DxilProgramHeader` | None | union of shader info structures, not relevant here. |
| 16 | 4 | `uint32_t MinimumExpectedWaveLaneCount` | Always | None | minimum wave size for shader |
| 20 | 4 | `uint32_t MaximumExpectedWaveLaneCount` | Always | None | maximum wave size for shader |

#### PSVRuntimeInfo Version 1

`PSVRuntimeInfo1` includes `PSVRuntimeInfo0`, total size: `36 bytes`:

| Offset | Size | Field | Availability | Dependency | Description |
|-|-|-|-|-|-|
| 24 | 1 | `uint8_t ShaderStage` | Always | None | This encodes the `DXIL::ShaderKind` locally, which required decoding from `ProgramVersion` in the `DxilProgramHeader` in version 0 |
| 25 | 1 | `uint8_t UsesViewID` | Always | None | `1` if shader uses ViewID input directly, otherwise `0` |
| 26 | 2 | `union {...}` | union member depends on `ShaderStage` | None | Additional data needed depending on `ShaderStage` |
| 26 | 2 | `uint16_t MaxVertexCount` | when `ShaderStage` is `Geometry` (2) | None | `MaxVertexCount` for geometry shader |
| 26 | 1 | `uint8_t SigPatchConstOrPrimVectors` | when `ShaderStage` is `Hull` (3) or `Domain` (4) | Bitvector sizes | Number of patch constant input or output signature packed vectors |
| 26 | 1 | `uint8_t SigPrimVectors` | when `ShaderStage` is `Mesh` (13) | Bitvector sizes | Number of primitive output signature packed vectors |
| 27 | 1 | `uint8_t MeshOutputTopology` | when `ShaderStage` is `Mesh` (13) | None | Mesh output topology (`DXIL::MeshOutputTopology`) |
| 28 | 1 | `uint8_t SigInputElements` |  | PSVSignatureElement count |  |
| 29 | 1 | `uint8_t SigOutputElements` |  | PSVSignatureElement count |  |
| 30 | 1 | `uint8_t SigPatchConstOrPrimElements` |  | PSVSignatureElement count |  |
| 31 | 1 | `uint8_t SigInputVectors` |  | Bitvector sizes | Number of input signature packed vectors |
| 32 | 4 | `uint8_t SigOutputVectors[4]` |  | Bitvector sizes | Number of output signature packed vectors per stream (only `Geometry` may use more than one stream, up to 4) |

#### PSVRuntimeInfo Version 2

`PSVRuntimeInfo2` includes `PSVRuntimeInfo1`, total size: `48 bytes`:

| Offset | Size | Field | Availability | Dependency | Description |
|-|-|-|-|-|-|
| 36 | 4 | `uint32_t NumThreadsX` | when `ShaderStage` is `Compute` (5), `Mesh` (13), or `Amplification` (14) | None | Number of threads `X` dimension for compute-like targets |
| 40 | 4 | `uint32_t NumThreadsY` | when `ShaderStage` is `Compute` (5), `Mesh` (13), or `Amplification` (14) | None | Number of threads `Y` dimension for compute-like targets |
| 44 | 4 | `uint32_t NumThreadsZ` | when `ShaderStage` is `Compute` (5), `Mesh` (13), or `Amplification` (14) | None | Number of threads `Z` dimension for compute-like targets |

#### Proposed PSVRuntimeInfo Version 3

`PSVRuntimeInfo3` includes `PSVRuntimeInfo2`, total size: `52 bytes`:

| Offset | Size | Field | Availability | Dependency | Description |
|-|-|-|-|-|-|
| 48 | 4 | `uint32_t EntryFunctionName` | Always | None | Name of the entry function as an offset into `StringTable` data to a null-terminated utf-8 string |

#### Additional data sections

There are several patterns used for the sections of additional data in PSV0:

- `Record`
  - Flat serialized record structure:
  - offset and size alignment minimum of 4 bytes
  - little-endian encoded values
- `StringTable` (or string buffer)
  - starts with: `uint32_t` `StringTableSize` size in bytes, rounded up to next 4 byte alignment
  - follwed by: `StringTableSize` bytes of utf-8 encoded, null-terminated strings
  - record fields may refer to a string with a byte offset into this buffer, not including the 4 bytes for string table size
- `RecordTable`
  - starts with a `uint32_t` `RecordStride` in bytes. Record stride must be 4-byte aligned
  - followed by array of flat serialized records separated by `RecordStride` bytes
  - the number of records in the array depends on state in the PSVRuntimeData structure
- `IndexTable`
  - starts with: `uint32_t` `IndexTableCount` count of indices in the index table
  - follwed by: `IndexTableCount` `uint32_t` indices
  - an index array in the index table is an array of indices preceded by the count of elements in the array
  - a member of a record can refer to an array of indices by using the index into the index table pointing to the count that precedes the array of indices.
- `Bitvector`
  - Array of `uint32_t` values containing bitvector data
  - Size dependent on some state in PSVRuntimeInfo

The following table describes the overall PSV0 layout, with extra data sections
that follow the `PSVRuntimeInfo` structure.  The extra data sections starting
with the `StringTable` are only present for Version 1 and above.  The starting
location for additional data sections will be 4 bytes for the `PSVRuntimeInfo`
structure size plus the size specified in that location.  The offset of each
item is immediately following the 4-byte aligned end of the previous section.

##### Main runtime info structure

| Element | Type | Dependency | Description |
|-|-|-|-|
| `PSVRuntimeInfo` size | `uint32_t` | PSV version | 4-byte aligned size of the primary runtime info structure in bytes |
| `PSVRuntimeInfo` contents | `PSVRuntimeInfo` version depending on size | PSV version | structure containing all of the main fixed-sized fields describing the shader for the runtime |

##### Resource binding table

| Element | Type | Dependency | Description |
|-|-|-|-|
| `ResourceCount` | `uint32_t` | | number of resources defined in the following `PSVResourceBindInfo` `RecordTable` |
| `PSVResourceBindInfo` size | `uint32_t` | | size of the `PSVResourceBindInfo` `Record` used in the following `PSVResourceBindInfo` `RecordTable` |
| `PSVResourceBindInfo`s | `RecordTable` of `PSVResourceBindInfo`s | | resource binding table |

##### String table

Only present in PSV version 1 and above.  Used for signature element semantic
strings.  This proposal uses this string table for entry function name as well.

| Element | Type | Dependency | Description |
|-|-|-|-|
| `StringTable` data size | `uint32_t` |  | size in bytes of the string table data following this value (size must be 4-byte aligned) |
| `StringTable` data | `char` array | | sequence of utf-8 null-terminated strings ending in null characters up to aligned size |

##### Index table

Only present in PSV version 1 and above.  Used for signature element semantic
index arrays.

| Element | Type | Dependency | Description |
|-|-|-|-|
| `IndexTableCount` | `uint32_t` | | number of `uint32_t` values in the `IndexTable` |
| `IndexTable` | `uint32_t` array | | array of `IndexTableCount` `uint32_t` values |

##### Signature element table

Only present in PSV version 1 and above, and only when `SigInputElements` or
`SigOutputElements` or `SigPatchConstOrPrimElements` are nonzero.

| Element | Type | Dependency | Description |
|-|-|-|-|
| `PSVSignatureElement` size | `uint32_t` | if `SigInputElements` or `SigOutputElements` or `SigPatchConstOrPrimElements` are nonzero | size of the structure used in the following `PSVSignatureElement` `RecordTable` |
| `PSVSignatureElement`s | `RecordTable` of `PSVSignatureElement`s | `SigInputElements` + `SigOutputElements` + `SigPatchConstOrPrimElements` array elements | signature element description |

##### ViewID dependency tables

Only present in PSV version 1 and above, only when `UsesViewID` is `1`, and
only if there is any data to store, based on output vector sizes.  Depends on
`UsesViewID`, `ShaderStage`, `SigOutputVectors[...]`, and
`SigPatchConstOrPrimVectors` from `PSVRuntimeInfo1`.

| Element | Type | Dependency | Description |
|-|-|-|-|
| `ViewIDOutputMask`s | 0 to 4 `Bitvector`s | if `UsesViewID` | Zero to 4 `Bitvector`s of output components from packed vector streams 0 to 3, indicating whether each component is ViewID dependent, where number of `uint32_t` values used for each `Bitvector` is `(SigOutputVectors[i] + 7) >> 3` |
| `ViewIDPCOrPrimOutputMask` | `Bitvector` | if `UsesViewID` and `SigPatchConstOrPrimVectors` is non-zero and (`ShaderStage` is `Hull` (3) or `ShaderStage` is `Mesh` (13)) | `Bitvector` of patch constant or primitive output components from packed vectors, indicating whether each component is ViewID dependent, where number of `uint32_t` values used is `(SigPatchConstOrPrimVectors + 7) >> 3` |

##### Input to output dependency tables

Only present in PSV version 1 and above, only when there is any data to store,
based on input to output size combinations.  Depends on
`ShaderStage`, `SigInputVectors`, `SigOutputVectors[...]`, and
`SigPatchConstOrPrimVectors` from `PSVRuntimeInfo1`.

| Element | Type | Dependency | Description |
|-|-|-|-|
| `InputToOutputTable` | 0 to 4 `Bitvector`s | non-zero`SigInputVectors` and `SigOutputVectors[i]` (where `i` is 0 to 3) | `Bitvector` of output components affected by each input component, number of `uint32_t` elements in each `Bitvector` array is `((SigOutputVectors[i] + 7) >> 3) * InputVectors * 4` |
| `InputToPCOutputTable` | `Bitvector` | `ShaderStage` is `Hull` (3) and non-zero `SigInputVectors` and `SigPatchConstOrPrimVectors` | `Bitvector` of output components affected by each input component, number of `uint32_t` elements in each `Bitvector` array is `((SigPatchConstOrPrimVectors + 7) >> 3) * InputVectors * 4` |
| `PCInputToOutputTable` | `Bitvector` | `ShaderStage` is `Domain` (4) and non-zero `SigPatchConstOrPrimVectors` and `SigOutputVectors[0]` | `Bitvector` of output components affected by each input patch constant component, number of `uint32_t` elements in each `Bitvector` array is `((SigOutputVectors[0] + 7) >> 3) * SigPatchConstOrPrimVectors * 4` |

### Versioning PSV0 for the new data

The `PSV0` part has a versioning convention that allows backward and forward
compatibility, and is tied to validator version, as opposed to shader model.
Data added to the format will be safely ignored by an older runtime.

This works as follows:

- Depending on the validator version, we select a versioned top-level
  `PSVRuntimeInfo` structure to use.  The version and contents of this
  structure also determine the extra data that will be included after this
  structure in the part.
- The structure size is the first element of the `PSV0` part, indicating to a
  reader the available versions in the serialized data.  If that size is larger
  than the newest structure a reader knows about, it must ignore additional
  data after the end of the newest version of `PSVRuntimeInfo` structure that
  it knows about.
- Adding new data is a matter of deriving from (or including) the last version
  of the `PSVRuntimeInfo` structure, adding new fields to the new structure,
  and updating the size indicating the structure version that's available when
  `PSV0` is written.
  - This proposal adds a new `PSVRuntimeInfo3` structure that will update this
    size value to 52.
- Additional data (such as record tables) needed for newer versions of the
  structure will appear after this additional data for previous versions of the
  structure.
  - This proposal does not add any new additional data sections to PSV0.

This document proposes a new `PSVRuntimeInfo3` structure versioned after
`PSVRuntimeInfo2`, and adding one `uint32_t` `EntryFunctionName` field for the
offset into the string table.

### Validation

DxilContainer validation checks that `PSV0` exactly matches what is expected
for the module based on the validator version set in the module metadata.  This
means that any changes to data in the  `PSV0` part without gating that change
on a new validator version will cause a failure with existing validators.  This
new PSV version 3 will only be used when the validator version is `1.8` or
higher.

## Alternatives considered

### Switch shaders to RDAT

Dxil libraries use the `RDAT` part to describe everything required by the
runtime in one unified container part.  This part can replace the `PSV0` part,
the I/O signature parts, and the root signature part, instead of just using it
for library shaders.  Most of the additions necessary to do this have already
been added and used experimentally, because switching shaders to `RDAT` was the
original plan for SM 6.8.

There are a few missing pieces of information which would have to be added or
filled in to completely replace the legacy parts.  This includes the root
signature, and the ViewID & input to output dependency maps.  The root
signature part can be kept separate for ordinary shader targets, since this
part can be removed or replaced separately, so there is a pretty good argument
for keeping this a separate part.  The ViewID & I/O dependency maps have
already been computed for inclusion in the `PSV0` part, so they just need to be
written out to the `RDAT` part, to the locations already reserved for this.

Switching away from the old parts can only be done with a new shader model,
otherwise prior shader targets would no longer run on older runtime versions.

In an application, shaders may be compiled to prior shader targets when they do
not require new features introduced in the latest shader model.  This makes
shipped shaders sharable in multiple pipelines targeting different levels of
feature support.  Requiring a new shader model to provide this name would
complicate things whenever a shader compiled to an earlier shader model may be
used in the state object API.

If the runtime requires the latest shader model for use with the state object
API, an app designed to work on a previous runtime version or on more limited
feature support would need to compile and keep track of an additional compiled
version of shaders that otherwise would not require the latest shader model
features.  If instead the runtime accepts shaders compiled to an earlier shader
model, then it must rely on the existing parts to supply the information it
needs.  If the name isn't added to an existing part (like `PSV0` in this
proposal), then any potential use of these shaders will constrain the app's use
of the state object API to a narrower scenario that can be supported without
knowing the entry function name.

A potential mitigation would be to do both, add the name to `PSV0`, and replace
legacy parts with `RDAT` for the latest shader model.  This could be a workable
path to removing the legacy I/O signature and `PSV0` parts, reducing redundant
information (strings) currently included in these DxilContainer parts.
However, the runtime would need to be able to read the information it needs
from either the old container parts, or `RDAT`, depending on which is included
in the shader container.  Some information is formatted differently in `RDAT`
than it is in the original container parts, so code designed to work with
either one has to either do translation, or have multiple code paths for the
same purpose.  This will increase potential for bugs, and the testing burden in
these areas.

### Add a general purpose symbol table

See detailed proposal [here](https://github.com/microsoft/hlsl-specs/pull/110).

A Symbol table representing the exported functions and entry points could be
useful for identifying linkage dependencies in the future, without using the
information in the `RDAT` part.

For non-library shaders, this new symbol table could meet the runtime need for
the entry function name, instead of adding that name to the `PSV0` data.  It's
hard to see value for these shaders beyond supplying this one function name for
this scenario.

For a Dxil library, this symbol table will be fully redundant with information
contained in the `RDAT` part, and lack the ability to encode the additional
information needed by the runtime, so it would not be able to replace `RDAT`.

Since a symbol table can't replace the existing need for any of the other parts
in DxilContainer, adding it at this point will have the effect of adding yet
another part with another data format that needs to be generated, parsed and
maintained, beyond the ones we already have.

The argument for this approach appears to be that is looks/feels like part of
something we might want to include in a future container format that replaces
DxilContainer and all the legacy parts in favor of another, hopefully more
widely used and standardized format, as of yet undetermined.  However, there
are many decisions to be made before we know what our desired destination looks
like.

Adding this proposed symbol table at this point would only add to the
complexity and maintenance costs for an intermediate DxilContainer format that
can't realize any theorized advantages without larger changes that would have
to be made in some future container format.

<!-- {% endraw %} -->
