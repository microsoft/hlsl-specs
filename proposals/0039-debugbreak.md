<!-- {% raw %} -->

# DebugBreak()

* Proposal: [0039](0039-debugbreak.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Issue(s): https://github.com/microsoft/hlsl-specs/issues/33

## Introduction

This proposal specifies a new HLSL function `DebugBreak()` which will lower to a
new DXIL operation described in this spec for DirectX and to the SPIRV
[NonSemantic.DebugBreak](https://github.khronos.org/SPIRV-Registry/nonsemantic/NonSemantic.DebugBreak.html)
for SPIRV targets.

## Motivation

As shaders have become increasingly complex the need for robust debugging tools
has grown. Current feature sets of shader debuggers don't adequately address all
needs. One challenge amplified by the massively parallel nature of GPU programs
is conditional breakpoints. A developer may have a shader program that executes
millions of times without issue, but in one instance produces a bad result.
Conditional breakpoints can be a powerful tool for shader authors to narrow down
and identify these complex rare-occurring problems.

This proposal introduces a `DebugBreak()` intrinsic, which can be combined with
an `assert()` macro implementation to provide support for conditional
breakpoints in shader code.

## Proposed solution

This proposal introduces a new HLSL intrinsic `DebugBreak()`, a new header
`assert.h` which will define the `assert()` macro in a C-compatible interface.

assert.h will provide the following definitions
```c
#if NDEBUG
#define assert(cond) do { } while(false)
#else
#define assert(cond) do { if (!cond) DebugBreak();} while(false)
#endif
```

This will enable shader authors to write code such as:

```c++
#include <assert.h>

[numthreads(8,1,1)]
void main(uint GI : SV_GroupIndex) {
    assert(GI < 8);
}
```

This aligns with C/C++ conventions that our users are already familiar with.

## Detailed Design

This proposal introduces a new HLSL `DebugBreak` intrinsic which has a
runtime-defined behavior to facilitate shader debugging workflows. If the
runtime does not support or is not configured to enable support for the
corresponding DXIL instruction must be treated as a no-op by the driver.

### HLSL Surface

A new `DebugBreak` function is added with the signature:

```
void DebugBreak();
```

A new header `assert.h` is added and included with the compiler packaging which
implements the `assert` macro:

```c
#if NDEBUG
#define assert(cond) do { } while(false)
#else
#define assert(cond) do { if (!cond) DebugBreak();} while(false)
#endif
```

### DXIL Lowering

This change introduces a new DXIL operation:


``` llvm
declare void @dx.op.debugBreak(
  immarg i32             ; opcode
)
```

This DXIL operation must be treated as `convergent` even though it is not to
prevent code motion.

This instruction will only be valid in a new shader model.

Because it is valid to treat this operation as a no-op, it is a required
supported feature and does not require a capabilities bit.

### SPIRV Lowering

This change will utilize the existing `NonSemantic.DebugBreak` instruction.
While this instruction is not widely supported by Vulkan debuggers, it is
supported by NVIDIA's NSight and can be safely ignored by Vulkan runtimes.

The SPIRV usage will utilize the following instructions:

```
%1 = OpExtInstImport "NonSemantic.DebugBreak"
%2 = OpExtInst %void %1 DebugBreak
```

## Open Questions

* Consider introducing the `convergent` attribute to DXIL.
  * This should be "cheap" and would potentially address pre-existing bugs.
  * This would preserve the requirement that this operation not be moved during
    optimization in the final DXIL.


<!-- {% endraw %} -->
