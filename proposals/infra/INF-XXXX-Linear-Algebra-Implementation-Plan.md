---
title: "INF-XXXX - Linear Algebra Implementation Plan"
params:
  authors:
    - V-FEXrt: Ashley Coleman
  sponsors:
    - V-FEXrt: Ashley Coleman
  status: Under Consideration
---

 
* Impacted Projects: DXC, Clang implementation not considered here

## Introduction

This implementation plan covers a high level description of the work necessary
to implement the
[linalg spec](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0035-linalg-matrix.md)
for SM6.10 including back-of-the-napkin time estimates. This document is being
continually refined with higher resolution estimates. Currently estimates are
expected to be correct within an order of magnatude.

## Time Estimate Windows

In order to facilitate useful discussion, the table below defines terms for
various low resolution time windows. Each term intentionally overlaps with
nearby terms.

| Term    | Window     |
|---------|------------|
| Day     | 1-2 day    |
| Days    | 3-7 days   |
| Weeks   | 1-2 weeks  |
| Sprints | 2-4 weeks  |
| Months  | 1-3 months |

Anything smalller than days is too small resolution to discuss and should be
bundled with other tasks while anything larger than months is too large to discuss
and should be split up.

## Top Level Work Items

The table below represents identified work items with top level estimates.
See [Commentary](#Commentary) for discussion on specific work items.

| Item Class            | Time Window |
|-----------------------|-------------|
| Impl Headers using __builtins()   | Days       |
| Check in HLSL Headers | Day         |
| Header Distribution   | Weeks       |
| Groupshared Args      | Weeks       |
| HLSL + DXIL api       | Months*     |
| DXIL Validator        | Sprints     |
| HLK Testing           | Months      |
| PSV0 Updates          | Weeks       |
| RDAT Updates          | Weeks       |
| Shader Reflection     | Weeks       |

*:The HLSL builtins api and DXIL api are large enough to be subdivided below.

A couple notes on the tables below:
 - The tables below are subject to change and may fall out of sync. The [linalg spec](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0035-linalg-matrix.md) is the source of truth
 - The HLSL builtin ops will have different names, the names are used as placeholders
 - It's useful to pair the builtin and dxil op work when they are 1:1 mapped so the table below reflects that

| Name                  | Time Window |
|-----------------------|-------------|
| `__matrix_create()` + `dx.op.createMatrix` | Days |
| `__matrix_annotate()` + `dx.op.annotateMatrix` | Weeks |
| `__matrix_fill()` + `dx.op.fillMatrix` | Days |
| `__matrix_cast()` + `dx.op.castMatrix` | Days |
| `__matrix_length()` + `dx.op.matrixLength` | Days |
| `__matrix_get_coordinate()` + `dx.op.matrixGetCoordinate` | Days |
| `__matrix_get_element()` + `dx.op.matrixGetElement` | Days |
| `__matrix_set_element()` + `dx.op.matrixSetElement` | Days |
| `__matrix_load_from_descriptor()` + `dx.op.matrixLoadFromDescriptor` | Days |
| `__matrix_load_from_memory()` + `dx.op.matrixLoadFromMemory` | Days |
| `__matrix_store_to_descriptor()` + `dx.op.matrixStoreToDescriptor` | Days |
| `__matrix_store_to_memory()` + `dx.op.matrixStoreToMemory` | Days |
| `__matrix_accumulate_to_descriptor()` + `dx.op.matrixAccumulateToDescriptor` | Days |
| `__matrix_accumulate_to_memory()` + `dx.op.matrixAccumulateToMemory` | Days |
| `__matrix_vector_multiply` + `dx.op.matvecmul` | Days |
| `__matrix_vector_multiply_add` + `dx.op.matvecmuladd` | Days |
| `__matrix_outer_product()` + `dx.op.matrixOuterProduct` | Days |
| `__matrix_matrix_multiply` + `dx.op.matrixOp(1)` | Days |
| `__matrix_matrix_multiply_accumulate()` + `dx.op.matrixOp(2)` | Days |
| `__matrix_matrix_sum_accumulate()` + `dx.op.matrixOp(3)` | Days |
| `__matrix_query_accumulator_layout()` + `dx.op.matrixQueryAccumulatorLayout` | Days |

Loosely adding everything up gives ~4 months of serialized work with a wide error margin.

## Milestones

### Spec Complete (DXIL Ops)
While we expect the spec to move more, we need to have a resonable expectation
that the DXIL ops are mostly finalized before moving into implementation.

### IVH Preview Drops
IHVs will need early previews to test their driver implementation. Each drop
will increase the total number of supported operations until the full list
below is completed. Early drops may have minimum feature support but the tasks must be
iteratively completed by the end of this milestone.

 - Check in linalg.h
 - Groupshared Args
 - HLSL builtins api
 - DXIL op api
 - Basic HLKs
 - DXIL Validation - Trival / Free

Each drop should unlock a new set of useful and independent features. Below is
a proposal for a useful division of features in each drop. Drops 2 through 5 can
be completed in any order based on feature unlock priorities.

#### Drop 1 (~Sprint)
The absolute minimum obserable matrix

 - The following HLSL / DXIL Ops
   - createMatrix
   - annotateMatrix (simple version, no attempt to deduplicate annotations)
   - fillMatrix
   - matrixLoadFromDescriptor
   - matrixStoreToMemory

#### Drop 2 (~Sprint)
Expanded Load/Store operations + cast

 - Groupshared Args
 - The following HLSL / DXIL Ops
   - matrixLoadFromMemory
   - matrixStoreToMemory
   - castMatrix (abritrarily added here to balance drop size)

### Drop 3 (~Week)
Elementwise Matrix Operations

 - The following HLSL / DXIL Ops
   - matrixLength
   - matrixGetCoordinate
   - matrixGetElement
   - matrixSetElement

### Drop 4 (~Week)
Matrix Multiply

 - The following HLSL / DXIL Ops
   - matvecmul
   - matvecmuladd
   - matrixOp(1) (Mat Mat Multiply)

### Drop 5 (~Sprint)
Matrix Accumlate

 - The following HLSL / DXIL Ops
   - matrixAccumulateToDescriptor
   - matrixAccumulateToMemory (depends on Drop 2)
   - matrixOuterProduct
   - matrixQueryAccumulatorLayout
   - matrixOp(2) (Mat Mat Multiply Accumulate)
   - matrixOp(3) (Mat Mat Sum Accumulate)

#### Drop 6 (~Sprint)
Complete IHV preview feature set
 - Checked in final version of linalg.h with all calls to builtins
 - Complex `annotate` implementation with deduplication
 - Basic HLKs


### Public Preview
Public preview is a beta verson of the compiler with the features enabled so
that public developers can try out the new features in a mostly complete state.
The expectation at the point is near feature completeness / minimal api changes
to enable the developers to test out the features in real world scenarios. Only
one drop is planned and it needs the following tasks to be completed.

 - Header Distribution
 - PSV0 Updates
 - DXIL Validation - Local / Simple

### Release
The official public release of the compiler with the full launch feature set.
Should be the finalzied features at production quality and requires all the
remaining tasks to be completed.

 - RDAT Updates
 - DXIL Validation - Global / Complex
 - Full HLKs
 - Shader Reflection

## Commentary

### Publish HLSL Headers
Very trivial task, just need to make a PR with header code that already exists.

### Header Distribution
There is an open discussion on how to ship HLSL headers in DXC. Shipping HLSL
source with the compiler is a very new thing for DXC and consideration is needed
to make sure we have the right solution/process for users.

### Groupshared Args
See [the groupshared args proposal](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0043-groupshared-arguments.md)

### HLSL __builtins api
Each function/operation in the HLSL linalg spec needs an underlying builtin
function to call to actually do the underlying work.

The work for each operation is as follows:
 - Perform sema checks
 - Lower the call to DXCs "High level ops"
 - Write unit/integration level tests

### DXIL api
The DXIL api is the final api that IHVs operate over.

The High Level Ops emitted by the __builtins api need to be lowered into DXIL.
Each lowering could use any number of new DXIL ops but the average tends towards
one so that is assumed here.

The work for each HLOp give then above context is roughly:
 - Lower the op to DXIL
 - Create one new DXIL op
 - Write unit/integration level tests

### DXIL Validator
There are various different validation tasks. The terms used above are reflected
below with examples of each.

 - Trivial / Free
   - Validations that are baked into the DXIL op system already
   - Stuff like "operation call with correct overloads and types"
 - Local / Simple
   - Validations that require special handling but are trivial from the call
   - Stuff like "`Stride` must be `0` on matrix load when `Layout` is not `RowMajor` or `ColMajor`"
 - Global / Complex
   - Validations that require larger context windows to resolve
   - Stuff like "operation is only valid if `MatrixRef` has `Use` type of `Wave`"

### HLK Testing
Based on challenges and timelines for Long Vector HLK testing, I choose "Months" here.
Lots of tricky subtle details to make sure drivers match expectations. One
example is the multiple allowed outcomes of OOB behaviour.

### PSV0/RDAT Updates
We need to update both, discussion was had on deprecating PSV0 and just doing
RDAT however this doesn't align with near term goals for modernization.

### Shader Reflection
Would require a refelction api version bump, reflection would be based on the
PSV0/RDAT updates. Still unclear if its something we want to do.
