<!-- {% raw %} -->

# Add shader name to Pipeline State Validation data (PSV0)

* Proposal: [NNNN](NNNN-psv0-entry-name.md)
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
for non-library shaders, in order to import shaders into collections, and
construct graphics or compute programs referring to them by name.  The `PSV0`
part of a DxilContainer encodes information for the D3D12 runtime so it can
construct and validate state objects without parsing llvm bitcode.  This
proposes to add the entry function name to the existing `PSV0` container part.

## Motivation

In an upcoming feature, the D3D12 runtime needs to know the entry
function name for non-library shaders in order to import shaders into
collections, and construct graphics or compute programs using them.

Dxil libraries encode information about entry functions and exports, among
other facts the runtime needs, in the Runtime Data `RDAT` part.
However, non-library targets, such as `vs_6_7`, `cs_6_0`, and so on, do not
use the `RDAT` part to describe data for the runtime.  Instead, for historical
reasons, they use several different parts to describe information about the
shader that the runtime needs for pipeline construction and validation.
There is an optional part holding a root signature, up to three parts for I/O
signatures, and a `PSV0` (`PipelineStateValidation`) part that encodes all
additional information for the runtime.

None of these parts included for non-library shaders currently capture the name
of the entry function inside the DxilModule.  This name is available through
metadata in the DxilModule, but that is encoded in llvm bitcode, so it is not
accessible to the runtime without adding significant dependencies, and parsing
through a lot of data it otherwise does not need to parse.

## Proposed solution

The natural way to express data like this for D3D runtime consumption,
within the current set of container parts, would be to use the `PSV0` part.
The `PSV0` part has a string table, and a versioning convention that allows
backward and forward compatibility when adding new data.
Adding a new structure version with a field for the entry name which is an
offset into the string table is a natural and straightforward way to add this
information for the D3D12 runtime to access.

Adding this information will not impact an older runtime's ability to read the
`PSV0` data in the container.  If the new runtime is reading an older version
of the `PSV0` data, the name will simply appear to be unset.  If the name is
unset, the runtime can fall back to default behavior, which limits the state
object API usage scenarios.

With this solution, when a new compiler and validator are used to compile an
application's shaders, these shaders will still be compatible with older
pipeline API and runtime versions while including the additional information
that makes them convenient to use in the new state object API.

## Detailed design

### PSV0 data layout

The data layout for `PSV0` is described with pseudo-code
[here](https://github.com/microsoft/DirectXShaderCompiler/blob/e496555aae0c9efdc67430994055a8077a8b86cc/include/dxc/DxilContainer/DxilPipelineStateValidation.h#L821).
Like all other DxilContainer parts, values in `PSV0` are little-endian.

### Versioning PSV0 for the new data

The `PSV0` part has a versioning convention that allows backward and forward
compatibility, and is tied to validator version, as opposed to shader model.
Data added to the format will be safely ignored by an older runtime.

This works as follows:

- A version number determines which version of the top-level `PSVRuntimeInfoN`
  structure will be used, based on the validator version.  This version also
  determines what additional information will be included in the part.
- Adding new data is a matter of deriving from the last version of the
  `PSVRuntimeInfoN` structure, incrementing the number at the end, and adding
  the needed fields to the new structure.
- The structure size is the first element of the `PSV0` part, indicating to a
  reader the available versions in the serialized data.  If that size is larger
  than the newest structure a reader knows about, it must ignore additional
  data after the end of the newest version of `PSVRuntimeInfoN` that it knows
  about.
- Additional data (such as record tables) needed for newer versions of the
  structure will appear after this additional data for previous versions of the
  structure.

Hooking up a new `PSVRuntimeInfoN` version requires:
- updating the `MAX_PSV_VERSION` and the `RuntimeInfoSize()` function
- adding a pointer for the new structure to `DxilPipelineStateValidation`
- updating `ReadOrWrite` method to use `AssignDerived` for the new pointer
- updating `DxilContainerAssembler` to use the new version based on the next
  validator version, so containers produced will work with existing validators.

Making the new data available requires adding any needed accessors to
`DxilPipelineStateValidation` and writing the new data from
`DxilContainerAssembler`, when a new version is selected.

In this case this consists of:
- Adding one accessor that returns a null-terminated utf-8 string pointer, by
  looking it up in the string table at the offset provided by the new field in
  the new version of the `PSVRuntimeInfoN` structure.
- In `DxilContainerAssembler`, when writing the new version of `PSV0`, add the
  entry function name to the string table, and write the offset a new
  `EntryFunctionName` field in the new `PSVRuntimeInfoN` structure.

### Validation

DxilContainer validation checks that `PSV0` exactly matches what is expected
for the module based on the validator version set in the module metadata.
This means that any changes to data in the  `PSV0` part without gating that
change on a new validator version will cause a failure with existing
validators.  This new version will only be used when the validator version
is `1.8` or higher.

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
