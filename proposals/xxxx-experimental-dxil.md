---
title: "XXXX - Experimental DXIL"
params:
  authors:
    - V-FEXrt: Ashley Coleman
    - llvm-beanz: Chris Bieneman
    - tex3d: Tex Riddell
  sponsors:
    - V-FEXrt: Ashley Coleman
  status: Under Consideration
---

* Planned Version: SM 6.10

## Introduction

This proposal introduces a method for denoting and tracking experimental dxil
operations that minimize churn when an operation is rejected or delayed to a
later DXIL version.

## Motivation

During iterative development of the shader compiler it is beneficial to
implement real lowering into real opcodes to validate that a proposal actually
solves real world use cases. Traditionally this has been done by marking all in
development opcodes as expirmental opcodes of the next dxil version release.
In most cases this is sufficient as the opcodes are accepted into the next
release but challenges arise when one or more opcodes are rejected or delayed
from the release while the opcodes following them are not. In the rejection
case the opcodes must be burned and in the delayed case the opcodes must be
manually moved to the next release with special casing code. This proposal
seaks to implemented a systematic method to handle these issues.

## Goals
This proposal seeks to address the following points:
 * Needless churn when experimental op are delayed or rejected
 * Expermental op boundary point is rigid and moves with every SM update
 * Long term experiments (and potentially extensions) aren't currently feasible
 * Focused on core api system (hlsl instrinsics and DXIL ops)
 * Works within the current intrinsics/DXIL op mechanisms
 * Minimizes overall changes to the system and IHV processes
 * Straightforward transition route from experimental to stable
 * IHV drivers can support both experimental and stable versions of an op simultaneously
   * simplifies migrations

## Non-goals
Future proposals may address the topics below but this proposal seeks to be a
smaller isloated change. It intends to solves immediate term challenges
without investing significant engineering efforts into a generalized solution.
That said, an attempt is made to avoid proposals that preclude a generalized
solution. Thus this proposal explicitly avoids addressing these issues:
 * Full scale generalized extension system
 * Process development to enable asynchronous non-colliding development
 * Metadata/RDAT/PSV0/Custom lowering are out of scope for this document



## Potential DXIL Op Solutions

### Top 1 bit as "is experimental" flag

The top bit of all opcodes is a flag stating if the opcode is experimental.

No structural or shape changes to the DXIL occur, simply the fact that the opcode
has the high bit set informs that it is experimental. This makes it very easy
for the compiler and drivers to detect experimental opcodes. When an opcode is
transistioned to stable the opcode needs to be assigned a stable number.
This splits the 4 billion opcode space into two 2 billion partions. One for
stable one for experimental.

This is the simpliest proposal with the least invasive set of changes.

Pros:
 * Very simple
 * Quick to implement
 * Could be implemented "by hand" today by hard coding opcodes
Cons:
 * Not a solution for extensions
 * transistion from experimental to stable isn't just unsetting the bit
   * other stable ops may have already taken that number
   * complicates the experimental->stable mapping

### Top 8 bits as "opcode partition" value
This is pretty much identical to the 1 bit flag proposal except there are 256
partitions with 16 million opcodes each. The key difference is that it unlocks
extension potential as extension developers such as IHVs could reserve a
partition for their own use without collision with other opcodes.

| Partition | Use |
|-----------|-----|
| 0 | stable |
| 1 | experimental |
| 2 | extension foo |
| .. | extension .. |
| 255 | extension 255 |


Pros:
 * Fairly simple
 * Quick to implement
 * Enables basic opcodes extension system
Cons:
 * transistion from experimental to stable isn't just clearing the partition
   * other stable ops may have already taken that number
   * complicates the experimental->stable mapping

### Top 16 bits as "opcode partition" value
Identical concept as above but with 64k partitions, each with 64k opcodes.

### Split the opcode in half
Lower 16 bits are the core/stable opcodes, Upper 16 bits are the experimental opcodes.

Gives 64k opcodes for stable then the upper 64k can either be chunked manually
leaving all number available for opcodes or it can be partitioned as 256
chunks of 256 opcodes with the partition encoded into the opcode itself

Very similar concept as before but keeping track of opcodes is complicated.
Also enables a weird situation where two opcodes "could" be encoded into a
single value.

