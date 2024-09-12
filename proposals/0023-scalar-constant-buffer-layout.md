<!-- {% raw %} -->

# Scalar constant buffer layout

* Proposal: [0023](0023-scalar-constant-buffer-layout.md)
* Author(s): [Tobias Hector](https://github.com/tobski)
* Sponsor: TBD
* Status: **Under Consideration**


## Introduction

This proposal adds the ability to define constant buffers with alignment
defined only by the scalar components of its structure members.
This allows layout compatibility with native C/C++ structure layouts, where
there is no native vector type.
This functionality already exists in Vulkan via the
[VK_EXT_scalar_block_layout](https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_EXT_scalar_block_layout.html)
extension, but not yet in DirectX.


## Motivation

When generating data to be passed to a shader from the CPU programming
language, applications need to be very deliberate with how that data is packed
if they use vector and array types in HLSL.
The packing rules for constant buffers are described here:
https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-packing-rules.
The gist is that most things are aligned to either 4 or 16 bytes, but members
are packed down to a smaller alignment where possible, such that information
about all elements is necessary to determine the final layout.


## Proposed solution

Given that scalar block layout is now widely supported across all recent
hardware in Vulkan, this document proposes adding a new `bufferlayout`
attribute that takes one of two values; either `legacy`, matching the current
layout constraints, or the new `scalar` layout.
The new `scalar` layout aligns structure members to the size of the scalar
element of each type, with no additional alignment for arrays, vectors, or
matrices; effectively matching standard C/C++ memory layouts.

The new attribute would have a default value of `legacy` if not specified,
but this could be changed with a command line option.
A future version of HLSL may choose to make `scalar` the default, or even
remove the `legacy` path altogether.


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

As the default layout of buffers is not changing without user intervention,
there should be no breakages introduced by this change.
What may break things is if the default layout is ever changed by a new HLSL
version; but while that seems likely, whether and how that happens is outside
of the scope of this proposal.

If the new attribute is specified without targeting the new shader model, the
compiler should raise an error directing the user to use a later shader model.


## Alternatives considered (Optional)

One alternative method to solve this issue would be to add something similar
to the `#pragma pack` directive in C/C++, but this would need to be set on all
members, and requires a more complex implementation to be fully supported,
given the push/pop variants supported by compilers.
It may still be worthwhile to support something like this for more control over
 layouts, but that can be considered as a separate feature.


## Acknowledgments (Optional)

 - Chris Bieneman
 - Jesse Natalie
 - Contributors to
   [VK_EXT_scalar_block_layout](https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_EXT_scalar_block_layout.html)

<!-- {% endraw %} -->
