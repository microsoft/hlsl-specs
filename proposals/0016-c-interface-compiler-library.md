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

_The detailed design is not required until the feature is under review._

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
