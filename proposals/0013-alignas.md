<!-- {% raw %} -->

# HLSL alignas Specifier

* Proposal: [NNNN](NNNN-alignas.md)
* Author(s): [Mike Apodaca (NVIDIA)](https://github.com/mapodaca-nv)
* Sponsor: TBD
* Status: **Under Consideration**
* Impacted Project(s): (DXC, Clang, etc)

*During the review process, add the following fields as needed:*

* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues:
  [#2193](https://github.com/microsoft/DirectXShaderCompiler/issues/2193)

## Introduction

The proposal is to add to HLSL support for the `alignas` specifier on the
declaration of a structure and the declaration of a structure member, used by
`[RW]StructuredBuffer` declarations, and templated `ByteAddressBuffer` loads
and stores.

As additional benefits, this proposal would:  
 (a) eliminate the need for applications to add dummy elements to structures
to force specific alignments, and  
 (b) further converge HLSL and C++11 syntax.

## Motivation

Some GPUs can optimize 16-byte memory accesses for buffer loads and stores.
Unfortunately, in many instances, IHV compilers must assume 4-byte alignments
for structured buffer element accesses.

In the current specification, UAV buffer root views may be aligned to 4 bytes,
whereas as descriptors in descriptor tables must be aligned to 256 bytes.
Therefore, when an application chooses to use root views, the IHV compiler must
assume the worst-case alignment.
For some GPUs, this will disable vectorized loads and stores from memory that
require 16-byte aligned addresses.

Under consideration for future specifications, placed resource alignment
requirements may be tightened to as much as 1-byte alignment.
This change would further justify maintaining minimum alignment requirements
and additional explicit application hints.

Currently, these limitations can only be optimized using runtime monitoring and
bookkeeping of root view addresses, followed by background thread
re-compilation and re-caching of shaders.

## Proposed solution

The `alignas` specifier may be specified on the declaration of a
structure or the declaration of a structure member, when used by
`[RW]StructuredBuffer` declarations, and templated `ByteAddressBuffer` loads
and stores.

### Syntax

The following excepts from the
[C++ reference manual](https://en.cppreference.com/w/cpp/language/alignas)
would apply to HLSL.

> **alignas**( _expression_ )  
> **alignas**( _type-id_ )  
> 1. _expression_ must be an integral constant expression that evaluates to
> zero, or to a valid value for an alignment or extended alignment.
> 2. Equivalent to `alignas(alignof(type-id))`.

> The `alignas` specifier may be applied to:
> - the declaration or definition of a class;
> - the declaration of a non-bitfield class data member;

> The object or the type declared by such a declaration will have its
> alignment requirement equal to the strictest (largest) non-zero expression
> of all `alignas` specifiers used in the declaration, unless it would weaken
> the natural alignment of the type.

> If the strictest (largest) `alignas` on a declaration is weaker than the
> alignment it would have without any `alignas` specifiers (that is, weaker
> than its natural alignment or weaker than `alignas` on another declaration
> of the same object or type), the program is ill-formed.

> Invalid non-zero alignments, such as `alignas(3)` are ill-formed.

> Valid non-zero alignments that are weaker than another `alignas` on the same
> declaration are ignored.

> `alignas(0)` is always ignored.

### Example Usage

```c++
///////////////////////////////////////////////////////////////////////////////
// common.h
// every object of type Foo will be aligned to 16-bytes
struct alignas(16) Foo
{ 
    float3 bar; 
    alignas(16) uint baz; // 16-byte aligned member
}; 
static_assert(sizeof(Foo) == 32);

///////////////////////////////////////////////////////////////////////////////
// compute.hlsl
#include "common.h"
ByteAddressBuffer InBuf : register(t0);
RWStructuredBuffer<Foo> OutBuf : register(u0); 

[numthreads(1, 1, 1)]
void main(uint gid : SV_GroupID) 
{ 
    Foo tmp = InBuf.Load<Foo>(gid * sizeof(Foo)); // 16-byte aligned reads
    OutBuf[gid].bar = tmp.bar;      // 16-byte aligned write
    OutBuf[gid].baz = tmp.baz + 1;  // 16-byte aligned write
    ...
}

///////////////////////////////////////////////////////////////////////////////
// app.cpp
#include "common.h"
void main()
{
    // every element of vector is aligned to 16-bytes
    std::vector<Foo> vecFoo(1K);
    ...

    ComPtr<ID3D12Resource> uavBuffer;
    ThrowIfFailed(device->CreateCommittedResource(
        &CD3DX12_HEAP_PROPERTIES(D3D12_HEAP_TYPE_DEFAULT),
        D3D12_HEAP_FLAG_NONE,
        &CD3DX12_RESOURCE_DESC::Buffer(vecFoo.size() * sizeof(Foo),
          D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS),
        D3D12_RESOURCE_STATE_COMMON,
        nullptr,
        IID_PPV_ARGS(&uavBuffer)));
    ...

    // SRV GPUVA guaranteed to be 16-byte aligned
    commandList->SetComputeRootShaderResourceView(0,
        uavBuffer->GetGPUVirtualAddress() + 1 * sizeof(Foo));

    // UAV GPUVA guaranteed to be 16-byte aligned
    commandList->SetComputeRootUnorderedAccessView(0,
        uavBuffer->GetGPUVirtualAddress() + 3 * sizeof(Foo));

    commandList->Dispatch(32, 1, 1);
}
```

### DXIL

The structure base alignment hint needs to be passed down to IHV compiler
via DXIL metadata.

```diff
  target datalayout = "e-m:e-p:32:32-i1:32-i8:32-i16:32-i32:32-i64:64-f16:32-f32:32-f64:64-n8:16:32:64"
  target triple = "dxil-ms-dx"

  %dx.types.Handle = type { i8* }
  %dx.types.ResRet.f32 = type { float, float, float, float, i32 }
  %dx.types.ResRet.i32 = type { i32, i32, i32, i32, i32 }
  %struct.ByteAddressBuffer = type { i32 }
  %"class.RWStructuredBuffer<Foo>" = type { %struct.Foo }
- %struct.Foo = type { <3 x float>, i32 }
+ %struct.Foo = type { <3 x float>, i32, i32, <3 x i32> } ; implicit padding (tbd - may not be needed)

  define void @main() {
    %1 = call %dx.types.Handle @dx.op.createHandle(i32 57, i8 1, i32 0, i32 0, i1 false)  ; CreateHandle(resourceClass,rangeId,index,nonUniformIndex)
    %2 = call %dx.types.Handle @dx.op.createHandle(i32 57, i8 0, i32 0, i32 0, i1 false)  ; CreateHandle(resourceClass,rangeId,index,nonUniformIndex)
    %3 = call i32 @dx.op.groupId.i32(i32 94, i32 0)  ; GroupId(component)
-   %4 = shl i32 %3, 4
+   %4 = shl i32 %3, 5
    %5 = call %dx.types.ResRet.f32 @dx.op.bufferLoad.f32(i32 68, %dx.types.Handle %2, i32 %4, i32 undef)  ; BufferLoad(srv,index,wot)
    %6 = extractvalue %dx.types.ResRet.f32 %5, 0
    %7 = extractvalue %dx.types.ResRet.f32 %5, 1
    %8 = extractvalue %dx.types.ResRet.f32 %5, 2
-   %9 = or i32 %4, 12
+   %9 = or i32 %4, 16
    %10 = call %dx.types.ResRet.i32 @dx.op.bufferLoad.i32(i32 68, %dx.types.Handle %2, i32 %9, i32 undef)  ; BufferLoad(srv,index,wot)
    %11 = extractvalue %dx.types.ResRet.i32 %10, 0
-   call void @dx.op.bufferStore.f32(i32 69, %dx.types.Handle %1, i32 %3, i32 0, float %6, float %7, float %8, float undef, i8 7)  ; BufferStore(uav,coord0,coord1,value0,value1,value2,value3,mask)
+   call void @dx.op.bufferStore.f32(i32 69, %dx.types.Handle %1, i32 %3, i32 0, float %6, float %7, float %8, float undef, i8 7, i32 16)  ; +alignment
    %12 = add i32 %11, 1
-   call void @dx.op.bufferStore.i32(i32 69, %dx.types.Handle %1, i32 %3, i32 12, i32 %12, i32 undef, i32 undef, i32 undef, i8 1)  ; BufferStore(uav,coord0,coord1,value0,value1,value2,value3,mask)
+   call void @dx.op.bufferStore.i32(i32 69, %dx.types.Handle %1, i32 %3, i32 16, i32 %12, i32 undef, i32 undef, i32 undef, i8 1, i32 16)  ; +alignment
    ret void
  }

  ; Function Attrs: nounwind readnone
  declare i32 @dx.op.groupId.i32(i32, i32) #0

  ; Function Attrs: nounwind readonly
  declare %dx.types.Handle @dx.op.createHandle(i32, i8, i32, i32, i1) #1

  ; Function Attrs: nounwind readonly
  declare %dx.types.ResRet.i32 @dx.op.bufferLoad.i32(i32, %dx.types.Handle, i32, i32) #1

  ; Function Attrs: nounwind readonly
  declare %dx.types.ResRet.f32 @dx.op.bufferLoad.f32(i32, %dx.types.Handle, i32, i32) #1

  ; Function Attrs: nounwind
  declare void @dx.op.bufferStore.f32(i32, %dx.types.Handle, i32, i32, float, float, float, float, i8) #2

  ; Function Attrs: nounwind
  declare void @dx.op.bufferStore.i32(i32, %dx.types.Handle, i32, i32, i32, i32, i32, i32, i8) #2

  attributes #0 = { nounwind readnone }
  attributes #1 = { nounwind readonly }
  attributes #2 = { nounwind }

  !llvm.ident = !{!0}
  !dx.version = !{!1}
  !dx.valver = !{!2}
  !dx.shaderModel = !{!3}
  !dx.resources = !{!4}
  !dx.entryPoints = !{!10}

  !0 = !{!"dxc(private) 1.7.0.4219 (staging-sm-6.8, c468d525d)"}
  !1 = !{i32 1, i32 0}
  !2 = !{i32 1, i32 8}
  !3 = !{!"cs", i32 6, i32 0}
  !4 = !{!5, !7, null, null}
  !5 = !{!6}
  !6 = !{i32 0, %struct.ByteAddressBuffer* undef, !"", i32 0, i32 0, i32 1, i32 11, i32 0, null}
- !7 = !{!8}
+ !7 = !{i32 1, i32 16} ; alignment
  !8 = !{i32 0, %"class.RWStructuredBuffer<Foo>"* undef, !"", i32 0, i32 0, i32 1, i32 12, i1 false, i1 false, i1 false, !9}
- !9 = !{i32 1, i32 16} ; stride
+ !9 = !{i32 1, i32 32, i32 16} ; stride and alignment
  !10 = !{void ()* @main, !"main", null, !4, !11}
  !11 = !{i32 0, i64 16, i32 4, !12}
  !12 = !{i32 1, i32 1, i32 1}
```

### Device Compatibility

Any device that supports SM6.XX+ is expected to support this alignment hint.

### Device Behavior

In order to avoid undefined behavior, or inconsistent behavior across IHV
devices, the device **must** ignore (e.g., mask out) any address value bits
smaller than the alignment specified when accessing memory.
The device cannot ignore the alignment even if it is larger than what the
device supports or optimizes for the operation.

> **Remark**: it is expected that an IHV driver implementation could perform
> this address mask during root signature binding rather than during shader
> execution.  As such, this feature requires a driver update and cannot be
> retroactively supported by existing, shipped drivers that support an older
> shader model.

### Validation

The DXIL compiler may issue errors or warnings for ill-formed or ignored
alignment specifiers, respectively, in accordance with the syntax rules above.
Since the compiler is not aware of the calculation of the GPUVA itself,
it cannot issue errors or warnings for the value not being properly aligned.

Runtime validation may check if the GPUVA value provided to
`Set[Graphics|Compute]RootUnorderedAccessView` meets the base alignment
requirements, as specified in the shader, when the `Draw` or `Dispatch` call
is added to the command list.

Tests may be authored to validate that the device properly ignores address
value bits smaller than the alignment specified.

## Alternatives considered (Optional)


## Acknowledgments (Optional)

* Contributor(s):
  + [Anupama Chandrasekhar (NVIDIA)](https://github.com/anupamachandra)
  + [Justin Holewinski (NVIDIA)](https://github.com/jholewinski)

<!-- {% endraw %} -->
