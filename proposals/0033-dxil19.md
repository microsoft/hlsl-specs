<!-- {% raw %} -->

# DXIL 1.9

* Proposal: [NNNN](NNNN-dxil19.md)
* Author(s): [Damyan Pepper](https://github.com/damyanp)
* Sponsor: [Damyan Pepper](https://github.com/damyanp)
* Status: **Under Review**
* Planned Version: Shader Model 6.9

## Introduction

Shader Model 6.9 introduces new features to HLSL which need representations in
DXIL.  This proposal provides an index of the new features:


## Opacity Micromaps

[Proposal 0024] - Opacity Micromaps (OMM)

This adds a new DXIL op, `AllocateRayQuery2` and some new flags.


## Shader Execution Reordering

[Proposal 0027] - Shader Execution Reordering (SER)

This adds a new DXIL type, `%dx.types.HitObject` and 30 new DXIL ops.


## DXIL Vectors

[Proposal 0030] - DXIL Vectors

This enables native vectors, as supported by LLVM 3.7, in DXIL 1.9. A new
`rawBufferVectorLoad` opcode is added that loads an entire vector. Elementwise
intrinsics are extended to accept vector arguments.

The HLSL changes related to this feature can be found in [Proposal 0026] - HLSL
Long Vector Type.


## Cooperative Vectors

[Proposal 0029] - Cooperative Vector

This enables hardware-accelerated multiplation of vectors with matrices.  Four
new opcodes are added - `matvecmul`, `matvecmuladd`, `outerproductaccumulate`,
`vectoraccumulate`.

The HLSL API related to this feature can be found in [Proposal 0031] - HLSL
Vector / Matrix Operations.


[Proposal 0024]: 0024-opacity-micromaps.md
[Proposal 0026]: 0026-hlsl-long-vector-type.md
[Proposal 0027]: 0027-shader-execution-reordering.md
[Proposal 0029]: 0029-cooperative-vector.md
[Proposal 0030]: 0030-dxil-vectors.md
[Proposal 0031]: 0031-hlsl-vector-matrix-operations.md

