---
title: "0051 - ByteAddressBuffer Alignment
params:
  authors:
     - mapodaca-nv: Mike Apodaca
   sponsors:
     - tex3D: Tex Riddell
   status: Under Consideration
---

* Required Version: Shader Model X.Y, Vulkan X.Y, and/or HLSL 20XY
* Issues: [#543](https://github.com/microsoft/hlsl-specs/issues/543),
   [#258](https://github.com/microsoft/hlsl-specs/issues/258)

## Introduction

This proposal introduces a `BaseAlignment` attribute for byte address buffer object declarations that specifies base
address alignment requirements, and new `AlignedLoad`/`AlignedStore` functions for buffer access operations that specify
the relative offset alignment requirements. Modern GPU architectures may perform optimizations based on higher
alignments, but current HLSL provides no mechanism to communicate these alignment guarantees from the application to the
shader compiler. While DXIL already contains alignment fields in its intermediate representation, this information is
currently inaccessible through HLSL source code, forcing compilers to, for example, assume worst-case 4-byte alignment
for root descriptor buffer views. This proposal bridges that gap by introducing syntax to specify both buffer base
alignment and access operation relative alignment requirements directly in HLSL, enabling compilers to generate
optimized memory access patterns and improving performance for applications that can guarantee higher alignment.

## Motivation

Applications frequently allocate GPU buffer resources with alignment guarantees that exceed the minimum requirements,
and carefully structure their buffer access patterns with known alignment properties, particularly for
performance-critical workloads involving structured data or vectorized operations. However, current HLSL provides no
mechanism to communicate either buffer base address alignment or individual access operation alignment properties to the
shader compiler, creating a significant optimization barrier.

The primary limitation occurs with root descriptor buffer views, which are constrained to 4-byte alignment in the
current specification. When applications choose root descriptors over descriptor tables for performance or resource
binding reasons, shader compilers must conservatively assume this worst-case alignment scenario. This conservative
assumption prevents optimizations that depend on higher alignment guarantees, even when the application has allocated
and bound buffers with stronger alignment properties.

A concrete example of this limitation appears in cooperative vector operations. Consider an application using
cooperative vector `MulAdd` intrinsics versus separate `Mul + Load(Bias) + Add(Bias)` sequences. The matrix and bias
buffers are required to be allocated with 16-byte alignment when using the cooperative vector intrinsics. However, when
hardware constraints require decomposing into a sequence of operations, the lack of alignment information in HLSL
prevents the compiler from generating vectorized loads, even though the underlying buffers maintain 16-byte alignment
throughout the operation.

This problem extends beyond cooperative vector operations to any scenario requiring vectorized buffer access patterns.
The DXIL intermediate representation includes alignment parameters for `dx.op.rawBufferLoad`, `dx.op.rawBufferStore`,
`dx.op.rawBufferVectorLoad` and `dx.op.rawBufferVectorStore` operations that could enable these optimizations, but these
parameters are currently fixed to the vector element size due to the absence of alignment specification in HLSL source
code. Additionally, DXIL resource properties contain base alignment fields that remain underutilized because HLSL
provides no mechanism to specify buffer base address alignment requirements.

Without this feature, applications seeking optimal performance must rely on complex, driver-based workarounds including
runtime address monitoring, dynamic shader recompilation based on observed alignment patterns, and sophisticated caching
systems to manage multiple shader variants. These approaches add significant complexity to both driver development and
application runtime overhead that could be eliminated with proper alignment specification.

## High-level description

This proposal introduces a `BaseAlignment` attribute that can be applied to HLSL byte address buffer object declarations
and function parameters to specify the buffer's base address minimum alignment, and new `AlignedLoad`/`AlignedStore`
functions for buffer access operations that specify the relative offset alignment (how the offset aligns relative to the
buffer's base address). The solution leverages existing DXIL infrastructure for alignment information, requiring changes
to HLSL and DXC, but no changes to the DXIL intermediate representation itself.

```cpp
// Base address alignment specification
[BaseAlignment(16)]
RWByteAddressBuffer MyBuffer : register(u0);
```

The compiler uses the `BaseAlignment` attribute to populate existing base alignment fields in DXIL
`dx.types.ResourceProperties` during `dx.op.annotateHandle` operations, communicating the buffer's base address
alignment to the backend compiler.

```cpp
// Per-operation alignment specification
uint4 data = MyBuffer.AlignedLoad<uint4>(index0, 16);
```

The compiler uses the `BaseAlignment` attribute and the relative offset alignment parameters from
`AlignedLoad`/`AlignedStore` functions to populate existing alignment parameters in DXIL operations, such as
`dx.op.rawBufferLoad` and `dx.op.rawBufferStore`, which already include alignment fields but currently default to
largest scalar type size alignment. This design provides comprehensive alignment control by separating buffer base
address constraints from individual operation offset alignment requirements, allowing applications to precisely
communicate their alignment guarantees at both levels. The approach leverages existing DXIL infrastructure without
requiring intermediate representation changes, ensuring broad vendor compatibility while eliminating the complex runtime
workarounds currently necessary for achieving similar optimizations.

## Detailed design

### HLSL Additions

This proposal introduces a `BaseAlignment` attribute that can be applied to byte address buffer object declarations and
function parameters to specify the buffer's base address alignment, and new `AlignedLoad`/`AlignedStore` functions that
provide per-operation relative alignment specification.

The `BaseAlignment` attribute and `AlignedLoad`/`AlignedStore` functions work together to provide complete alignment
specification:

* **BaseAlignment Attribute:**
  * Declares the minimum alignment of the buffer's base GPU virtual address
  * Applied at buffer declaration time and affects all operations on that buffer
  * Applied to function parameters to specify alignment requirements during parameter passing

* **AlignedLoad/AlignedStore Functions:**
  * Specify the relative alignment of the offset parameter to the buffer's base address for individual access operations
  * Each operation can specify different relative offset alignment values

#### BaseAlignment Attribute

| Attribute | Required | Description |
|:---       |:--------:|:------------|
| `[BaseAlignment(value)]` | N | `value` must be: a literal, a power of 2, >= 4, and <= 4096. |

* Supported Buffer Types:
  * `ByteAddressBuffer` and `RWByteAddressBuffer`

> **Author's note**: The "power of two" requirement comes from the existing DXIL bitfield definition.  The minimum
> alignment of `4` maintains the existing requirements for root view GPUVAs.  The maximum alignment of `4096` seems
> sufficient but can be as high as `32K` if desired.

#### AlignedLoad/AlignedStore Functions

Added `[RW]ByteAddressBuffer` access operations:

* `ByteAddressBuffer`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment) const;`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment, out uint status) const;`
* `RWByteAddressBuffer`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment) const;`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment, out uint status) const;`
  * `template<typename T> void AlignedStore(in uint offset, in uint alignment, in T value);`

These `AlignedLoad`/`AlignedStore` functions include an `alignment` parameter that specifies the **relative alignment of
the offset** to the buffer's base address:

* **`alignment` parameter**
  * Must be a literal, a multiple of 4, >= 4 and <= 4096
  * specifies the alignment of the `offset` parameter _relative_ to the buffer's base address, not the absolute
    alignment of the final memory address

> **Author's note**: The minimum alignment of `4` maintains the existing requirements for root view GPUVAs.  However, we
> may want to allow tighter alignments for small element sizes.  The maximum alignment of `4096` seems sufficient but
> can be as higher if desired.

#### Relative Offset Alignment Explained

The `alignment` parameter in `AlignedLoad`/`AlignedStore` functions specifies **relative alignment** - how the offset
value aligns relative to the buffer's base address. This is a crucial distinction:

* **Relative alignment**: `offset % alignment == 0` (offset is aligned relative to base address)
* **Absolute alignment**: `(base_address + offset) % alignment == 0` (final address is aligned)

The compiler uses the relative offset alignment information combined with the buffer's base address alignment to
determine the absolute alignment of the final memory access. This allows for efficient optimization even when the
absolute address cannot be determined at compile time.

> **Author's note**: The choice of relative alignment (offset alignment relative to buffer base address) over absolute
> alignment (final memory address alignment) provides better code composability and robustness. With relative alignment,
> developers can write reusable buffer access patterns that work regardless of the specific `BaseAlignment` value,
> separating data structure layout concerns from buffer allocation details. For example, code that processes structured
> data with 32-byte strides can specify 32-byte relative alignment and work correctly whether the buffer has
> `BaseAlignment(64)` or `BaseAlignment(128)`. This approach aligns with how developers naturally think about structured
> data layouts while maintaining the performance benefits through DXC's automatic calculation of the final absolute
> alignment passed to DXIL operations.

**Example:**

```cpp
[BaseAlignment(64)]  // Buffer base address: 0x12345C00 (64-byte aligned)
RWByteAddressBuffer MyBuffer;

// These calls specify relative offset alignment with actual memory addresses:
MyBuffer.AlignedLoad<uint4>(0x00, 16);   // Final address: 0x12345C00 (16-byte aligned ✓)
MyBuffer.AlignedLoad<uint4>(0x10, 16);   // Final address: 0x12345C10 (16-byte aligned ✓)
MyBuffer.AlignedLoad<uint4>(0x20, 32);   // Final address: 0x12345C20 (32-byte aligned ✓)
MyBuffer.AlignedLoad<uint4>(0x40, 64);   // Final address: 0x12345C40 (64-byte aligned ✓)

// Invalid relative alignment examples:
MyBuffer.AlignedLoad<uint4>(0x08, 16);   // Final address: 0x12345C08 (only 8-byte aligned ✗)
MyBuffer.AlignedLoad<uint4>(0x04, 8);    // Final address: 0x12345C04 (only 4-byte aligned ✗)
MyBuffer.AlignedLoad<uint4>(0x14, 16);   // Final address: 0x12345C14 (only 4-byte aligned ✗)
```

> **Developer's note**: The offset alignment relative to the base address determines the final memory address alignment.
> Even though the buffer base is 64-byte aligned, an offset of 0x08 (8-byte aligned relative to base) results in a final
> address that is only 8-byte aligned, not 16-byte aligned as requested.

#### Shader Stage and Feature Compatibility

The `BaseAlignment` attribute and `AlignedLoad`/`AlignedStore` functions are independent of shader stage and can be used
in any shader type (vertex, pixel, compute, geometry, hull, domain, etc.). The alignment information is processed during
compilation and embedded into the generated DXIL, making it available to backend compilers for optimization regardless
of the target shader stage.

The feature works orthogonally to existing HLSL features without introducing conflicts or dependencies:

* **Register binding**: Fully compatible with `register(t#)` for SRV and `register(u#)` for UAV binding
* **Resource binding**: Compatible with all binding methods: root descriptors, descriptor tables, and descriptor heap
  indexing
* **Buffer access patterns**: The `AlignedLoad`/`AlignedStore` functions can be used selectively for individual
  operations, allowing different alignment specifications for different accesses to the same buffer
* **Existing syntax**: Does not interfere with existing buffer declarations, function parameters, method calls, or
  operator usage

#### Effective Alignment Calculation

The compiler uses the `BaseAlignment` attribute and `AlignedLoad`/`AlignedStore` function parameters to determine the
final effective alignment for optimization purposes. The operation's effective alignment is calculated as the minimum
of:

1. The buffer's declared `BaseAlignment` value (absolute alignment of the buffer's base address)
2. The operation's specified `alignment` parameter (relative alignment of the offset to the base address)

