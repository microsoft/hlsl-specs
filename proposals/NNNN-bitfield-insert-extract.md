<!-- {% raw %} -->

# Bitfield Insert and Extract Intrinsics

## Instructions

> This template wraps at 80-columns. You don't need to match that wrapping, but
> having some consistent column wrapping makes it easier to view diffs on
> GitHub's review UI. Please wrap your lines to make it easier to review.

> When filling out the template below for a new feature proposal, please do the
> following first:

> 1. exclude the "Planned Version", "PRs" and "Issues" from the header.
> 2. Do not spend time writing the "Detailed design" until the feature has been
>    merged in the "Under Consideration" phase.
> 3. Delete this Instructions section including the line below.

---

* Proposal: [NNNN](NNNN-bitfield-insert-extract.md)
* Author(s): [Nate Morrical](https://github.com/natevm)
* Sponsor: [Nate Morrical](https://github.com/natevm)
* Status: **Under Consideration**

## Introduction

This proposal aims to add official "bitfield insert" and "bitfield extract" 
intrinsics to HLSL, which would allow users to leverage DXIL's `Lbfe`, `Ubfe`, 
and `Bfi` instructions (or equivalently, SPIR-V's `OpBitfieldUExtract`, 
`OpBitfieldSExtract`, and `OpBitfieldInsert`). 

## Motivation

For certain GPU workloads where memory bandwidth is a leading bottleneck, it
can be very useful to employ a mixture of "quantized" and compressed data 
representations alongside cache aligned loads and stores. 
(For example, the work by [Ylitie et al](https://users.aalto.fi/~laines9/publications/ylitie2017hpg_paper.pdf))

However, this poses a new challenge: users need a way to quickly and efficiently
manipulate subsequences of bits within an integer. (In the example above, in 
extracting the N-bit quantized AABB within a multinode for intersection.) 

One approach is to use a combination of logical operations to generate shifts 
and masks to extract and insert bits for a given field. However, when billions 
of such operations are required in a given invocation, this can quickly lead 
to ALU bottlenecks ([one example I've found here](https://github.com/shader-slang/slang/issues/4817#issuecomment-2325257908).)

To aleviate these bottlenecks, GPU architectures support accelerated bitfield
insertion and extraction routines (exposed through instructions like DXIL's
`Lbfe`/`Ubfe`/`Bfi`.) 

In languages like GLSL, users have direct access to these intrinsics
via the built-in language functions, eg `bitfieldExtract` / `bitfieldInsert`.
However, HLSL has no equivalent language level intrinsic, and users must 
instead depend on the compiler to optimize DXIL to use `Lbfe`/`Ubfe`/`Bfi`. 
At the same time, it is difficult to ensure that the compiler identifies a 
given logical shifting / masking operation as a bitfield extraction / insertion 
routine. ([afaik, this never happens](https://github.com/microsoft/DirectXShaderCompiler/issues/6902)). As a result, the `Lbfe`, `Ubfe`, 
and `Bfi` instructions currently go unused. 

Another application where bitfield extraction and insertion is useful is in
efficient "reinterpretation" of structures. (For example, accessing the fourth
byte of a 32-bit integer as if it were an int8_t4). We would like to use these
intrinsics within [Slang](https://github.com/shader-slang/slang/issues/4817) to 
help with casting from one structure layout to another, where a mix of 8, 16, 
32, and 64-bit type sizes might be used. 

Beyond this, certain priority queues and stacks depend on the "sign extension"
behavior that bitfield intrinsics expose, which enable reducing register pressure
for N-wide data structure traversals. This can be very helpful for compute shader
operations, particularly for two-wide BVH to N-wide BVH conversions like what's 
done in [H-PLOC](https://gpuopen.com/download/publications/HPLOC.pdf), or like 
the N-wide stack entries proposed by Ylitie.

In short, HLSL is missing bitfield insertion and extraction intrinsics, and so 
at the moment there doesn't seem to be a way to leverage the corresponding DXIL
intrinsics. 

## Proposed solution

This proposal would introduce `bitfieldExtract` and `bitfieldInsert` intrinsics, 
which would map to their corresponding DXIL instructions. For HLSL->SPIR-V compilation, 
we would directly map these intrinsics to the corresponding SPIR-V operations
(namely, `OpBitfieldSExtract`, `OpBitfieldUExtract`, and `OpBitfieldInsert`).

In the case of bitfield extraction, the logical expression:
```
int value = ..., offset = ..., bits = ...;
int extracted = (((value>>offset)&((1u<<bits)-1))<<(32-bits)>>(32-bits));
```
Would then simplify to
```
int value = ..., offset = ..., bits = ...;
int extracted = bitfieldExtract(value, offset, bits);
```
Where the resulting instruction would involve `Lbfe`.

If value is unsigned, then the logical expression:
```
uint value = ..., offset = ..., bits = ...;
uint extracted = ((value>>offset)&((1u<<bits)-1));
```
Would then simplify to
```
uint value = ..., offset = ..., bits = ...;
int extracted = bitfieldExtract(value, offset, bits);
```
Where the resulting instruction would involve `Ubfe`.

Finally, in the case of bitfield insertion, the logical expression:
```
uint clearMask = ~(((1u << bits) - 1u) << offset);
uint clearedBase = base & clearMask;
uint maskedInsert = (insert & ((1u << bits) - 1u)) << offset;
uint result = clearedBase | maskedInsert; 
```
Would then simplify to
```
uint base = ..., insert = ..., offset = ..., bits = ...;
int extracted = bitfieldInsert(base, insert, value, bits);
```
Where the resulting instruction would involve `Bfi`.

The `bitfieldExtract` intrinsic would support a component-wise value, for 
example `uint4`, and the `bitfieldInsert` intrinsic would support 
component-wise `base` and `insert` values. 

For hardware compatibility reasons, we would assume that `value`, `base`, and 
`insert` be 32-bit integers (either signed or unsigned).

<!-- {% endraw %} -->
