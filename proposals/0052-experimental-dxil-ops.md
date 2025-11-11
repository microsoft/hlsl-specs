---
title: "0052 - Experimental DXIL Ops"
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
solves real world use cases. Traditionally this has been done by adding new
opcodes right after the last released opcode in the prior DXIL version.
In some cases this is sufficient, when feature development is unified, opcodes
don't change after being added, and all opcodes in a contiguous block starting
from the prior release are accepted into the next release.
But challenges arise during parallel feature development, from experimental
feature evolution requiring opcode changes, or when a feature and its opcodes
are excluded from the release while the opcodes following them are not.
Excluded opcodes must either be turned into reserved opcodes or a breaking DXIL
change must be synchronized between the compiler, tests, and drivers.
This proposal seeks to implement a systematic method to handle these issues.

## Goals
This proposal seeks to address the following points:
 * Needless churn when experimental op are delayed or rejected
 * Experimental feature boundaries are rigid and unaffected by SM updates
 * Enable long term experiments
 * Focused on core api system (hlsl instrinsics and DXIL ops)
 * Works within the current intrinsics/DXIL op mechanisms
 * Minimizes overall changes to the system and IHV processes
 * Straightforward transition route from experimental to stable
 * Soft transitions between versions of experimental ops and final ops simplify migrations
   * IHV drivers can support multiple experimental versions and the final version
     of a set of ops in the same driver

## Non-goals
Future proposals may address the topics below but this proposal seeks to be a
smaller isloated change. It intends to solves immediate term challenges
without investing significant engineering efforts into a generalized solution.
That said, an attempt is made to avoid proposals that preclude a generalized
solution. Thus this proposal explicitly avoids addressing these issues:
 * Full scale generalized extension system
 * Process development to enable asynchronous non-colliding development
 * Metadata/RDAT/PSV0/Custom lowering are out of scope for this document



## Existing DXIL Op and HLSL Intrinsic Infrastructure

In DXC, there exists a large amount of infrastructure for handling DXIL ops as
special types of functions throughout the compiler. From definition to lowering
to passes to validation and consumption, any solution that doesn't fit into this
system will face significant challenges from development through to the
transition of operations from experimental to final official DXIL ops in a
shader model, both in the compiler and in drivers consuming the ops.

There is also a high-level intrinsic system which uses its own set of opcodes
in the generated enum: `hlsl::IntrinsicOp`. Though these are internal to the DXC
compilation pipeline, stability of these opcodes impacts any tests with
high-level IR, such as tests for lowering.

This section outlines key areas of this system for clarity in reasoning about
solutions.

### DXIL Op Definitions

DXIL Ops are defined in `hctdb.py`, which is used by `hctdb_instrhelp.py` to
generate header and cpp code used directly by drivers to consume the operations,
as well as generate a variety of other code for the compiler, validator, DXIL
spec, etc...

`DxilOperations.h/cpp` implements the core of the system for handling DXIL
operations in a DxilModule.

DXIL OpCodes, which are always passed as a literal in the first argument of a
DXIL operation call, are a contiguous set of values starting at 0, such that they
may be used to directly index a table of opcode definitions at the core of this
infrastructure. This OpCode argument in the DXIL Op call is the sole identifier
of the operation being called. Function names reflect OpCodeClass and overloads,
but this is only a means to prevent collisions between functions used by
operations requiring different signatures and attributes.

