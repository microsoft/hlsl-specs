<!-- {% raw %} -->

# 16 bit isSpecialFloat DXIL Op

* Proposal: [NNNN](NNNN-16bit-isspecialfloat.md)
* Author(s): [Sarah Spall](https://github.com/spall)
* Sponsor: [Sarah Spall](https://github.com/spall)
* Status: **Under Consideration**

* Planned Version: Shader Model 6.9
* PRs:
* Issues: [#521](https://github.com/microsoft/hlsl-specs/issues/521)
  [#7496](https://github.com/microsoft/DirectXShaderCompiler/issues/7496)

## Introduction

The IsSpecialFloat DXIL Op is used to implement operations, 'isinf', 'isnan', 'isfinite', and 'isnormal'.
Due to a bug (#7496), the IsSpecialFloat DXIL operations were never generated for 16-bit types.

## Motivation

The 'isinf', 'isnan', and 'isfinite' functions (there is no 'isnormal' function), support fp16 but instead of generating a 16 bit
IsSpecialFloat DXIL Op, DXC extends to the 32 bit float op. See (https://github.com/microsoft/DirectXShaderCompiler/issues/7496).
Some Vendor drivers support the 16 bit IsSpecialFloat op, but some do not. 

## Proposed solution

Beginning with SM 6.9 we would like to have DXC be able to generate this operation, and not extend to 32-bit.
For shader models before 6.9 we want to emulate the functionality using LLVM IR rather than DXIL op

<!-- {% endraw %} -->
