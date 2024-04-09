<!-- {% raw %} -->

# Implementation of RootSignature in clang

* Proposal: [0021](0021-root-signature-in-clang.md)
* Author(s): [Xiang Li](https://github.com/python3kgae)
* Sponsor: TBD
* Status: **Under Consideration**


## Introduction

In HLSL, the [root signature](https://learn.microsoft.com/en-us/windows/win32/direct3d12/root-signatures)
defines what types of resources are bound to the graphics pipeline.

A root signature can be specified in HLSL as a [string](https://learn.microsoft.com/en-us/windows/win32/direct3d12/specifying-root-signatures-in-hlsl#an-example-hlsl-root-signature).
The string contains a collection of comma-separated clauses that describe root
signature constituent components.

## Motivation

To support root signature in clang-dxc.

## Requirements

1) Compiler must parse existing root signature grammars and provide 
diagnostics.
2) Compiler must translate textual root signatures into binary encoded 
formats.
3) Compiler must support reading and writing binary encoded root 
ignatures to and from DXContainer files.
4) Compiler must validate root signatures before emitting them.
5) Compiler must have a comprehensive test infrastructure to test all 
software components.

Non-requirements
1) Compiler is not required to validate or modify root signatures read 
from a DXContainer.

Other requirements for the overall effort that need to influence the design:
1) Enable other frontends to utilize the DirectX backend.
2) Plan for the evolution of root signatures in future versions.

## Proposed solution

The root signature in a compiler begins with a string in the root signature
attribute and ends with a serialized root signature in the DXContainer.

To report errors as early as possible, root signature string parsing should
occur in Sema.

To ensure that a used resource has a binding in the root signature, this
information should be accessible in the backend to make sure legal dxil is
generated.

A new AST node HLSLRootSignatureDecl will be added to represent the root
signature in the AST.
Assuming the cost to parse root signature string is cheap,
HLSLRootSignatureDecl will follow common Clang approach which only save the
string in the AST.

A root signature will be parsed twice, once in Sema for diagnostic and once in
clang code generation for generating the serialized root signature.
The first parsing will check register overlap and run on all root signatures
in the translation unit.
The second parsing will calculate the offset for serialized root signature and
only run on the root signature for the entry function or local/global root
signature which used in SubobjectToExportsAssociation.

HLSLRootSignatureDecl will have method to parse the string for diagnostic and
generate the SerializedRS mentioned above.

A HLSLRootSignatureAttr will be created when meet RootSignature attribute in
HLSL.
Because the RootSignature attribute in hlsl only have the string, it is easier
to add a StringArgument to save the string first.
A HLSLRootSignatureDecl will be created and added to the HLSLRootSignatureAttr
 for diagnostic and saved to the HLSLEntryRootSignatureAttr for clang 
 code generation.
The HLSLRootSignatureDecl will save StringLiteral instead StringRef for 
diagnostic.

In clang code generation, the HLSLRootSignatureAttr in AST will be translated
into a global variable with struct type to express the layout and metadata to
save things like static sampler, root flags, space and NumDescriptors in LLVM IR.

CGHLSLRuntime will generate metadata to link the global variable as root
signature for given entry function.

For case compile to a standalone root signature blob, the
HLSLRootSignatureAttr will be bind to a fake empty entry.

In the case of local or global root signatures, only the HLSLRootSignatureDecl 
will be created.

Additionally, a new AST node, SubobjectToExportsAssociationDecl, should be 
added to handle the SubobjectToExportsAssociation statement in HLSL. 
The SubobjectToExportsAssociationDecl will contain a HLSLRootSignatureDecl and 
a list of FunctionDecls.

## Detailed design


* Example root signature

