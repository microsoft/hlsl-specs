<!-- {% raw %} -->

# Conforming Literals

* Proposal: [0017](0017-conforming-literals.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: HLSL 202x
* PRs: #175
* Issues: #73, microsoft/DirectXShaderCompiler#6147,
  microsoft/DirectXShaderCompiler#3973, microsoft/DirectXShaderCompiler#4683,
  microsoft/DirectXShaderCompiler#5493, microsoft/DirectXShaderCompiler#6410,
  shader-slang/slang#1185

## Introduction

In C-based languages literals are tokens which the compiler interprets in the
most basic translation to preserve the exact meaning expressed in the source to
the final program.

HLSL's handling of literals is complex, undocumented, and inconsistent.

## Motivation

The implementation of literal types in DXC today is the source of significant
bugs and user confusion. The issues linked in the header are a non-exhaustive
sampling of issues (resolved and unresolved) which have stemmed from DXC's
implementation of literal types.

Since the current behavior is complex and undocumented, matching the existing
behavior in Clang without copying the implementation is impossible. This
proposal defines a common solution that is simple and implementable in DXC and
Clang to allow users to adapt to the new behavior before switching to Clang.

## Proposed solution

The [official HLSL
documentation](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-appendix-grammar#floating-point-numbers)
defines floating literal values to be 32-bit. This is consistent with the
[OpenGL Shader Language
Specification](https://registry.khronos.org/OpenGL/specs/gl/GLSLangSpec.4.60.pdf),
which states:

> When the suffix "lf" or "LF" is present, the literal has type double.
> Otherwise, the literal has type float.

This proposal adopts this behavior for floating literals.

Similarly this proposal adopts 32-bit integer as the default representation for
integer literals.

### Benefits of this solution

The most clear and obvious benefits of this solution are its simplicity. The
implementation of this behavior is just a few lines of code. The full
specification is simple and concise.

This solution also works with modern C++ features that have come into HLSL like
templates, and other features like `auto` which we would like to add. It
addresses issues like the bugs with the [ternary
operator](microsoft/DirectXShaderCompiler#6147), where a comprehensive solution
within the rules of C/C++ is nigh impossible.

This solution also allows for a radical simplification of our handling in IR
layers because we can restrict the compiler to only generating valid operation
overloads.

> Note: today DXC supports generating some invalid overloads so as to allow
> literal values to constant evaluate at double precision. If the invalid
> operations aren't fully optimized away, this can result in generating invalid
> DXIL.

### Problems with this solution

This is a significant change in behavior which will cause subtle issues for
existing shaders due to variations in precision of compile-time constant
evaluation. This behavior difference will cause subtle bugs that will be
challenging to diagnose in the midst of a larger compiler transition (i.e.
adopting Clang).

For that reason, this feature proposal targets HLSL 202x, with support for the
new literal behavior in DXC.

## Detailed Design

The full proposed specification for floating literals in HLSL is in #175. A
Separate PR will propose the specification for integer literals.

<!-- {% endraw %} -->
