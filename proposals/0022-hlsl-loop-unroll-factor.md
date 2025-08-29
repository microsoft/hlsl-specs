---
title: 0022 - HLSL Loop Unroll Factor
params:
  authors:
  - farzonl: Farzon Lotfi
  sponsors:
  - farzonl: Farzon Lotfi
  status: Accepted
---

 
* Planned Version: 202x
* Impacted Projects: DXC & Clang

## Introduction

This proposal seeks to unify the diverging behaviors between the agreed upon
[spec for HLSL loop unroll](https://github.com/microsoft/hlsl-specs/pull/263)
and the current behavior of DXC.

The new spec wants to treat the unroll factor as a hint to the compiler for
partial loop unroll. The current behavior in dxc is that the unroll factor
specifies the maximum number of times the loop is to execute.

The DXC behavior was determined to violate user expectations by overriding
the existing loop termination conditions. Further the DXC behavior diverges
from how both clang and openCL treat the loop unroll factor which would have
made our port of HLSL loop unroll a bunch special cases instead of just
syntactic sugar that could sit on top of the existing loop unroll
implementations that exist in LLVM.

## Motivation
The HLSL compilers transition to clang has resulted in a compat break between
the [HLSL loop unroll implementation in clang](https://github.com/llvm/llvm-project/pull/93879)
and the one in DXC. While there is an expectation that the new compiler will
not be fully compatible with the previous compilers, These compat breaks should
 be minimized when possible.

## Proposed solution
In [HLSL 202X](0020-hlsl-202x-202y.md) the DXC implementation of the loop
unroll factor should no longer alter the  number of iteration executions.
Ideally the loop unroll factor will also become a compiler hint for partial
loop unroll. If this can not be done because of concerns of invalid DXIL
generation then the loop unroll factor as a feature should be removed from DXC.
Removal in this case means ignoring the unroll factor and issuing a warning to
inform the user.
