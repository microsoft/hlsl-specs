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

This proposal specifies two new HLSL debugging intrinsics:

1. **`DebugBreak()`**: Triggers a breakpoint when a debugger is attached,
   allowing developers to pause execution and inspect shader state.
2. **`IsDebuggerPresent()`**: Returns whether a graphics debugger is currently
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

Additionally, shader authors need a way to conditionally enable expensive debug
checks only when a debugger is attached, avoiding runtime overhead in production
scenarios.

This proposal introduces two intrinsics that together provide a debugging
toolkit for shader development.

## Proposed solution

This proposal introduces two new HLSL intrinsics for debugging shader code.

### Intrinsics

```hlsl
void DebugBreak();        // Trigger a breakpoint if debugger attached
bool IsDebuggerPresent(); // Query if a debugger is attached
```

### Example Usage

```hlsl
[numthreads(8,1,1)]
void main(uint GI : SV_GroupIndex) {
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

Two new intrinsic functions are added:

#### `DebugBreak()`

```hlsl
void DebugBreak();
```

Triggers a breakpoint if a graphics debugger is attached. If no debugger is
attached or the runtime does not support this operation, it is treated as a
no-op. Execution continues after the breakpoint.

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
        if (data[i] < 0.0f || data[i] > 1.0f) {
            DebugBreak();
        }
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
        if (any(pixelCoord >= screenDimensions)) {
            DebugBreak();
        }
        
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

This change introduces two new DXIL operations:

#### `dx.op.debugBreak`

```llvm
declare void @dx.op.debugBreak(
  immarg i32             ; opcode
) convergent
```

Triggers a debugger breakpoint. Must be treated as `convergent` to prevent code
motion. Should not be marked `readonly` or `readnone`. If no debugger is
attached, this is a no-op.

#### `dx.op.isDebuggerPresent`

```llvm
declare i1 @dx.op.isDebuggerPresent(
  immarg i32             ; opcode
) readonly
```

Returns `true` (1) if a debugger is attached, `false` (0) otherwise. Marked
`readonly` as it only queries state. 

### Convergence Requirements

`debugBreak` operations must be treated as `convergent` to prevent
code motion that could change their observable behavior:
- `debugBreak`: Must break at the exact location specified by the programmer

These operations should not be hoisted, sunk, or duplicated by optimizers.

### Shader Model Requirements

These instructions will only be valid in Shader Model 6.10 or later.

Because `DebugBreak()` and `IsDebuggerPresent()` can be treated as no-ops when
no debugger is present, they are required supported features and do not require
capability bits.

### D3D12 Runtime Behavior for DebugBreak

#### Default Behavior: DebugBreak as No-Op

By default, when no debugger is attached, `DebugBreak()` is treated as a no-op
i.e the `dx.op.debugBreak` operation has no effect at runtime.

The allows for driver back end compilers to optimize away these instructions
and any instructions that lead up to them (provided they don't have any visible
side effects); however, they must retain the ability to re-enable the Debug
Break behavior in the case of a debugger being attached after pipeline creation.

While this gives developers confidence that Debug Break operations left
in retail code will not fire and cause an application to exit unexpectedly
it does limit the usefulness of Debug Break for tracking down rare/hard to
reproduce issues.

To enable that scenario a D3D12 PSO flag is proposed.

#### Enabling DebugBreak via PSO Flag

A new Pipeline State Object (PSO) creation flag is introduced to enable Debug
Break without debuggers being attached for specific pipelines:

```cpp
typedef enum D3D12_PIPELINE_STATE_FLAGS {
    D3D12_PIPELINE_STATE_FLAG_NONE = 0,
    D3D12_PIPELINE_STATE_FLAG_TOOL_DEBUG = 0x1,
    // ... existing flags ...
    D3D12_PIPELINE_STATE_FLAG_HALT_ON_DEBUG_BREAK = 0x..., // New flag
} D3D12_PIPELINE_STATE_FLAGS;
```

When `D3D12_PIPELINE_STATE_FLAG_HALT_ON_DEBUG_BREAK` is set:
- `DebugBreak()` instructions are active and will halt shader execution
- The backend compiler must preserve abort instructions and their control flow
- If no debugger is attached to intercept the shader halt, Timeout Detection 
and Recovery (TDR) will initiate to indicate that the Debug Break has been hit.

#### Use Cases for Selective Debug Break Enabling

This design enables several important scenarios:

1. **Retail Debugging**: Developers can selectively enable debug breaks for
   specific users experiencing rare bugs without requiring a separate debug
   build:
   ```cpp
   D3D12_GRAPHICS_PIPELINE_STATE_DESC psoDesc = {};
   // ... configure PSO ...
   if (userOptedIntoDebugMode || detectingRareBug) {
       psoDesc.Flags |= D3D12_PIPELINE_STATE_FLAG_HALT_ON_DEBUG_BREAK;
   }
   ```

2. **A/B Testing**: Enable debug breaks for a subset of users to detect issues
   in production without impacting all users.

3. **Development Builds**: Always enable debug breaks for internal testing while
   keeping it disabled for public releases.

4. **Per-Pipeline Control**: Enable debug breaks only for specific shaders that
   are suspected of containing bugs, minimizing performance impact.

### SPIR-V Lowering

#### DebugBreak

Uses the existing `NonSemantic.DebugBreak` instruction:

```
%1 = OpExtInstImport "NonSemantic.DebugBreak"
%2 = OpExtInst %void %1 DebugBreak
```

While this instruction is not widely supported by Vulkan debuggers, it is
supported by NVIDIA's NSight and can be safely ignored by Vulkan runtimes.

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

### Validation Testing

- Confirm validation accepts the new operations in SM 6.10+
- Confirm validation rejects operations in earlier shader models
- Verify convergence requirements are properly validated

### Execution Testing

- Test `DebugBreak()` triggers breakpoint when debugger attached
- Test `DebugBreak()` is no-op when no debugger present
- Test `IsDebuggerPresent()` returns correct value based on debugger state

## Open Questions

* Consider introducing the `convergent` attribute to DXIL.
  * This should be "cheap" and would potentially address pre-existing bugs.
  * This would preserve the requirement that these operations not be moved
    during optimization in the final DXIL.