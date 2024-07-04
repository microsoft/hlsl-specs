<!-- {% raw %} -->

# Inline SPIR-V

*   Proposal: [0011](0011-inline-spirv.md)
*   Author(s): [Steven Perron](https://github.com/s-perron)
*   Sponsor: [Chris B](https://github.com/llvm-beanz) and
    [Steven Perron](https://github.com/s-perron)
*   Status: **Under Review**

## Introduction

Define a set of Vulkan specific builtin functions, types, and attributes that
will allow vendors to implement their extensions. The vendors should be able to
write a self-contained header file that users can use without knowing about
inline SPIR-V.

## Motivation

In Vulkan, there is a culture of allowing a vendor to define extensions that are
only interesting to them. From the perspective of a driver this is acceptable
because company A does not have to support the extension put out by vendor B if
they do not want to. It does not create extra work for anyone else.

From a compiler perspective, this is not true. If a vendor wants DXC, or any
other SPIR-V generator, to generate the SPIR-V for their extension it generally
requires a code change to the compiler that must be maintained.

If those extensions could be defined as a header file that DXC consumes, then a
vendor would not have to modify the compiler other than possibly updating the
submodules.

The existing
[inline SPIR-V](https://github.com/microsoft/DirectXShaderCompiler/wiki/GL_EXT_spirv_intrinsics-for-SPIR-V-code-gen)
was the first attempt at solving this problem. However, the features are not
easy to use, the documentation is incorrect, and it does not interact with the
rest of HLSL very well.

For example, `vk::ext_execution_mode` is a builtin function that
[needs to be called from the entry point](https://github.com/microsoft/DirectXShaderCompiler/blob/adc0363539ef423ca3f6e9d0211a665756b81080/tools/clang/test/CodeGenSPIRV/spv.intrinsicExecutionMode.hlsl#L13)
to which it applies. It would be much better as an attribute.

The inline type definitions are also very involved. You can see the
[sample](https://github.com/microsoft/DirectXShaderCompiler/blob/adc0363539ef423ca3f6e9d0211a665756b81080/tools/clang/test/CodeGenSPIRV/spv.intrinsicTypeInteger.hlsl)
to get an idea of how hard it is to define a type.

Finally, adding decorations to declare builtin inputs does not work in all
shader stages. There are examples that show how to
[declare a builtin variable](https://github.com/microsoft/DirectXShaderCompiler/blob/adc0363539ef423ca3f6e9d0211a665756b81080/tools/clang/test/CodeGenSPIRV/spv.intrinsicDecorate.hlsl)
in a pixel shader. However, it
[does not work in compute shaders](https://github.com/microsoft/DirectXShaderCompiler/issues/4217),
or any other shader stage where there cannot be arbitrary inputs. This makes
many extensions impossible to implement.

Common feedback on the feature is that it is
["a bit patchy, edge cases that don't work and that sort of thing"](https://github.com/microsoft/DirectXShaderCompiler/issues/5181#issuecomment-1537757720).

## Proposed solution

The existing inline SPIR-V was a step in the right direction, and worked for the
use cases that were considered at the time. Now that we have more experience, we
should be able to improve on the implementation, while keeping the style
similar.

Most SPIR-V extensions only introduce certain types of changes to the SPIR-V
spec:

1.  add a new execution mode,
1.  add a new instruction or extended instruction,
1.  add a new type,
1.  add a new decoration,
1.  add a new storage class, or
1.  add a new builtin.

Most extensions also define
[capabilities](https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html#Capability)
that are used to enable the new features, but the capabilities usually do
nothing on their own.

The proposed solution will add syntax to define each of these features, and give
them a meaningful name. They can be defined in a header file that users will be
able to use. They will not have to see the inline SPIR-V.

### Execution modes

The existing `vk::ext_execution_mode` is a builtin function. Using a function
allows the `vk::ext_capability` and `vk::ext_extension` attributes to be
attached to the execution mode. This is useful for adding execution modes that
was not yet present in SPIRV-Headers.

This design is awkward to use because the execution mode is only indirectly
connected to the entry point. This proposal adds a new attribute
`vk::spvexecutionmode(ExecutionMode)`, where `ExecutionMode` values are defined
by SPIRV-Headers. The required extensions and capabilities could be applied to
the entry point.

For example, suppose we wanted to implement the
[SPV_KHR_post_depth_coverage](http://htmlpreview.github.io/?https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/KHR/SPV_KHR_post_depth_coverage.html)
extension in a header file. The header file could be something like

```
// spv_khr_post_depth_coverage.h

// It would be nice to have this live in a namespace spv::khr::, but not possible with attributes.
static const uint32_t SampleMaskPostDepthCoverageCapabilityId = 4447;
static const uint32_t PostDepthCoverageExecutionModeId = 4446;
#define SPV_KHR_PostDepthCoverageExecutionMode vk::ext_extension("SPV_KHR_post_depth_coverage"), vk::ext_capability(SampleMaskPostDepthCoverageCapabilityId), vk::spvexecutionmode(PostDepthCoverageExecutionModeId)
```

Then the user could write:

```
#include "spv_khr_post_depth_coverage.h"

[[SPV_KHR_PostDepthCoverageExecutionMode]]
float4 PSMain(...) : SV_TARGET
{ ...
}
```

### Instructions and extended instructions

The existing `vk::ext_instruction` attribute is used to define a function as a
specific SPIR-V instruction. Suppose we wanted to implement the
[SPV_INTEL_subgroups](http://htmlpreview.github.io/?https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/INTEL/SPV_INTEL_subgroups.html)
extension in a header file. It contains 8 new instructions. Each one could be
defined in the header file as a function, and then the function can be called by
the users. For example,

```
template<typename T>
[[vk::ext_capability(5568)]]
[[vk::ext_extension("SPV_INTEL_subgroups")]]
[[vk::ext_instruction(/* OpSubgroupShuffleINTEL */ 5571)]]
T SubgroupShuffleINTEL(T data, uint32 invocationId);
```

Then the user calls `SubgroupShuffleINTEL()` to use this instruction.

### Types

Some extensions introduce new types. It is possible to define and use a SPIR-V
type with the existing inline SPIR-V, but it is awkward to use. You can see a
sample in the
[spv.intrinsictypeInteger.hlsl](https://github.com/microsoft/DirectXShaderCompiler/blob/128b6fd16b449df696a5c9f9405982903a4f88c4/tools/clang/test/CodeGenSPIRV/spv.intrinsicTypeInteger.hlsl)
test. Some of the difficulties are:

1.  The definition of the type is split in two. There is a definition of a
    function which has an arbitrary id and the id for the `OpType*` opcode for
    the type. The second part calls the function with values for all of the
    operands to the `OpType*` instruction in SPIR-V.
1.  The function call must be reachable from the entry point that will use the
    type even if it will be used to declare a global variable.
1.  The arbitrary id that is part of the type function is what is used to
    declare an object of that type. This means the same function cannot be used
    to declare two different types. Also, if there are multiple header files,
    they cannot use the same id for two different types. This can become hard to
    manage.

This proposal deprecates the old mechanism, and replaces it with two new types
`vk::SpirvOpaqueType<uint OpCode, typename... Operands>` and
`vk::SpirvType<uint OpCode, uint size, uint alignment, typename... Operands>`.
For `SpirvOpaqueType`, the template on the type contains the opcode and all of
the parameters necessary for that opcode. Each parameter must be one of three
kinds of values:

1.  An instantiation of the `vk::integral_constant<typename T, T v>` type
    template. This can be used to pass in any constant integral value. This
    value will be passed in to the type-declaration instruction as the id of an
    `OpConstant*` instruction.

    For example, `123` can be passed in by using
    `vk::integral_constant<uint, 123>`.
1.  An instantiation of the `vk::Literal<typename T>` type template. `T` should
    be an instantiation of `integral_constant`. The value of this constant will
    be passed in to the type-declaration instruction as an immediate literal
    value.

    For example, `123` can be passed in as an immediate literal by using
    `vk::Literal<vk::integral_constant<uint, 123> >`.

1.  Any type. The id of the lowered type will be passed in to the
    type-declaration instruction.

For example, [`OpTypeArray`](https://registry.khronos.org/SPIR-V/specs/unified1/
SPIRV.html#OpTypeArray) takes an id for the element type and an id for the
element length, so an array of 16 integers could be declared as

```
vk::SpirvOpaqueType</* OpTypeArray */ 28, int, vk::integral_constant<uint, 16> >
```

[`OpTypeVector`](https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html#
OpTypeVector) takes an id for the component type and a literal for the component
count, so a 4-integer vector could be declared as

```
vk::SpirvOpaqueType</* OpTypeVector */ 23, int, vk::Literal<vk::integral_constant<uint, 4> > >
```

The header file could create a partial instantiation with a more meaningful
name. For example, if you wanted to declare the types from the
[SPV_INTEL_device_side_avc_motion_estimation](http://htmlpreview.github.io/?https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/INTEL/SPV_INTEL_device_side_avc_motion_estimation.html)
you could have

```
[[vk::ext_capability(/* SubgroupAvcMotionEstimationINTEL */ 5696)]]
[[vk::ext_extension("SPV_INTEL_device_side_avc_motion_estimation")]]
typedef vk::SpirvOpaqueType</* OpTypeAvcMcePayloadINTEL */ 5704> AvcMcePayloadINTEL;

// Requires HLSL2021
template<typename ImageType>
using VmeImageINTEL
[[vk::ext_capability(/* SubgroupAvcMotionEstimationINTEL */ 5696)]]
[[vk::ext_extension("SPV_INTEL_device_side_avc_motion_estimation")]]
    = vk::SpirvOpaqueType</* OpTypeVmeImageINTEL */ 5700, Imagetype>;
```

Then the user could simply use the types:

```
VmeImageINTEL<Texture2D> image;
AvcMcePayloadINTEL payload;
```

If you want to use an inline SPIR-V type in a context where the size and
alignment matter, for example as an interface type or in a push constant, you
should use `SpirvType` instead of `SpirvOpaqueType`.

`SpirvType` additionally takes a `size` parameter, specifying the number of
bytes a single value of the type occupies, and an `alignment` parameter,
specifying a power of two that the value will be aligned to in memory. For
example, an unsigned 8-bit integer type could be declared as

```
typedef vk::SpirvType</* OpTypeInt */ 21,
    /* size */ 1,
    /* alignment */ 1,
    vk::Literal<vk::integral_constant<uint, 8> >,
    vk::Literal<vk::integral_constant<bool, false> >
> uint8_t;
```

Neither `SpirvType` nor `SpirvOpaqueType` may be used as the component type for
an HLSL vector or matrix.

### Decorations

The current inline SPIR-V includes the `vk::ext_decorate` attribute. This works
well as an attribute. A header file could handle the attribute in the same way
that it handles the execution mode attribute.

### Storage classes

The existing inline SPIR-V allows the developer to set the storage class for a
variable using the `vk::ext_storage_class` attribute. A storage class is similar
to an address space, which HLSL does not have yet. The attribute can be hidden
in a header file the same way that the execution mode attribute is.

### Builtin input

The existing inline SPIR-V has limited support for adding a builtin input. There
is a sample that shows how to
[add a builtin input to a pixel shader](https://github.com/microsoft/DirectXShaderCompiler/blob/128b6fd16b449df696a5c9f9405982903a4f88c4/tools/clang/test/CodeGenSPIRV/spv.intrinsicDecorate.hlsl).
This works for pixel shaders because the parameters to a pixel shader can have
arbitrary semantics. However, it is not possible to
[declare a SPIR-V specific builtin in a compute shader](https://github.com/microsoft/DirectXShaderCompiler/issues/4217).

A builtin input requires more than just a decoration on the variable. It must be
in the input storage class, and get added to the `OpEntryPoint` instruction.
With the existing inline SPIR-V, the variable can be decorated and assigned to
the correct storage class. However, it cannot always be correctly associated
with the entry point.

To support adding builtin inputs from source, this proposal adds a new
`vk::ext_builtin_input` attribute which takes a `builtInId` parameter and
applies to a variable declaration. This attribute must be applied to a static
const variable.

For example, the `gl_NumWorkGroups` builtin could be declared in a header file
like this:

```
[[vk::ext_builtin_input(/* NumWorkgroups */ 24)]]
static const uint3 gl_NumWorkGroups;
```

Then the compiler will be able to add a variable in the Input storage class,
with the BuiltIn decoration, with a type that is the same as the type of the
variable, and add it to the OpEntryPoint instruction when it is referenced by
the entry point’s call tree.

The developer can use the builtin input by simply using the variable.

### Builtin output

The existing inline SPIR-V has limited support for adding a builtin output. This
would have most of the same problems as declaring a builtin input.

To support adding builtin outputs from source, this proposal adds a new
`vk::ext_builtin_output` attribute which takes a `builtInId` parameter and
applies to a variable declaration. This attribute must be applied to a static
variable.

For example, the `gl_FragStencilRefARB` builtin could be declared in a header
file like this:

```
[[vk::ext_extension("SPV_EXT_shader_stencil_export")]]
[[vk::ext_builtin_output(/* FragStencilRefEXT */ 5014)]]
static int gl_FragStencilRefARB;
```

Then the compiler will be able to add a variable in the Output storage class,
with the BuiltIn decoration, with a type that is the same as the variable, and
add it to the OpEntryPoint for the entry points from which it is reachable.

The developer can set the builtin output by simply assigning to the variable.

A single variable declaration may not have both the `vk::ext_builtin_input` and
`vk::ext_builtin_output` attributes. A specific builtin ID may only be used for
either an input or an output, not both.

### Capability and extension instructions

Existing inline SPIR-V has attributes to indicate that a capability or extension
is needed by a particular part of the code. There are examples above. This
proposal allows these attribute to be applied to an entry point.

For types, the existing inline SPIR-V allows these attributes to be used on the
function that was used to define the type. However, that function is no longer
used when types are defined using `vk::SpirvType` and `vk::SpirvOpaqueType`. To
be able to add the capabilities and extensions that are required for a type, we
will allow these attributes to be used on variable declarations, field
declarations, and type aliases. Examples of these attributes with a typedef and
using statement are in the Types section.

The attributes can be added to fields and variable declarations for cases when a
type alias is not used.

For example,

```c++
class Payload {

  [[vk::ext_capability(/* SubgroupAvcMotionEstimationINTEL */ 5696)]]
  [[vk::ext_extension("SPV_INTEL_device_side_avc_motion_estimation")]]
  vk::SpirvOpaqueType</* OpTypeAvcMcePayloadINTEL */ 5704> payload;
};

[[vk::ext_capability(/* SubgroupAvcMotionEstimationINTEL */ 5696)]]
[[vk::ext_extension("SPV_INTEL_device_side_avc_motion_estimation")]]
vk::SpirvOpaqueType</* OpTypeAvcMcePayloadINTEL */ 5704> globalPayload;
```

In this case, the user of the header file, could use `Paylaod::payload` and
`globalPayload`. without worrying about the capabilities and extensions.

When a compiler encounters either attribute, it is expected to add the
capability and extension to the module. However, the compiler is allowed, but
not required, to remove capabilities and extensions that are not required.

## Detailed design

## Alternatives considered (Optional)

### Auto-generating builtin functions and attributes from [spirv.core.grammar.json](https://github.com/KhronosGroup/SPIRV-Headers/blob/8e2ad27488ed2f87c068c01a8f5e8979f7086405/include/spirv/unified1/spirv.core.grammar.json)

When we considered auto-generating, we noticed that not enough information is
available. For example, it is not possible to tell if a builtin should be an
input or output, and we cannot know its types. The other problem is that it will
require testing in DXC when new functions or attributes are added. The solution
proposed above leave a smaller testing surface in DXC, and places the testing
burden on the writer of the header file.

### Removing explicit references to capabilities and extensions

It is possible to get the list of required capabilities from
[spirv.core.grammar.json](https://github.com/KhronosGroup/SPIRV-Headers/blob/8e2ad27488ed2f87c068c01a8f5e8979f7086405/include/spirv/unified1/spirv.core.grammar.json).
It would generally be possible for the compiler to automatically add the
required capabilities an instruction is used. However, there are some cases
where the capability allows an instruction to take a new type of operand. These
are not part of the grammar, and would still require some way of explicitly
adding a capability and annotation.

If we can hide all of the cases that could be implicitly added in a header file,
then there is very little burden on users. This is why we chose to not have
implicit inclusion of the capabilities and extensions.

<!-- {% endraw %} -->
