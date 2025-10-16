---
title: NNNN - 8-bit integer support
params:
    authors:
    - anteru: Matthäus Chajdas
    sponsors:
    - llvm-beanz: Chris Bieneman
    status: Under Consideration
---

* Planned Version: SM 6.x
* Issues: [HLSL 337](https://github.com/microsoft/hlsl-specs/issues/337)

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

DXIL/LLVM IR doesn't discern between `i8` and `u8`, so during lowering, we need to restrict/select between the `I` and `U` instructions.

For the elementwise overloads defined in [DXIL vectors](0030-dxil-vectors.md), the following subset would be supported:

| Opcode |  Name              | Class              | Note          |
| ------ | --------------     | --------           | ----          |
| 30     | Bfrev              | Unary              | See note      |
| 31     | Countbits          | UnaryBits          |               |
| 32     | FirstBitLo         | UnaryBits          |               |
| 33     | FirstBitHi         | UnaryBits          |               |
| 34     | FirstBitSHi        | UnaryBits          |               |
| 37     | IMax               | Binary             | `i8` only     |
| 38     | IMin               | Binary             | `i8` only     |
| 39     | UMax               | Binary             | `u8` only     |
| 40     | UMin               | Binary             | `u8` only     |
| 48     | IMad               | Tertiary           | `i8` only     |
| 49     | UMad               | Tertiary           | `u8` only     |
| 115    | WaveActiveAllEqual | WaveActiveAllEqual |               |
| 117    | WaveReadLaneAt     | WaveReadLaneAt     |               |
| 118    | WaveReadLaneFirst  | WaveReadLaneFirst  |               |
| 119    | WaveActiveOp       | WaveActiveOp       |               |
| 120    | WaveActiveBit      | WaveActiveBit      |               |
| 121    | WavePrefixOp       | WavePrefixOp       |               |
| 122    | QuadReadLaneAt     | QuadReadLaneAt     |               |
| 123    | QuadOp             | QuadOp             |               |
| 165    | WaveMatch          | WaveMatch          |               |

TODO: Do we really need `Bfrev`?

### SPIR-V changes

SPIR-V already supports 8-bit integers.

