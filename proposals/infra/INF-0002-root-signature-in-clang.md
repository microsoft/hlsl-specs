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
signatures to and from DXContainer files.
4) Compiler must validate root signatures before emitting them.
5) Compiler must have a comprehensive test infrastructure to test all 
software components.

Non-requirements
1) Compiler is not required to validate or modify root signatures read 
from a DXContainer.

Other requirements for the overall effort that need to influence the design:
1) Enable other frontends to utilize the DirectX backend.
2) Plan for the evolution of root signatures in future versions.

## Background

What is root signature
https://learn.microsoft.com/en-us/windows/win32/direct3d12/root-signatures

How to create root signature in hlsl
https://learn.microsoft.com/en-us/windows/win32/direct3d12/specifying-root-signatures-in-hlsl

Local/Global root signature
https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-state-object

There're different root signature in hlsl.

With RootSignature attribute.

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

    [RootSignature(RS)]
    float4 main(float4 coord : COORD) : SV_Target
    {
    …
    }

```

The other mechanism is to create a standalone root signature blob, perhaps to 
reuse it with a large set of shaders, saving space. There're shader model 
rootsig_1_0 androotsig_1_1 to generate the standalone root signature blob.
The name of the define string is specified via the usual /E argument.

For example:

```

dxc.exe /T rootsig_1_1 MyRS1.hlsl /E RS /Fo MyRS1.fxo
```
Note that the root signature string define can also be passed on the command 
line, e.g, /D MyRS1=”…”.


In DXR, there're local and global root signature which could be also create 
root signature in hlsl

```

GlobalRootSignature MyGlobalRootSignature =
{
    "DescriptorTable(UAV(u0)),"                     // Output texture
    "SRV(t0),"                                      // Acceleration structure
    "CBV(b0),"                                      // Scene constants
    "DescriptorTable(SRV(t1, numDescriptors = 2))"  // Static index and vertex buffers.
};

LocalRootSignature MyLocalRootSignature = 
{
    "RootConstants(num32BitConstants = 4, b1)"  // Cube constants 
};

```

There's -setrootsignature option in DXC which attach root signature part to an existing input DXIL container. It is a DXIL container level operation. Not AST or llvm IR.

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
To avoid parsing root signature string twice, HLSLRootSignatureDecl will 
save the parsed root siganture instead of the string.

HLSLRootSignatureDecl will be looked like this:

```

class HLSLRootSignatureDecl final : public NamedDecl {
    hlsl::ParsedRootSignature RootSig;
public:
    const hlsl::ParsedRootSignature &getRootSignature() const {return RootSig;}
};

