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
"vk/khr/cooperative_matrix.h". This class will create an object with SPIR-V type
`OpTypeCooperativeMatrixKHR`. Functions are added that will expose the SPIR-V
operations that take cooperative matrices as operands. All functions are defined
to match the corresponding operations in the
(SPV_KHR_cooperative_matrix)[https://htmlpreview.github.io/?https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/KHR/SPV_KHR_cooperative_matrix.html]
extension.

To help implement `vk::khr::CooperativeMatrix`, we will also introduce utility
classes `vk::util::ArithmeticSelector` and `vk::util::ConversionSelector`. This
class will be defined in a header file "vk/opcode_selector.h". They can be used
to generate inline SPIR-V arithmetic and conversion instructions with the
correct opcode for the types.

The interface for `vk::khr::CooperativeMatrix` uses enums that are defined in
the SPIR-V specification. The required enums will be defined in "vk/spirv.h".

## Detailed design

### `vk::khr::CooperativeMatrix`

The `CooperativeMatrix` class will be defined in a header file as a wrapper
around a `vk::SpirvType` that will expand to the appropriate SPIR-V type. This
class will have the following interface.

```c++

// The base cooperative matrix class. The template arguments correspond to the
// operands in the OpTypeCooperativeMatrixKHR instruction.
template <typename ComponentType, Scope scope, uint rows, uint columns,
          CooperativeMatrixUse use>
class CooperativeMatrix {
  template <class NewComponentType>
  CooperativeMatrix<NewComponentType, scope, rows, columns, use> cast();

  // Apply OpSNegate or OFNegate, depending on ComponentType, in a element by
  // element manner.
  CooperativeMatrix negate();

  // Apply OpIAdd or OFAdd, depending on ComponentType, in a element by element
  // manner.
  CooperativeMatrix operator+(CooperativeMatrix other);

  // Apply OpISub or OFSub, depending on ComponentType, in a element by element
  // manner.
  CooperativeMatrix operator-(CooperativeMatrix other);

  // Apply OpIMul or OFMul, depending on ComponentType, in a element by element
  // manner.
  CooperativeMatrix operator*(CooperativeMatrix other);

  // Apply OpSDiv, OpUDiv or OFDiv, depending on ComponentType, in a element by
  // element manner.
  CooperativeMatrix operator/(CooperativeMatrix other);

  // Apply OpMatrixTimesScalar in a element by element manner.
  CooperativeMatrix operator*(ComponentType scalar);

  // Store the cooperative matrix using OpCooperativeMatrixStoreKHR to
  // data using the given memory layout, stride, and memory access mask.
  //
  // This function uses a SPIR-V pointer because HLSL does not allow grouphsared
  // memory object to be passed by reference. The pointer is a hack to get
  // around that.
  template <MemoryAccessMask memoryAccessMask, class Type>
  void Store(WorkgroupSpirvPointer<Type> data, CooperativeMatrixLayout layout,
             uint32_t stride);

  // Same as above, but uses MemoryAccessMaskNone for the memory access mask.
  template <class Type>
  void Store(WorkgroupSpirvPointer<Type> data, CooperativeMatrixLayout layout,
             uint32_t stride);

  // Store the cooperative matrix using OpCooperativeMatrixStoreKHR to
  // data[index] using the given memory layout, stride, and memory access mask.
  template <MemoryAccessMask memoryAccessMask, class Type>
  void Store(RWStructuredBuffer<Type> data, uint32_t index,
             CooperativeMatrixLayout layout, uint32_t stride);

  // Same as above, but uses MemoryAccessMaskNone for the memory access mask.
  template <class Type>
  void Store(RWStructuredBuffer<Type> data, uint32_t index,
             CooperativeMatrixLayout layout, uint32_t stride)

  // Loads a cooperative matrix using OpCooperativeMatrixStoreKHR from
  // data using the given memory layout, stride, and memory access mask.
  //
  // This function uses a SPIR-V pointer because HLSL does not allow grouphsared
  // memory object to be passed by reference. The pointer is a hack to get
  // around that.
  template <MemoryAccessMask memoryAccessMask, class Type>
  static CooperativeMatrix Load(WorkgroupSpirvPointer<Type> data,
                                CooperativeMatrixLayout layout,
                                uint32_t stride);

  // Same as above, but uses MemoryAccessMaskNone for the memory access mask.
  template <class Type>
  static CooperativeMatrix Load(WorkgroupSpirvPointer<Type> data,
                                CooperativeMatrixLayout layout,
                                uint32_t stride);

  // Loads a cooperative matrix using OpCooperativeMatrixLoadKHR from
  // data[index] using the given memory layout, stride, and memory access mask.
  template <MemoryAccessMask memoryAccessMask, class Type>
  static CooperativeMatrix Load(RWStructuredBuffer<Type> data, uint32_t index,
                                CooperativeMatrixLayout layout,
                                uint32_t stride);

  // Same as above, but uses MemoryAccessMaskNone for the memory access mask.
  template <class Type>
  static CooperativeMatrix Load(RWStructuredBuffer<Type> data, uint32_t index,
                                CooperativeMatrixLayout layout,
                                uint32_t stride);

  // Loads a cooperative matrix using OpCooperativeMatrixLoadKHR from
  // data[index] using the given memory layout, stride, and memory access mask.
  template <class Type>
  static CooperativeMatrix
  Load(StructuredBuffer<Type> data, uint32_t index,
       CooperativeMatrixLayout layout, uint32_t stride,
       MemoryAccessMask memoryAccessMask = MemoryAccessMaskNone);

  // Constructs a cooperative matrix with all values initialized to v. Note that
  // all threads in scope must have the same value for v.
  static CooperativeMatrix Splat(ComponentType v);

  // Returns the result of OpCooperativeMatrixLengthKHR on the current type.￼
  static uint32_t GetLength();

  // Functions to access the elements of the cooperative matrix. The index must
  // be less than GetLength().
  void Set(ComponentType value, uint32_t index);
  ComponentType Get(uint32_t index);

  static const bool hasSignedIntegerComponentType =
      (ComponentType(0) - ComponentType(1) < ComponentType(0));

  // clang-format off
  using SpirvMatrixType = vk::SpirvOpaqueType<
      /* OpTypeCooperativeMatrixKHR */ 4456, ComponentType,
      vk::integral_constant<uint, scope>, vk::integral_constant<uint, rows>,
      vk::integral_constant<uint, columns>, vk::integral_constant<uint, use> >;

  [[vk::ext_extension("SPV_KHR_cooperative_matrix")]]
  [[vk::ext_capability(/* CooperativeMatrixKHRCapability */ 6022)]]
  SpirvMatrixType _matrix;
  // clang-format on
};

// Cooperative matrix that can be used in the "a" position of a multiple add
// instruction (r = (a * b) + c).
template <typename ComponentType, Scope scope, uint rows, uint columns>
using CooperativeMatrixA =
    CooperativeMatrix<ComponentType, scope, rows, columns,
                      CooperativeMatrixUseMatrixAKHR>;

// Cooperative matrix that can be used in the "b" position of a multiple add
// instruction (r = (a * b) + c).
template <typename ComponentType, Scope scope, uint rows, uint columns>
using CooperativeMatrixB =
    CooperativeMatrix<ComponentType, scope, rows, columns,
                      CooperativeMatrixUseMatrixBKHR>;

// Cooperative matrix that can be used in the "r" and "c" position of a multiple
// add instruction (r = (a * b) + c).
template <typename ComponentType, Scope scope, uint rows, uint columns>
using CooperativeMatrixAccumulator =
    CooperativeMatrix<ComponentType, scope, rows, columns,
                      CooperativeMatrixUseMatrixAccumulatorKHR>;

// Returns the result of OpCooperativeMatrixMulAddKHR when applied to a, b, and
// c. The cooperative matrix operands are inferred, with the
// SaturatingAccumulationKHR bit not set.
template <typename ComponentType, Scope scope, uint rows, uint columns, uint K>
CooperativeMatrixAccumulator<ComponentType, scope, rows, columns>
cooperativeMatrixMultiplyAdd(
    CooperativeMatrixA<ComponentType, scope, rows, K> a,
    CooperativeMatrixB<ComponentType, scope, K, columns> b,
    CooperativeMatrixAccumulator<ComponentType, scope, rows, columns> c);

// Returns the result of OpCooperativeMatrixMulAddKHR when applied to a, b, and
// c. The cooperative matrix operands are inferred, with the
// SaturatingAccumulationKHR bit set.
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
errors if these rules are violated.

This will be tested by adding SPIR-V codegen tests that will verify that the
correct code is generated when the header file is used.

#### Design decisions

1.  HLSL does not allow constructors. When constructors are added, it will be
    useful to add constructors for conversions and splat.
2.  HLSL does not allow certain arithmetic operators to be overloaded, so we
    could not use those. We have implemented all that we are able to implement.
3.  The memory operations are limited to groupshared, RWStructuredBuffer, and
    StructuredBuffers.
4.  Loads from groupshared require getting the address using
    `vk::GetGroupSharedAddress` because HLSL does not allow arrays to be passed
    by reference. This is worked around by defining an opaque pointer type that
    does not have to be explicitly laid out.
5.  We do not have loads from cbuffer because they cannot be passed by
    reference. Also, the compiler will not be able to apply the correct layout
    to the opaque pointer, so the workaround used for groupshared variables will
    not work in general.
6.  The `GetLength()` cannot be implemented using a `vk::ext_instruction`
    function because the opcode expects an id of a type, and that cannot be
    defined in inline SPIR-V.
7.  The `Get` and `Set` functions are used instead of `operator[]` because
    `operator[]` returns a reference, which is not available in HLSL.
8.  We chose to default the memory operand on the load and store function to
    None. This choice was arbitrary. DXC does not support the Vulkan memory
    model, so we do not add MakePointerAvailableKHR and NonPrivatePointerKHR by
    default.
9.  For the multiply-add function, we preferred to avoid flag parameters, and we
    added multiple versions of the function. We feel this provides better
    readability. If we were to pass the operand as a parameter, it would have to
    be a template parameter. The call to the builtin requires a literal, and
    compilation fails if it is passed as a function parameter.
10. The memory access mask on loads and stores is passed in using a template for
    the same reason. We did not want to add multiple versions of the function
    because there are too many combinations. This limits the memory operands to
    a single operand, so values like `Aligned` that require an extra operand
    following the mask cannot be represented. This is a limitation because we
    cannot have variable arguments to `vk::ext_instruction` functions.

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

### `vk::utils::ConversionSelector`

The `vk::utils::ConversionSelector` class is a template class that can be used
to generate SPIR-V instructions that will convert one numerical type to another.

```c++
// The conversion selector is will be used to convert one type to another
// using the SPIR-V conversion instructions. See
// https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html#_conversion_instructions.
// SourceType and TargetType must be integer or floating point scalar type.
template <class SourceType, class TargetType> class ConversionSelector {
    // Converts an object of type S to an object of type T.
    // S must be SourceType, a vector of SourceType, or a cooperative matrix
    // of SourceType. T must be TargetType, a vector of TargetType, or a
    // cooperative matrix of TargetType. T must have the same number of
    // components as S. T is a cooperative matrix if and only if S is a
    // cooperative matrix.
    template <class T, class S> static T Convert(S a) {
      return OpConvert<T>(a);
    }
  };
```

There will be template specializations for all pairs of the following types:

*   `half`
*   `float`
*   `double`
*   `int16_t`
*   `uint16_t`
*   `int32_t`
*   `uint32_t`
*   `int64_t`
*   `uint64_t`

### SPIR-V pointers

To be able to pass a GroupShared array by reference, we introduce a new type and
function to `vk/spirv.h`.

~~~
template <typename T>
vk::WorkgroupSpirvPointer
````

This is a type with no members. An instance of this type can be created by calling

~~~

template <typename T> WorkgroupSpirvPointer<T>
GetGroupSharedAddress([[vk::ext_reference]] T v); ```

where `v` must be a object in GroupShared memory.

For example,

```
groupshared float shared_data[64];
...
WorkgroupSpirvPointer<float> scalar_ptr = vk::GetGroupSharedAddress(shared_data[0]);
WorkgroupSpirvPointer<float[64]> array_ptr = vk::GetGroupSharedAddress(shared_data);
```

Then the resulting pointers can be used in the Load and Store functions.

### SPIR-V enums

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

enum StorageClass {
  StorageClassWorkgroup = 4,
};
```

<!-- {% endraw %} -->
