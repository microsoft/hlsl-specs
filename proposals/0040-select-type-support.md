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
matrix types (e.g. structs).

## Motivation
The `select` intrinsic was introduced in HLSL 2021 to preserve the
non-short-circuiting behavior of pre-HLSL-2021 ternary operators, where both
sides are evaluated regardless of the condition. Its primary use is supporting
vector selection of components.

In DXC, the pre-HLSL-2021 ternary operator supported value types (scalar,
vector, and matrix) as well as some other arbitrary types (namely SamplerState).
DXC's `select` implementation was initially restricted to value types only;
sampler support was [added
later](https://github.com/microsoft/DirectXShaderCompiler/pull/5508) due to user
requests, but support for other types was not.

While Clang aims to match HLSL intrinsic behaviors to DXC, it wouldn't make much
sense for Clang's `select` implementation to have the same restrictions as
DXC's. HLSL in Clang aims to align more closely with C++ conventions, and given
that the C++ ternary operator works with more general types, it would be
reasonable for Clang’s `select` to be similarly general.

## Proposed solution
Allow Clang's `select` intrinsic to support more types outside of the ones
supported by DXC, such as structs. This support would apply through the scalar
degenerate case:
```hlsl
template <typename T>
_HLSL_BUILTIN_ALIAS(__builtin_hlsl_select)
T select(bool, T, T);
```
*Note: Since HLSL does not support array return types from functions, `select`
would not support arrays.*

This proposal does not suggest making similar changes to DXC, as DXC’s ternary
operator intentionally limits its supported types. Clang’s divergence here is
justified by its alignment with C++ semantics.

## Alternatives considered
An alternative approach would be to restrict Clang's `select` to value types
only, rather than supporting more general types. Since `select`'s main purpose
was to support vector selection of components, extending it to other types (like
resources) doesn't align with its original intent. Allowing the scalar
degenerate case to accept arbitrary types could also enable code that should
otherwise be illegal.

Under this approach, the manually added sampler support in DXC should be
reverted for consistency. Users who rely on `select` with SamplerState should
use the ternary operator instead.

Regardless of which approach is chosen, Clang's `select` should not mirror DXC's
current behavior of supporting only value types with a special case for
samplers. Clang should either support more general types (as proposed) or
restrict to value types only (this alternative).