```

The hlsl::ParsedRootSignature will be struct type shared between clang and 
llvm for in memory presentation of root signature.
Please note that struct type, such as ContainerRootDescriptorTable is not map 
to the serialization format.

```
namespace hlsl {

namespace RootSignature {

// Constant values.
static const uint32_t DescriptorRangeOffsetAppend = 0xffffffff;
static const uint32_t SystemReservedRegisterSpaceValuesStart = 0xfffffff0;
static const uint32_t SystemReservedRegisterSpaceValuesEnd = 0xffffffff;
static const float MipLodBiasMax = 15.99f;
static const float MipLodBiasMin = -16.0f;
static const float Float32Max = 3.402823466e+38f;
static const uint32_t MipLodFractionalBitCount = 8;
static const uint32_t MapAnisotropy = 16;

// Enumerations and flags.
enum class DescriptorRangeFlags : uint32_t {
  None = 0,
  DescriptorsVolatile = 0x1,
  DataVolatile = 0x2,
  DataStaticWhileSetAtExecute = 0x4,
  DataStatic = 0x8,
  DescriptorsStaticKeepingBufferBoundsChecks = 0x10000,
  ValidFlags = 0x1000f,
  ValidSamplerFlags = DescriptorsVolatile
};
enum class DescriptorRangeType : uint32_t {
  SRV = 0,
  UAV = 1,
  CBV = 2,
  Sampler = 3,
  MaxValue = 3
};
enum class RootDescriptorFlags : uint32_t {
  None = 0,
  DataVolatile = 0x2,
  DataStaticWhileSetAtExecute = 0x4,
  DataStatic = 0x8,
  ValidFlags = 0xe
};
enum class RootSignatureVersion : uint32_t {
  Version_1 = 1,
  Version_1_0 = 1,
  Version_1_1 = 2
};

enum class RootSignatureCompilationFlags {
  None = 0x0,
  LocalRootSignature = 0x1,
  GlobalRootSignature = 0x2,
};

enum class RootSignatureFlags : uint32_t {
  None = 0,
  AllowInputAssemblerInputLayout = 0x1,
  DenyVertexShaderRootAccess = 0x2,
  DenyHullShaderRootAccess = 0x4,
  DenyDomainShaderRootAccess = 0x8,
  DenyGeometryShaderRootAccess = 0x10,
  DenyPixelShaderRootAccess = 0x20,
  AllowStreamOutput = 0x40,
  LocalRootSignature = 0x80,
  DenyAmplificationShaderRootAccess = 0x100,
  DenyMeshShaderRootAccess = 0x200,
  CBVSRVUAVHeapDirectlyIndexed = 0x400,
  SamplerHeapDirectlyIndexed = 0x800,
  AllowLowTierReservedHwCbLimit = 0x80000000,
  ValidFlags = 0x80000fff
};
enum class RootParameterType : uint32_t {
  DescriptorTable = 0,
  Constants32Bit = 1,
  CBV = 2,
  SRV = 3,
  UAV = 4,
  MaxValue = 4
};



enum class ComparisonFunc : uint32_t {
  Never = 1,
  Less = 2,
  Equal = 3,
  LessEqual = 4,
  Greater = 5,
  NotEqual = 6,
  GreaterEqual = 7,
  Always = 8
};
enum class Filter : uint32_t {
  MIN_MAG_MIP_POINT = 0,
  MIN_MAG_POINT_MIP_LINEAR = 0x1,
  MIN_POINT_MAG_LINEAR_MIP_POINT = 0x4,
  MIN_POINT_MAG_MIP_LINEAR = 0x5,
  MIN_LINEAR_MAG_MIP_POINT = 0x10,
  MIN_LINEAR_MAG_POINT_MIP_LINEAR = 0x11,
  MIN_MAG_LINEAR_MIP_POINT = 0x14,
  MIN_MAG_MIP_LINEAR = 0x15,
  ANISOTROPIC = 0x55,
  COMPARISON_MIN_MAG_MIP_POINT = 0x80,
  COMPARISON_MIN_MAG_POINT_MIP_LINEAR = 0x81,
  COMPARISON_MIN_POINT_MAG_LINEAR_MIP_POINT = 0x84,
  COMPARISON_MIN_POINT_MAG_MIP_LINEAR = 0x85,
  COMPARISON_MIN_LINEAR_MAG_MIP_POINT = 0x90,
  COMPARISON_MIN_LINEAR_MAG_POINT_MIP_LINEAR = 0x91,
  COMPARISON_MIN_MAG_LINEAR_MIP_POINT = 0x94,
  COMPARISON_MIN_MAG_MIP_LINEAR = 0x95,
  COMPARISON_ANISOTROPIC = 0xd5,
  MINIMUM_MIN_MAG_MIP_POINT = 0x100,
  MINIMUM_MIN_MAG_POINT_MIP_LINEAR = 0x101,
  MINIMUM_MIN_POINT_MAG_LINEAR_MIP_POINT = 0x104,
  MINIMUM_MIN_POINT_MAG_MIP_LINEAR = 0x105,
  MINIMUM_MIN_LINEAR_MAG_MIP_POINT = 0x110,
  MINIMUM_MIN_LINEAR_MAG_POINT_MIP_LINEAR = 0x111,
  MINIMUM_MIN_MAG_LINEAR_MIP_POINT = 0x114,
  MINIMUM_MIN_MAG_MIP_LINEAR = 0x115,
  MINIMUM_ANISOTROPIC = 0x155,
  MAXIMUM_MIN_MAG_MIP_POINT = 0x180,
  MAXIMUM_MIN_MAG_POINT_MIP_LINEAR = 0x181,
  MAXIMUM_MIN_POINT_MAG_LINEAR_MIP_POINT = 0x184,
  MAXIMUM_MIN_POINT_MAG_MIP_LINEAR = 0x185,
  MAXIMUM_MIN_LINEAR_MAG_MIP_POINT = 0x190,
  MAXIMUM_MIN_LINEAR_MAG_POINT_MIP_LINEAR = 0x191,
  MAXIMUM_MIN_MAG_LINEAR_MIP_POINT = 0x194,
  MAXIMUM_MIN_MAG_MIP_LINEAR = 0x195,
  MAXIMUM_ANISOTROPIC = 0x1d5
};
enum class ShaderVisibility : uint32_t {
  All = 0,
  Vertex = 1,
  Hull = 2,
  Domain = 3,
  Geometry = 4,
  Pixel = 5,
  Amplification = 6,
  Mesh = 7,
  MaxValue = 7
};
enum class StaticBorderColor : uint32_t {
  TransparentBlack = 0,
  OpaqueBlack = 1,
  OpaqueWhite = 2,
  OpaqueBlackUint = 3,
  OpaqueWhiteUint = 4
};
enum class TextureAddressMode : uint32_t {
  Wrap = 1,
  Mirror = 2,
  Clamp = 3,
  Border = 4,
  MirrorOnce = 5
};

struct ContainerRootDescriptor {
  uint32_t ShaderRegister;
  uint32_t RegisterSpace = 0;
  uint32_t Flags;
};

struct ContainerDescriptorRange {
  hlsl::RootSignature::DescriptorRangeType RangeType;
  uint32_t NumDescriptors;
  uint32_t BaseShaderRegister;
  uint32_t RegisterSpace;
  uint32_t Flags;
  uint32_t OffsetInDescriptorsFromTableStart;
};

struct ContainerRootDescriptorTable {
  llvm::SmallVector<RootSignature::ContainerDescriptorRange, 8>
      DescriptorRanges;
};

struct ContainerRootConstants {
  uint32_t ShaderRegister;
  uint32_t RegisterSpace = 0;
  uint32_t Num32BitValues;
};

struct ContainerRootParameter {
  hlsl::RootSignature::RootParameterType ParameterType;
  hlsl::RootSignature::ShaderVisibility ShaderVisibility =
      hlsl::RootSignature::ShaderVisibility::All;
  std::variant<RootSignature::ContainerRootConstants,
                   RootSignature::ContainerRootDescriptor,
                   RootSignature::ContainerRootDescriptorTable> Extra;
};

struct StaticSamplerDesc {
  hlsl::RootSignature::Filter Filter =
      hlsl::RootSignature::Filter::ANISOTROPIC;
  hlsl::RootSignature::TextureAddressMode AddressU =
      hlsl::RootSignature::TextureAddressMode::Wrap;
  hlsl::RootSignature::TextureAddressMode AddressV =
      hlsl::RootSignature::TextureAddressMode::Wrap;
  hlsl::RootSignature::TextureAddressMode AddressW =
      hlsl::RootSignature::TextureAddressMode::Wrap;
  float MipLODBias = 0;
  uint32_t MaxAnisotropy = 16;
  hlsl::RootSignature::ComparisonFunc ComparisonFunc =
      hlsl::RootSignature::ComparisonFunc::LessEqual;
  hlsl::RootSignature::StaticBorderColor BorderColor =
      hlsl::RootSignature::StaticBorderColor::OpaqueWhite;
  float MinLOD = 0;
  float MaxLOD = hlsl::RootSignature::Float32Max;
  uint32_t ShaderRegister;
  uint32_t RegisterSpace = 0;
  hlsl::RootSignature::ShaderVisibility ShaderVisibility =
      hlsl::RootSignature::ShaderVisibility::All;
};

struct ParsedRootSignature {
  RootSignature::RootSignatureVersion Version;
  uint32_t RootFlags;
  llvm::SmallVector<RootSignature::ContainerRootParameter, 8>
      RSParameters;
  llvm::SmallVector<RootSignature::StaticSamplerDesc, 8> StaticSamplers;
};

}

```

This will require more work for print and serialization the AST node.

The AST node serialization code might be looked like this:
```
void ASTDeclWriter::VisitHLSLRootSignatureDecl(HLSLRootSignatureDecl *D) {
  VisitNamedDecl(D);
  Record.AddSourceLocation(D->getKeywordLoc());
  hlsl::ParsedRootSignature &RS = D->getRootSignature();
  Record.push_back(RS.RSDesc.Version);
  Record.push_back(RS.RSDesc.Flags);
  
  Record.push_back(ParsedRS.RSParameters.size());
  for (const auto &P : ParsedRS.RSParameters) {
    // push_back all the fields of root parameters.
  }
  Record.push_back(ParsedRS.StaticSamplers.size());
  for (const auto &SS : ParsedRS.StaticSamplers) {
    // push_back all the fields of static samplers.
  }
  
  Code = serialization::DECL_HLSL_ROOT_SIGNATURE;
}

```


A HLSLRootSignatureAttr will be created when meet RootSignature attribute in
HLSL.

```

[RootSignature(MyRS1)]
float4 main(float4 coord : COORD) : SV_Target
{
…
}

```

For RootSignature attribute in hlsl, a clang Attribute will be added like this:
```

