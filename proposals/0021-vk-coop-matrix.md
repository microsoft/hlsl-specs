<!-- {% raw %} -->

# Vulkan cooperative matrix extension

*   Proposal: [0021](0021-vk-coop-matrix.md)
*   Author(s): [Steven Perron](https://github.com/s-perron)
*   Sponsor: TBD
*   Status: **Accepted**
*   Required Version: Vulkan 1.1
*   PRs: [#6720](https://github.com/microsoft/DirectXShaderCompiler/pull/6720)

## Introduction

A new type, `vk::khr::CooperativeMatrix`, with functions to act on them will be
added to allow HLSL shaders to expose
[VK_KHR_cooperative_matrix](https://registry.khronos.org/vulkan/specs/1.3-extensions/man/html/VK_KHR_cooperative_matrix.html).

## Motivation

Users have no user-friendly way to write Vulkan shaders that use cooperative
matrices. This is a useful feature that users would like to use.

## High-level description

The solution to this problem is to add a new class,
`vk::khr::CooperativeMatrix`, which will be defined in a header file
"vk/khr/cooperative_matrix.h". This class will create an object with Spir-V type
`OpTypeCooperativeMatrixKHR`. Functions are added that will expose the Spir-V
the operations that take cooperative matrices as operands. All functions are
defined to match the corresponding operations in the
(SPV_KHR_cooperative_matrix)[https://htmlpreview.github.io/?https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/KHR/SPV_KHR_cooperative_matrix.html]
extension.

To help implement `vk::khr::CooperativeMatrix`, we will also introduce a utility
class `vk::util::ArithmeticSelector`. This class will be defined in a header
file "vk/util/arithmetic_selector.h". It can be used to generate inline Spir-V
arithmetic instructions with the correct opcode for the type.

The interface for `vk::khr::CooperativeMatrix` uses enums that are defined in
the Spir-V specification. The required enums will be defined in "vk/spirv.h".

## Detailed design

### `vk::khr::CooperativeMatrix`

The `CooperativeMatrix` class will defined in a header file as a wrapper around
a `vk::SpirvType` that will expand to the appropriate SPIR-V type. This class
will have the following interface.

```c++

// The base cooperative matrix class. The template arguments correspond to the
// operands in the OpTypeCooperativeMatrixKHR instruction.
template <typename ComponentType, Scope scope, uint rows, uint columns,
CooperativeMatrixUse use>
class CooperativeMatrix {

// Apply OpSNegate or OFNegate, depending on ComponentType, in a element by element manner.
CooperativeMatrix negate();

// Apply OpIAdd or OFAdd, depending on ComponentType, in a element by element manner.
CooperativeMatrix operator+(CooperativeMatrix other);

// Apply OpISub or OFSub, depending on ComponentType, in a element by element manner.
CooperativeMatrix operator-(CooperativeMatrix other);

// Apply OpIMul or OFMul, depending on ComponentType, in a element by element manner.
CooperativeMatrix operator*(CooperativeMatrix other);

// Apply OpSDiv, OpUDiv or OFDiv, depending on ComponentType, in a element by element manner.
CooperativeMatrix operator/(CooperativeMatrix other);

// Apply OpMatrixTimesScalar in a element by element manner.
CooperativeMatrix operator*(ComponentType scalar);

// Store the cooperative matrix using OpCooperativeMatrixStoreKHR to data[i] using
// memory layout RowMajorKHR.￼
void StoreRowMajor(RWStructuredBuffer<ComponentType> data, uint32_t index);

// Store the cooperative matrix using OpCooperativeMatrixStoreKHR to data[i] using
// memory layout ColumnMajorKHR.￼
void StoreColumnMajor(RWStructuredBuffer<ComponentType> data, uint32_t index);

// Store the cooperative matrix using OpCooperativeMatrixStoreKHR to data[i] using
// memory layout RowMajorKHR and the given stride and memory access mask.
void StoreRowMajor(RWStructuredBuffer<ComponentType> data, uint32_t index,
uint32_t stride, MemoryAccessMask memoryAccessMask);

// Store the cooperative matrix using OpCooperativeMatrixStoreKHR to data[i] using
// memory layout ColumnMajorKHR and the given stride and memory access mask.
void StoreColumnMajor(RWStructuredBuffer<ComponentType> data, uint32_t index,
uint32_t stride, MemoryAccessMask memoryAccessMask);

// Loads a cooperative matrix using OpCooperativeMatrixLoadKHR from data[i] using
// memory layout RowMajorKHR.￼
template <class BufferType>
static CooperativeMatrix LoadRowMajor(BufferType buffer, uint32_t index);

// Loads a cooperative matrix using OpCooperativeMatrixLoadKHR from data[i] using
// memory layout ColumnMajorKHR.￼
template <class BufferType>
static CooperativeMatrix LoadColumnMajor(BufferType buffer, uint32_t index);

// Loads a cooperative matrix using OpCooperativeMatrixLoadKHR from data[i] using
// memory layout RowMajorKHR, and the given stride and memory access mask.
template <class BufferType>
static CooperativeMatrix
LoadRowMajor(BufferType buffer, uint32_t index, uint32_t stride,
MemoryAccessMask memoryAccessMask = MemoryAccessMaskNone);

// Loads a cooperative matrix using OpCooperativeMatrixLoadKHR from data[i] using
// memory layout ColumnMajorKHR, and the given stride and memory access mask.
template <class BufferType>
static CooperativeMatrix
LoadColumnMajor(BufferType buffer, uint32_t index, uint32_t stride,
MemoryAccessMask memoryAccessMask = MemoryAccessMaskNone);

// Returns the result of OpCooperativeMatrixLengthKHR on the current type.￼
static uint32_t GetLength();

static const bool hasSignedComponentType =
(ComponentType(0) - ComponentType(1) < ComponentType(0));
};

// Cooperative matrix that can be used in the "a" position of a multiple add instruction (r = (a * b) + c).
template <typename ComponentType, Scope scope, uint rows, uint columns>
using CooperativeMatrixA =
CooperativeMatrix<ComponentType, scope, rows, columns,
CooperativeMatrixUseMatrixAKHR>;

// Cooperative matrix that can be used in the "b" position of a multiple add instruction (r = (a * b) + c).
template <typename ComponentType, Scope scope, uint rows, uint columns>
using CooperativeMatrixB =
CooperativeMatrix<ComponentType, scope, rows, columns,
CooperativeMatrixUseMatrixBKHR>;

// Cooperative matrix that can be used in the "r" and "c" position of a multiple add instruction (r = (a * b) + c).
template <typename ComponentType, Scope scope, uint rows, uint columns>
using CooperativeMatrixAccumulator =
CooperativeMatrix<ComponentType, scope, rows, columns,
CooperativeMatrixUseMatrixAccumulatorKHR>;

// Returns the result of OpCooperativeMatrixMulAddKHR when applied to a, b, and c.
// The cooperative matrix operands are inferred, with the SaturatingAccumulationKHR bit not set.
template <typename ComponentType, Scope scope, uint rows, uint columns, uint K>
CooperativeMatrixAccumulator<ComponentType, scope, rows, columns>
cooperativeMatrixMultiplyAdd(
CooperativeMatrixA<ComponentType, scope, rows, K> a,
CooperativeMatrixB<ComponentType, scope, K, columns> b,
CooperativeMatrixAccumulator<ComponentType, scope, rows, columns> c);

// Returns the result of OpCooperativeMatrixMulAddKHR when applied to a, b, and c.
// The cooperative matrix operands are inferred, with the SaturatingAccumulationKHR bit set.
template <typename ComponentType, Scope scope, uint rows, uint columns, uint K>
CooperativeMatrixAccumulator<ComponentType, scope, rows, columns>
cooperativeMatrixSaturatingMultiplyAdd(
CooperativeMatrixA<ComponentType, scope, rows, K> a,
CooperativeMatrixB<ComponentType, scope, K, columns> b,
CooperativeMatrixAccumulator<ComponentType, scope, rows, columns> c);
```

All functions, except for `GetLength()`, are wrappers around a function with the
attribute `vk::ext_instruction`. The `GetLength()` function is a wrapper around
a builtin function, which the compiler expands the appropriate SPIR-V
instruction.

The header file will check that the targeted Vulkan version is at least Vulkan
1.1, and issue an error if it is not.

Interactions with other HLSL features are implicitly compiler errors. The
interface enforces all SPIR-V validation rules, and the compiler will issue
errors if these rules are voilated.

This will be tested by adding Spir-V codegen tests that will verify that the
correct code is generated when the header file is used.

### `vk::utils::ArithmeticSelector`

The `vk::utils::ArithmeticSelector` class is a template class that takes a base
type and has a series of static function that are implemented using inline
SPIR-V. The functions can generate arithemtic operations for the base type or a
vector of the base type.

```c++
template <class BaseType>
class ArithmeticSelector {
    template <class T> static T Negate(T a);
    template <class T> static T Add(T a, T b);
    template <class T> static T Sub(T a, T b);
    template <class T> static T Mul(T a, T b);
    template <class T> static T Div(T a, T b);
};
```

There will be template specializations for the following types:

*   `half`
*   `float`
*   `double`
*   `int16_t`
*   `uint16_t`
*   `int32_t`
*   `uint32_t`
*   `int64_t`
*   `uint64_t`

### Spir-V enums

In the header file "vk/spirv.h", the following enums are defined in the `vk`
namespace:

```c++
enum CooperativeMatrixUse {
  CooperativeMatrixUseMatrixAKHR = 0,
  CooperativeMatrixUseMatrixBKHR = 1,
  CooperativeMatrixUseMatrixAccumulatorKHR = 2,
  CooperativeMatrixUseMax = 0x7fffffff,
};

enum CooperativeMatrixLayout {
  CooperativeMatrixLayoutRowMajorKHR = 0,
  CooperativeMatrixLayoutColumnMajorKHR = 1,
  CooperativeMatrixLayoutRowBlockedInterleavedARM = 4202,
  CooperativeMatrixLayoutColumnBlockedInterleavedARM = 4203,
  CooperativeMatrixLayoutMax = 0x7fffffff,
};

enum CooperativeMatrixOperandsMask {
  CooperativeMatrixOperandsMaskNone = 0,
  CooperativeMatrixOperandsMatrixASignedComponentsKHRMask = 0x00000001,
  CooperativeMatrixOperandsMatrixBSignedComponentsKHRMask = 0x00000002,
  CooperativeMatrixOperandsMatrixCSignedComponentsKHRMask = 0x00000004,
  CooperativeMatrixOperandsMatrixResultSignedComponentsKHRMask = 0x00000008,
  CooperativeMatrixOperandsSaturatingAccumulationKHRMask = 0x00000010,
};

enum MemoryAccessMask {
  MemoryAccessMaskNone = 0,
  MemoryAccessVolatileMask = 0x00000001,
  MemoryAccessAlignedMask = 0x00000002,
  MemoryAccessNontemporalMask = 0x00000004,
  MemoryAccessMakePointerAvailableMask = 0x00000008,
  MemoryAccessMakePointerAvailableKHRMask = 0x00000008,
  MemoryAccessMakePointerVisibleMask = 0x00000010,
  MemoryAccessMakePointerVisibleKHRMask = 0x00000010,
  MemoryAccessNonPrivatePointerMask = 0x00000020,
  MemoryAccessNonPrivatePointerKHRMask = 0x00000020,
  MemoryAccessAliasScopeINTELMaskMask = 0x00010000,
  MemoryAccessNoAliasINTELMaskMask = 0x00020000,
};

enum Scope {
  ScopeCrossDevice = 0,
  ScopeDevice = 1,
  ScopeWorkgroup = 2,
  ScopeSubgroup = 3,
  ScopeInvocation = 4,
  ScopeQueueFamily = 5,
  ScopeQueueFamilyKHR = 5,
  ScopeShaderCallKHR = 6,
  ScopeMax = 0x7fffffff,
};
```
<!-- {% endraw %} -->
