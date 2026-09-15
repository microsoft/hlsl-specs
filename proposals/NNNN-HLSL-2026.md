---
title: "NNNN - HLSL 2026"
params:
  authors:
    - llvm-beanz: Chris Bieneman
  sponsors:
    - llvm-beanz: Chris Bieneman
  status: Under Consideration
---

## Introduction

This proposal outlines the target feature-set for HLSL 2026.

## Motivation

It's been 5 years since the last HLSL language version bump introducing new
features, and we have a set of valuable low hanging fruit features that are
fully implemented and other features that are either approved by TC57 or highly
likely to be approved.

This proposal seeks to take a set of approved and highly likely features and
group them into a new HLSL 2026 language version as an officially supported
(non-standard) version of HLSL.

## Proposed solution

This proposal recommends adopting the following HLSL proposals as the
feature set for HLSL 2026:

| Proposal | TC57 State | DXC Status | Clang Status |
| -------- | ---------- | ---------- | ------------ |
| [0002 - Conforming Literals](https://hlsl-tc57.github.io/tc57/proposal/0002/) | Completed | Completed | Completed |
| [0004 - 202x Feature Removals](https://hlsl-tc57.github.io/tc57/proposal/0004/) | Accepted | [In Progress](https://github.com/microsoft/DirectXShaderCompiler/issues/8479) | Competed |
| [0005 - Refined cbuffer Contexts](https://hlsl-tc57.github.io/tc57/proposal/0005/) | Accepted | [Not Started](https://github.com/microsoft/DirectXShaderCompiler/issues/8484) | Completed |
| [0006 - Restricted Unbound Arrays](https://hlsl-tc57.github.io/tc57/proposal/0006/) | Accepted | Not Started | Not Started |
| [0009 - HLSL namespace](https://hlsl-tc57.github.io/tc57/proposal/0009/) | Accepted | [In Progress](https://github.com/microsoft/DirectXShaderCompiler/issues/8918) | In Progress |
| [0010 - Modern C++ Features](https://hlsl-tc57.github.io/tc57/proposal/0010/) | Refinement | [In Progress](https://github.com/microsoft/DirectXShaderCompiler/issues/8904) | Partial |
| [0012 - HLSL Loop Unroll Factor](https://hlsl-tc57.github.io/tc57/proposal/0012/) | Refinement | Completed | Completed |
| [0013 - Named Casts](https://hlsl-tc57.github.io/tc57/proposal/0013/) | Refinement | [Not Started](https://github.com/microsoft/DirectXShaderCompiler/issues/8919) | Not Started |
| [0014 - `groupshared` arguments](https://hlsl-tc57.github.io/tc57/proposal/0014/) | Refinement | Completed | Completed |
| [0015 - const-qualified Non-Static Member Functions](https://hlsl-tc57.github.io/tc57/proposal/0015/) | Accepted | [Not Started](https://github.com/microsoft/DirectXShaderCompiler/issues/8923) | Completed |
| [0016 - Non-member Operator Overloading](https://hlsl-tc57.github.io/tc57/proposal/0016/) | Accepted | [Not Started](https://github.com/microsoft/DirectXShaderCompiler/issues/8924) | Completed |
| [0018 - User-defined Conversion Functions](https://hlsl-tc57.github.io/tc57/proposal/0018/) | Accepted | [Not Started](https://github.com/microsoft/DirectXShaderCompiler/issues/8925) | Completed |
| [0017 - HLSL Ternary Operator Behavior](https://hlsl-tc57.github.io/tc57/proposal/0017/) | Under Consideration | Not Started | Not Started |
| [0019 - Size Type](https://hlsl-tc57.github.io/tc57/proposal/0019/) | Under Consideration | Not Started | Not Started |

These features represent a mixture of breaking changes and new features which
will be compelling to users, and enable a wide array of useful functionality.
