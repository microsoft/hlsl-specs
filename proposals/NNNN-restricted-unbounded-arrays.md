---
title: "NNNN - Restricted Unbounded Arrays"
params:
  authors:
    - llvm-beanz: Chris Bieneman
  sponsors:
    - llvm-beanz: Chris Bieneman
  status: Under Consideration
---

* Planned Version: 202x
* PRs: [#634](https://github.com/microsoft/hlsl-specs/pull/634)

## Introduction

New restrictions imposed on where declarators of arrays of unknown size can be
used legally in HLSL.

## Motivation

Arrays of unknown size cause a variety of problems within HLSL. When used as
parameters they cannot be copied in and out which violates the base calling
convention. For resource arrays, passing arrays of unknown size makes resource
initialization fragile across call boundaries.

Since the behavior of out of bounds accesses is undefined, losing the array
bound information at the source level and in the calling convention is rife with
potential pitfalls.

## Proposed solution

This proposal suggests limiting declarators of arrays of unknown size to:
* Global declarations of resources.
* Variables where an initializer is provided and the array bound is implied by
  the initializer.

## Detailed design

Full specification language is proposed in [#634](https://github.com/microsoft/hlsl-specs/pull/634).
