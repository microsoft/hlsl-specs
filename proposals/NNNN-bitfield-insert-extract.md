<!-- {% raw %} -->

# Bitfield Insert and Extract Intrinsics

* Proposal: [NNNN](NNNN-bitfield-insert-extract.md)
* Author(s): [Nate Morrical](https://github.com/natevm)
* Sponsor: [Damyan Pepper](https://github.com/damyanp)
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
extracting the N-bit quantized AABB within a multinode for intersection,
or in dynamically rearranging "hit" bits within 32-bit stack entries.) 

One approach is to use a combination of logical operations to generate shifts 
and masks to extract and insert bits for a given field. However, when billions 
of such operations are required in a given invocation, this can quickly lead 
to ALU bottlenecks ([one example I've found here](https://github.com/shader-slang/slang/issues/4817#issuecomment-2325257908).)

To aleviate these bottlenecks, GPU architectures support accelerated bitfield
insertion and extraction routines (exposed through instructions like DXIL's
`Lbfe`/`Ubfe`/`Bfi`.) These act similar in behavior to C++-style "bitfield" 
syntax; but they support two additional features that C++ bitfields do not,
namely, 
1. "offset" and "bit width" parameters do not need to be known during compilation
time. And, 
2. The `Lbfe` intrinsic additionally supports sign extension, which is useful
for efficiently generating bit masks at runtime.  

In languages like GLSL, users have direct access to these intrinsics
via the built-in language functions, eg `bitfieldExtract` / `bitfieldInsert`.
However, HLSL has no equivalent language level intrinsic, and users must 
instead depend on the compiler to optimize DXIL to use `Lbfe`/`Ubfe`/`Bfi`. 
For use cases where the bit width and offset are known at compilation time, 
developers can leverage HLSL's C++-style "bitfield" attributes. But when these
parameters can only be determined at runtime, it is difficult to ensure that the 
compiler identifies a given logical shifting / masking operation as a bitfield 
extraction / insertion routine. ([afaik, this never happens](https://github.com/microsoft/DirectXShaderCompiler/issues/6902)). 
As a result, the dynamic offset and bit width parameters given to `Lbfe`, `Ubfe`, 
and `Bfi` instructions cannot currently be used. 

Another application where bitfield extraction and insertion is useful is in
efficient runtime "reinterpretation" of structures. (For example, accessing the 
fourth byte of a 32-bit integer as if it were an int8_t4 in one branch, or the
first and second bytes as if it were an int16_t2 in another branch). We would like 
to use these intrinsics within [Slang](https://github.com/shader-slang/slang/issues/4817) 
to help with casting from one structure layout to another, where a mix of 8, 16, 
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

In the case of bitfield extraction, a developer writing the logical expression:
```
int value = ..., offset = ..., bits = ...;
int extracted = (((value>>offset)&((1u<<bits)-1))<<(32-bits)>>(32-bits));
```
could replace this code with the more efficient intrinsic:
```
int value = ..., offset = ..., bits = ...;
int extracted = bitfieldExtract(value, offset, bits);
```
where the resulting instruction would involve `Lbfe`.

If value is unsigned, then a developer could replace the logical expression:
```
uint value = ..., offset = ..., bits = ...;
uint extracted = ((value>>offset)&((1u<<bits)-1));
```
with
```
uint value = ..., offset = ..., bits = ...;
int extracted = bitfieldExtract(value, offset, bits);
```
where the resulting instruction would involve `Ubfe`.

Finally, in the case of bitfield insertion, a user could express:
```
uint clearMask = ~(((1u << bits) - 1u) << offset);
uint clearedBase = base & clearMask;
uint maskedInsert = (insert & ((1u << bits) - 1u)) << offset;
uint result = clearedBase | maskedInsert; 
```
more efficiently with
```
uint base = ..., insert = ..., offset = ..., bits = ...;
int extracted = bitfieldInsert(base, insert, value, bits);
```
where the resulting instruction would be a `Bfi`.

The `bitfieldExtract` intrinsic would support component-wise vector values 
(as this is what most IHVs support), and the `bitfieldInsert` intrinsic would 
support component-wise vector `base` and `insert` values. The "offset" and "bits"
parameters would be allowed to be runtime variables, rather than compilation-time
constants.

For hardware compatibility reasons, we would assume that `value`, `base`, and 
`insert` be 32-bit integers (either signed or unsigned). To keep the scope 
of the proposed intrinsics focused, we would leave the extended use of these
intrinsics to tensors / matrices of integers to the user to implement on a 
row by row or column by column basis.

One example usage: implementing a "priority queue" of six hexadecimal items. The
6 most significant bits indicate which slots in the queue are occupied, while the 
low 24 bits describe 6 hexadecimal "items":
```
uint popHexFromQueue(inout uint hexadecimalQueue) {
    // This line selects the first occupied "slot" in the queue. 
    uint slot = firstBitLow(bitfieldExtract(hexadecimalQueue, 24, 6));

    // This line extracts the item within the selected slot
    uint hex = bitfieldExtract(hexadecimalQueue, 4 * slot, 4);

    // This line clears the slot...
    hexadecimalQueue = bitfieldInsert(hexadecimalQueue, 0xF, 4 * slot, 4);

    // And then this line clears the bit in the occupancy mask
    hexadecimalQueue = bitfieldInsert(hexadecimalQueue, 0, 24 + slot, 1);

    return hex;
}
```

Another example usage, masking out the middle two bytes of each component in a 
vector of integers depending on the state of the 23rd bit:
```
int4 clearFlaggedItems(int4 items) {
    // Sign extension behavior results in either 0x00000000 or 0xFFFFFFFF
    int4 masks = bitfieldExtract(items, 23, 1);
    return bitfieldInsert(items, masks, 8, 16);
}
```

<!-- {% endraw %} -->
