<!-- {% raw %} -->

# Strict Availability Diagnostics

* Proposal: [INF-NNNN](INF-NNNN-availability-diagnostics.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 20YY (Clang-only)

## Introduction

Strict availability diagnostics introduces two new modes for diagnosing the use
of unavailable shader APIs. Unavailable shader APIs are APIs that are exposed in
HLSL code but are not available in the target shader stage or shader model
version.

## Motivation

Today the enforcement of API availability is the responsibility of bytecode
validators, runtimes and drivers operating on optimized shader code. Depending
contextually on where this enforcement occurs this can result in errors being
produced either late in compilation when mapping back to source locations is
difficult or at runtime when the runtime or driver rejects the compiled shader.

Strict availability diagnostics provides more actionable diagnostics for users
by both having detailed error messages and accurate message locations. It also
provides diagnostics early and allows implementations to generate meaningful
diagnostics even without generation of debug information.

> Note: The DXIL validator requires line table information to generate error
> locations which can be inaccurate. Disabling line table information can have a
> significant compile-time benefit.

## Proposed solution

### Availability Annotations

In Clang, most shader APIs have header declarations that live in the default
included `hlsl_intrinsics.h`. All shader API declarations have Clang
availability attributes denoting version information for when the APIs are
introduced, deprecated, and removed. This version annotation can be per-stage or
for all stages. The availability annotations will need to exist on declarations
regardless of this proposal, as they provide information to AST-based tooling
such as IDE workflows.

As an example of the annotations in action take the following declaration from
`hlsl_intrinsics.h`:

```c++
__attribute__((availability(shadermodel, introduced = 6.0)))
__attribute__((clang_builtin_alias(__builtin_hlsl_wave_active_count_bits)))
uint WaveActiveCountBits(bool Bit);
```

> Note: the actual header uses macros to condense the attribute descriptions.
> The example expands the macros for explicitness.

The example above declares the `WaveActiveCountBits` function to require shader
model 6.0+. This AST annotation allows clangd to communicate to users the
availability information to language server protocol clients. This can drive
more informed auto-complete, refactoring, and in-editor diagnostics.

### Diagnostic Modes

This proposal introduces three new modes for diagnosing API availability:
default, relaxed, and strict.

### Default Diagnostic Mode

The default diagnostic mode performs an AST traversal after the translation unit
has been fully parsed, and requires construction of a call graph. In the relaxed
mode, an AST visitor will traverse to all `CallExpr` nodes that are reachable
from exported functions (either library exports or entry functions). If the
callee of a `CallExpr` has availability annotations that signify that the API is
unavailable for the target shader model and stage the compiler emits an
_error_.

Clang encodes the target shader model version in the target triple, and the
shader stage in the `HLSLShaderAttr` which is implicitly or explicitly applied
to the entry function.

The default mode does not issue diagnostics for `CallExpr` nodes that are inside
functions which are not reachable from exported functions.

### Relaxed Diagnostic Mode

The implementation of the relaxed diagnostic mode matches the default mode,
except that when a `CallExpr` references an unavailable API, the compiler emits
a _warning_.

The relaxed mode does not issue diagnostics for `CallExpr` nodes that are inside
functions which are not reachable from exported functions. A user enables
relaxed mode by passing `-Wno-error-hlsl-availability`.

### Strict Diagnostic Mode

The strict diagnostic mode strives to aggressively issue diagnostics. For
non-library shaders, during parsing any callee of a `CallExpr` that has
availability annotation that marks it as unavailable for the target shader model
and stage will produce an _error_.

For library shaders, during parsing any callee of a `CallExpr` that has
availability annotation that marks it as unavailable for the target shader model
version will produce an _error_. After parsing the translation unit, an AST
visitor will traverse to all `CallExpr` nodes that are reachable from annotated
shader entry functions. If the callee of a `CallExpr` has availability
annotations that signify that the API is unavailable for the target shader stage
the compiler emits an _error_.

A user enables strict mode by passing `-fhlsl-strict-diagnostics`.

### Comparison Against Existing Behavior

Today DXC allows the use of APIs in shaders regardless of the specified target
profile. The responsibility for enforcing API availability falls to the bytecode
validator. This results in compilation passing but the validator failing. For
example take the following code:

> [Godbolt Link](https://godbolt.org/z/v1sjEEETW)
```c++
Texture2D texture : register(t0);
SamplerState samplerState : register(s0);

FeedbackTexture2D<SAMPLER_FEEDBACK_MIN_MIP> map : register(u0);

[numthreads(4, 4, 1)] 
void main(uint3 threadId : SV_DispatchThreadId) {
  float2 uv = threadId.xy;
  uv /= 256;

  map.WriteSamplerFeedbackLevel(texture, samplerState, uv, threadId.x % 8);
}
```

Compiled with the `-T cs_6_4` flag this produces the validation error:
```
<>:11:3: error: Opcode WriteSamplerFeedbackLevel not valid in shader model cs_6_4.
note: at 'call void @dx.op.writeSamplerFeedbackLevel(i32 176, %dx.types.Handle %1, %dx.types.Handle %2, %dx.types.Handle %3, float %8, float %9, float undef, float undef, float %11)' in block '#0' of function 'main'.
Validation failed.
```

This error displays the LLVM IR text for the error site. In a trivial example
like the one above finding the error is easy. In a complex shader that could be
thousands of lines long this is unmanageable.

With this proposal under the _relaxed_ mode, clang will emit the following
warning:

```
<>:11:6: warning: 'WriteSamplerFeedbackLevel' is available beginning with Shader Model 6.6
   11 |   map.WriteSamplerFeedbackLevel(texture, samplerState, uv, threadId.x % 8);
      |       ^~~~~~~~~~~~~~~~~~~~~~~~~
```

With this proposal under the _default_ or _strict_ mode, clang will emit the
following error:

```
<>:11:6: error: 'WriteSamplerFeedbackLevel' is available beginning with Shader Model 6.6
   11 |   map.WriteSamplerFeedbackLevel(texture, samplerState, uv, threadId.x % 8);
      |       ^~~~~~~~~~~~~~~~~~~~~~~~~
```

In all three cases above the DXIL validator will also emit the same diagnostic
as it does today.

To illustrate the difference between _default_ and _strict_ take the following
example:

```c++
Texture2D texture : register(t0);
SamplerState samplerState : register(s0);

FeedbackTexture2D<SAMPLER_FEEDBACK_MIN_MIP> map : register(u0);

void fn(uint3 threadId) {
  float2 uv = threadId.xy;
  uv /= 256;
  map.WriteSamplerFeedbackLevel(texture, samplerState, uv, threadId.x % 8);
}

[numthreads(4, 4, 1)] 
void main(uint3 threadId : SV_DispatchThreadId) { }
```

In this example the call of the unavailable API is in an unused function. In
both the _relaxed_ and _default_ diagnostic modes, clang will emit no
diagnostics. In the _strict_ mode, clang emits the following diagnostic:

```
<>:9:6: error: 'WriteSamplerFeedbackLevel' is available beginning with Shader Model 6.6
   9 |   map.WriteSamplerFeedbackLevel(texture, samplerState, uv, threadId.x % 8);
     |       ^~~~~~~~~~~~~~~~~~~~~~~~~
```

In this case the DXIL validator will emit no diagnostic since the call to the
unavailable API is not present in the final output.

Because bytecode validation occurs late (after optimization), some more complex
cases can occur. For example, users have reported situations that produce
validation errors when building un-optimized shaders for debugging proposes that
do not appear with optimized shaders.

One presentation of such a case is if a call to an unavailable API occurs under
control flow. If the compiler optimizes away the control flow it may remove the
API call. In these cases shaders that compile and verify successfully with DXC
may produce warnings or errors with Clang.

<!-- {% endraw %} -->
