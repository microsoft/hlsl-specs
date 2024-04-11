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
into metadata to express the layout and things like static sampler, root 
flags, space and NumDescriptors in LLVM IR.

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

The default root signature version number is 2 which maps to rootsig_1_1.
With option -force-rootsig-ver rootsig_1_0 could make it to 1.

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

* LLVM IR for root signature saved in metadata.

```

  ; named metadata for entry root signature
  !hlsl.entry.rootsignatures = !{!2}
  …
  !2 = !{ptr @main, !3}

  !3 = !{i32 2, i32 3, !4, !15}

  !4 = !{!5, !6, !7, !8, !12, !14}

  !5 = !{i32 2, i32 0, i32 0, i32 1, i32 8}

  !6 = !{i32 3, i32 0, i32 0, i32 0, i32 0}

  !7 = !{i32 4, i32 0, i32 0, i32 0, i32 0}

  !8 = !{i32 0, i32 0, !9, !10, !11}
  !9 = !{i32 2, i32 1, i32 1, i32 0, i32 0, i32 -1}
  !10 = !{i32 0, i32 8, i32 1, i32 0, i32 1, i32 -1}
  !11 = !{i32 1, i32 -1, i32 1, i32 0, i32 1, i32 -1}

  !12 = !{i32 0, i32 0, !13}
  !13 = !{i32 3, i32 4, i32 0, i32 1, i32 0, i32 -1}

  !14 = !{i32 1, i32 0, i32 10, i32 0, i32 3}

  !15 = !{!16, !17}
  !16 = !{i32 85, i32 1, i32 1, i32 1, float 0.000000e+00, i32 16, i32 4, i32 2, float 0.000000e+00, float 0x47EFFFFFE0000000, i32 1, i32 0, i32 0}
  !17 = !{i32 21, i32 3, i32 1, i32 1, float 0.000000e+00, i32 16, i32 4, i32 2, float 0.000000e+00, float 0x47EFFFFFE0000000, i32 2, i32 0, i32 0}

```

* Metadata format

Root Signature
| | Version | Flag | RootParameters | StaticSamplers |
|-| --- | --- | --- | --- |
| !3 | i32 2 | i32 3 | !4 | !15 |

RootConstant
| | ParameterType | Visibility | Register | Space | Num32BitValues |
|-| --- | --- | --- | --- | --- |
| !14 | i32 1 |  i32 0 | i32 10 | i32 0 | i32 3 |

RootDescriptor
| | ParameterType | Visibility | Register | Space | Flags |
|-| --- | --- | --- | --- | --- |
| !5 | i32 2 |  i32 0 | i32 0 | i32 1 | i32 8 |
| !6 | i32 3 |  i32 0 | i32 0 | i32 0 | i32 0 |
| !7 | i32 4 |  i32 0 | i32 0 | i32 0 | i32 0 |

DescriptorTable
| | ParameterType | Visibility | DescriptorRanges
|-| --- | --- | --- | 
| !8 | i32 0 |  i32 0 | !9, !10, !11 |
| !12 | i32 0 |  i32 0 | !13 |

DescriptorRange
| | RangeType | NumDescriptors | BaseShaderRegister | Space | Flags | Offset |
|-| --- | --- | --- | --- | --- | --- |
| !9 | i32 2 | i32 1 | i32 1 | i32 0 | i32 0 | i32 -1 |
| !10 | i32 0 | i32 8 | i32 1 | i32 0 | i32 1 | i32 -1 |
| !11 | i32 1 | i32 -1 | i32 1 | i32 0 | i32 1 | i32 -1 |
| !13 | i32 3 | i32 4 | i32 0 | i32 1 | i32 0 | i32 -1 |

StaticSampler

|| Filter | AddressU | AddressV | AddressW | MipLODBias | MaxAnisotropy | ComparisonFunc | BoarderColor | MinLOD | MaxLOD | Register | Space | Visibility |
| - | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| !16 | i32 85 | i32 1 | i32 1 | i32 1 | float 0.000000e+00 | i32 16 | i32 4 | i32 2 | float 0.000000e+00 | float 0x47EFFFFFE0000000 | i32 1 | i32 0 | i32 0 |
| !17 | i32 21 | i32 3 | i32 1 | i32 1 | float 0.000000e+00 | i32 16 | i32 4 | i32 2 | float 0.000000e+00 | float 0x47EFFFFFE0000000 | i32 2 | i32 0 | i32 0 |

## Alternatives considered (Optional)

* Save parsed root signature to AST. 

  This could avoid parse the root signature more than once.

  Since root signature parsing doesn't cost much, decide following the common 
  clang approach which only save the string.


## Acknowledgments (Optional)



<!-- {% endraw %} -->
