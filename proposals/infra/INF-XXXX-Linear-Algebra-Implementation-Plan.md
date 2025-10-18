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
for SM6.10 including back-of-the-napkin time
estimates. This document is not intended to be a comprehensive implementation
timeline, instead the estimates are purely for strawmanning discussion and
should be expected to vary in at least an order of magnetude in either direction.

## Time Estimate Windows

In order to facilitate useful discussion, the table below defines terms for
various low resolution time windows. Each term intentionally overlaps with
nearby terms.

| Term    | Window     |
|---------|------------|
| Days    | 1-10 days  |
| Weeks   | 1-2 weeks  |
| Sprints | 2-4 weeks  |
| Months  | 1-3 months |

Anything smalller than days is too small resolution to discuss and should be
bundled with other tasks while anything larger than months is too large to discuss
and should be split up.

## Top Level Work Items

The table below represents identified work items with top level estimates.
See [Commentary](#Commentary) for discussion on specific work items.

| Item Class | Time Window | Item Count  |
|----------------------|---------|---|
| Publish HLSL Headers | Days    | 1   |
| Header Distribution  | Weeks   | 1   |
| Groupshared Args     | Weeks   | 1   |
| HLSL __builtins api  | Weeks   | 19* |
| DXIL api             | Days    | 19* |
| DXIL Validator       | Sprints | 1   |
| HLK Testing          | Months  | 1   |
| PSV0/RDAT Updates    | ???     | 1   |
| Shader Reflection    | ???     | 1   |

Loosely adding everything up gives ~7 "Months" of serialized work with a wide error margin.

*: At the time of writing there are 19 identified matrix operations. The table assumes 1 DXIL Op and 1 HLSL __builtin per operation which is likely incorrect.

## Commentary

### Publish HLSL Headers
Very trivial task, just need to make a PR with header code that already exists.

### Header Distribution
There is an open discussion on how to ship HLSL headers in DXC. Shipping HLSL
source with the compiler is a very new thing for DXC and consideration is needed
to make sure we have the right solution/process for users.

## Groupshared Args
See [the groupshared args proposal](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0043-groupshared-arguments.md)

## HLSL __builtins api
Each function/operation in the HLSL linalg spec needs an underlying builtin
function to call to actually do the underlying work.

The work for each operation is as follows:
 - Perform sema checks
 - Lower the call to DXCs "High level ops"
 - Write unit/integration level tests

## DXIL api
The DXIL api is the final api that IHVs operate over.

The High Level Ops emitted by the __builtins api need to be lowered into DXIL.
Each lowering could use any number of new DXIL ops but the average tends towards
one so that is assumed here.

The work for each HLOp give then above context is roughly:
 - Lower the op to DXIL
 - Create one new DXIL op
 - Write unit/integration level tests

## DXIL Validator
I don't have strong context here, but members of the team implied that there
is a large chunck of work here, so marked as "Sprints" kind of arbirarily.

This should be revisted

## HLK Testing
Based on challenges and timelines for Long Vector HLK testing, I choose "Months" here.

This should be revisted

## PSV0/RDAT Updates
I don't have enough context to even posit a guess.

## Shader Reflection
I don't have enough context to even posit a guess.