> **Implementation note**: The calculated effective alignment represents the **absolute alignment** of the final memory
> access address (`base_address + offset`) and is the value that DXC passes to the DXIL operation's alignment parameter.

**Example:**

```cpp
[BaseAlignment(32)]  // Buffer's base address is 32-byte aligned
RWByteAddressBuffer MyBuffer : register(u0);

// Example 1: Function alignment smaller than base alignment
uint offset1 = computeOffset1();  // Runtime offset, alignment unknown at compile time
uint4 data1 = MyBuffer.AlignedLoad<uint4>(offset1, 16);
// DXC calculation: min(BaseAlignment=32, function_alignment=16) = 16
// DXIL gets: alignment = 16 (absolute) - developer promises offset meets 16-byte alignment

// Example 2: Function alignment larger than base alignment
uint offset2 = computeOffset2();  // Runtime offset, alignment unknown at compile time
vector<uint, 16> data2 = MyBuffer.AlignedLoad< vector<uint, 16> >(offset2, 64);
// DXC calculation: min(BaseAlignment=32, function_alignment=64) = 32
// DXIL gets: alignment = 32 (absolute) - limited by BaseAlignment regardless of offset
```

#### Behavior of Load/Store Functions with BaseAlignment Attribute

When a buffer is declared with `BaseAlignment` but individual operations use the existing `Load`/`Store` functions
instead of `AlignedLoad`/`AlignedStore`, then DXC applies the same alignment calculation using the "largest scalar type
contained in the given aggregate type" as the implied alignment argument.  This maintains backwards compatibility with
existing code.

