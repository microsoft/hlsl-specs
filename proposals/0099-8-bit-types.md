<!-- {% raw %} -->

# Refined `cbuffer` Contexts

## Instructions

* Proposal: [0099](0099-8-bit-types.md)
* Author(s): [Matthäus Chajdas](https://github.com/anteru)
* Sponsor: TBD
* Status: TBD
* Planned Version: 202x
* Issues: [HLSL 334](https://github.com/microsoft/hlsl-specs/issues/337)

## Introduction

This proposal introduces 8-bit integer types to HLSL, to align it more closely with C/C++ and other languages, and allow tight interop with the 8-bit types used in the cooperative vector proposal.

## Motivation

8-bit types are very special in HLSL as they only exist for some arithmetic instructions, but aren't generally accessible. For example, cooperative vectors allow inputs to be specified as 8-bit quantities, but only by packing them into 32-bit. This is cumbersome if for example an application needs to modify the values before passing in, for example, to add a bias -- the application is now forced to unpack the value, modify it, and pack it back in.

## Proposed solution

Introduce two new, native types:

* `uint8_t`: 8-bit unsigned integer
* `int8_t`: 8-bit signed integer

For support and conversion rules, those new types would match the [16-bit scalar types](https://github.com/microsoft/DirectXShaderCompiler/wiki/16-Bit-Scalar-Types), that is, new `uint8_t`.

### DXIL changes

[DXIL](https://github.com/microsoft/DirectXShaderCompiler/blob/main/docs/DXIL.rst) mentions under [Primitive types](https://github.com/microsoft/DirectXShaderCompiler/blob/main/docs/DXIL.rst#primitive-types) that `i8` is supported only for limited operations. With this proposal: `i8` gets supported for computation by shader. For memory access, we'd only support loading multiples of 4 `i8`.

### SPIR-V changes

SPIR-V already supports 8-bit integers.

