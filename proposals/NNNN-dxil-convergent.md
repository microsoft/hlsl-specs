---
title: NNNN - LLVM convergent Attribute in DXIL
params:
  authors:
  - llvm-beanz: Chris Bieneman
  sponsors:
  - llvm-beanz: Chris Bieneman
  status: Under Consideration
---

## Introduction

This proposal permits the LLVM `convergent` function attribute in DXIL. The
attribute marks calls whose behavior depends on other shader threads and
prevents invalid control-flow transformations. This change affects only DXIL
representation; it adds no HLSL syntax or hardware requirements.

## Motivation

Wave operations, quad operations, derivatives, and some synchronization
operations depend on threads executing together. Moving them into or out of
divergent control flow can change participating threads, producing different
results or making the operation invalid.

LLVM 3.7 represents this restriction with the `convergent` function attribute.
Compiler transformations may move or transform a convergent call only when the
new call is under equivalent control flow to the original.

DXIL currently restricts the function attributes that may appear in a module,
and the validator rejects unknown attributes. DXIL producers therefore cannot
communicate convergence requirements through LLVM's standard representation.
Instead, each transformation needs DXIL-specific knowledge, duplicating LLVM's
model and increasing the risk that generic transformations miscompile shaders.

## Proposed solution

Permit LLVM's `convergent` enum function attribute in DXIL, with the semantics
defined by the LLVM 3.7 Language Reference. A call to a `convergent` function
may be moved or transformed only when the resulting call is under equivalent
control flow to the original.

A DXIL producer should add `convergent` to declarations of operations whose
semantics depend on participating threads. It may also mark function definitions
whose calls require the same restriction. For example:

```llvm
declare i32 @dx.op.waveGetLaneIndex(i32) #0

attributes #0 = { convergent }
```

The attribute is optional, so existing DXIL remains valid. When present, tools
that transform DXIL, including optimizers, linkers, validators, and driver
compilers, must preserve and honor it.

The DXIL validator must accept `convergent` as an enum function attribute while
continuing to reject unknown attributes. No shader flag, capability bit,
metadata record, bitcode version change, or runtime check is needed because this
will be a required feature of the new DXIL version.

This proposal defines no user-facing HLSL attribute. Compiler and DXIL
definitions carry convergence requirements for HLSL intrinsics and DXIL
operations without source annotations.

## Compatibility

Using `convergent` requires a new DXIL version. Producers targeting earlier
versions must not emit it, and consumers may reject unsupported versions.
Existing modules and source compatibility are unaffected.

Consumers supporting the new version must decode, preserve, and honor the
attribute according to LLVM semantics. Although LLVM bitcode already supports
`convergent`, independent bitcode readers must represent it, and non-LLVM driver
compilers must respect it. Discarding the attribute could enable incorrect
transformations.

## Alternatives considered

### Continue using implicit DXIL operation knowledge

DXIL-aware optimizers can maintain a table of convergent operations. Older
modules still require this table, but it does not protect IR from generic LLVM
transformations and duplicates the classification across producers and
consumers.

### Add DXIL-specific metadata

DXIL metadata could express this restriction, but generic LLVM transformations
may not understand or preserve it. The LLVM attribute already provides the
required semantics and encoding.

## Testing

Validator tests should verify that `convergent` is accepted on declarations and
definitions, unknown attributes remain rejected, and the attribute survives
bitcode round trips.