If the `BaseAlignment` is smaller than the effective alignment when `Load`/`Store` functions are used, then the compiler
will issue an error message as this mismatch indicates the buffer is not properly aligned for these `Load`/`Store`
operations.

**Example:**

```cpp
[BaseAlignment(64)]
RWByteAddressBuffer MyBuffer : register(u0);

// Existing Load/Store functions - DXC applies min(BaseAlignment, largest_scalar_type_size) calculation:
uint4 data1 = MyBuffer.Load<uint4>(offset1);       // DXC: min(64, 4) = 4 → DXIL alignment = 4
                                                    // Note: uint4 largest scalar type is uint (4 bytes)
uint data2 = MyBuffer.Load<uint>(offset2);         // DXC: min(64, 4) = 4 → DXIL alignment = 4
uint64_t data3 = MyBuffer.Load<uint64_t>(offset3); // DXC: min(64, 8) = 8 → DXIL alignment = 8

// Example where largest scalar type size exceeds BaseAlignment:
[BaseAlignment(4)]  // Minimum allowed BaseAlignment
RWByteAddressBuffer MyOtherBuffer : register(u1);

uint64_t data4 = MyOtherBuffer.Store<uint64_t>(offset4, data3); // DXC error: BaseAlignment = 4 < scalar type alignment = 8
```

> **Implementation note**: The `BaseAlignment` attribute affects both the base address alignment information in DXIL
> resource properties and the operation-level alignment calculation for existing `Load`/`Store` functions. This ensures
> consistent alignment semantics across all buffer access methods. Code that doesn't use `BaseAlignment` continues to
> work unchanged. Code that adds `BaseAlignment` may experience improved alignment for current operations.

#### Behavior of AlignedLoad/AlignedStore Functions without BaseAlignment Attribute

When the `BaseAlignment` attribute is _not_ specified on the buffer, but the new `AlignedLoad`/`AlignedStore` functions
are used, then DXC uses the existing alignment requirements to calculate the effective alignment:

> **HLSL Specification, 1.7.2 Memory Spaces**: _"The alignment requirements of an offset into device memory space is the
> size in bytes of the largest scalar type contained in the given aggregate type"_

If the `alignment` parameter passed to the `AlignedLoad`/`AlignedStore` functions is smaller than the scalar alignment,
then the compiler will issue an error message.  If the value is larger, then the compiler will issue a warning message
to inform the developer that this mismatch may be unexpected.  However, for the sake of code reuse, this mismatch will
be allowed.

#### BaseAlignment Attribute on Function Parameters

The `BaseAlignment` attribute can be applied to `[RW]ByteAddressBuffer` function parameters to specify alignment
requirements during parameter passing. This enables functions to declare their alignment assumptions explicitly and
ensures that callers provide buffers with sufficient alignment guarantees. The attribute follows standard alignment
decay rules where parameter alignment can be less than or equal to the argument's declared alignment, but cannot exceed
it.

When a function parameter specifies `BaseAlignment`, the argument passed to that function must have been declared with
`BaseAlignment`, and the argument's alignment value must be greater than or equal to the parameter's alignment
requirement. If the parameter does not specify `BaseAlignment`, arguments with or without `BaseAlignment` can be passed.
The effective alignment calculation within the function uses the parameter's declared `BaseAlignment` value, not the
argument's original alignment, ensuring consistent behavior regardless of the caller's buffer alignment.

Function parameters with `BaseAlignment` maintain the same alignment semantics as buffer declarations: they affect both
the base address alignment information passed to DXIL operations and the effective alignment calculations for
`Load`/`Store` and `AlignedLoad`/`AlignedStore` functions called within the function scope. This allows functions to be
written with specific alignment assumptions while maintaining type safety and preventing alignment-related errors at
compile time.