```

    #define RS "RootFlags( ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT | " \
              "DENY_VERTEX_SHADER_ROOT_ACCESS), " \
              "CBV(b0, space = 1, flags = DATA_STATIC), " \
              "SRV(t0), " \
              "UAV(u0), " \
              "DescriptorTable( CBV(b1), " \
              "                 SRV(t1, numDescriptors = 8, " \
              "                     flags = DESCRIPTORS_VOLATILE), " \
              "                 UAV(u1, numDescriptors = unbounded, " \
              "                     flags = DESCRIPTORS_VOLATILE)), " \
              "DescriptorTable(Sampler(s0, space=1, numDescriptors = 4)), " \
              "RootConstants(num32BitConstants=3, b10), " \
              "StaticSampler(s1)," \
              "StaticSampler(s2, " \
              "              addressU = TEXTURE_ADDRESS_CLAMP, " \
              "              filter = FILTER_MIN_MAG_MIP_LINEAR )"

```

* Define of HLSLEntryRootSignatureAttr

```

    def HLSLEntryRootSignature: InheritableAttr {
      let Spellings = [GNU<"RootSignature">];
      let Subjects = Subjects<[HLSLEntry]>;
      let LangOpts = [HLSL];
      let Args = [StringArgument<"InputString">, DeclArgument<HLSLRootSignature, "RootSignature", 0, /*fake*/ 1>];
    }

```

* HLSLEntryRootSignatureAttr in AST.

```

    HLSLEntryRootSignatureAttr
      "RootFlags( ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT | DENY_VERTEX_SHADER_ROOT_ACCESS),
       CBV(b0, space = 1, flags = DATA_STATIC), SRV(t0), UAV(u0),
       DescriptorTable( CBV(b1), SRV(t1, numDescriptors = 8,flags = DESCRIPTORS_VOLATILE),
       UAV(u1, numDescriptors = unbounded, flags = DESCRIPTORS_VOLATILE)),
       DescriptorTable(Sampler(s0, space=1, numDescriptors = 4)),
       RootConstants(num32BitConstants=3, b10),
       StaticSampler(s1),
       StaticSampler(s2, addressU = TEXTURE_ADDRESS_CLAMP, filter = FILTER_MIN_MAG_MIP_LINEAR )"
       HLSLRootSignature 'main.RS'

```

* LLVM IR for the root signature saved in ConstantStruct.

```

  ; named metadata for entry root signature
  !hlsl.entry.rootsignatures = !{!2}
  …
  ; link the global variable to entry function
  !2 = !{ptr @main,
    %0 {
       %"dxbc::RootSignature::ContainerRootSignatureDesc" 
          { i32 2, i32 0, i32 24, i32 0, i32 96, i32 3 }, 
      [6 x %"dxbc::RootSignature::ContainerRootParameter"]  
        [%"dxbc::RootSignature::ContainerRootParameter" 
        { i32 2, i32 0, i32 200 }, 
        %"dxbc::RootSignature::ContainerRootParameter" 
        { i32 3, i32 0, i32 212 }, 
        %"dxbc::RootSignature::ContainerRootParameter" 
        { i32 4, i32 0, i32 224 }, 
        %"dxbc::RootSignature::ContainerRootParameter" 
        { i32 0, i32 0, i32 236 }, 
        %"dxbc::RootSignature::ContainerRootParameter" 
        { i32 0, i32 0, i32 316 }, 
        %"dxbc::RootSignature::ContainerRootParameter" 
        { i32 1, i32 0, i32 348 }], 
      [2 x %"dxbc::RootSignature::StaticSamplerDesc"]
         [%"dxbc::RootSignature::StaticSamplerDesc" 
           { i32 85, i32 1, i32 1, i32 1, float 0.000000e+00, i32 16, i32 4, 
             i32 2, float 0.000000e+00, float 0x47EFFFFFE0000000, i32 1, 
             i32 0, i32 0 }, 
          %"dxbc::RootSignature::StaticSamplerDesc" 
           { i32 21, i32 3, i32 1, i32 1, float 0.000000e+00, i32 16, i32 4, 
           i32 2, float 0.000000e+00, float 0x47EFFFFFE0000000, i32 2, 
           i32 0, i32 0 }], 
      %1 { 
        %"dxbc::RootSignature::ContainerRootDescriptor" 
          { i32 0, i32 1, i32 8 }, 
        %"dxbc::RootSignature::ContainerRootDescriptor" 
          zeroinitializer, 
        %"dxbc::RootSignature::ContainerRootDescriptor" 
          zeroinitializer, 
        %2 { %"dxbc::RootSignature::ContainerRootDescriptorTable" 
        { i32 3, i32 244 }, 
        [3 x %"dxbc::RootSignature::ContainerDescriptorRange"] 
         [%"dxbc::RootSignature::ContainerDescriptorRange" 
           { i32 2, i32 1, i32 1, i32 0, i32 0, i32 -1 }, 
          %"dxbc::RootSignature::ContainerDescriptorRange" 
           { i32 0, i32 8, i32 1, i32 0, i32 1, i32 -1 }, 
          %"dxbc::RootSignature::ContainerDescriptorRange" 
           { i32 1, i32 -1, i32 1, i32 0, i32 1, i32 -1 }] 
       }, 
       %3 {
           %"dxbc::RootSignature::ContainerRootDescriptorTable" 
           { i32 1, i32 324 }, 
           [1 x %"dxbc::RootSignature::ContainerDescriptorRange"] 
           [%"dxbc::RootSignature::ContainerDescriptorRange" 
             { i32 3, i32 4, i32 0, i32 1, i32 0, i32 -1 }] }, 
           %"dxbc::RootSignature::ContainerRootConstants" 
             { i32 10, i32 0, i32 3 } 
       }
      }
    }

```