    def HLSLEntryRootSignature: InheritableAttr {
      let Spellings = [GNU<"RootSignature">];
      let Subjects = Subjects<[HLSLEntry]>;
      let LangOpts = [HLSL];
      let Args = [StringArgument<"InputString">, DeclArgument<HLSLRootSignature, "RootSignature", 0, /*fake*/ 1>];
    }

```

The StringArgument was introduced to capture the root signature string. 
The DeclArgument was implemented to store the parsed root signature in a 
HLSLRootSignatureDecl AST node.

During the construction of the HLSLRootSignatureAttr, the StringArgument 
is parsed first. If the string is not well-formed, the parsing process will
emit a diagnostic. 
A ParsedRootSignature object, which is the result of the parsing, is then
used to create a HLSLRootSignatureDecl.

Then the HLSLRootSignatureDecl is added to the HLSLRootSignatureAttr for 
Clang code generation.

In clang code generation, the HLSLRootSignatureAttr in AST will be translated
into metadata to express the layout and things like static sampler, root 
flags, space and NumDescriptors in LLVM IR with the ParsedRootSignature object 
saved in its HLSLRootSignatureDecl.

CGHLSLRuntime will generate metadata to link the metadata as root
signature for given entry function. 

For case compile to a standalone root signature blob with option like:
```

dxc.exe /T rootsig_1_1 MyRS1.hlsl /E RS /Fo MyRS1.fxo
```
 the HLSLRootSignatureAttr will be bind to a fake empty entry.


When In the case of local or global root signatures like:
```

GlobalRootSignature MyGlobalRootSignature =
{
    "DescriptorTable(UAV(u0)),"                     // Output texture
    "SRV(t0),"                                      // Acceleration structure
    "CBV(b0),"                                      // Scene constants
    "DescriptorTable(SRV(t1, numDescriptors = 2))"  // Static index and vertex buffers.
};

LocalRootSignature MyLocalRootSignature = 
{
    "RootConstants(num32BitConstants = 4, b1)"  // Cube constants 
};

```
 only a HLSLRootSignatureDecl will be created.

Additionally, a new AST node, SubobjectToExportsAssociationDecl, should be 
added to handle the SubobjectToExportsAssociation statement in HLSL.
```
SubobjectToExportsAssociation MyLocalRootSignatureAssociation =
{
    "MyLocalRootSignature",    // Subobject name
    "MyHitGroup;MyMissShader"  // Exports association 
};
```
The SubobjectToExportsAssociationDecl will contain a HLSLRootSignatureDecl and 
a list of FunctionDecls.


The default root signature version number is 2 which maps to rootsig_1_1.
With option -force-rootsig-ver rootsig_1_0 could make it to 1.

## Metadata format

Here is the metadata presentation for the root signature.
An example can be found in the Example section..

Root Signature
| | Version | Flag | RootParameters | StaticSamplers |
|-| --- | --- | --- | --- |
| | i32 | i32 | list of RootParameters (RootConstant, RootDescriptor, DescriptorTable) | list of StaticSamplers |

RootConstant
| | ParameterType | Visibility | Register | Space | Num32BitValues |
|-| --- | --- | --- | --- | --- |
| | i32 |  i32 | i32 | i32 | i32 |


RootDescriptor
| | ParameterType | Visibility | Register | Space | Flags |
|-| --- | --- | --- | --- | --- |
| | i32 |  i32 | i32 | i32 | i32 |


DescriptorTable
| | ParameterType | Visibility | DescriptorRanges
|-| --- | --- | --- |
|  | i32 |  i32 | list of DescriptorRanges |


DescriptorRange
| | RangeType | NumDescriptors | BaseShaderRegister | Space | Flags | Offset |
|-| --- | --- | --- | --- | --- | --- |
| | i32 | i32 | i32 | i32 | i32 | i32 |


StaticSampler

|| Filter | AddressU | AddressV | AddressW | MipLODBias | MaxAnisotropy | ComparisonFunc | BoarderColor | MinLOD | MaxLOD | Register | Space | Visibility |
| - | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | i32 | i32 | i32 | i32 | float | i32 | i32 | i32 | float | float | i32 | i32 | i32 |


## Examples


* Example root signature string

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


* HLSLEntryRootSignatureAttr in AST.

```
    HLSLRootSignature 'main.RS'
      "RootFlags( ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT | DENY_VERTEX_SHADER_ROOT_ACCESS),
       CBV(b0, space = 1, flags = DATA_STATIC), SRV(t0), UAV(u0),
       DescriptorTable( CBV(b1), SRV(t1, numDescriptors = 8,flags = DESCRIPTORS_VOLATILE),
       UAV(u1, numDescriptors = unbounded, flags = DESCRIPTORS_VOLATILE)),
       DescriptorTable(Sampler(s0, space=1, numDescriptors = 4)),
       RootConstants(num32BitConstants=3, b10),
       StaticSampler(s1),
       StaticSampler(s2, addressU = TEXTURE_ADDRESS_CLAMP, filter = FILTER_MIN_MAG_MIP_LINEAR )"

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
It is possible to avoid the root signature string in HLSLEntryRootSignatureAttr
 print.
Leave it here now to look at the root signature string without go to the 
HLSLRootSignatureDecl dump.


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
Put the metadata into format table so it is easier to understand.
```
  Root Signature
| | Version | Flag | RootParameters | StaticSamplers |
|-| --- | --- | --- | --- |
| | i32 | i32 | list of RootParameters (RootConstant, RootDescriptor, DescriptorTable) | list of StaticSamplers |
| !3 | i32 2 | i32 3 | !4 | !15 |

RootConstant
| | ParameterType | Visibility | Register | Space | Num32BitValues |
|-| --- | --- | --- | --- | --- |
| | i32 |  i32 | i32 | i32 | i32 |
| !14 | i32 1 |  i32 0 | i32 10 | i32 0 | i32 3 |

RootDescriptor
| | ParameterType | Visibility | Register | Space | Flags |
|-| --- | --- | --- | --- | --- |
| | i32 |  i32 | i32 | i32 | i32 |
| !5 | i32 2 |  i32 0 | i32 0 | i32 1 | i32 8 |
| !6 | i32 3 |  i32 0 | i32 0 | i32 0 | i32 0 |
| !7 | i32 4 |  i32 0 | i32 0 | i32 0 | i32 0 |

DescriptorTable
| | ParameterType | Visibility | DescriptorRanges
|-| --- | --- | --- |
|  | i32 |  i32 | list of DescriptorRanges |
| !8 | i32 0 |  i32 0 | !9, !10, !11 |
| !12 | i32 0 |  i32 0 | !13 |

DescriptorRange
| | RangeType | NumDescriptors | BaseShaderRegister | Space | Flags | Offset |
|-| --- | --- | --- | --- | --- | --- |
| | i32 | i32 | i32 | i32 | i32 | i32 |
| !9 | i32 2 | i32 1 | i32 1 | i32 0 | i32 0 | i32 -1 |
| !10 | i32 0 | i32 8 | i32 1 | i32 0 | i32 1 | i32 -1 |
| !11 | i32 1 | i32 -1 | i32 1 | i32 0 | i32 1 | i32 -1 |
| !13 | i32 3 | i32 4 | i32 0 | i32 1 | i32 0 | i32 -1 |

StaticSampler

|| Filter | AddressU | AddressV | AddressW | MipLODBias | MaxAnisotropy | ComparisonFunc | BoarderColor | MinLOD | MaxLOD | Register | Space | Visibility |
| - | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | i32 | i32 | i32 | i32 | float | i32 | i32 | i32 | float | float | i32 | i32 | i32 |
| !16 | i32 85 | i32 1 | i32 1 | i32 1 | float 0.000000e+00 | i32 16 | i32 4 | i32 2 | float 0.000000e+00 | float 0x47EFFFFFE0000000 | i32 1 | i32 0 | i32 0 |
| !17 | i32 21 | i32 3 | i32 1 | i32 1 | float 0.000000e+00 | i32 16 | i32 4 | i32 2 | float 0.000000e+00 | float 0x47EFFFFFE0000000 | i32 2 | i32 0 | i32 0 |

```


## Alternatives considered (Optional)

* Save root signature string to AST.

