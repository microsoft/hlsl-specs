<!-- {% raw %} -->

# DXIL Vectors

---

* Proposal: [NNNN](NNNN-dxil-vectors.md)
* Author(s): [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.9

## Introduction

While DXIL is intended and able to support language vectors,
 those vectors must be broken up into individual scalars to be valid DXIL.
This feature introduces the ability to represent native vectors in DXIL for some uses.

## Motivation

While the original shape of the vectors may be reconstructed from their scalarized form,
 it requires additional work of the DXIL consumer and results in larger DXIL binary sizes.
Although it has never been allowed in DXIL, the LLVM IR that DXIL is based on can represent native vectors.
By allowing these native vector types in DXIL, the size of generated DXIL can be reduced and
 new opportunities for expanding vector capabilities in DXIL ar introduced.

## Proposed solution

Native vectors are allowed in DXIL version 1.9 or greater.
These can be stored in allocas, static globals, and groupshared variables.
They can be loaded from or stored to raw buffers and used as arguments to a selection
 of element-wise intrinsic functions as well as the standard math operators.
They cannot be used in shader signatures, constant buffers, typed buffer, or texture types.

## Detailed design

### Vectors in memory representations

In their alloca and variable representations, vectors in DXIL will always be represented as vectors.
Previously individual vectors would get scalarized into scalar arrays and arrays of vectors would be flattened
 into a one-dimensional scalar array with indexing to reflect the original intents.
Individual vectors will now be represented as a single native vector and arrays of vectors will remain
 as arrays of native vectors, though multi-dimensional arrays will still be flattened to one dimension.

Scalarization of these vectors will continue to be done for uses that don't support native vectors,
 but it will be done using extractelement instructions from the native vectors
 instead of loads from the scalarized array representation.

Single-element vectors are not valid in DXIL.
At the language level, they may be supported for corresponding intrinsic overloads,
 but such vectors should be represented as scalars in the final DXIL output.
Since they only contain a single scalar, single-element vectors are
 informationally equivalent to actual scalars.
Rather than include conversions to and from scalars and single-element vectors,
 it is cleaner and functionally equivalent to represent these as scalars in DXIL.

Although matrices are represented as vectors in some contexts such as unlinked library shaders,
 their final DXIL representation will continue to be as arrays of scalars.
This is consistent with both their past and future intended representation.

### Changes to DXIL Intrinsics

A new form of rawBufferLoad allows loading of full vectors instead of four scalars.
The status integer for tiled resource access is loaded just as before.
The returned vector value and the status indicator are grouped into a new `ResRet` helper structure type
 that the load intrinsic returns.

```asm
  ; overloads: SM6.9: f16|f32|i16|i32
  ; returns: status, vector
  declare %dx.types.ResRet.v[NUM][TY] @dx.op.rawBufferLoad.v[NUM][TY](
      i32,                  ; opcode
      %dx.types.Handle,     ; resource handle
      i32,                  ; coordinate c0 (index)
      i32,                  ; coordinate c1 (elementOffset)
      i8,                   ; mask
      i32,                  ; alignment
  )
```

The return struct contains a single vector and a single integer representing mapped tile status.

```asm
  %dx.types.ResRet.v[NUM][TY] = type { vector<TYPE, NUM>, i32 }
```

Here and hereafter, `NUM` is the number of elements in the loaded vector, `TYPE` is the element type name,
 and `TY` is the corresponding abbreviated type name (e.g. `i64`, `f32`).

#### Elementwise intrinsics

A selection of elementwise intrinsics are given additional native vector forms.
Elementwise intrinsics are those that perform their calculations irrespective of the location of the element
 in the vector or matrix arguments except insofar as that position corresponds to those of the other elements
 that might be used in the individual element calculations.
An elementwise intrinsic `foo` that takes scalar or vector arguments could theoretically implement its vector version using a simple loop and the scalar intrinsic variant.

```c++
vector<TYPE, NUM> foo(vector<TYPE, NUM> a, vector<TYPE, NUM> b) {
  vector<TYPE, NUM> ret;
  for (int i = 0; i < NUM; i++)
    ret[i] = foo(a[i], b[i]);
}
```
  
For example, `fma` is an elementwise intrinsic because it multiplies or adds each element of its argument vectors,
 but `cross` is not because it performs an operation on the vectors as units,
 pulling elements from different locations as the operation requires.

The elementwise intrinsics that have native vector variants represent the
 unary, binary, and tertiary generic operations:

```asm
 <[NUM] x [TYPE]> @dx.op.unary.v[NUM][TY](i32 opcode, <[NUM] x [TYPE]> operand1)
 <[NUM] x [TYPE]> @dx.op.binary.v[NUM][[TY]](i32 opcode, <[NUM] x [TYPE]> operand1, <[NUM] x [TYPE]> operand2)
 <[NUM] x [TYPE]> @dx.op.tertiary.v[NUM][TY](i32 opcode, <[NUM] x [TYPE]> operand1, <[NUM] x [TYPE]> operand2, <[NUM] x [TYPE]> operand3)
```

The only opcodes allowed with vector variants are:

* Unary
  * Exp
  * Htan
  * Atan
  * Log
* Binary
  * FMin
  * FMax
* Tertiary
  * Fma

Unsupported DXIL intrinsics will continue to operate on scalarized representations even if those scalars
 are extracted from native vectors.

### Potential Changes to DXIL Consumers

As this removes no existing DXIL features, the former representation of vectors is still valid.
However, DXIL consumers may expect native vectors where they are supported and may misinterpret
 vectors scalarized into arrays as being native arrays.
This is unlikely to produce any faulty results, but may miss some optimizations.

As DXIL with native vectors might be linked to create a DXIL shader without that support,
 some additional scalarization might be necessary when linking in such cases.

This feature involves no changes to previous shader models and any DXIL produced for earlier versions
  should continue to behave exactly as before.

#### Validation Changes

Validation errors for use of native vectors in DXIL are removed.
Any errors for using vectors in unsupported intrinsics or operations are maintained,
 but made more specific to the operations or locations that don't allow native vector types.
More specific errors will be generated for usage of native vectors in any unsupported intrinsics.
New errors will be generated for any use of native vectors in shader signatures or cbuffer locations.

A validation error should be produced for any representation of a single element vector.
Such vectors should be represented as scalars.

### Runtime Additions

#### Runtime information

When native vectors are present, a DXIL unit will signal a dependency on Shader Model 6.9.

#### Device Capability

Devices that support Shader Model 6.9 will be required to support native vectors in rawbuffer resources,
 allocas, and groupshared memory.
These native vectors must be supported for the above indicated DXIL intrinsics.

## Testing

A compiler targeting shader model 6.9 should be able to represent vectors in the supported memory spaces
 in their native form and generate native calls for supported intrinsics
 and scalarized versions for unsupported intrinsics.

Verify that supported intrinsics and operations will retain vector types.

The DXIL 6.9 validator should allow native vectors in the supported memory and intrinsic uses.
It should produce errors for uses in signatures, cbuffers, and type buffers and any uses in unsupported intrinsics.
Any representation of a single element vector should produce a validation error.
These shouldn't be directlty produceable with a compatible compiler and will require custom DXIL generation.

Full runtime execution should be tested by using the native vector intrinsics on different types of memory
 and confirming that the calculations produce the correct results in all cases for an assortment of vector sizes.

## Acknowledgments

* [Anupama Chandrasekhar](https://github.com/anupamachandra) and [Tex Riddell](https://github.com/tex3d) for foundational contributions to the design.

<!-- {% endraw %} -->
