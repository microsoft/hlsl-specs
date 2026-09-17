<!-- {% raw %} -->

# Scalar constant buffer layout

* Proposal: [0023](0023-scalar-constant-buffer-layout.md)
* Author(s): [Tobias Hector](https://github.com/tobski)
* Sponsor: Chris Bieneman
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

Further, a compiler flag can be provided to switch the default layout to
scalar, allowing for users to move to scalar layout without re-authoring large
numbers of existing shaders.


## Detailed Design

### HLSL Additions

A new `[bufferlayout("layout")]` attribute will be applicable to `cbuffer` and
`ConstantBuffer<struct>` definitions.

The `layout` may be either `legacy` or `scalar`.

To avoid incompatibility with existing code, when the `bufferlayout`
attribute is not applied to a constant buffer the layout will default to the
`legacy` layout.
The addition of this feature to HLSL will not have any effect on existing HLSL
code as a result.


#### Layouts

`legacy` layout uses the current packing rules described here:
https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-packing-rules.

`scalar` layout modifies the alignment rules for constant buffers, requiring
that each element is packed to align with it's scalar size.
For composite types such as vectors and matrices this requires that each
component be aligned individually to it's size, rather than the composite type
be aligned to it's total size.
The intention of these rules is to match the `scalarBlockLayout` in Vulkan,
providing easy compatibility between DXIL and SPIR-V layouts.


### Interchange Format Additions

This feature does not require any change to the DXIL language to represent
scalar layouts.

SPIR-V already has full support for scalar layouts.


### Diagnostic Changes

These changes introduce two new errors for the `bufferlayout` attribute.

First if the `bufferlayout` attribute is applied to any definition other than a
constant buffer an error must be reported.

Second if the `bufferlayout` attribute is given an invalid layout name an error
must be reported.


### Validation Changes

DXIL Validation must be updated to accept scalar layout constant buffers in
addition to the existing layout constant buffers.


## Examples

The following example demonstrates legal uses of the attribute.

```
[bufferlayout("legacy")]
cbuffer MyBuffer ...

[bufferlayout("scalar")]
cbuffer MyBuffer ...

[bufferlayout("legacy")]
ConstantBuffer<MyStruct> MyBuffer ...

[bufferlayout("scalar")]
ConstantBuffer<MyStruct> MyBuffer ...
```

The following example demonstrates the difference in buffer alignment and size
between legacy and scalar layouts in DXIL.
Note that in legacy layout the float3 is aligned such that it begins in the
second 16 byte space, while in scalar layout it begins immediately after the
float2, with the 3rd element starting at offset 16.

```
[bufferlayout("legacy")]
cbuffer MyBuffer {
  float2 Foo;
  float3 Bar;
};

; cbuffer MyBuffer
; {
;
;   struct MyBuffer
;   {
;
;       float2 Foo;                                   ; Offset:    0
;       float3 Bar;                                   ; Offset:   16
;
;   } MyBuffer;                                       ; Offset:    0 Size:    28
;
; }

[bufferlayout("scalar")]
cbuffer MyBuffer {
  float2 Foo;
  float3 Bar;
};

; cbuffer MyBuffer
; {
;
;   struct MyBuffer
;   {
;
;       float2 Foo;                                   ; Offset:    0
;       float3 Bar;                                   ; Offset:    8
;
;   } MyBuffer;                                       ; Offset:    0 Size:    20
;
; }
```

As all values must be aligned to their scalar size, a scalar or element of a
composite type may not lay across the 16 byte boundary.
In the following example the double is aligned identically in both legacy and
scalar layout, to 8 bytes, demonstrating this point.

```
[bufferlayout("legacy")]
cbuffer MyBuffer {
  float3 Foo;
  double Bar;
};

; cbuffer MyBuffer
; {
;
;   struct MyBuffer
;   {
;
;       float3 Foo;                                   ; Offset:    0
;       double Bar;                                   ; Offset:   16
;
;   } MyBuffer;                                       ; Offset:    0 Size:    24
;
; }

[bufferlayout("scalar")]
cbuffer MyBuffer {
  float3 Foo;
  double Bar;
};

; cbuffer MyBuffer
; {
;
;   struct MyBuffer
;   {
;
;       float3 Foo;                                   ; Offset:    0
;       double Bar;                                   ; Offset:   16
;
;   } MyBuffer;                                       ; Offset:    0 Size:    24
;
; }
```

Matrix types in legacy layout are significantly different to scalar layout.
With legacy layout a matrix is laid out so each row is 16 byte aligned.
The exception to this is a matrix of doubles, in which case a double3x and
double4x matrix will have the rows aligned to 32 bytes.
With scalar layouts, as with vectors, each element is aligned to it's own scalar
size.
The following example demonstrates the differences in matrix layout by
showing the cbuffer loads and extractvalue instructions needed to load each
element of a 2x2 float matrix.
Note that the legacy example requires two 16 byte loads from the cbuffer, while
the scalar example requires only one.


```
[bufferlayout("legacy")]
cbuffer MyBuffer {
  float2x2 Foo;
};

  %loadOne = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %cbufferHandle, i32 0)
  %elemOne = extractvalue %dx.types.CBufRet.f32 %loadOne, 0
  %elemTwo = extractvalue %dx.types.CBufRet.f32 %loadOne, 1
  %loadTwo = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %cbufferHandle, i32 1)
  %elemThree = extractvalue %dx.types.CBufRet.f32 %loadTwo, 0
  %elemFour = extractvalue %dx.types.CBufRet.f32 %loadTwo, 1


[bufferlayout("scalar")]
cbuffer MyBuffer {
  float2x2 Foo;
};

  %loadOne = call %dx.types.CBufRet.f32 @dx.op.cbufferLoadLegacy.f32(i32 59, %dx.types.Handle %cbufferHandle, i32 0)
  %elemOne = extractvalue %dx.types.CBufRet.f32 %loadOne, 0
  %elemTwo = extractvalue %dx.types.CBufRet.f32 %loadOne, 1
  %elemThree = extractvalue %dx.types.CBufRet.f32 %loadThree, 2
  %elemFour = extractvalue %dx.types.CBufRet.f32 %loadFour, 3

```

### SPIR-V Support

SPIR-V already supports this scalar layout proposal through the
[VK_EXT_scalar_block_layout](https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_EXT_scalar_block_layout.html)
extension.


## Open Questions

* Do we require an update to DXIL metadata to describe that scalar layout is in
use per module or per buffer, if at all?


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