  Assuming the cost to parse root signature string is cheap,
  HLSLRootSignatureDecl could follow common Clang approach which only save 
  the string in the AST.

  A root signature will be parsed twice, once in Sema for diagnostic and once 
  in clang code generation for generating the serialized root signature.
  The first parsing will check register overlap and run on all root signatures 
  in the translation unit.
  The second parsing will calculate the offset for serialized root signature 
  and only run on the root signature for the entry function or local/global 
  root signature which used in SubobjectToExportsAssociation.

  HLSLRootSignatureDecl will be something like:
```
  class HLSLRootSignatureDecl final : public NamedDecl {

     const StringLiteral *RootSigStr;
public:
     llvm::StringRef getRootSignatureString() const { return RootSigStr->getString();}
  };

```  

  Pro:
    AST serialization is easier, something like:
```
void ASTDeclWriter::VisitHLSLRootSignatureDecl(HLSLRootSignatureDecl *D) {
  VisitNamedDecl(D);
  Record.AddSourceLocation(D->getKeywordLoc());
  Record.AddString(D->getRootSignatureString());
  Code = serialization::DECL_HLSL_ROOT_SIGNATURE;
}
```

  Con:
    Need to parse more than once.

## Acknowledgments (Optional)



<!-- {% endraw %} -->