### Introduce dx.opx.opcodeclass for experimental/extended ops
Denotes the experimental status in the actual opcode. Potentially doubles the
opcode space depending on implementation however it doesn't make the transistion
to stable any easier and complicated the integration with the current intrinsics
system.

Pros:
 * Enables fairly robust extension system
 * Doesn't consume large portions of the current opcode space
 * obvious from reading the DXIL that experimental/extension is being used
Cons:
 * transistion from experimental to stable isn't just dropping the `x`
   * other stable ops may have already taken that number
   * complicates the experimental->stable mapping
 * Not well integrated into the current system, would require notable dev work
 * Unclear how to allocate extension vs experimental ops in the opx space

### Extension/Experimental Feature Opcode
Relaxing the restriction that DXIL opcodes are immediate constants would allow
a call that returns a value representing a special operation. The call creates
the value from a feature ID and feature local opcode. Unique-ify information
could be stored in the call directory or in metadata.

```llvm
%feature_id = i32 123
%cool_operation = i32 456
%opcode = i32 dx.create.extensionop(%feature_id, %cool_operaton)
%result = i32 dx.op.binary(%opcode, %a, %b)
```

Pros:
 * Enables vary robust extension system
 * Doesn't consume any of the current opcode space
 * Obvious from reading the DXIL that experimental/extension is being used
Cons:
 * Transistion from experimental to stable is non trivial. [See here](####stabilizing-with-opcode-subsets)
 * Not integrated into the current system, would require notable dev work
 * Breaks a pretty fundamental DXIL assumption

### Single Specific Experimental Opcode with varargs
A new opcode class `dx.op.extension` is introduced as a core stable opcode in
which named opcode subsets can be called directly.


```llvm
%opcode_set = str "My Cool Experiment"
%opcode = i32 123
%res = i32 dx.op.extension(i32 12345, %opcode_set, %opcode, operands...)
```

The opcode set name and specific opcode are just arbitrary values from other
parts of the compiled shader.

Pros:
 * Doesn't consume any of the current opcode space
 * Obvious from reading the DXIL that experimental/extension is being used
 * Very flexible
 * Maintains first args as immediate constant
 * All the information is encoded in the call
Cons:
 * Transistion from experimental to stable is non trivial. [See here](####stabilizing-with-opcode-subsets)
 * Unclear how well the current system will handle varargs
 * More complex to implement and integrate
 * `dx.op.extension` will need to support any arbitrary overload

#### Stabilizing with opcode subsets
Some proposals in this doc create new opcodes sets that reuse existing numbers
nested under a set name or feature id. These proposals have a more complex route
for transistioning from experimental to stable. There are two potential routes
to be considered.

 * Create a new stable opcode from scratch using the normal mechanisms that
   currently exist then migrate lowering paths to use it
 * Maintain a notion of experimental and non-experimental opcode subsets then
   update the specific subset to no longer be considered experimental keeping
   all lowering the same

The first option has a larger churn burden but maintains the status quo and keeps
the generated code relatively dense while the second option is likely the easiest
transistion system from any proposal in this document at the cost of code density
and introducing a second way for stable operations to exist in DXIL.

## Potential HLSL Intrinsic Solutions
There are two types of intrinsic solutions that can be imagined. One where an
extension author provides external code that has a custom lowering to an
arbitrary extension DXIL op and one that is prebaked into the compiler and
conditional enabled/disabled as appropiate.

As HLSL intrinsics are more flexable and can be reordered/renamed without
burning some finite resource only the second type is being considered at the
moment. The first type falls under "general purpose extension system" which is
out of scope for this document.

Intrinsic functions should be handled in a reasonable way. Ideally this means
that an intrinsic is only available if the experimental/extension op is also
available. Likely this means updating gen_intrin_main to mark an intrinsic as
experimental/extension then generating code that errors if it used in a
non-experimental/non-extension environment. But that is subject to change based
on the DXIL solution chosen. Once a proposal is selected this section will be
updated to reflect that.

## Outstanding Questions

* Should DXC have some kind of --experimental flag that turns on/off
  experimental intrinsics and DXIL ops?
* Related, when/how are experimental ops exposed in the compiler, when are they
  errors to use?
* Should the validator warn on experimental op usage?
