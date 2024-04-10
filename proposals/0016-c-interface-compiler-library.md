<!-- {% raw %} -->

# C interface for HLSL compiler as a library

* Proposal: [0016](0016-c-interface-compiler-library.md)
* Author(s): [Cooper Partin](https://github.com/coopp)
* Sponsor: [Cooper Partin](https://github.com/coopp)
* Status: **Under Consideration**
* Impacted Project(s): (Clang)

* Issues:
  [#63631](https://github.com/llvm/llvm-project/issues/63631)

## Introduction

An effort is underway to modernize compilation of HLSL based shaders by adding
HLSL compilation to clang. This effort is a long term play that positions
HLSL shader compilation in a place that provides the most stability and
maintainability for the future by giving as many options to DirectX while the
GPU/NPU landscape evolves.

There are multiple ways to compile a shader today.
* dxc.exe - Executable that takes command line options and outputs bytecode
* IDxc** interfaces - COM-based library that is consumed by toolchains to
compile shaders.

## Motivation

One of the HLSL compiler's primary usage modes is as a library. The clang
compiler will also need to expose a library for toolchains to compile a shader.

## Proposed solution

The existing HLSL compiler's library support on Windows is COM based.
This is a non-starter for clang.  COM doesn't fit any of the
existing patterns and is considered to be a Windows-only thing.  Many
developers do not like COM and are immediately turned off on seeing it as a 
requirement.

A better fit in the clang architecture will be to introduce a library with one
or more c style exports to perform compilation tasks.

This export could be part of an existing shared library exposed from clang
(example: libClang, libTooling, etc) or a completely new library that is HLSL
specific. (example: libHlsl, libCompile).

Support for [legacy HLSL compiler toolchains](#alternatives-considered-for-supporting-legacy-toolchains)
will also be addressed in this proposal. The design will help migration of
older DXC-based solutions to adopt clang as the preferred HLSL compiler.

## Detailed design
The current DirectX shader compiler library is a nano-COM implementation that
supports the following features.

* [Include Handlers](#include-handlers)
* [Compiler](#compile-shader)
* [Linker](#link-shader)
* [Reflection Data Access](#shader-reflection)
* [DXIL Container Access](#dxil-container-access)
* [PDB Symbol Access](#shader-pdbs)

The following interfaces are used to work with data being passed to/from the
library.

#### Buffers
```c++
// Structure for supplying bytes or text input to Dxc APIs. Represents both
// text (DxcText) and non-text byte buffers (DxcBuffer).
struct DxcBuffer {
  LPCVOID Ptr;
  SIZE_T Size;
  UINT Encoding;
};
typedef DxcBuffer DxcText;

// General purpose buffers
struct IDxcBlob : public IUnknown {
public:
  LPVOID GetBufferPointer();
  SIZE_T GetBufferSize();
};

// String buffers that guarantee null-terminated text and the stated encoding
struct IDxcBlobEncoding : public IDxcBlob {
public:
  HRESULT GetEncoding(BOOL *pKnown, UINT32 *pCodePage);
};

struct IDxcBlobUtf16 : public IDxcBlobEncoding {
public:
  LPCWSTR GetStringPointer();
  SIZE_T GetStringLength();
};

struct IDxcBlobUtf8 : public IDxcBlobEncoding {
public:
  LPCSTR GetStringPointer();
  SIZE_T GetStringLength();
};
```
#### Status and other data
Errors, status, and other kinds of data are returned as an IDxcResult
interface. A unique DXC_OUT_KIND is defined for each different type of data
being returned.  The type of data is determined by the interface method used to
produce the IDxcResult.

Example:
IDxcCompiler3::Compile() and IDxcCompiler3::Disassemble() both return an 
IDxcResult.

```c++
typedef enum DXC_OUT_KIND {
  DXC_OUT_NONE = 0,
  DXC_OUT_OBJECT = 1,         // IDxcBlob - Shader or library object
  DXC_OUT_ERRORS = 2,         // IDxcBlobUtf8 or IDxcBlobUtf16
  DXC_OUT_PDB = 3,            // IDxcBlob
  DXC_OUT_SHADER_HASH = 4,    // IDxcBlob - DxcShaderHash of shader or shader
                              // with source info (-Zsb/-Zss)
  DXC_OUT_DISASSEMBLY = 5,    // IDxcBlobUtf8/16 - from Disassemble
  DXC_OUT_HLSL = 6,           // IDxcBlobUtf8/16 - from Preprocessor or Rewriter
  DXC_OUT_TEXT = 7,           // IDxcBlobUtf8/16 - other text, such as -ast-dump
                              // or -Odump
  DXC_OUT_REFLECTION = 8,     // IDxcBlob - RDAT part with reflection data
  DXC_OUT_ROOT_SIGNATURE = 9, // IDxcBlob - Serialized root signature output
  DXC_OUT_EXTRA_OUTPUTS  = 10,// IDxcExtraResults - Extra outputs

  DXC_OUT_FORCE_DWORD = 0xFFFFFFFF
} DXC_OUT_KIND;

struct IDxcOperationResult : public IUnknown {
  HRESULT GetStatus(HRESULT *pStatus);

struct IDxcResult : public IDxcOperationResult {
  BOOL HasOutput(DXC_OUT_KIND dxcOutKind);
  HRESULT GetOutput(DXC_OUT_KIND dxcOutKind,
                    REFIID iid, void **ppvObject,
                    IDxcBlobUtf16 **ppOutputName);
  UINT32 GetNumOutputs();
  DXC_OUT_KIND GetOutputByIndex(UINT32 Index);
  DXC_OUT_KIND PrimaryOutput();
};
```
#### Helper library
The shader compiler library also provides a helper library IDxcUtils that is
provided to create/consume the different data forms referred to above.

```c++
struct IDxcUtils : public IUnknown {
  // Create a sub-blob that holds a reference to the outer blob and points to
  // its memory.
  HRESULT CreateBlobFromBlob(
    IDxcBlob *pBlob,
    UINT32 offset,
    UINT32 length,
    IDxcBlob **ppResult);

  // Creates a blob referencing existing memory, with no copy.
  HRESULT CreateBlobFromPinned(
    LPCVOID pData,
    UINT32 size,
    UINT32 codePage,
    IDxcBlobEncoding **pBlobEncoding);

  // Create blob, taking ownership of memory allocated with supplied allocator.
  HRESULT MoveToBlob(
    LPCVOID pData,
    IMalloc *pIMalloc,
    UINT32 size,
    UINT32 codePage,
    IDxcBlobEncoding **pBlobEncoding);

  // Copy blob contents to memory owned by the new blob.
  HRESULT CreateBlob(
    LPCVOID pData,
    UINT32 size,
    UINT32 codePage,
    IDxcBlobEncoding **pBlobEncoding);

  HRESULT LoadFile(
    LPCWSTR pFileName,
    UINT32* pCodePage,
    IDxcBlobEncoding **pBlobEncoding);

  HRESULT CreateReadOnlyStreamFromBlob(
    IDxcBlob *pBlob,
    IStream **ppStream);

  HRESULT CreateDefaultIncludeHandler(
    IDxcIncludeHandler **ppResult);

  // Convert or return matching encoded text blobs
  HRESULT GetBlobAsUtf8(
    IDxcBlob *pBlob,
    IDxcBlobUtf8 **pBlobEncoding);

  HRESULT GetBlobAsUtf16(
    IDxcBlob *pBlob,
    IDxcBlobUtf16 **pBlobEncoding);

  HRESULT GetDxilContainerPart(
    const DxcBuffer *pShader,
    UINT32 DxcPart,
    void **ppPartData,
    UINT32 *pPartSizeInBytes);

  // Create reflection interface from serialized Dxil container, or 
  // DXC_PART_REFLECTION_DATA.
  HRESULT CreateReflection(
    const DxcBuffer *pData,
    REFIID iid, void **ppvReflection);

  // Create arguments for IDxcCompiler2::Compile
  HRESULT BuildArguments(
    LPCWSTR pSourceName,      // Optional file name for pSource. Used in errors
                              // and include handlers.
    LPCWSTR pEntryPoint,      // Entry point name. (-E)
    LPCWSTR pTargetProfile,   // Shader profile to compile. (-T)
    LPCWSTR *pArguments,      // Array of pointers to arguments
    UINT32 argCount,          // Number of arguments
    const DxcDefine *pDefines,// Array of defines
    UINT32 defineCount,       // Number of defines
    IDxcCompilerArgs **ppArgs); // Arguments you can use with Compile() method

  // Takes the shader PDB and returns the hash and the container inside it
  HRESULT GetPDBContents(
    IDxcBlob *pPDBBlob, IDxcBlob **ppHash,
    IDxcBlob **ppContainer);
};
```

### Features supported in DirectX shader compiler library (dxcapi.h)
#### Include Handlers
Provided to customize the handling of include directives. An implementation of
the following interface is provided as a hook into compilation. A default
implementation that reads include files from the filesystem can also be created
using IDxcUtils::CreateDefaultIncludeHandler.

```c++
struct IDxcIncludeHandler : public IUnknown {
  HRESULT STDMETHODCALLTYPE LoadSource(
    LPCWSTR pFilename,            // candidate filename.
    IDxcBlob **ppIncludeSource);  // resultant source object for included file,
                                  // nullptr if not found.
};
```

#### Compile Shader
IDxcCompiler3 is the most current entrypoint for compiling a shader or 
disassembling DXIL containers/bitcode.

Provides support for:
* Compiling a single entry point to the target shader model
* Compiling a library to a library target (using -R lib_*)
* Compiling a rootsignature (-T rootsig_*)
* Preprocessing HLSL source (-P)
* Disassembling DXIL container or bitcode

```c++
struct IDxcCompiler3 : public IUnknown {
  HRESULT Compile(
    const DxcBuffer *pSource,            // source text to compile
    LPCWSTR *pArguments,                 // array of pointers to arguments
    UINT32 argCount,                     // number of arguments
    IDxcIncludeHandler *pIncludeHandler, // user-provided interface to handle
                                         // #include directives (optional)
    REFIID riid, LPVOID *ppResult);      // IDxcResult: status, buffer, and
                                         // errors

  HRESULT Disassemble(
    const DxcBuffer *pObject,            // dxil container or bitcode
    REFIID riid, LPVOID *ppResult);      // IDxcResult: status, disassembly
                                         // text, and errors
};
```
#### Link Shader
TBD

#### Shader Reflection
TBD

#### DXIL Container Access
TBD

#### Shader PDBs
TBD

## Alternatives considered for supporting legacy toolchains

### Alternative 1: Open Source wrapper code for IDxcCompiler interface

This approach involves creating wrapper code released on
https://github.com/microsoft that can be included into existing toolchain
projects. This wrapper implementation will be a drop-in match to all of the
existing public interfaces allowing easy adoption to using clang.

The wrapper implementation will call into the new C export for compilation.

### Alternative 2: Build/Ship Nuget package library

This approach combines Alternative 1 and adds compiling the wrapper code into
formal header/libraries that can be consumed by legacy toolchains.

## Resources

* [DXC Api](https://learn.microsoft.com/en-us/windows/win32/api/dxcapi/)
* [IDxcCompiler](https://learn.microsoft.com/en-us/windows/win32/api/dxcapi/ns-dxcapi-idxccompiler)
* [IDxCompiler2](https://learn.microsoft.com/en-us/windows/win32/api/dxcapi/ns-dxcapi-idxccompiler2)
* [IDxCompiler3](https://learn.microsoft.com/en-us/windows/win32/api/dxcapi/ns-dxcapi-idxccompiler3)
* [IDxcCompilerArgs](https://learn.microsoft.com/en-us/windows/win32/api/dxcapi/ns-dxcapi-idxccompilerargs)

## Acknowledgments

[Chris Bieneman](https://github.com/llvm-beanz)

<!-- {% endraw %} -->
