---
title: 0039 - Debugging Intrinsics
params:
    authors:
    - llvm-beanz: Chris Bieneman
    - joecitizen: Jack Elliott
    sponsors:
    - llvm-beanz: Chris Bieneman
    status: Under Consideration
---

 
* Issue(s): https://github.com/microsoft/hlsl-specs/issues/33

## Introduction

This proposal specifies three new HLSL debugging intrinsics:

1. **`DebugBreak()`**: Triggers a breakpoint when a debugger is attached,
   allowing developers to pause execution and inspect shader state.
2. **`Abort()`**: Terminates shader execution abnormally, signaling an
   unrecoverable error condition (similar to C's `abort()`).
3. **`IsDebuggerPresent()`**: Returns whether a graphics debugger is currently
   attached to the process, enabling conditional debug-only code paths.

These intrinsics will lower to new DXIL operations for DirectX and to
appropriate SPIR-V instructions for Vulkan targets.

## Motivation

As shaders have become increasingly complex the need for robust debugging tools
has grown. Current feature sets of shader debuggers don't adequately address all
needs. One challenge amplified by the massively parallel nature of GPU programs
is conditional breakpoints. A developer may have a shader program that executes
millions of times without issue, but in one instance produces a bad result.
Conditional breakpoints can be a powerful tool for shader authors to narrow down
and identify these complex rare-occurring problems.

Additionally, shader authors need:
- A way to terminate execution when an unrecoverable error is detected, matching
  the behavior of `abort()` in C/C++ for implementing proper `assert()` semantics.
- A way to conditionally enable expensive debug checks only when a debugger is
  attached, avoiding runtime overhead in production scenarios.

This proposal introduces three intrinsics that together provide a complete
debugging toolkit for shader development.

## Proposed solution

This proposal introduces three new HLSL intrinsics and a new header `assert.h`
which will define the `assert()` macro in a C-compatible interface.

### Intrinsics

```hlsl
void DebugBreak();        // Trigger a breakpoint if debugger attached
void Abort();             // Terminate execution abnormally  
bool IsDebuggerPresent(); // Query if a debugger is attached
```

### assert.h

The `assert.h` header will provide the following definitions:

```c
#if NDEBUG
#define assert(cond) do { } while(false)
#else
#define assert(cond) do { if (!(cond)) Abort(); } while(false)
#endif
```

Note: The `assert()` macro uses `Abort()` rather than `DebugBreak()` to match
standard C/C++ behavior where a failed assertion terminates the program. Users
who prefer to break into a debugger on assertion failure can define their own
macro using `DebugBreak()`.

### Example Usage

```hlsl
#include <assert.h>

[numthreads(8,1,1)]
void main(uint GI : SV_GroupIndex) {
    // Standard assertion - aborts if condition fails
    assert(GI < 8);
    
    // Conditional expensive debug checks
    if (IsDebuggerPresent()) {
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

Three new intrinsic functions are added:

#### `DebugBreak()`

```hlsl
void DebugBreak();
```

Triggers a breakpoint if a graphics debugger is attached. If no debugger is
attached or the runtime does not support this operation, it is treated as a
no-op. Execution continues after the breakpoint.

#### `Abort()`

```hlsl
void Abort();
```

Terminates shader execution abnormally. This function does not return. The
implementation signals abnormal termination to the runtime, which may:
- Terminate the dispatch/draw
- Signal a device removed/lost condition
- Log diagnostic information
- Trigger a debugger break before termination (implementation-defined)

The exact behavior is implementation-defined, but the shader must not continue
execution past this point. This matches the semantics of C's `abort()` function.

#### `IsDebuggerPresent()`

```hlsl
bool IsDebuggerPresent();
```

Returns `true` if a graphics debugger is currently attached to the process,
`false` otherwise. This allows shader authors to conditionally execute expensive
debug validation code only when a debugger is present:

```hlsl
if (IsDebuggerPresent()) {
    // Expensive bounds checking, validation, etc.
    for (uint i = 0; i < arraySize; ++i) {
        assert(data[i] >= 0.0f && data[i] <= 1.0f);
    }
}
```

The value returned is uniform across all threads in a dispatch/draw and remains
constant for the duration of shader execution.

#### Enabling Semi-Optimized Development Builds

`IsDebuggerPresent()` is particularly valuable for studios with large shader
compilation costs. It enables a "semi-optimized" build strategy where:

1. **Single Shader Variant**: Debug validation code is compiled into the shader
   but guarded by `IsDebuggerPresent()`. This eliminates the need to maintain
   separate debug and release shader variants, significantly reducing shader
   cook times.

2. **On-Demand Debug Activation**: The expensive debug code paths exist in the
   compiled shader but remain dormant until a developer attaches a graphics
   debugger to investigate an issue. This provides the best of both worlds:
   production-like performance during normal development, with instant access
   to debug validation when needed.

3. **Reduced Iteration Time**: Developers don't need to recompile shaders when
   switching between "debug" and "release" modes. Simply attaching or detaching
   a debugger toggles the debug code paths at runtime.

**Example: Comprehensive Debug Validation**

```hlsl
void ProcessLighting(uint2 pixelCoord, LightData lights[], uint lightCount) {
    float3 result = 0;
    
    if (IsDebuggerPresent()) {
        // Expensive validation only runs when actively debugging
        ValidateLightDataIntegrity(lights, lightCount);
        assert(all(pixelCoord < screenDimensions));
        
        // Debug visualization overlays
        if (showDebugHeatmap) {
            DebugVisualizeLightComplexity(pixelCoord, lightCount);
        }
    }
    
    // Normal lighting computation (always runs)
    for (uint i = 0; i < lightCount; ++i) {
        result += ComputeLightContribution(lights[i], pixelCoord);
    }
    
    OutputColor(pixelCoord, result);
}
```

**Cost-Benefit for Large Studios**

For studios with thousands of shader permutations, shader cook times can extend
to hours or even days. The traditional approach of maintaining separate debug
and release builds effectively doubles this cost. 

### DXIL Lowering

This change introduces three new DXIL operations:

#### `dx.op.debugBreak`

```llvm
declare void @dx.op.debugBreak(
  immarg i32             ; opcode
) convergent
```

Triggers a debugger breakpoint. Must be treated as `convergent` to prevent code
motion. Should not be marked `readonly` or `readnone`. If no debugger is
attached, this is a no-op.

#### `dx.op.abort`

```llvm
declare void @dx.op.abort(
  immarg i32             ; opcode
) noreturn convergent
```

Terminates shader execution abnormally. Marked `noreturn` as control flow does
not continue past this point. Must be treated as `convergent` to prevent code
motion. The implementation must signal abnormal termination to the runtime.

#### `dx.op.isDebuggerPresent`

```llvm
declare i1 @dx.op.isDebuggerPresent(
  immarg i32             ; opcode
) readonly
```

Returns `true` (1) if a debugger is attached, `false` (0) otherwise. Marked
`readonly` as it only queries state. 

### Convergence Requirements

`debugBreak` and `abort` operations must be treated as `convergent` to prevent
code motion that could change their observable behavior:
- `debugBreak`: Must break at the exact location specified by the programmer
- `abort`: Must terminate at the exact location specified

These operations should not be hoisted, sunk, or duplicated by optimizers.

### Shader Model Requirements

These instructions will only be valid in Shader Model 6.10 or later.

Because `DebugBreak()` and `IsDebuggerPresent()` can be treated as no-ops when
no debugger is present, they are required supported features and do not require
capability bits.

`Abort()` requires runtime support for abnormal termination signaling, but as
all conforming implementations must handle this (even if by treating it as a
no-op in release drivers), it also does not require a capability bit.

### D3D12 Runtime Behavior for Abort

#### Default Behavior: Abort as No-Op

By default, the D3D12 runtime treats `Abort()` instructions as no-ops. When
abort is disabled:

1. The `dx.op.abort` operation has no effect at runtime
2. The driver's backend compiler may optimize away:
   - The abort instruction itself
   - Any conditional branches leading to the abort
   - Any instructions computing values used solely to determine whether to abort
   
   provided these instructions have no visible side effects.

This default behavior ensures that:
- Shaders containing assertions have zero runtime overhead in production
- The same shader binary can be used in both debug and release scenarios
- Developers can ship shaders with assertions without performance penalty

#### Enabling Abort via PSO Flag

A new Pipeline State Object (PSO) creation flag is introduced to enable abort
behavior for specific pipelines:

```cpp
typedef enum D3D12_PIPELINE_STATE_FLAGS {
    D3D12_PIPELINE_STATE_FLAG_NONE = 0,
    D3D12_PIPELINE_STATE_FLAG_TOOL_DEBUG = 0x1,
    // ... existing flags ...
    D3D12_PIPELINE_STATE_FLAG_ENABLE_SHADER_ABORT = 0x..., // New flag
} D3D12_PIPELINE_STATE_FLAGS;
```

When `D3D12_PIPELINE_STATE_FLAG_ENABLE_SHADER_ABORT` is set:
- `Abort()` instructions are active and will terminate shader execution
- The backend compiler must preserve abort instructions and their control flow
- The runtime will signal abnormal termination when an abort is triggered

#### Use Cases for Selective Abort Enabling

This design enables several important scenarios:

1. **Retail Debugging**: Developers can selectively enable assertions for
   specific users experiencing rare bugs without requiring a separate debug
   build:
   ```cpp
   D3D12_GRAPHICS_PIPELINE_STATE_DESC psoDesc = {};
   // ... configure PSO ...
   if (userOptedIntoDebugMode || detectingRareBug) {
       psoDesc.Flags |= D3D12_PIPELINE_STATE_FLAG_ENABLE_SHADER_ABORT;
   }
   ```

2. **A/B Testing**: Enable assertions for a subset of users to detect issues
   in production without impacting all users.

3. **Development Builds**: Always enable abort for internal testing while
   keeping it disabled for public releases.

4. **Per-Pipeline Control**: Enable assertions only for specific shaders that
   are suspected of containing bugs, minimizing performance impact.

#### Backend Compiler Optimization

When abort is disabled (the default), the backend compiler is permitted to
perform dead code elimination on abort-related code paths. Specifically:

```hlsl
// Original shader code
if (someCondition) {
    // expensive computation only for the abort path
    uint result = ExpensiveValidation();
    if (result != EXPECTED_VALUE) {
        Abort();
    }
}
```

When compiled with abort disabled, the compiler may optimize this to:

```hlsl
// Optimized: entire block removed if it has no side effects
// (empty)
```

The compiler must preserve any code with visible side effects (memory writes,
atomics, etc.) even if they lead to an abort. Only pure computations and
control flow leading exclusively to abort may be eliminated.

#### Runtime Signaling

When abort is enabled and triggered, the runtime behavior is:
- The current dispatch/draw is terminated
- A debug message is logged (if debug layer is enabled)
- The application may query for abort occurrences via debug interfaces
- If a debugger is attached, the shader will be halted for inspection but cannot
be continued.
- Device removal is triggered

### SPIR-V Lowering

#### DebugBreak

Uses the existing `NonSemantic.DebugBreak` instruction:

```
%1 = OpExtInstImport "NonSemantic.DebugBreak"
%2 = OpExtInst %void %1 DebugBreak
```

While this instruction is not widely supported by Vulkan debuggers, it is
supported by NVIDIA's NSight and can be safely ignored by Vulkan runtimes.

#### Abort

Maps to `OpTerminateInvocation` (SPIR-V 1.6+) or `OpKill` for fragment shaders.
For compute shaders, this may require vendor-specific extensions or be lowered
to an infinite loop with side effects that prevents further execution:

```
; SPIR-V 1.6+ for fragment shaders
OpTerminateInvocation

; For compute shaders, implementation-defined behavior
; May use vendor extensions or controlled termination patterns
```

#### IsDebuggerPresent

There is no direct SPIR-V equivalent. Implementations may:
- Lower to a specialization constant that can be set by the debugger
- Use a vendor-specific extension
- Return a conservative value (e.g., always `false` in release, always `true`
  in debug builds)

```
; Example using specialization constant
%debug_present = OpSpecConstant %bool false
```

## Testing

### Compiler Testing

- Verify correct DXIL generation for all three intrinsics
- Verify correct SPIR-V generation where applicable
- Test `assert.h` macro expansion with and without `NDEBUG` defined
- Verify `Abort()` is marked `noreturn` and affects control flow analysis

### Validation Testing

- Confirm validation accepts the new operations in SM 6.10+
- Confirm validation rejects operations in earlier shader models
- Verify convergence requirements are properly validated

### Execution Testing

- Test `DebugBreak()` triggers breakpoint when debugger attached
- Test `DebugBreak()` is no-op when no debugger present
- Test `Abort()` terminates execution and signals to runtime
- Test `IsDebuggerPresent()` returns correct value based on debugger state
- Test `assert()` macro behavior with passing and failing conditions

## Open Questions

* Consider introducing the `convergent` attribute to DXIL.
  * This should be "cheap" and would potentially address pre-existing bugs.
  * This would preserve the requirement that these operations not be moved
    during optimization in the final DXIL.
  
* For SPIR-V targets without native `Abort()` support, what is the fallback
  behavior? Infinite loop? Discard? Implementation-defined?