**Example 1: Alignment Decay (Valid)**

```cpp
// Function expects 16-byte aligned buffer
void ProcessAligned([BaseAlignment(16)] RWByteAddressBuffer buffer, uint offset) {
    // Function can assume buffer base address is at least 16-byte aligned
    uint4 data = buffer.AlignedLoad<uint4>(offset, 16);
    buffer.AlignedStore<uint4>(offset + 16, 16, data);
}

[BaseAlignment(64)]  // 64-byte alignment can decay to 16-byte requirement
RWByteAddressBuffer MyBuffer : register(u0);

void main() {
    ProcessAligned(MyBuffer, 0);  // Valid: 64 >= 16
}
```

**Example 2: Alignment Mismatch (Compiler Error)**

```cpp
// Function expects 32-byte aligned buffer
void ProcessAligned([BaseAlignment(32)] RWByteAddressBuffer buffer, uint offset) {
    uint4 data = buffer.AlignedLoad<uint4>(offset, 32);
    buffer.AlignedStore<uint4>(offset + 16, 16, data);
}

[BaseAlignment(16)]  // Only 16-byte alignment available
RWByteAddressBuffer MyBuffer : register(u0);

void main() {
    ProcessAligned(MyBuffer, 0);  // Error: 16 < 32, insufficient alignment
}
```

**Example 3: Optional Parameter Alignment (Valid)**

```cpp
// Function can accept buffers with or without BaseAlignment
void Process(RWByteAddressBuffer buffer, uint offset) {
    uint4 data = buffer.Load<uint4>(offset);
    buffer.Store<uint4>(offset + 16, data);
}

[BaseAlignment(32)]
RWByteAddressBuffer MyAlignedBuffer : register(u0);
RWByteAddressBuffer MyUnalignedBuffer : register(u1);

void main() {
    Process(MyAlignedBuffer, 0);    // Valid: BaseAlignment is optional for this function
    Process(MyUnalignedBuffer, 0);  // Valid: No alignment requirement
}
```

#### DXIL Validation Changes