The contiguous nature of DXIL OpCodes used to index into a table is the first
key hurdle in defining experimental ops. If an operation at a particular index
is changed in any significant way, the interpretation of IR across that change
boundary produces undefined behavior (crash if you're lucky), with no
automatic mechanism to guard against this.

### HLSL IntrinsicOp definitions

Intrinsic operations are normally defined in `gen_intrin_main.txt`, which is
parsed by `hctdb.py` and used by `hctdb_instrhelp.py` to generate the
`hlsl::IntrinsicOp` enum, and a bunch of tables used by custom intrinsic
overload handling code in `Sema.cpp`.

There is infrastructure that tracks previously assigned HL op indices by
intrinsic name in `hlsl_intrinsic_opcodes.json`. This can be a merge conflict
point between any parallel feature development.

While indices are separated between functions and methods, all functions or
all methods with the same name will share the same HL opcode. Generally this
isn't a problem as the arguments (which would include an object) allow you to
differentiate things when handling opcode calls. Recently a `class_prefix`
attribute was added to the intrinsic definition syntax for `gen_intrin_main.tx
` to prepend a class name, used for `DxHitObject`. This is just an example of
how this system can be extended to separate out ops if necessary.

`HLOperationLower.cpp` uses a direct table lookup from the (unsigned) 
IntrinsicOp` value to the lowering function and arguments. This creates
another merge point for any experimental features (and potentially extension),
which integrate into the same intrinsic table.

There is an extension mechanism defined through the `IDxcLangExtensions`
interface on the DXC compiler API object. It allows you to define a separate
intrinsic table with predefined lowering strategies to produce extended ops as
external function calls outside the recognized DXIL operations. It's meant to
enable target extensions (extra intrinsics within certain limited definitional
bounds) in HLSL for a custom backend. Modules using extensions wouldn't be
accepted by the DXIL validator (unmodified). The way extensions must be defined,
used, and interpreted differs significantly from adding built-in HLSL
intrinsics and DXIL operations, which means it will introduce significant
burdens and limitations to initial op definitions, lowering and compiler
interaction, and make the transition to final DXIL operations painful. For
these reasons, I don't think we should consider this extension mechanism as
part of our solution at this time.

While this document focuses on a solution for DXIL ops, the HL opcodes can
lead to difficult conflicts between independent feature development branches
as well. Avoiding these requires synchronizing `hlsl_intrinsic_opcodes.json`
and pre-allocated lowering table entries in `HLOperationLower.cpp` in a common
branch as a very first step whenever adding any new HLSL intrinsics.

### IR Tests

Tests that contain DXIL, will have DXIL operation calls passing a literal `i3`
OpCode value in as the first argument. If these opcodes are to change
between experimental and final versions, there should be an easy way to update
the tests accordingly. Same for any high-level IR for the IntrinsicOp numbers.

There are two places where hard-coded numbers appear in tests: source IR and
FileCheck statements for checking output IR.

There isn't any known solution that doesn't involve a change to at least the
DXIL OpCodes when transitioning from experimental to final DXIL ops.

That requires either updating these across all tests (potentially with
scripted regex replacement - matching could be error-prone) or adding some
tool (or tool option) to translate symbolic opcodes to literal numbers as a
first step.

### Summary of key elements a solution should address

- DXIL Op property table indexed by OpCode
- HLOperationLower table indexed by IntrinsicOp
- A way to update and deprecate experimental opcodes during development
  without a new opcode overlapping an old one, leading to undefined behavior in
  a driver if mismatched IR is used.
- A way for the same driver to accept multiple versions of ops without undefined behavior.
- A way to easily transition tests from experimental ops to final DXIL ops
- Potentially: A way to avoid some of the more difficult HL opcode conflicts
  between independent feature development branches
- Minimal, or ideally no, changes required to source code interacting with or
  consuming DXIL ops when transitioning from experimental to final ops.

## Potential DXIL Op Solutions

### Top 1 bit as "is experimental" flag

The top bit of all opcodes is a flag stating if the opcode is experimental.

No structural or shape changes to the DXIL occur, simply the fact that the opcode
has the high bit set informs that it is experimental. This makes it very easy
for the compiler and drivers to detect experimental opcodes. When an opcode is
transistioned to stable the opcode needs to be assigned a stable number.
This splits the 4 billion opcode space into two 2 billion partions. One for
stable one for experimental. The proposal results in two separatlye contiguous
op code tables.

This is marginally the simpliest proposal with the least invasive set of changes.
It is only marginally simpler than other reserved bit proposals.

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
   * significantly complicates the experimental->stable transition

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
 * Causes issues for drivers as drivers don't currently consider the op code class

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
