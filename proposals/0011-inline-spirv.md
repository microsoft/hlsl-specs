<!-- {% raw %} -->

# Inline SPIR-V

## Instructions

> This template wraps at 80-columns. You don't need to match that wrapping, but
> having some consistent column wrapping makes it easier to view diffs on
> GitHub's review UI. Please wrap your lines to make it easier to review.

> When filling out the template below for a new feature proposal, please do the
> following first:

> 1. exclude the "Planned Version", "PRs" and "Issues" from the header.
> 2. Do not spend time writing the "Detailed design" until the feature has been
>    merged in the "Under Consideration" phase.
> 3. Delete this Instructions section including the line below.

---

* Proposal: [0011](0011-inline-spirv.md)
* Author(s): [Steven Perron](https://github.com/s-perron)
* Sponsor: TBD
* Status: **Under Consideration**

*During the review process, add the following fields as needed:*

* Planned Version: 20YY
* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues:
  [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/issues/NNNN)

## Introduction

Define a set of Vulkan specific builtin functions, types, and attributes that
will allow vendors to implement their extensions. The vendors should be able
to write a self-contained header file that users can use without
knowing about inline SPIR-V.

## Motivation

In Vulkan, there is a culture of allowing a vendor to define extensions that are
only interesting to them. From the perspective of a driver this is acceptable
because company B does not have to support the extension put out by vendor B, if
they do not want to. It does not create extra work for anyone else.

From a compiler perspective, this is no longer true. If a vendor wants DXC, 
or any other SPIR-V generator, to generate the SPIR-V for their extension it 
generally requires a code change to the compiler that must be maintained.

If those extensions could be defined as a header file that DXC consumes, then
a vendor would not have to modify the compiler other than possibly updating
the submodules.

The existing [inline SPIR-V](https://github.com/microsoft/DirectXShaderCompiler/wiki/GL_EXT_spirv_intrinsics-for-SPIR-V-code-gen)
was the first attempt at solving this problem. However, the features are 
not easy to use, the documentation is incorrect, and is does not interact with the rest of HLSL very well.

For example, `vk::ext_execution_mode` is a builtin function that [needs to be
called from the entry point](https://github.com/microsoft/DirectXShaderCompiler/blob/adc0363539ef423ca3f6e9d0211a665756b81080/tools/clang/test/CodeGenSPIRV/spv.intrinsicExecutionMode.hlsl#L13) to which it applies. It would be much better as an attribute.

The call to the execution mode builtin requires the enabling extension and
capabilities to be added as attributes on the call. This seems unnecessary 
since that information should be available to the compiler through the 
spirv-headers JSON. This would be needed only if the spirv-header have not
been updated to include the extension. We will need to decide if we want to
support that workflow.

The inline type definitions are also very involved. You can see the [sample](https://github.com/microsoft/DirectXShaderCompiler/blob/adc0363539ef423ca3f6e9d0211a665756b81080/tools/clang/test/CodeGenSPIRV/spv.intrinsicTypeInteger.hlsl) to get an idea of how hard it is to define a type.

Finally, adding decorations to declare builtin inputs does not work in all shader stages. There are examples that show how to [declare a builtin variable](https://github.com/microsoft/DirectXShaderCompiler/blob/adc0363539ef423ca3f6e9d0211a665756b81080/tools/clang/test/CodeGenSPIRV/spv.intrinsicDecorate.hlsl) in a pixel shader. However, it [does not work in compute shaders](https://github.com/microsoft/DirectXShaderCompiler/issues/4217), or any other shader stage where there cannot be arbitrary inputs. This makes it impossible to implement many extensions.

Common feedback on the feature is that is is ["a bit patchy, edge cases that don't work and that sort of thing"](https://github.com/microsoft/DirectXShaderCompiler/issues/5181#issuecomment-1537757720).

## Proposed solution

The existing inline SPIR-V was a step in the right direction, and worked for the use cases that were considered at the time. Now that we have more experience, we should be able to improve on the implementation, while keeping the style similar.

Most SPIR-V extension so only certain types of changes to the SPIR-V sped:

1. add a new [execution mode](https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html#Execution_Mode),
1. add a new instruction or extended instruction,
1. add a new type,
1. add a new decoration,
1. add a new storage class, or
1. add a new builtin input.

Most extension also define [capabilities](https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html#Capability) that are used to enable the new features, but the capabilities do nothing on their own.

The proposed solution will add syntax to define each of these features aliased to a meaningful name, so that they can be defined in a header file. Then users will be able to use the header file, and use the feature by using the name. They will not have to see consider the inline SPIR-V. The proposed solution will also expect that the SPIR-V referenced is defined in the version of spirv-headers that was used to build DXC.

### Execution modes

The existing `vk::ext_execution_mode` is a builtin function. I'm guessing it was defined as a builtin function because the original designers want to be able to add an execution mode that was not yet defined in spirv-headers. Since we are not considering that workflow anymore, I propose that we define a new attribute `vk::spvexecutionmode(ExecutionMode)`.

Then suppose we wanted to implement the [SPV_KHR_post_depth_coverage](http://htmlpreview.github.io/?https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/KHR/SPV_KHR_post_depth_coverage.html) extension in a header file.

The header file could be something like 

```
// spv_khr_post_depth_coverage.h

namespace spv {
  namespace khr {
    const uint32_t PostDepthCoverageExecutionMode = 4446;
  }
}
```

The a user could use the extension:

```
#include "spv_khr_post_depth_coverage.h"

[[vk::spvexecutionmode(spv::khr::PostDepthCoverageExecutionMode)]]
float4 PSMain(...) : SV_TARGET
{ ...
}
```

Another way of using it would be:

```
// spv_khr_post_depth_coverage.h

#define PostDepthCoverageExecutionMode vk::spvexecutionmode(spv::khr::PostDepthCoverageExecutionMode)
```

Then the user could write:

```
#include "spv_khr_post_depth_coverage.h"

[[PostDepthCoverageExecutionMode]]
float4 PSMain(...) : SV_TARGET
{ ...
}
```

### Instructions and extended instructions
### Types
### Decorations
### Storage classes
### Builtin inputs
### Capability and extension instructions

## Detailed design

_The detailed design is not required until the feature is under review._

This section should grow into a feature specification that will live in the
specifications directory once complete. Each feature will need different levels
of detail here, but some common things to think through are:

* How is this feature represented in the grammar?
* How does it work interact other HLSL features (semantics, buffers, etc)?
* How does this interact with C++ features that aren't already in HLSL?
* Does this have implications for existing HLSL source code compatibility?
* Does this change require DXIL changes?
* Can it be CodeGen'd to SPIR-V?

## Alternatives considered (Optional)

If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing.

## Acknowledgments (Optional)

Take a moment to acknowledge the contributions of people other than the author
and sponsor.

<!-- {% endraw %} -->
