<!-- {% raw %} -->

# Buffer Pointers in HLSL With vk::BufferPointer

*   Author(s): [Greg Fischer](https://github.com/greg-lunarg)
*   Sponsor(s): [Chris Bieneman](https://github.com/llvm-beanz),
    [Steven Perron](https://github.com/s-perron),
    [Diego Novillo](https://github.com/dnovillo)
*   Status: **Accepted**
*   Planned Version: Retroactive addition to Vulkan 1.2 (requires SPIR-V 1.3.
    Some language details require HLSL 202x

## Introduction

This proposal seeks to improve tool support for Vulkan shaders doing buffer
device addressing by adding the vk::BufferPointer type to HLSL.

## Motivation

vk::RawBufferLoad() and vk::RawBufferStore are currently used to reference
physical storage buffer space. Unfortunately, use of these functions has a
number of shortcomings. One is that they generate low-level SPIR-V so that tools
such as spirv-reflect, spirv-opt and renderdoc do not have the context to
analyze and report on which members of a buffer are used in a logical manner. A
bigger problem is that the HLSL programmer must compute the physical offsets of
the members of a buffer which is error prone and difficult to maintain.

For example, here is a shader using vk::RawBufferLoad(). Note the physical
offset 16 hard-coded into the shader:

```c++
// struct GlobalsTest_t
// {
//       float4 g_vSomeConstantA;
//       float4 g_vTestFloat4;
//       float4 g_vSomeConstantB;
// };

struct TestPushConstant_t
{
      uint64_t m_nBufferDeviceAddress;  // GlobalsTest_t
};

[[vk::push_constant]] TestPushConstant_t g_PushConstants;

float4 MainPs(void) : SV_Target0
{
    float4 vTest = vk::RawBufferLoad<float4>(g_PushConstants.m_nBufferDeviceAddress + 16);

      return vTest;
}
```

The SPIR-V for this shader can be seen in Appendix A. Note the lack of logical
context for the accessed buffer i.e. no declaration for the underlying structure
GlobalsTest_t as is generated for other buffers.

There is another way to use RawBufferLoad which does allow logical selection of
the buffer fields, but it inefficiently loads the entire buffer to do it. See
https://github.com/microsoft/DirectXShaderCompiler/issues/4986.

The goal of this proposal is to have a solution that meets the following
requirements:

*   Removes the need for having to manually or automatically generate offsets to
    load structured data with BufferDeviceAddress.
*   Enables equivalent tooling functionality as is provided by the buffer
    reference feature in GLSL. Namely, tools like RenderDoc are able to
    introspect the type information such that its buffer inspection and shader
    debugger are able to properly understand and represent the type of the data.
*   Make it possible through SPIR-V reflection to determine which members of a
    struct accessed by BufferDeviceAddress are statically referenced and at what
    offset. This is already possible for other data like cbuffers in order for
    shader tooling to be able to identify which elements are used and where to
    put them.

## Proposed solution

Our solution is to add a new builtin type in the vk namespace that is a pointer
to a buffer of a given type:

```c++
template <struct S, int align>
class vk::BufferPointer {
    vk::BufferPointer(const vk::BufferPointer&);
    vk::BufferPointer& operator=(const vk::BufferPointer&);
    vk::BufferPointer(const uint64_t);
    S& Get() const;
    operator uint64_t() const;
}
```

This class represents a pointer to a buffer of type struct `S`. `align` is the
alignment in bytes of the pointer. If `align` is not specified, the alignment is
assumed to be alignof(S).

This new type will have the following operations

*   Copy assignment and copy construction - These copy the value of the pointer
    from one variable to another.
*   Dereference Method - The Get() method represents the struct lvalue reference
    of the pointer to which it is applied. The selection . operator can be
    applied to the Get() to further select a member from the referenced struct.
    The reference returned by the Get() method is supported in all APIs that
    take reference, `inout` or `out` parameters, and can be converted to an
    rvalue following standard conversion rules.
*   Two new cast operators are introduced. vk::static_pointer_cast<T, A> allows
    casting any vk::BufferPointer<SrcType, SrcAlign> to
    vk::BufferPointer<DstType, DstAlign> only if SrcType is a type derived from
    DstType. vk::reinterpret_pointer_cast<T, A> allows casting for all other
    BufferPointer types. For both casts, DstAlign <= SrcAlign must be true.
*   A buffer pointer can be constructed from a uint64_t using the constructor
    syntax vk::BufferPointer<T,A>(u).
*   A buffer pointer can be cast to a uint64_t. The cast will return the 64-bit
    address that the pointer points to.

Note the operations that are not allowed:

*   There is no default construction. Every vk::BufferPointer<T> is either
    contained in a global resource (like a cbuffer, ubo, or ssbo), or it must be
    constructed using the copy constructor.
*   There is no explicit pointer arithmetic. All addressing is implicitly done
    using the `.` operator, or indexing an array in the struct T.
*   The comparison operators == and != are not supported for buffer pointers.

Most of these restrictions are there for safety. They minimize the possibility
of getting an invalid pointer. If a buffer pointer is cast to and from a
uint64_t, then it is the responsibility of the user to make sure that a valid
pointer is generated, and that aliasing rules are followed.

If the Get() method is used on a null or invalid pointer, the behaviour is
undefined.

When used as a member in a buffer, vk::BufferPointer can be used to pass
physical buffer addresses into a shader, and address and access buffer space
with logical addressing, which allows tools such as spirv-opt, spirv-reflect and
renderdoc to be able to better work with these shaders.

For example, here is a shader using vk::BufferPointer to do the same thing as
the shader above using vk::RawBufferLoad. Note the natural, logical syntax of
the reference:

```c++

struct Globals_s
{
      float4 g_vSomeConstantA;
      float4 g_vTestFloat4;
      float4 g_vSomeConstantB;
};

typedef vk::BufferPointer<Globals_s> Globals_p;

struct TestPushConstant_t
{
      Globals_p m_nBufferDeviceAddress;
};

[[vk::push_constant]] TestPushConstant_t g_PushConstants;

float4 MainPs(void) : SV_Target0
{
      float4 vTest = g_PushConstants.m_nBufferDeviceAddress.Get().g_vTestFloat4;
      return vTest;
}

```

In SPIR-V, Globals_p would be a pointer to the physical buffer storage class.
The struct type of the push constant would contain one of those pointers. The
SPIR-V for this shader can be seen in Appendix B. Note the logical context of
the declaration and addressing of underlying struct Globals_s including Offset
decorations all Globals_s members.

## Linked Lists and Local Variables

vk::BufferPointer can be used to program a linked list of identical buffers:

```c++

// Forward declaration
typedef struct block_s block_t;
typedef vk::BufferPointer<block_t> block_p;

struct block_s
{
      float4 x;
      block_p next;
};

struct TestPushConstant_t
{
      block_p root;
};

[[vk::push_constant]] TestPushConstant_t g_PushConstants;

float4 MainPs(void) : SV_Target0
{
      block_p g_p(g_PushConstants.root);
      g_p = g_p.Get().next;
      if ((uint64_t)g_pi == 0) // Null pointer test
          return float4(0.0,0.0,0.0,0.0);
      return g_p.Get().x
}

```

Note also the ability to create local variables of type vk::BufferPointer such
as g_p which can be read, written and dereferenced.

## Design Details

### Writing Buffer Pointer Pointees

The pointees of vk::BufferPointer objects can be written as well as read. See
Appendix C for example HLSL. See Appendix D for the SPIR-V.

### Differences from C++ Pointers

vk::BufferPointer is different from a C++ pointer in that the method Get() can
and must be applied to de-reference it.

### Buffer Pointer Target Alignment

The target alignment `A` of `vk::BufferPointer<T,A>` must be at least as large
as the largest component type in the buffer pointer's pointee struct type `T` or
the compiler may issue an error.

### Buffer Pointer Data Size and Alignment

For the purpose of laying out a buffer containing a vk::BufferPointer, the data
size and alignment is that of a uint64_t.

### Buffer Pointer Pointee Buffer Layout

The pointee of a vk::BufferPointer is considered to be a buffer and will be laid
out as the user directs all buffers to be laid out through the dxc compiler. All
layouts that are supported by dxc are supported for vk::BufferPointer pointee
buffers.

### Buffer Pointer Usage

vk::BufferPointer cannot be used in Input and Output variables.

A vk::BufferPointer can otherwise be used whereever the HLSL spec does not
otherwise disallow it through listing of allowed types. Specifically, buffer
members, local and static variables, function argument and return types can be
vk::BufferPointer. Ray tracing payloads and shader buffer table records may also
contain vk::BufferPointer.

### Buffer Pointer and Semantic Annotations

Applying HLSL semantic annotations to objects of type vk::BufferPointer is
disallowed.

### Buffer Pointers and Aliasing

By default, buffer pointers are assumed to be restrict pointers as defined by
the C99 standard.

An attribute vk::aliased_pointer can be attached to a variable, function
parameter or a struct member of BufferPointer type. It is assumed that the
pointee of a BufferPointer with this attribute can overlap with the pointee of
any other BufferPointer with this attribute if they have the same pointee type
and their scopes intersect. This also means that the pointee of a BufferPointer
with this attribute does not overlap with the pointee of a default (restrict)
BufferPointer.

The result of vk::static_pointer_cast and vk::reinterpret_pointer_cast as well
as all constructors is restrict.

A pointer value can be assigned to a variable, function parameter or struct
member entity, even if the aliasing disagrees. Such an assignment is an implicit
cast of this property.

See Appendix E for example of aliasing casting.

### Buffer Pointers and Address Space

All buffer pointers are presumed to point into the buffer device address space
as defined by the Vulkan type VkDeviceAddress. See the following link for
additional detail:
https://registry.khronos.org/vulkan/specs/1.3-khr-extensions/html/vkspec.html#VkDeviceAddress.

### Buffer Pointer Availability

The following can be used at pre-processor time to determine if the current
compiler supports vk::BufferPointer: __has_feature(hlsl_vk_buffer_pointer).

### Buffer Pointers and Type Punning Through Unions

While buffer pointer types are allowed in unions, type punning with buffer
pointer types is disallowed as it is with all other types in HLSL. Specifically,
when a member of a union is defined, all other members become undefined, no
matter the types.

## SPIR-V Appendices

### Appendix A: SPIR-V for RawBufferLoad

Note the lack of logical context for the accessed buffer i.e. no declaration for
the underlying structure GlobalsTest_t as is generated for other buffers.

```

               OpCapability Shader
               OpCapability Int64
               OpCapability PhysicalStorageBufferAddresses
               OpExtension "SPV_KHR_physical_storage_buffer"
               OpMemoryModel PhysicalStorageBuffer64 GLSL450
               OpEntryPoint Fragment %MainPs "MainPs" %out_var_SV_Target0 %g_PushConstants
               OpExecutionMode %MainPs OriginUpperLeft
               OpSource HLSL 600
               OpName %type_PushConstant_TestPushConstant_t "type.PushConstant.TestPushConstant_t"
               OpMemberName %type_PushConstant_TestPushConstant_t 0 "m_nBufferDeviceAddress"
               OpName %g_PushConstants "g_PushConstants"
               OpName %out_var_SV_Target0 "out.var.SV_Target0"
               OpName %MainPs "MainPs"
               OpDecorate %out_var_SV_Target0 Location 0
               OpMemberDecorate %type_PushConstant_TestPushConstant_t 0 Offset 0
               OpDecorate %type_PushConstant_TestPushConstant_t Block
        %int = OpTypeInt 32 1
      %int_0 = OpConstant %int 0
      %ulong = OpTypeInt 64 0
   %ulong_16 = OpConstant %ulong 16
%type_PushConstant_TestPushConstant_t = OpTypeStruct %ulong
%_ptr_PushConstant_type_PushConstant_TestPushConstant_t = OpTypePointer PushConstant %type_PushConstant_TestPushConstant_t
      %float = OpTypeFloat 32
    %v4float = OpTypeVector %float 4
%_ptr_Output_v4float = OpTypePointer Output %v4float
       %void = OpTypeVoid
         %14 = OpTypeFunction %void
         %15 = OpTypeFunction %v4float
%_ptr_Function_v4float = OpTypePointer Function %v4float
%_ptr_PushConstant_ulong = OpTypePointer PushConstant %ulong
%_ptr_PhysicalStorageBuffer_v4float = OpTypePointer PhysicalStorageBuffer %v4float
%g_PushConstants = OpVariable %_ptr_PushConstant_type_PushConstant_TestPushConstant_t PushConstant
%out_var_SV_Target0 = OpVariable %_ptr_Output_v4float Output
     %MainPs = OpFunction %void None %14
         %19 = OpLabel
         %20 = OpVariable %_ptr_Function_v4float Function
         %21 = OpVariable %_ptr_Function_v4float Function
         %22 = OpAccessChain %_ptr_PushConstant_ulong %g_PushConstants %int_0
         %23 = OpLoad %ulong %22
         %24 = OpIAdd %ulong %23 %ulong_16
         %25 = OpBitcast %_ptr_PhysicalStorageBuffer_v4float %24
         %26 = OpLoad %v4float %25 Aligned 4
               OpStore %20 %26
               OpStore %21 %26
               OpStore %out_var_SV_Target0 %26
               OpReturn
               OpFunctionEnd

```

### Appendix B: SPIR-V for vk::buffer_ref

Here is the SPIR-V for this shader. Note the logical context of the declaration
and addressing of underlying struct Globals_s including Offset decorations all
Globals_s members:

```
               OpCapability Shader
               OpCapability PhysicalStorageBufferAddresses
               OpExtension "SPV_KHR_physical_storage_buffer"
               OpMemoryModel PhysicalStorageBuffer64 GLSL450
               OpEntryPoint Fragment %MainPs "MainPs" %out_var_SV_Target0 %g_PushConstants
               OpExecutionMode %MainPs OriginUpperLeft
               OpSource HLSL 600
               OpName %type_PushConstant_TestPushConstant_t "type.PushConstant.TestPushConstant_t"
               OpMemberName %type_PushConstant_TestPushConstant_t 0 "m_nBufferDeviceAddress"
               OpName %Globals_s "Globals_s"
               OpMemberName %Globals_s 0 "g_vSomeConstantA"
               OpMemberName %Globals_s 1 "g_vTestFloat4"
               OpMemberName %Globals_s 2 "g_vSomeConstantB"
               OpName %g_PushConstants "g_PushConstants"
               OpName %out_var_SV_Target0 "out.var.SV_Target0"
               OpName %MainPs "MainPs"
               OpDecorate %out_var_SV_Target0 Location 0
               OpMemberDecorate %Globals_s 0 Offset 0
               OpMemberDecorate %Globals_s 1 Offset 16
               OpMemberDecorate %Globals_s 2 Offset 32
               OpDecorate %Globals_s Block
               OpMemberDecorate %type_PushConstant_TestPushConstant_t 0 Offset 0
               OpDecorate %type_PushConstant_TestPushConstant_t Block
        %int = OpTypeInt 32 1
      %int_0 = OpConstant %int 0
      %int_1 = OpConstant %int 1
      %float = OpTypeFloat 32
    %v4float = OpTypeVector %float 4
  %Globals_s = OpTypeStruct %v4float %v4float %v4float
%_ptr_PhysicalStorageBuffer_Globals_s = OpTypePointer PhysicalStorageBuffer %Globals_s
%type_PushConstant_TestPushConstant_t = OpTypeStruct %_ptr_PhysicalStorageBuffer_Globals_s
%_ptr_PushConstant_type_PushConstant_TestPushConstant_t = OpTypePointer PushConstant %type_PushConstant_TestPushConstant_t
%_ptr_Output_v4float = OpTypePointer Output %v4float
       %void = OpTypeVoid
         %15 = OpTypeFunction %void
         %16 = OpTypeFunction %v4float
%_ptr_Function_v4float = OpTypePointer Function %v4float
%_ptr_PushConstant__ptr_PhysicalStorageBuffer_Globals_s = OpTypePointer PushConstant %_ptr_PhysicalStorageBuffer_Globals_s
%_ptr_PhysicalStorageBuffer_v4float = OpTypePointer PhysicalStorageBuffer %v4float
%g_PushConstants = OpVariable %_ptr_PushConstant_type_PushConstant_TestPushConstant_t PushConstant
%out_var_SV_Target0 = OpVariable %_ptr_Output_v4float Output
     %MainPs = OpFunction %void None %15
         %20 = OpLabel
         %23 = OpAccessChain %_ptr_PushConstant__ptr_PhysicalStorageBuffer_Globals_s %g_PushConstants %int_0
         %24 = OpLoad %_ptr_PhysicalStorageBuffer_Globals_s %23
         %25 = OpAccessChain %_ptr_PhysicalStorageBuffer_v4float %24 %int_1
         %26 = OpLoad %v4float %25 Aligned 16
               OpStore %out_var_SV_Target0 %26
               OpReturn
               OpFunctionEnd
```

### Appendix C: HLSL for Write through vk::BufferPointer

```c++

struct Globals_s
{
      float4 g_vSomeConstantA;
      float4 g_vTestFloat4;
      float4 g_vSomeConstantB;
};

typedef vk::BufferPointer<Globals_s> Globals_p;

struct TestPushConstant_t
{
      Globals_p m_nBufferDeviceAddress;
};

[[vk::push_constant]] TestPushConstant_t g_PushConstants;

float4 MainPs(void) : SV_Target0
{
      float4 vTest = float4(1.0,0.0,0.0,0.0);
      g_PushConstants.m_nBufferDeviceAddress.Get().g_vTestFloat4 = vTest;
      return vTest;
}

```

### Appendix D: SPIR-V for Write through vk::BufferPointer

```
               OpCapability Shader
               OpCapability PhysicalStorageBufferAddresses
               OpExtension "SPV_KHR_physical_storage_buffer"
               OpMemoryModel PhysicalStorageBuffer64 GLSL450
               OpEntryPoint Fragment %MainPs "MainPs" %out_var_SV_Target0 %g_PushConstants
           OpExecutionMode %MainPs OriginUpperLeft
           OpSource HLSL 600
               OpName %type_PushConstant_TestPushConstant_t "type.PushConstant.TestPushConstant_t"
               OpMemberName %type_PushConstant_TestPushConstant_t 0 "m_nBufferDeviceAddress"
               OpName %Globals_s "Globals_s"
               OpMemberName %Globals_s 0 "g_vSomeConstantA"
               OpMemberName %Globals_s 1 "g_vTestFloat4"
               OpMemberName %Globals_s 2 "g_vSomeConstantB"
               OpName %g_PushConstants "g_PushConstants"
               OpName %out_var_SV_Target0 "out.var.SV_Target0"
               OpName %MainPs "MainPs"
               OpDecorate %out_var_SV_Target0 Location 0
               OpMemberDecorate %Globals_s 0 Offset 0
               OpMemberDecorate %Globals_s 1 Offset 16
               OpMemberDecorate %Globals_s 2 Offset 32
               OpDecorate %Globals_s Block
               OpMemberDecorate %type_PushConstant_TestPushConstant_t 0 Offset 0
               OpDecorate %type_PushConstant_TestPushConstant_t Block
        %int = OpTypeInt 32 1
      %int_0 = OpConstant %int 0
      %int_1 = OpConstant %int 1
      %float = OpTypeFloat 32
    %float_1 = OpConstant %float 1
    %float_0 = OpConstant %float 0
    %v4float = OpTypeVector %float 4
          %7 = OpConstantComposite %v4float %float_1 %float_0 %float_0 %float_0
  %Globals_s = OpTypeStruct %v4float %v4float %v4float
%_ptr_PhysicalStorageBuffer_Globals_s = OpTypePointer PhysicalStorageBuffer %Globals_s
%type_PushConstant_TestPushConstant_t = OpTypeStruct %_ptr_PhysicalStorageBuffer_Globals_s
%_ptr_PushConstant_type_PushConstant_TestPushConstant_t = OpTypePointer PushConstant %type_PushConstant_TestPushConstant_t
%_ptr_Output_v4float = OpTypePointer Output %v4float
       %void = OpTypeVoid
         %15 = OpTypeFunction %void
         %16 = OpTypeFunction %v4float
%_ptr_Function_v4float = OpTypePointer Function %v4float
%_ptr_PushConstant__ptr_PhysicalStorageBuffer_Globals_s = OpTypePointer PushConstant %_ptr_PhysicalStorageBuffer_Globals_s
%_ptr_PhysicalStorageBuffer_v4float = OpTypePointer PhysicalStorageBuffer %v4float
%g_PushConstants = OpVariable %_ptr_PushConstant_type_PushConstant_TestPushConstant_t PushConstant
%out_var_SV_Target0 = OpVariable %_ptr_Output_v4float Output
     %MainPs = OpFunction %void None %15
         %20 = OpLabel
         %23 = OpAccessChain %_ptr_PushConstant__ptr_PhysicalStorageBuffer_Globals_s %g_PushConstants %int_0
         %24 = OpLoad %_ptr_PhysicalStorageBuffer_Globals_s %23
         %25 = OpAccessChain %_ptr_PhysicalStorageBuffer_v4float %24 %int_1
               OpStore %25 %7 Aligned 16
               OpStore %out_var_SV_Target0 %7
               OpReturn
               OpFunctionEnd
```

### Appendix E: HLSL for Implicit Cast of Restrict to Aliased

```c++

struct Globals_s
{
      float4 g_vSomeConstantA;
      float4 g_vTestFloat4;
      float4 g_vSomeConstantB;
};

typedef vk::BufferPointer<Globals_s> Globals_p;

struct TestPushConstant_t
{
      Globals_p m_nBufferDeviceAddress;
};

[[vk::push_constant]] TestPushConstant_t g_PushConstants;

float4 MainPs(void) : SV_Target0
{
      float4 vTest = float4(1.0,0.0,0.0,0.0);
      [[vk::aliased_pointer]] Globals_p bp0(g_PushConstants.m_nBufferDeviceAddress);
      [[vk::aliased_pointer]] Globals_p bp1(g_PushConstants.m_nBufferDeviceAddress);
      bp0.Get().g_vTestFloat4 = vTest;
      return bp1.Get().g_vTestFloat4; // Returns float4(1.0,0.0,0.0,0.0)
}

```

<!-- {% endraw %} -->
