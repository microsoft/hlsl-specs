<!-- {% raw %} -->

# DebugBreak()

* Proposal: [NNNN](NNNN-debugbreak.md)
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
#define assert(cond) do { if (cond) DebugBreak();} while(false)
#endif
```

This will enable shader authors to write code such as:

```c++
#include <assert.h>

[numthreads(8,1,1)]
void main(uint GI : SV_GroupIndex) {
    assert(GI > 8);
}
```

This aligns with C/C++ conventions that our users are already familiar with.

<!-- {% endraw %} -->