The compiler validates that both `BaseAlignment` attribute values and `AlignedLoad`/`AlignedStore` function `alignment`
parameters meet their respective constraints. When an `alignment` parameter value exceeds the buffer's `BaseAlignment`
value, the effective alignment is limited to the `BaseAlignment` value without generating an error, ensuring that
alignment guarantees remain consistent and achievable.  See [DXIL Diagnostic Changes](#dxil-diagnostic-changes) for
more details.

#### HLSL Compatibility

This feature maintains source code compatibility with existing HLSL. The `BaseAlignment` attribute is optional and the
new `AlignedLoad`/`AlignedStore` functions are additional functionality. Existing buffer declarations, function
parameters, and access operations continue to compile and execute correctly. When `BaseAlignment` is added to existing
buffers, existing `Load`/`Store` operations may receive improved alignment for larger element types, which should only
enhance performance without affecting correctness.

#### Common Usage Patterns

This section demonstrates real-world scenarios where buffer alignment features provide significant benefits:

##### Structure-of-Arrays Layout

```cpp
[BaseAlignment(32)]
RWByteAddressBuffer MyBuffer;

struct MyStruct {
    uint3 a;    // 12 bytes
    uint3 b;    // 12 bytes
    uint2 b;    // 8 bytes
};  // Total: 32 bytes per vertex

uint baseOffset = index * 32;  // 32-byte aligned offsets

// Optimal aligned access to each component
uint3 a = MyBuffer.AlignedLoad<uint3>(baseOffset + 0, 32); // 32-byte aligned
uint3 b = MyBuffer.AlignedLoad<uint3>(baseOffset + 12, 4); // 4-byte aligned
uint2 c = MyBuffer.AlignedLoad<uint2>(baseOffset + 24, 8); // 8-byte aligned
```

##### Tightly Packed Data Processing

```cpp
[BaseAlignment(64)]
RWByteAddressBuffer MyBuffer;

// Process 16-byte chunks in a 64-byte cache line
for (uint i = 0; i < 4; ++i) {
    uint4 chunk = MyBuffer.AlignedLoad<uint4>(i * 16, 16);
    // Each chunk is 16-byte aligned for optimal vector processing
    // Backend can generate efficient vector load instructions
}
```

##### Matrix Data Layout

```cpp
[BaseAlignment(64)]
RWByteAddressBuffer MyBuffer;

// 4x4 matrices stored row-major, each row is 16 bytes
uint matrixIndex = 5;
uint matrixOffset = matrixIndex * 64;  // Each matrix is 64-byte aligned

// Store matrix rows with optimal alignment
MyBuffer.AlignedStore<uint4>(matrixOffset +  0, 64, row0);  // 64-byte aligned
MyBuffer.AlignedStore<uint4>(matrixOffset + 16, 16, row1);  // 16-byte aligned
MyBuffer.AlignedStore<uint4>(matrixOffset + 32, 16, row2);  // 16-byte aligned
MyBuffer.AlignedStore<uint4>(matrixOffset + 48, 16, row3);  // 16-byte aligned
```

##### Conditional Alignment

```cpp
[BaseAlignment(32)]
RWByteAddressBuffer MyBuffer;

// Different code paths with different alignment guarantees
if (useOptimizedPath) {
    // Optimized path guarantees 32-byte alignment
    uint alignedOffset = computeAlignedOffset();  // Returns 32-byte aligned offset
    uint4 data = MyBuffer.AlignedLoad<uint4>(alignedOffset, 32);
}
else {
    // Fallback path only guarantees 4-byte alignment
    uint basicOffset = computeBasicOffset();  // Returns 4-byte aligned offset
    uint4 data = MyBuffer.AlignedLoad<uint4>(basicOffset, 4);
}
```

#### Performance Considerations

This section explains how alignment choices impact performance and provides guidance for optimal usage:

##### Memory Access Patterns

```cpp
[BaseAlignment(32)]
RWByteAddressBuffer MyBuffer;

// Good: Alignment enables vectorization
uint4 vector1 = MyBuffer.AlignedLoad<uint4>(offset1, 16);  // Can use vector load
uint4 vector2 = MyBuffer.AlignedLoad<uint4>(offset2, 16);  // Can use vector load

// Suboptimal: Misaligned access requires scalar operations
uint4 vector3 = MyBuffer.AlignedLoad<uint4>(offset3, 4);   // May require scalar loads
```

##### Vectorization Opportunities

```cpp
[BaseAlignment(64)]
RWByteAddressBuffer MyBuffer;

// Sequential 16-byte aligned loads can be vectorized by backend
uint4 a = MyBuffer.AlignedLoad<uint4>(baseOffset +  0, 16);
uint4 b = MyBuffer.AlignedLoad<uint4>(baseOffset + 16, 16);
uint4 c = MyBuffer.AlignedLoad<uint4>(baseOffset + 32, 16);
uint4 d = MyBuffer.AlignedLoad<uint4>(baseOffset + 48, 16);
// Backend may combine these into wider vector operations
```

### Interchange Format Additions

This proposal requires no changes to DXIL or SPIR-V intermediate representations. Instead, it leverages existing
alignment infrastructure already present in both formats, utilizing separate mechanisms for buffer-level and
operation-level alignment specification. The implementation can utilize these existing fields to enable more efficient
operations, including vectorization and optimized memory access patterns.

#### Existing DXIL Infrastructure

The proposal depends on two distinct existing DXIL capabilities that correspond to the `BaseAlignment` attribute and the
`AlignedLoad`/`AlignedStore` function alignment parameters:

#### Buffer Object Base Alignment (BaseAlignment attribute)

The `dx.types.ResourceProperties` structure already includes a `uint8_t BaseAlignLog2 : 4;` field in BYTE 1 of DWORD 0.
This field stores the base-2 logarithm of the buffer's base address alignment and will be populated from the
`BaseAlignment` attribute value.

> **Implementation note:** Applied during `dx.op.annotateHandle` operations to communicate buffer base address alignment
> to backend compilers.

#### Buffer Operation Alignment (AlignedLoad/AlignedStore functions)

The following DXIL operations already include alignment parameters that currently default to largest scalar type size.
These parameters expect **absolute alignment** (the final effective alignment of the memory access address) and will be
populated with values calculated by DXC from both existing `Load`/`Store` functions and new `AlignedLoad`/`AlignedStore`
function calls:

* `dx.op.rawBufferLoad.*` - includes alignment parameter for load operations
* `dx.op.rawBufferStore.*` - includes alignment parameter for store operations
* `dx.op.rawBufferVectorLoad.*` - includes alignment parameter for vector load operations
* `dx.op.rawBufferVectorStore.*` - includes alignment parameter for vector store operations

> **Implementation notes:**
>
> DXC populates DXIL operation alignment parameters with **absolute alignment** values calculated from the scenarios
> described in the behavior sections above:
>
> * **AlignedLoad/AlignedStore with BaseAlignment**: Calculates `min(BaseAlignment, function_alignment_parameter)`
> * **Existing Load/Store with BaseAlignment**: Calculates `min(BaseAlignment, largest_scalar_type_size)`
> * **AlignedLoad/AlignedStore without BaseAlignment**: Uses existing HLSL specification alignment requirements based on
>   largest scalar type size, with appropriate error checking for mismatches
>
> The key distinction is that HLSL functions specify **relative alignment** (offset alignment relative to base address)
> while DXIL operations expect **absolute alignment** (final memory address alignment). DXC performs this conversion
> automatically.

**Example DXIL Usage:**

The following example illustrates how DXC calculates the absolute alignment passed to DXIL operations.

**HLSL Source:**

```cpp
[BaseAlignment(32)]  // Buffer base is 32-byte aligned
RWByteAddressBuffer MyBuffer : register(u0);

// Function specifies 16-byte relative offset alignment
uint4 data = MyBuffer.AlignedLoad<uint4>(offset, 16);
```

**Generated DXIL:**
```llvm
  ; AnnotateHandle(res,props)  resource: ByteAddressBuffer
  %26 = call %dx.types.Handle @dx.op.annotateHandle(
    i32 216,
    %dx.types.Handle %2,
    %dx.types.ResourceProperties {
      i32 1035, ; ResourceKind = RawBuffer(11), BaseAlignLog2 = 5 (BaseAlignment = 32)
      i32 0     ; n/a
      }
    )

  ; RawBufferLoad(srv,index,elementOffset,mask,alignment)
  %27 = call %dx.types.ResRet.f32 @dx.op.rawBufferLoad.f32(
    i32 139,
    %dx.types.Handle %26,
    i32 %25,
    i32 undef,
    i8 15,
    i32 16      ; DXC calculated: min(BaseAlignment=32, function_alignment=16) = 16 (absolute)
    )
```

**DXC Calculation Process:**

1. Buffer base alignment: 32 bytes (from `BaseAlignment` attribute)
2. Function relative offset alignment: 16 bytes (from `AlignedLoad` parameter)
3. **Absolute alignment for DXIL**: `min(32, 16) = 16` (absolute alignment passed to DXIL operation)

The implementation uses these two DXIL mechanisms together: the `BaseAlignLog2` field communicates buffer-level
alignment guarantees during resource binding, while the operation-level alignment parameters specify the final effective
alignment of each memory access. Backend compilers can use both pieces of information to determine the most aggressive
optimization strategies for each buffer access operation.

#### SPIR-V Compatibility

SPIR-V buffer operations similarly include alignment parameters and resource metadata fields that can be populated with
the alignment information from the `BaseAlignment` attribute and `AlignedLoad`/`AlignedStore` function parameters.
Buffer objects can carry base alignment information in their descriptors, while individual buffer access operations can
specify per-operation alignment requirements through existing SPIR-V alignment parameters, requiring no new SPIR-V
instructions or capabilities.

**Note**: Like DXIL, SPIR-V alignment parameters expect **absolute alignment** values. The compiler must perform the
same relative-to-absolute alignment conversion when generating SPIR-V as it does for DXIL.

### DXIL Diagnostic Changes

This proposal introduces several new compile-time error conditions when the `BaseAlignment` attribute and
`AlignedLoad`/`AlignedStore` functions are used incorrectly or inconsistently.

#### New Error Conditions

* **E1001: Unsupported buffer type for alignment features**
  * **Condition**: `BaseAlignment` attribute or `AlignedLoad`/`AlignedStore` functions used on unsupported buffer types
  * **Trigger**: Using alignment features on `[RW]Buffer`, `[RW]StructuredBuffer`, `ConstantBuffer`, `cbuffer`, or
    `Texture*` resources
  * **Message**: `"Alignment features cannot be applied to <type>. Supported types are ByteAddressBuffer and
    RWByteAddressBuffer"`
  * **Example**:
    ```cpp
    [BaseAlignment(16)]
    Texture2D MyTexture; // Error: unsupported type

    Buffer<uint4> TypedBuffer;
    uint4 data = TypedBuffer.AlignedLoad<uint4>(0, 16); // Error: unsupported type
    ```

* **E1002: Invalid alignment value**
  * **Condition**: Alignment value is not a compile-time constant, not a power of 2, or outside valid range
  * **Trigger**: Using variable or runtime-computed alignment values, or values that violate constraints
  * **Message**: `"Alignment values require compile-time constant values that are powers of 2, >= 4, and <= 4096"`
  * **Example**:
    ```cpp
    static const int align = 16;
    [BaseAlignment(align)]  // Error: not a literal constant
    ByteAddressBuffer MyBuffer;

    int dynamicAlign = calculateAlignment();
    uint4 data = MyBuffer.AlignedLoad<uint4>(0, dynamicAlign);  // Error: not a compile-time constant

    [BaseAlignment(3)]    // Error: not power of 2
    [BaseAlignment(2)]    // Error: less than 4
    [BaseAlignment(8192)] // Error: greater than 4096
    ByteAddressBuffer MyBuffer2;
    ```

* **E1003: BaseAlignment smaller than element size for Load/Store functions**
  * **Condition**: Buffer declared with `BaseAlignment` smaller than the largest scalar type size when using existing
    `Load`/`Store` functions
  * **Trigger**: Using existing `Load`/`Store` functions where the largest scalar type size exceeds the buffer's
    `BaseAlignment`
  * **Message**: `"BaseAlignment of <value> bytes is smaller than required alignment of <largest_scalar_type_size> bytes
    for <type> element type"`
  * **Example**:
    ```cpp
    [BaseAlignment(4)]  // Minimum allowed BaseAlignment
    RWByteAddressBuffer MyBuffer : register(u0);

    uint64_t data = MyBuffer.Load<uint64_t>(offset); // Error: BaseAlignment = 4 < scalar type alignment = 8
    ```

* **E1004: AlignedLoad/AlignedStore alignment parameter smaller than scalar alignment without BaseAlignment**
  * **Condition**: Using `AlignedLoad`/`AlignedStore` functions without `BaseAlignment` attribute where alignment
    parameter is smaller than the largest scalar type size
  * **Trigger**: Alignment parameter violates HLSL specification requirement for scalar type alignment
  * **Message**: `"Alignment parameter of <value> bytes is smaller than required scalar alignment of <scalar_size> bytes
    for <type> element type"`
  * **Example**:
    ```cpp
    ByteAddressBuffer MyBuffer : register(t0);  // No BaseAlignment declared

    uint64_t data = MyBuffer.AlignedLoad<uint64_t>(0, 4);  // Error: alignment = 4 < scalar type alignment = 8
    ```

* **E1005: Function parameter alignment exceeds argument alignment**
  * **Condition**: Function parameter specifies `BaseAlignment` value larger than the argument's declared
    `BaseAlignment`
  * **Trigger**: Calling function with buffer argument that has insufficient alignment for the parameter requirement
  * **Message**: `"Function parameter requires BaseAlignment of <param_value> bytes, but argument has BaseAlignment of
    <arg_value> bytes"`
  * **Example**:
    ```cpp
    void Process([BaseAlignment(32)] RWByteAddressBuffer buffer, uint offset) {
        uint4 data = buffer.AlignedLoad<uint4>(offset, 32);
    }

    [BaseAlignment(16)]  // Only 16-byte alignment available
    RWByteAddressBuffer MyBuffer : register(u0);

    void main() {
        Process(MyBuffer, 0);  // Error: 16 < 32, insufficient alignment
    }
    ```

* **E1006: Function parameter requires BaseAlignment but argument has none**
  * **Condition**: Function parameter specifies `BaseAlignment` but argument buffer was not declared with
    `BaseAlignment`
  * **Trigger**: Calling function that requires alignment guarantee with unaligned buffer argument
  * **Message**: `"Function parameter requires BaseAlignment of <param_value> bytes, but argument has no BaseAlignment
    declared"`
  * **Example**:
    ```cpp
    void Process([BaseAlignment(16)] RWByteAddressBuffer buffer, uint offset) {
        uint4 data = buffer.AlignedLoad<uint4>(offset, 16);
    }

    RWByteAddressBuffer MyBuffer : register(u0);  // No BaseAlignment declared

    void main() {
        Process(MyBuffer, 0);  // Error: function requires BaseAlignment but argument has none
    }
    ```

#### New Warning Conditions

* **W1001: AlignedLoad/AlignedStore alignment parameter larger than scalar alignment without BaseAlignment**
  * **Condition**: Using `AlignedLoad`/`AlignedStore` functions without `BaseAlignment` attribute where alignment
    parameter is larger than the largest scalar type size
  * **Trigger**: Alignment parameter exceeds required scalar alignment, which may be unexpected
  * **Message**: `"Alignment parameter of <value> bytes is larger than required scalar alignment of <scalar_size> bytes
    for <type> element type. This mismatch may be unexpected but is allowed for code reuse"`
  * **Example**:
    ```cpp
    ByteAddressBuffer MyBuffer : register(t0);  // No BaseAlignment declared

    uint data = MyBuffer.AlignedLoad<uint>(0, 16);  // Warning: alignment = 16 > scalar type alignment = 4
    ```

#### No Existing Errors Removed

This proposal does not remove any existing error or warning conditions.

### Runtime Validation Changes

This proposal introduces runtime validation for alignment mismatches that can only be detected during shader execution.
This proposal does not remove any existing validation conditions.

#### GPU-Based Validation

When GPU-Based Validation is enabled, the following runtime checks are performed:

* **V1001: Buffer base address alignment mismatch**
  * **Condition**: Actual buffer base address does not meet the declared `BaseAlignment` requirement
  * **Detection**: During buffer binding when the buffer's GPU virtual address is not aligned to the `BaseAlignment`
    value
  * **Action**: GPU-Based Validation reports a validation error with details about the expected vs. actual base
    alignment
  * **Message**: `"Buffer bound at address 0x<address> violates declared BaseAlignment of <value> bytes. Address is only
    aligned to <actual> bytes"`
  * **Example Scenarios**:
    ```cpp
    [BaseAlignment(16)]
    ByteAddressBuffer MyBuffer : register(t0);

    // Scenario 1: Buffer bound to misaligned address
    // If buffer is bound to address 0x1000000C (only 12-byte aligned, not 16-byte aligned)
    // V1001 validation error: "Buffer bound at address 0x1000000C violates declared
    // BaseAlignment of 16 bytes. Address is only aligned to 4 bytes"

    // Scenario 2: Buffer bound to completely unaligned address
    // If buffer is bound to address 0x10000001 (only 1-byte aligned)
    // V1001 validation error: "Buffer bound at address 0x10000001 violates declared
    // BaseAlignment of 16 bytes. Address is only aligned to 1 bytes"

    // Scenario 3: Large alignment requirement violated
    [BaseAlignment(64)]
    ByteAddressBuffer LargeBuffer : register(t1);

    // If buffer is bound to address 0x10000020 (only 32-byte aligned, not 64-byte aligned)
    // V1001 validation error: "Buffer bound at address 0x10000020 violates declared
    // BaseAlignment of 64 bytes. Address is only aligned to 32 bytes"
    ```

* **V1002: Buffer operation alignment mismatch**
  * **Condition**: Buffer access operation does not meet the effective alignment requirement
  * **Detection**: During buffer load/store operations when the final access address (base address + offset) violates
    the effective alignment calculated as the minimum of: `BaseAlignment` and `AlignedLoad`/`AlignedStore` alignment
    parameter (relative offset alignment)
  * **Action**: GPU-Based Validation reports operation-specific alignment violations
  * **Message**: `"Buffer operation at address 0x<address> violates effective alignment of <value> bytes (BaseAlignment:
    <base>, offset_alignment: <op>). Address is only aligned to <actual> bytes"`
  * **Example Scenarios**:
    ```cpp
    [BaseAlignment(32)]
    ByteAddressBuffer MyBuffer : register(t0);

    // Scenario 1: Offset violates relative alignment requirement
    // Buffer base address: 0x10000000 (32-byte aligned)
    // Offset: 0x0C (12), only 4-byte aligned relative to base
    uint4 data1 = MyBuffer.AlignedLoad<uint4>(0x0C, 16);
    // Final address: 0x1000000C (4-byte aligned, but 16-byte alignment required)
    // V1002 validation error: "Buffer operation at address 0x1000000C violates effective
    // alignment of 16 bytes (BaseAlignment: 32, offset_alignment: 16). Address is only
    // aligned to 4 bytes"

    // Scenario 2: Misaligned offset with larger alignment request
    // Buffer base address: 0x10000000 (32-byte aligned)
    // Offset: 0x04 (4), only 4-byte aligned relative to base
    uint4 data2 = MyBuffer.AlignedLoad<uint4>(0x04, 32);
    // Final address: 0x10000004 (4-byte aligned, but 32-byte alignment required)
    // V1002 validation error: "Buffer operation at address 0x10000004 violates effective
    // alignment of 32 bytes (BaseAlignment: 32, offset_alignment: 32). Address is only
    // aligned to 4 bytes"

    // Scenario 3: Complex calculation leading to misalignment
    // Buffer base address: 0x10000000 (32-byte aligned)
    uint someIndex = 3;
    uint calculatedOffset = someIndex * 12;  // 36 = 0x24, only 4-byte aligned
    uint4 data3 = MyBuffer.AlignedLoad<uint4>(calculatedOffset, 16);
    // Final address: 0x10000024 (4-byte aligned, but 16-byte alignment required)
    // V1002 validation error: "Buffer operation at address 0x10000024 violates effective
    // alignment of 16 bytes (BaseAlignment: 32, offset_alignment: 16). Address is only
    // aligned to 4 bytes"

    // Scenario 4: Store operation alignment violation
    [BaseAlignment(16)]
    RWByteAddressBuffer WriteBuffer : register(u0);

    // Buffer base address: 0x20000000 (16-byte aligned)
    // Offset: 0x06 (6), only 2-byte aligned relative to base
    WriteBuffer.AlignedStore<uint4>(0x06, 16, someFloat4);
    // Final address: 0x20000006 (2-byte aligned, but 16-byte alignment required)
    // V1002 validation error: "Buffer operation at address 0x20000006 violates effective
    // alignment of 16 bytes (BaseAlignment: 16, offset_alignment: 16). Address is only
    // aligned to 2 bytes"
    ```

#### Behavior Without GPU-Based Validation

When GPU-Based Validation is **not** enabled:

* **Undefined Behavior**: Buffer accesses that violate declared alignment requirements result in undefined behavior
* **No Runtime Checks**: The system performs no validation of alignment requirements during execution
* **Implementation Dependent**: The actual behavior depends on hardware and driver implementation details
* **Potential Consequences**: May include incorrect results, performance degradation, or in extreme cases, hardware
  exceptions

### Runtime Additions

#### Runtime Information

This proposal leverages existing DXIL infrastructure and requires minimal additional runtime processing beyond what is
already provided by the Direct3D 12 runtime and driver stack.

##### Compiler Requirements

The compiler must provide the following information to the runtime for proper buffer alignment support:

* **DXIL Buffer Operation Alignment**: The compiler populates existing alignment parameters in DXIL buffer operations
  (`dx.op.rawBuffer[Vector]Load.*`, `dx.op.rawBuffer[Vector]Store.*`) with **absolute alignment** values calculated from
  multiple scenarios:
  * **AlignedLoad/AlignedStore with BaseAlignment**: DXC must convert the relative offset alignment from function
    parameters to absolute alignment by computing `min(BaseAlignment, function_alignment_parameter)`
  * **Existing Load/Store with BaseAlignment**: DXC calculates absolute alignment using the "largest scalar type
    contained in the given aggregate type" as the implied alignment argument, combined with the buffer's `BaseAlignment`
    via `min(BaseAlignment, largest_scalar_type_size)`
  * **AlignedLoad/AlignedStore without BaseAlignment**: DXC uses existing HLSL specification alignment requirements
    based on the largest scalar type size, with error checking for alignment parameter mismatches
  * **Format**: Standard DXIL buffer operation alignment parameters (expecting absolute alignment)
  * **Runtime Usage**: Backend compilers can use these parameters for vectorization and memory access optimization

* **DXIL Resource Properties Alignment**: The compiler populates the existing `BaseAlignLog2` field in
  `dx.types.ResourceProperties` during `dx.op.annotateHandle` operations with the declared `BaseAlignment` attribute
  values
  * **Format**: Standard DXIL resource metadata structures
  * **Runtime Usage**: Runtime and backend compilers can use this information for resource binding validation and
    optimization

## Testing

Testing should focus on DXC unit level tests to verify correct DXIL codegen for all `BaseAlignment` attribute and
`AlignedLoad`/`AlignedStore` function combinations, including buffer declarations, function parameters with alignment
decay scenarios, effective alignment calculations, and proper population of DXIL operation alignment parameters and
resource properties fields.

Diagnostic testing should verify all new error conditions and warning conditions trigger correctly with appropriate
error messages for invalid usage patterns.

Runtime validation testing should confirm GPU-Based Validation properly detects alignment violations when enabled.

An HLK test should verify that memory reads and writes occur at the correct addresses when `BaseAlignment` attributes
and `AlignedLoad`/`AlignedStore` functions are used, exercising the full matrix of valid combinations including buffers
with various `BaseAlignment` values, function parameter alignment decay, mixed usage of aligned and regular buffer
operations, and ensuring backend compilers receive accurate absolute alignment information for optimization purposes.

## Alternatives considered

Two alternative proposals have been considered for addressing buffer alignment optimization in HLSL.

1. The `alignas` proposal introduces a comprehensive C++-compatible alignment specifier that can be applied to both
structure declarations and structure members, providing a general-purpose alignment solution across HLSL for
`[RW]StructuredBuffer` objects. While this approach aligns well with C++ standards and offers broader functionality, it
does not address `[RW]ByteAddressBuffer` object operations for non-structures.

2. The `RootViewAlignment` proposal takes the opposite approach by adding a specific
`D3D12_ROOT_DESCRIPTOR_FLAG_DATA_ALIGNED_16BYTE` flag to the existing root signature API to communicate 16-byte
alignment guarantees. However, this approach has been generally rejected as it represents a narrow, API-specific
solution that adds complexity to legacy interfaces that may be replaced in the future.

This buffer object alignment proposal strikes a middle ground by providing targeted functionality specifically for byte
address buffer operations through both attribute declarations and specialized functions, without requiring extensive
language changes or API modifications. The approach leverages existing DXIL infrastructure while avoiding the
specificity limitations of root signature flags. It also does not preclude or conflict with the addition of `alignas` in
future versions of HLSL.

## Acknowledgments (Optional)

* Anupama Chandrasekhar (NVIDIA)
* Justin Holewinski (NVIDIA)
* Tex Riddell (Microsoft)
* Amar Patel (Microsoft)
