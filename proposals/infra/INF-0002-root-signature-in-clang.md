<!-- {% raw %} -->

# Implementation of Root Signatures in Clang

* Proposal: [0002](INF-0002-root-signture-in-clang.md)
* Author(s): [Xiang Li](https//github.com/python3kgae), [Damyan
  Pepper](https://github.com/damyanp)
* Sponsor: Damyan Pepper
* Status: **Under Consideration**
* Impacted Project(s): Clang

<!--
*During the review process, add the following fields as needed:*

* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues:
  [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/issues/NNNN)
  -->

## Introduction

[Root
Signatures](https://learn.microsoft.com/en-us/windows/win32/direct3d12/root-signatures-overview)
can be [specified in
HLSL](https://learn.microsoft.com/en-us/windows/win32/direct3d12/specifying-root-signatures-in-hlsl)
and included in the generated DXContainer in a binary serialized format.
Support for this functionality needs to be added to Clang.

This change proposes adding:

* New AST nodes to represent the root signature
* A metadata representation of the root signature so it can be stored in LLVM IR
* Validation and diagnostic generation for root signatures during semantic
  analysis
* Conversion of the metadata representation to the binary serialized format.

## Motivation

### What are Root Signatures?
In DirectX HLSL, resources can be associated with registers.  For example:

``` c++
StructuredBuffer<float4> b1 : register(t0);
StructuredBuffer<float4> b2 : register(t1);
StructuredBuffer<float4> bn[] : register(t2);
```

In Direct3D 12, resources can be assigned to these registers. Root Signatures
describe how these resources are set using the Direct3D API. A Root Signature
describes a list of root parameters and how they map onto registers. These Root
Signatures are all compatible with the HLSL shown above:

Three parameters - two root descriptors and a descriptor table:

```c++
"SRV(t0),"
"SRV(t1),"
"DescriptorTable(SRV(t1, numDescriptors = unbounded))"
```

This would be set with C++ code that looks like this:

```c++
cl->SetGraphicsRootShaderResourceView(0, buffer1);
cl->SetGraphicsRootShaderResourceView(1, buffer2);
cl->SetGraphicsRootDescriptorTable(2, baseDescriptor);
```

A single parameter that's a descriptor table:
```c++
"DescriptorTable(SRV(t0, numDescriptors = unbounded))"
```

This would be set with C++ code that looks like this:

```c++
cl->SetGraphicsRootDescriptorTable(0, baseDescriptor);
```

The application creates a root signature by passing a serialized root signature
blob to the
[`CreateRootSignature`](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-id3d12device-createrootsignature)
method. This root signature must then be used when creating the Pipeline State
Object and also set on the command list before setting any of the root
parameters.

### Specifying Root Signatures

A serialized root signature blob can be built in an application by using the
[`D3D12SerializeRootSignature`](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/nf-d3d12-d3d12serializerootsignature)
function. However, it is also helpful to be able to provide the shader compiler
with a root signature so that it can perform validation against it and the
shader being compiled. Also, the syntax for specifying a root signature in HLSL
can be more convenient than setting up the various structures required to do so
in C++. A compiled shader that contains a root signature can be passed to
`CreateRootSignature`.

In HLSL, Root Signatures are specified using a domain specific language as
documented
[here](https://learn.microsoft.com/en-us/windows/win32/direct3d12/specifying-root-signatures-in-hlsl).

> TODO: link to Xiang's documentation that includes the grammar

An example root signature string (see the documentation for some more extensive
samples):

```
"RootFlags(ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT), CBV(b0)"
```

A root signature can be associated with an entry point using the `RootSignature`
attribute.  eg:

```c++
[RootSignature("RootFlags(ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT), CBV(b0)")]
float4 main(float4 coord : COORD) : SV_TARGET {
    // ...
}
```

The compiler can then verify that any resources used from this entry point are
compatible with this root signature.

In addition, when using [HLSL State
Objects](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-state-object)
root signatures can also be specified using `GlobalRootSignature` and
`LocalRootSignature`, where the same string format is used with the state object. eg:

```c++
GlobalRootSignature my_global_root_signature = { "CBV(b0), SRV(t0)" };
LocalRootSignature my_local_root_signature = { "SRV(t1)" };
```

These root signatures (along with other subobjects) can be associated with
exports from a shader libary like so:

```c++
SubobjectToExportsAssociation my_association = {
    "my_global_root_signature",
    "MyMissShader"
};
```

> Note: HLSL State Objects are out of scope for this proposal, and so support
> for LocalRootSignature and GlobalRootSignature is not covered in this
> document.

#### Note on the root signature domain specific language

We have received feedback that the DSL for root signatures is not something that
every language that targets DirectX would want to adopt. For this reason we need
to ensure that our solution doesn't unnecessarily tie the non-HLSL parts to it.

### Validation and Diagnostics

As well as validating that the root signature is syntactically correct, the
compiler must also validate that the shader is compatible with the root. For
example, it must validate that the root signature binds each register that is
used by the shader. Note that only resources referenced by the entry point need
to be bound:

```c++
StructuredBuffer<float4> a : register(t0);
StructuredBuffer<float4> b : register(t1);

// valid
[RootSignature("SRV(t0)")]
float4 eg1() : SV_TARGET { return a[0]; }

// invalid: b is bound to t1 that is not bound in the root signature.
[RootSignature("SRV(t0)")]
float4 eg2() : SV_TARGET { return b[0]; } 
```

## Proposed solution

### Root Signatures in the AST

A new attribute, `HLSLRootSignatureAttr` (defined in `Attr.td`), is added to
capture the string defining the root signature. `AdditionalMembers` is used to
add a member that holds the parsed representation of the root signature.

Parsing of the root signature string happens in Sema, and some validation and
diagnostics can be produced at this stage. For example:

* is the root signature string syntactically correct?
* is the specified root signature internally consistent?
  * is the right type of register used in each parameter / descriptor range?
* is each register bound only once?
* see [Validations in Sema](#validations-in-sema) for full list

The in-memory representation is guaranteed to be valid as far as the above
checks are concerned.

The root signature AST nodes are serialized / deserialized as normal bitcode.

In the root signature DSL, a root signature is made up of a list of "root
elements". The in-memory datastructures are designed around this concept where
the RootSignature class is a vector of variants.

Example:

```c++
RootSignature[
 "RootFlags(ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT),"
 "CBV(b0, space=1),"
 "StaticSampler(s1),"
 "DescriptorTable("
 "  SRV(t0, numDescriptors=unbounded),"
 "  UAV(u5, space=1, numDescriptors=10))"
]
```

When parsed will produce a the equivalent of:

```c++
parsedRootSignature = RootSignature{
  RootFlags(ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT),
  RootCBV(0, 1), // register 0, space 1
  StaticSampler(1, 0), // register 1, space 0
  DescriptorTable({
    SRV(0, 0, unbounded), // register 0, space 0, unbounded
    UAV(5, 1, 10) // register 5, space 1, 10 descriptors
  })
};
```

### Root Signatures in the LLVM IR 

During frontend code generation an IR-based representation of the root signature
is generated from the in-memory data structures stored in the AST. This is
stored as metadata nodes, identified by named metadata. The metadata format
itself is a straightforward transcription of the in-memory data structure - so
it is a list of root elements.

See [Metadata Schema](#metadata-schema) for details.

The IR schema has been designed so that many of the things that need to be
validated during parsing can only be represented in valid way. For example, it
is not possible to have an incorrect register type for a root parameter /
descriptor range. However, it is possible to represent root signatures where
registers are bound multiple times, or where there are multiple RootFlags
entries, so subsequent stages should not assume that any given root signature in
IR is valid.


> **Open Question**: what should the named metadata be?  There's options I
> think...

Example for same root signature as above:

```llvm
; placeholder - update this once detailed design complete
!directx.rootsignatures = !{!2}
!2 = !{ptr @main, !3 }
!3 = !{ !4, !5, !6, !7 } ; reference 4 root parameters
!4 = !{ !"RootFlags", i32 1 } ; root flags, 1 is numeric value of flags
!5 = !{ !"RootCBV", i32 0, i32 1, i32 0, i32 0 } ; register 0, space 1, 0 = visiblity, 0 = flags
!6 = !{ !"StaticSampler", i32 1, i32 0, ... } ; register 1, space 0, (additional params omitted)
!7 = !{ !"DescriptorTable", i32 0, !8, !9 } ;  0 = visibility, 2 ranges,!8 and !9
!8 = !{ !"SRV", i32 0, i32 0, i32 -1, i32 0 } ; register 0, space 0, unbounded, flags 0
!9 = !{ !"UAV", i32 5, i32 1, i32 10, i32 0 } ; register 5, space 1, 10 descriptors, flags 0
```


### Code Generation

During backend code generation, the LLVM IR metadata representation of the root
signature is converted data structures that represent the root signature that
are more closely aligned to the final file format. For example, root parameters
and static samplers can be intermingled in the previous formats, but are now
separated into separate arrays at this point to aid in serializing.

Example for same root signature as above:

```c++
// placeholder - update this once detailed design complete
rootSignature = RootSignature(
  ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT,
  { // parameters
    RootCBV(0, 1),
    DescriptorTable({
      SRV(0, 0, unbounded, 0),
      UAV(5, 1, 10, 0)
    })
  },
  { // static samplers
    StaticSampler(1, 0)
  });
```

At this point, final validation is performed to ensure that the root signature
itself is valid. One key validation here is to check that each register is only
bound once in the root signature. Even though this validation has been performed
in the Clang frontend, we also need to support scenarios where the IR comes from
other frontends and so the validation must be performed here as well.

Once the root signature itself has been validated, validation is performed
against the shader to ensure that any registers that the shader uses are bound
in the root signature. This validation needs to occur after any dead-code
elimation has completed.

## Detailed design

### Validations in Sema

TODO

### Metadata Schema

TODO

### Validations during Codegen

TODO

<!--
* Is there any potential for changed behavior?
* Will this expose new interfaces that will have support burden?
* How will this proposal be tested?
* Does this require additional hardware/software/human resources?
-->

## Alternatives considered (Optional)

### Store Root Signatures as Strings

The root signature could be stored in its string form in the AST and in LLVM IR.
There's a simplicity to this, and precedant with some other attributes. However,
it does mean that there will be multiple places where the string needs to be
parsed creating challenges for code organization as well as performance
concerns.

In addition, it unnecessarily ties all parts of the system with the current root
signature DSL, which is something that should we [want to
avoid](#note-on-the-root-signature-domain-specific-language).

### Store Root Signatures in the serialized Direct3D format

Direct3D specifies a serialized format for root signatures, that we will
eventually need to generate in order to populate the DXBC container. One option
would be to generate this early on and store it in the AST / IR.

This approach was not chosen because the serialized format is not well suited to
manipulation and storage in Clang/LLVM, it loses data (eg the language allow a
"DESCRIPTOR_RANGE_OFFSET_APPEND" value that should be resolved in the serialized
format).

In addition, the specific serialized format is subject to change as the
root signature specification evolves and it seems that this is something that
Clang and LLVM should be decoupled from as much as possible.

### Introduce a HLSLRootSignatureDecl

Although the current design does not support HLSL state objects - specifically
the `LocalRootSignature` and `GlobalRootSignature` subobjects - we could
anticipate their needs and add a `HLSLRootSignatureDecl` that could be shared
between `HLSLRootSignatureAttr` and whatever AST nodes are introduces for these
subojects. The problem is that we'd need to design pretty much the entire HLSL
state objects feature to do this properly. Instead, we chose to build a complete
feature without state object support and accept that some refactoring in this
area may be necessary to share code between root signatures in attributes and
root signatures in subojects.

### Deduplicate root signatures

It's possible that the same root signature string could be presented to the
compiler multiple times. An extra layer of indirection in the parsing code could
allow us to avoid parsing the root signature multiple times.

As this would strictly be an optimization and isn't required for correctness,
this is something that will be considered if profiling shows us that
* multiple duplicate root signatures is a common scenario and
* parsing them takes a significant amount of time.

### Reused / share D3D code

We could conceivably just use the D3D12 `D3D12_VERSIONED_ROOT_SIGNATURE_DESC`
datastructures for this, rather than building our own parallel versions. Also,
we could even try and get D3D's serialization code open-sourced so we don't need
to maintain multiple implementations of it. This doesn't mesh well with LLVM
since it would be adding external dependencies. We would also need to ensure
that LLVM can be built in all the host environments it supports - this means
binary dependencies are not viable, and any existing code would likely need to
be reworked so much for portability and comformance with LLVM coding conventions
that the effort would not be worthwhile.



## Acknowledgments (Optional)


<!-- {% endraw %} -->
