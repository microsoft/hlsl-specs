---
title: 0039 - Debugging Intrinsics
params:
    authors:
    - llvm-beanz: Chris Bieneman
    - joecitizen: Jack Elliott
    sponsors:
    - llvm-beanz: Chris Bieneman
    status: Under Review
---


* Issue(s): https://github.com/microsoft/hlsl-specs/issues/33

## Introduction

This proposal specifies two new HLSL debugging intrinsics:

1. **`DebugBreak()`**: Triggers a breakpoint when debugging is enabled
   allowing developers to pause execution and inspect shader state.
2. **`dx::IsDebuggingEnabled()`**: Returns whether debugging is enabled for the
   currently executing thread, enabling conditional debug-only code paths.

`DebugBreak()` will lower to new DXIL operations for DirectX and to appropriate
SPIR-V instructions for Vulkan targets. `dx::IsDebuggingEnabled()` is a DirectX
extension and has no Vulkan/SPIR-V equivalent.

## Motivation

As shaders have become increasingly complex the need for robust debugging tools
has grown. Current feature sets of shader debuggers don't adequately address all
needs. One challenge amplified by the massively parallel nature of GPU programs
is conditional breakpoints. A developer may have a shader program that executes
millions of times without issue, but in one instance produces a bad result.
Conditional breakpoints can be a powerful tool for shader authors to narrow down
and identify these complex rare-occurring problems.

Additionally, shader authors need a way to conditionally enable expensive debug
checks only when debugging is enabled in the runtime, avoiding runtime overhead
in production scenarios.

This proposal introduces two intrinsics that together provide a debugging
toolkit for shader development.

## Proposed solution

This proposal introduces two new HLSL intrinsics for debugging shader code.

### Intrinsics

```hlsl
void DebugBreak();        // Trigger a breakpoint if debugging is enabled.
bool dx::IsDebuggingEnabled(); // Query if debugging is enabled (DirectX only).
```

### Example Usage

```hlsl
[numthreads(8,1,1)]
void main(uint GI : SV_GroupIndex) {
  // Conditional expensive debug checks
  if (dx::IsDebuggingEnabled()) {
    // Expensive validation only when debugging
    ValidateComplexInvariants();
  }

  // Manual breakpoint for debugging specific conditions
  if (someRareCondition) {
    DebugBreak();
  }
}
```

This aligns with C/C++ conventions that our users are already familiar with.

## Detailed Design

### HLSL Surface

Two new intrinsic functions are added:

#### `DebugBreak()`

```hlsl
void DebugBreak();
```

Triggers a breakpoint if debugging is enabled in the runtime. If debugging is
not enabled or the runtime does not support this operation, it is treated as a
no-op. Execution continues after the breakpoint.

#### `dx::IsDebuggingEnabled()`

```hlsl
bool dx::IsDebuggingEnabled();
```

Returns `true` if debugging is enabled on the current thread, `false` otherwise.
This allows shader authors to conditionally execute expensive debug validation
code only when debugging is enabled:

```hlsl
if (dx::IsDebuggingEnabled()) {
    // Expensive bounds checking, validation, etc.
    for (uint i = 0; i < arraySize; ++i) {
        if (data[i] < 0.0f || data[i] > 1.0f) {
            DebugBreak();
        }
    }
}
```

The value returned is uniform across all threads in a dispatch/draw and remains
constant for the duration of shader execution.

### DXIL Lowering

This change introduces two new DXIL operations:

#### `dx.op.debugBreak`

```llvm
declare void @dx.op.debugBreak(
  immarg i32             ; opcode
)
```

Triggers a debugger breakpoint. If debugging is not enabled, this is a no-op.

#### `dx.op.IsDebuggingEnabled`

```llvm
declare i1 @dx.op.IsDebuggingEnabled(
  immarg i32             ; opcode
) readonly
```

Returns `true` (1) if debugging is enabled, `false` (0) otherwise. Marked
`readonly` as it only queries state.

### Shader Model Requirements

These instructions will only be valid in Shader Model 6.10 or later.

Because `DebugBreak()` can be treated as a no-op when no debugger is present,
it is a required supported feature and does not require a capability bit.

### Runtime Behavior for DebugBreak

It is valid for the runtime to change the behavior of debug break on a
per-pipeline basis.

Behavioral changes may include:

- Breaking regardless of a debugging enabled
- Disabling debug break instructions entirely

It is expected that the driver compiler will alter behavior during lowering
based on information provided by the runtime at pipeline creation.

### SPIR-V Lowering

#### DebugBreak

Uses the existing `NonSemantic.DebugBreak` instruction:

```
%1 = OpExtInstImport "NonSemantic.DebugBreak"
%2 = OpExtInst %void %1 DebugBreak
```

While this instruction is not widely supported by Vulkan debuggers, it is
supported by NVIDIA's NSight and can be safely ignored by Vulkan runtimes.

No SPIR-V lowering is defined for `dx::IsDebuggingEnabled()`.

## Testing

### Compiler Testing

- Verify correct DXIL generation for both intrinsics
- Verify correct SPIR-V generation for `DebugBreak()` where applicable

### Validation Testing

- Confirm validation accepts the new operations in SM 6.10+
- Confirm validation rejects operations in earlier shader models

### Execution Testing

- Test `DebugBreak()` triggers breakpoint when debugging is enabled
- Test `DebugBreak()` is no-op when debugging is not enabled
- Test `dx::IsDebuggingEnabled()` returns correct value based on runtime state