* LLVM IR for root signature saved in metadata.

```

  ; named metadata for entry root signature
  !hlsl.entry.rootsignatures = !{!3}
  …
  !3 = !{ptr @main, !4}
  !4 = !{i32 2, i32 0, i32 24, i32 0, i32 96, i32 3, !5, !12, !15}
  !5 = !{!6, !7, !8, !9, !10, !11}
  !6 = !{i32 2, i32 0, i32 200}
  !7 = !{i32 3, i32 0, i32 212}
  !8 = !{i32 4, i32 0, i32 224}
  !9 = !{i32 0, i32 0, i32 236}
  !10 = !{i32 0, i32 0, i32 316}
  !11 = !{i32 1, i32 0, i32 348}
  !12 = !{!13, !14}
  !13 = !{i32 85, i32 1, i32 1, i32 1, float 0.000000e+00, i32 16, i32 4, i32 2, float 0.000000e+00, float 0x47EFFFFFE0000000, i32 1, i32 0, i32 0}
  !14 = !{i32 21, i32 3, i32 1, i32 1, float 0.000000e+00, i32 16, i32 4, i32 2, float 0.000000e+00, float 0x47EFFFFFE0000000, i32 2, i32 0, i32 0}
  !15 = !{!16, !17, !17, !18, !23, !26}
  !16 = !{i32 0, i32 1, i32 8}
  !17 = !{i32 0, i32 0, i32 0}
  !18 = !{!19}
  !19 = !{!20, !21, !22}
  !20 = !{i32 2, i32 1, i32 1, i32 0, i32 0, i32 -1}
  !21 = !{i32 0, i32 8, i32 1, i32 0, i32 1, i32 -1}
  !22 = !{i32 1, i32 -1, i32 1, i32 0, i32 1, i32 -1}
  !23 = !{!24}
  !24 = !{!25}
  !25 = !{i32 3, i32 4, i32 0, i32 1, i32 0, i32 -1}
  !26 = !{i32 10, i32 0, i32 3}

```

## Alternatives considered (Optional)

* Save parsed root signature to AST. 

  This could avoid parse the root signature more than once.

  Since root signature parsing doesn't cost much, decide following the common 
  clang approach which only save the string.


## Acknowledgments (Optional)



<!-- {% endraw %} -->
