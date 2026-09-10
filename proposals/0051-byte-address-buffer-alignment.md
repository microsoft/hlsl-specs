---
title: 0051 - ByteAddressBuffer Alignment
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

This proposal introduces new `AlignedLoad`/`AlignedStore` functions for byte
address buffer access operations that specify the absolute alignment of memory
accesses. Modern GPU architectures may perform optimizations based on higher
alignments, but current HLSL provides no mechanism to communicate these
alignment guarantees from the application to the shader compiler. While DXIL
already contains alignment fields in its intermediate representation, this
information is currently inaccessible through HLSL source code, forcing
compilers to assume worst-case alignment for operations. This proposal bridges
that gap by introducing syntax to specify memory access alignment requirements
directly in HLSL, enabling compilers to generate optimized memory access
patterns and improving performance for applications that can guarantee higher
alignment.

## Motivation

Applications frequently structure their buffer access patterns with known
alignment properties, particularly for performance-critical workloads involving
structured data or vectorized operations. However, current HLSL provides no
mechanism to communicate memory access alignment properties to the shader
compiler, creating a significant optimization barrier.

The primary limitation occurs with root descriptor buffer views, which are
constrained to 4-byte alignment in the current specification. When applications
choose root descriptors over descriptor tables for performance or resource
binding reasons, shader compilers must conservatively assume this worst-case
alignment scenario. This conservative assumption prevents optimizations that
depend on higher alignment guarantees, even when the application has allocated
and bound buffers with stronger alignment properties.

A concrete example of this limitation appears in cooperative vector operations.
Consider an application using cooperative vector `MulAdd` intrinsics versus
separate `Mul + Load(Bias) + Add(Bias)` sequences. The matrix and bias buffers
are required to be allocated with 16-byte alignment when using the cooperative
vector intrinsics. However, when hardware constraints require decomposing into a
sequence of operations, the lack of alignment information in HLSL prevents the
compiler from generating vectorized loads, even though the underlying buffers
maintain 16-byte alignment throughout the operation.

This problem extends beyond cooperative vector operations to any scenario
requiring vectorized buffer access patterns. The DXIL intermediate
representation includes alignment parameters for `dx.op.rawBufferLoad`,
`dx.op.rawBufferStore`, `dx.op.rawBufferVectorLoad` and
`dx.op.rawBufferVectorStore` operations that could enable these optimizations,
but these parameters are currently fixed to the vector element size due to the
absence of alignment specification in HLSL source code.

Without this feature, applications seeking optimal performance must rely on
complex, driver-based workarounds including runtime address monitoring, dynamic
shader recompilation based on observed alignment patterns, and sophisticated
caching systems to manage multiple shader variants. These approaches add
significant complexity to both driver development and application runtime
overhead that could be eliminated with proper alignment specification.

## High-level description

This proposal introduces new `AlignedLoad`/`AlignedStore` functions for byte
address buffer access operations that specify the absolute alignment of the
effective address (`base address + offset`). The solution leverages existing
DXIL infrastructure for alignment information, requiring changes to HLSL and
DXC, but no changes to the DXIL intermediate representation itself.

```cpp
RWByteAddressBuffer MyBuffer : register(u0);

// Application guarantees effective address (base + index0) is 16-byte aligned
uint4 data = MyBuffer.AlignedLoad<uint4>(index0, 16);
```

The compiler uses the absolute alignment parameters from
`AlignedLoad`/`AlignedStore` functions to populate existing alignment parameters
in DXIL operations, such as `dx.op.rawBufferLoad` and `dx.op.rawBufferStore`,
which already include alignment fields but currently default to largest scalar
type size alignment. This design allows applications to precisely communicate
their alignment guarantees for individual memory operations. The approach
leverages existing DXIL infrastructure without requiring intermediate
representation changes, ensuring broad vendor compatibility while eliminating
the complex runtime workarounds currently necessary for achieving similar
optimizations.

## Detailed design

### HLSL Additions

#### AlignedLoad/AlignedStore Functions

Added `[RW]ByteAddressBuffer` access operations:

* `ByteAddressBuffer`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment) const;`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment, out uint status) const;`
* `RWByteAddressBuffer`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment) const;`
  * `template<typename T> T AlignedLoad(in uint offset, in uint alignment, out uint status) const;`
  * `template<typename T> void AlignedStore(in uint offset, in uint alignment, in T value);`

These `AlignedLoad`/`AlignedStore` functions include an `alignment` parameter
that specifies the **absolute alignment** of the **effective address**
(`base address + offset`):

* **`alignment` parameter**
  * Must be a literal
  * Must be a power-of-two
  * Must be greater-than or equal-to the largest scalar type size contained in the
    aggregate template parameter type
  * Must be less-than or equal-to 4096

> **Author's note**: The power-of-two requirement comes from common hardware
> alignment constraints. The minimum alignment is determined by the largest
> scalar type size (e.g., 2 for 16-bit types, 4 for 32-bit types, 8 for 64-bit
> types). The maximum alignment of `4096` seems sufficient but can be higher, if
> desired. These requirements ensure compliance with the HLSL specification's
> memory space alignment requirements (section 1.7.2).
>
> **Developer's note**: The application must ensure that the effective address
> (`base_address + offset`) meets the specified alignment requirement. The
> alignment parameter must be greater-than or equal-to the largest scalar type
> size in the aggregate type (e.g., for `uint4`, the largest scalar is `uint` at
> 4 bytes, so alignment must be >= 4; for `uint64_t`, alignment must be >= 8).
> Incorrect alignment specifications result in undefined behavior.

#### Shader Stage and Feature Compatibility

The `AlignedLoad`/`AlignedStore` functions are independent of shader stage and
can be used in any shader type (vertex, pixel, compute, geometry, hull, domain,
etc.). The alignment information is processed during compilation and embedded
into the generated DXIL, making it available to backend compilers for
optimization regardless of the target shader stage.

The feature works orthogonally to existing HLSL features without introducing
conflicts or dependencies:

* **Register binding**: Fully compatible with `register(t#)` for SRV and
  `register(u#)` for UAV binding
* **Resource binding**: Compatible with all binding methods: root descriptors,
  descriptor tables, and descriptor heap indexing
* **Buffer access patterns**: The `AlignedLoad`/`AlignedStore` functions can be
  used selectively for individual operations, allowing different alignment
  specifications for different accesses to the same buffer
* **Existing syntax**: Does not interfere with existing buffer declarations,
  method calls, or operator usage

#### Alignment Validation

The compiler validates that `AlignedLoad`/`AlignedStore` function `alignment`
parameters meet the basic constraints (power-of-two, greater-than or equal-to
the largest scalar type size, and less-than or equal-to 4096). The application
is responsible for ensuring the effective address meets the specified absolute
alignment requirement. See [DXIL Diagnostic Changes](#dxil-diagnostic-changes)
for more details.

#### HLSL Compatibility

This feature maintains source code compatibility with existing HLSL. The new
`AlignedLoad`/`AlignedStore` functions are additional functionality that
applications can opt into when they have alignment guarantees to communicate.
Existing buffer declarations and access operations continue to compile and
execute correctly without any changes.

#### Common Usage Patterns

This section demonstrates real-world scenarios where buffer alignment features
provide significant benefits:

##### Structure-of-Arrays Layout

```cpp
RWByteAddressBuffer MyBuffer;  // Buffer allocated with 32-byte alignment

struct MyStruct {
    uint3 a;    // 12 bytes
    uint3 b;    // 12 bytes
    uint2 c;    //  8 bytes
};  // Total: 32 bytes per structure

uint baseOffset = GetIndex() * 32;  // Application ensures 32-byte aligned offsets

// Alignment must be power-of-two and >= largest scalar type size
// uint3 and uint2 have largest scalar type of uint (4 bytes), so alignment must be >= 4
uint3 a = MyBuffer.AlignedLoad<uint3>(baseOffset +  0, 32); // 32-byte aligned
uint3 b = MyBuffer.AlignedLoad<uint3>(baseOffset + 12,  4); // 4-byte aligned (largest power-of-two dividing 12)
uint2 c = MyBuffer.AlignedLoad<uint2>(baseOffset + 24,  8); // 8-byte aligned (largest power-of-two dividing 24)
```

##### Tightly Packed Data Processing

```cpp
RWByteAddressBuffer MyBuffer;  // Buffer allocated with 64-byte alignment

// Process 16-byte chunks of data from buffer
[unroll] for (uint i = 0; i < NUM_CHUNKS; ++i) {
    // Each chunk address is at least 16-byte aligned
    uint4 chunk = MyBuffer.AlignedLoad<uint4>(i * 16, 16);
}
```

##### Matrix Data Layout

```cpp
RWByteAddressBuffer MyBuffer;  // Buffer allocated with 64-byte alignment

// 4x4 matrices stored row-major, each row is 16 bytes
uint matrixOffset = GetMatrixIndex() * 64;  // Application ensures 64-byte aligned offsets

// Store matrix rows - all alignments are multiples of 4
MyBuffer.AlignedStore<uint4>(matrixOffset +  0, 64, row0);  // Row0 is 64-byte aligned
MyBuffer.AlignedStore<uint4>(matrixOffset + 16, 16, row1);  // Row1 is 16-byte aligned
MyBuffer.AlignedStore<uint4>(matrixOffset + 32, 32, row2);  // Row2 is 32-byte aligned
MyBuffer.AlignedStore<uint4>(matrixOffset + 48, 16, row3);  // Row3 is 16-byte aligned
```

#### Performance Considerations

This section explains how alignment choices impact performance and provides
guidance for optimal usage:

##### Memory Access Patterns

```cpp
RWByteAddressBuffer MyBuffer;

// Good: Higher alignment enables vectorization when application can guarantee it
uint4 vector1 = MyBuffer.AlignedLoad<uint4>(offset1, 16);
uint4 vector2 = MyBuffer.AlignedLoad<uint4>(offset2, 16);

// Suboptimal but valid: Lower alignment may require scalar operations
uint4 vector3 = MyBuffer.AlignedLoad<uint4>(offset3, 4);
```

##### Vectorization Opportunities

```cpp
RWByteAddressBuffer MyBuffer;  // Buffer allocated with 16-byte alignment

// Sequential, non-uniform 16-byte aligned loads
uint4 a = MyBuffer.AlignedLoad<uint4>(NURI(baseOffset +  0), 16);
uint4 b = MyBuffer.AlignedLoad<uint4>(NURI(baseOffset + 16), 16);
uint4 c = MyBuffer.AlignedLoad<uint4>(NURI(baseOffset + 32), 16);
uint4 d = MyBuffer.AlignedLoad<uint4>(NURI(baseOffset + 48), 16);
// Backend may combine these into more optimal vector load operations
```

### Interchange Format Additions

This proposal requires no changes to DXIL or SPIR-V intermediate
representations. Instead, it leverages existing alignment infrastructure already
present in both formats for operation-level alignment specification. The
implementation utilizes these existing fields to enable more efficient
operations, including vectorization and optimized memory access patterns.

#### Existing DXIL Infrastructure

The proposal leverages existing DXIL alignment parameters in buffer operations:

#### Buffer Operation Alignment (AlignedLoad/AlignedStore functions)

The following DXIL operations already include alignment parameters that
currently default to largest scalar type size. These parameters expect
**absolute alignment** and will be populated with values from the
`AlignedLoad`/`AlignedStore` function calls:

* `dx.op.rawBufferLoad.*`
* `dx.op.rawBufferStore.*`
* `dx.op.rawBufferVectorLoad.*`
* `dx.op.rawBufferVectorStore.*`

##### Example DXIL Usage

The following example illustrates how DXC passes the absolute alignment to DXIL
operations.

**HLSL Source:**

```cpp
RWByteAddressBuffer MyBuffer : register(u0);

// Application specifies 16-byte absolute alignment
// uint4 has largest scalar type of uint (4 bytes), 16 is multiple of 4
uint4 data = MyBuffer.AlignedLoad<uint4>(offset, 16);
```

**Generated DXIL:**

```llvm
  ; RawBufferLoad(srv,index,elementOffset,mask,alignment)
  %27 = call %dx.types.ResRet.f32 @dx.op.rawBufferLoad.f32(
    i32 139,
    %dx.types.Handle %26,
    i32 %25,
    i32 undef,
    i8 15,
    i32 16      ; DXC passes alignment parameter directly: 16 bytes (absolute)
    )
```

#### SPIR-V Compatibility

SPIR-V buffer operations similarly include alignment parameters that can be
populated with the alignment information from `AlignedLoad`/`AlignedStore`
function parameters. Individual buffer access operations can specify
per-operation alignment requirements through existing SPIR-V alignment
parameters, requiring no new SPIR-V instructions or capabilities.

**Note**: Like DXIL, SPIR-V alignment parameters expect **absolute alignment**
values. The compiler passes the alignment parameter value directly from the HLSL
function to the SPIR-V operation.

### DXIL Diagnostic Changes

This proposal introduces several new compile-time error conditions when
`AlignedLoad`/`AlignedStore` functions are used incorrectly.

#### New Error Conditions

* **E1001: Unsupported buffer type for AlignedLoad/AlignedStore functions**
  * **Condition**: `AlignedLoad`/`AlignedStore` functions used on unsupported
    buffer types
  * **Trigger**: Using alignment functions on `[RW]Buffer`,
    `[RW]StructuredBuffer`, `ConstantBuffer`, `cbuffer`, or `Texture*` resources
  * **Message**: `"AlignedLoad/AlignedStore functions cannot be used with
    <type>. Supported types are ByteAddressBuffer and RWByteAddressBuffer"`
  * **Example**:

    ```cpp
    Texture2D MyTexture;
    // Error: unsupported type
    uint4 data = MyTexture.AlignedLoad<uint4>(0, 16);

    Buffer<uint4> TypedBuffer;
    // Error: unsupported type
    uint4 data = TypedBuffer.AlignedLoad<uint4>(0, 16);
    ```

* **E1002: Invalid alignment value**
  * **Condition**: Alignment value is not a compile-time constant, not a
    power-of-two, or outside valid range
  * **Trigger**: Using variable or runtime-computed alignment values, or values
    that violate constraints
  * **Message**: `"Alignment values require compile-time constant power-of-two
    values that are >= largest scalar type size and <= 4096"`
  * **Example**:

    ```cpp
    ByteAddressBuffer MyBuffer;

    int dynamicAlign = calculateAlignment();
    // Error: not a compile-time constant
    uint4 data = MyBuffer.AlignedLoad<uint4>(0, dynamicAlign);

    // Error: not a power-of-two
    uint4 data1 = MyBuffer.AlignedLoad<uint4>(0, 3);

    // Error: less than largest scalar type size (uint = 4 bytes)
    uint4 data2 = MyBuffer.AlignedLoad<uint4>(0, 2);

    // Error: greater than 4096
    uint4 data3 = MyBuffer.AlignedLoad<uint4>(0, 8192);
    ```

* **E1003: Alignment parameter less than scalar type size**
  * **Condition**: Alignment parameter is less than the largest scalar type size
    in the aggregate type
  * **Trigger**: Violates HLSL specification requirement that alignment must be
    greater-than or equal-to the largest scalar type size
  * **Message**: `"Alignment parameter of <value> bytes must be >= the largest
    scalar type size <scalar_size> bytes for <type> element type"`
  * **Example**:

    ```cpp
    ByteAddressBuffer MyBuffer;

    // Valid: alignment = 8, largest scalar type (uint64_t) is 8 bytes
    uint64_t data1 = MyBuffer.AlignedLoad<uint64_t>(0, 8);  // Valid: 8 >= 8

    // Error: alignment = 4, but largest scalar type (uint64_t) is 8 bytes
    uint64_t data2 = MyBuffer.AlignedLoad<uint64_t>(0, 4);  // Error: 4 < 8

    // Valid: alignment = 16, largest scalar type (uint) is 4 bytes
    uint4 data3 = MyBuffer.AlignedLoad<uint4>(0, 16);  // Valid: 16 >= 4

    // Valid: alignment = 4, largest scalar type (uint) is 4 bytes
    uint4 data4 = MyBuffer.AlignedLoad<uint4>(0, 4);  // Valid: 4 >= 4
    ```

#### New Warning Conditions

No new warnings are introduced by this proposal beyond what is already present
in the HLSL compiler.

#### No Existing Errors Removed

This proposal does not remove any existing error or warning conditions.

### Runtime Validation Changes

This proposal introduces runtime validation for alignment mismatches that can
only be detected during shader execution. This proposal does not change any
existing validation conditions.

#### GPU-Based Validation

When GPU-Based Validation is enabled, the following runtime checks are
performed:

* **V1001: Buffer operation alignment mismatch**
  * **Condition**: Buffer access operation does not meet the specified alignment
    requirement
  * **Detection**: During buffer load/store operations when the effective
    address (`base address + offset`) violates the alignment specified in the
    `AlignedLoad`/`AlignedStore` function call
  * **Action**: GPU-Based Validation reports operation-specific alignment
    violations
  * **Message**: `"Buffer operation at address 0x<address> violates specified
    alignment of <value> bytes. Address is only aligned to <actual> bytes"`
  * **Example Scenarios**:

    ```cpp
    ByteAddressBuffer MyBuffer : register(t0);

    // Scenario 1: Application incorrectly specified alignment
    // Buffer base address: 0x10000000
    // Offset: 0x0C (12)
    uint4 data1 = MyBuffer.AlignedLoad<uint4>(0x0C, 16);  // Claims 16-byte alignment
    // Effective address: 0x1000000C (only 4-byte aligned, but 16-byte alignment specified)
    // V1001 validation error: "Buffer operation at address 0x1000000C violates specified
    // alignment of 16 bytes. Address is only aligned to 4 bytes"

    // Scenario 2: Calculation error leading to misalignment
    // Buffer base address: 0x10000000
    uint someIndex = 3;
    uint calculatedOffset = someIndex * 12;  // 36 = 0x24, only 4-byte aligned
    uint4 data2 = MyBuffer.AlignedLoad<uint4>(calculatedOffset, 16);  // Claims 16-byte alignment
    // Effective address: 0x10000024 (only 4-byte aligned, but 16-byte alignment specified)
    // V1001 validation error: "Buffer operation at address 0x10000024 violates specified
    // alignment of 16 bytes. Address is only aligned to 4 bytes"

    // Scenario 3: Store operation alignment violation
    RWByteAddressBuffer WriteBuffer : register(u0);
    // Buffer base address: 0x20000000
    // Offset: 0x06 (6)
    WriteBuffer.AlignedStore<uint4>(0x06, 16, someFloat4);  // Claims 16-byte alignment
    // Effective address: 0x20000006 (only 2-byte aligned, but 16-byte alignment specified)
    // V1001 validation error: "Buffer operation at address 0x20000006 violates specified
    // alignment of 16 bytes. Address is only aligned to 2 bytes"
    ```

#### Behavior Without GPU-Based Validation

When GPU-Based Validation is **not** enabled:

* **Undefined Behavior**: Buffer accesses that violate declared alignment
  requirements result in undefined behavior
* **No Runtime Checks**: The system performs no validation of alignment
  requirements during execution
* **Implementation Dependent**: The actual behavior depends on hardware and
  driver implementation details
* **Potential Consequences**: May include incorrect results, performance
  degradation, or in extreme cases, hardware exceptions

### Runtime Information

This proposal leverages existing DXIL infrastructure and requires no additional
runtime processing beyond what is already provided by the Direct3D 12 runtime
and driver stack.

## Testing

Testing should focus on DXC unit level tests to verify correct DXIL codegen for
`AlignedLoad`/`AlignedStore` functions, including proper pass-through of
alignment parameter values to DXIL operation alignment parameters, and
validation that alignment parameters are multiples of the largest scalar type
size.

Diagnostic testing should verify all new error conditions trigger correctly with
appropriate error messages for invalid usage patterns, including:

* Alignment values that are not powers-of-two
* Alignment values that are less than the largest scalar type size
* Alignment values that are greater than 4096
* Non-constant alignment values

Runtime validation testing should confirm GPU-Based Validation properly detects
alignment violations when enabled.

An HLK test should verify that memory reads and writes occur at correct
addresses when `AlignedLoad`/`AlignedStore` functions are used with various
alignment values (all being multiples of the scalar type size), mixed usage of
aligned and regular buffer operations, and ensuring backend compilers receive
accurate absolute alignment information for optimization purposes.

## Alternatives considered

Two alternative proposals have been considered for addressing buffer alignment
optimization in HLSL.

1. The `alignas` proposal introduces a comprehensive C++-compatible alignment
specifier that can be applied to both structure declarations and structure
members, providing a general-purpose alignment solution across HLSL for
`[RW]StructuredBuffer` objects. While this approach aligns well with C++
standards and offers broader functionality, it does not address
`[RW]ByteAddressBuffer` object operations for non-structures.

2. The `RootViewAlignment` proposal takes the opposite approach by adding a
specific `D3D12_ROOT_DESCRIPTOR_FLAG_DATA_ALIGNED_16BYTE` flag to the existing
root signature API to communicate 16-byte alignment guarantees. However, this
approach has been generally rejected as it represents a narrow, API-specific
solution that adds complexity to legacy interfaces that may be replaced in the
future.

3. A `BaseAlignment` attribute on buffer declarations combined with relative
offset alignment in `AlignedLoad`/`AlignedStore` functions was considered. This
approach separates buffer base address alignment from individual operation
offset alignment, allowing the compiler to calculate the final effective
alignment. While this provides some composability benefits, it adds complexity
by requiring two separate alignment specifications and may be less intuitive for
developers who must reason about the interaction between base and offset
alignment.

This proposal uses absolute alignment specification, placing full responsibility
on the application to ensure alignment correctness, but providing direct control
over optimization hints. The approach leverages existing DXIL infrastructure
while keeping the mental model simple: developers specify the exact alignment of
the effective address for each operation. It also does not preclude or conflict
with the addition of `alignas` in future versions of HLSL.

## Acknowledgments (Optional)

* Anupama Chandrasekhar (NVIDIA)
* Justin Holewinski (NVIDIA)
* Tex Riddell (Microsoft)
* Amar Patel (Microsoft)
