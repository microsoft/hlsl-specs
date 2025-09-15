---
title: "0040 - Select type support"
params:
  authors:
    - kmpeng: Kaitlin Peng
  sponsors:
    - kmpeng: Kaitlin Peng
  status: Accepted
---

---

* Planned Version: 202Y

## Introduction
This proposal seeks to extend the `select` intrinsic in Clang's HLSL
implementation to support additional result types beyond scalar, vector, and
matrix types (e.g. structs and arrays).

## Motivation
The `select` intrinsic was introduced in HLSL 2021 to replace the
non-short-circuiting vector ternary operators that existed in earlier versions
of HLSL. In DXC, this pre-HLSL-2021 ternary operator only supported scalar,
vector, matrix, and SamplerState result types. DXC’s `select` implementation
mirrors these restrictions.

While Clang aims to match HLSL intrinsic behaviors to DXC, it wouldn't make much
sense for Clang's `select` implementation to have the same restrictions as
DXC's. HLSL in Clang aims to align more closely with C++ conventions, and given
that the C++ ternary operator works with more general types, it would be
reasonable for Clang’s `select` to be similarly general.

## Proposed solution
Allow Clang's `select` intrinsic to support more types outside of the ones
supported by DXC, such as structs and arrays. This support would apply through
the scalar degenerate case:
```hlsl
template <typename T>
_HLSL_BUILTIN_ALIAS(__builtin_hlsl_select)
T select(bool, T, T);
```
This proposal does not suggest making similar changes to DXC, as DXC’s ternary
operator intentionally limits its supported types. Clang’s divergence here is
justified by its alignment with C++ semantics.
