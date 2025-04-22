# Numeric Constants

* Proposal: [0003](0003-numeric-constants.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

A new C++ STL-styled numeric constants interface will enable migrating off older
inconsistent language features and make cleaner more concise code.

## Motivation

The HLSL Infinity constant syntax violates C token rules by using the `#`
character, and is not consistent with C or C++ language styling. This causes
technical challenges by using reserved preprocessor tokens, but also makes the
feature foreign and less approachable in a C-like language.

## Proposed solution

Starting with adoption the `#INF` token becomes unsupported preferring instead a
new library class modeled after the C++ `std::numeric_limits` classes. Below is
the proposed interface for the `hlsl::numeric_limits` class:

```c++
  template<typename Ty>
  class numeric_limits {
  public:
    static Ty min();
    static Ty max();
    static Ty lowest();
    static Ty denorm_min();

    // Implement infinity in terms of __builtin_huge_val
    static Ty infinity();
    static Ty negative_infinity();

    static Ty quiet_NaN();
    static Ty signaling_NaN();
  }
```

This enables a straightforward code transformation from `1.#INF` to
`hlsl::numeric_limits<float>::infinity()`. While the later is more verbose, it
is more clear and provides a more consistent C++ style.
