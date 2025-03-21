# Unions

* Proposal: [0004](0004-unions.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

Introduce C++ Union data types into HLSL.

## Motivation

Unions in C++ are used in a wide array of cases.

One common case is when the layout of data matches between two data types and
the user wants to be able to access the data interchangeably as the two types.
This is frequently used in C++ SIMD code in conjunction with anonymous data
structures to implement vector objects. For example:

```
struct vector {
  union {
    struct {
      float x;
      float y;
      float z;
      float w;
    };
    struct {
      float r;
      float g;
      float b;
      float a;
    };
    float f[4];
  };
};
```

Additionally, unions are often used to reduce the storage requirements when a
data structure may contain one of a exclusive set of objects. The example below
is a common tagged union:

```
struct FloatOrBool {
  enum Format {
    Invalid,
    Float,
    Bool
  } F;
  union {
    float f;
    bool b;
  };
};
```

## Proposed solution

Union data types are defined in *\[class.union\]*of the ISO C++ language
specification. HLSL 202x introduces a compliant implementation with some HLSL
specific clarifications.

* Following C++ Unions are always sized large enough to contain their largest
  member type.
* Union members cannot have HLSL semantics applied to them.
* Union objects in buffer layouts are aligned as elements of their
  most-restrictive member type.
* Union objects in struct layouts behave as defined in C++.
* Union objects cannot have semantics applied to them.
* Union's cannot have user-defined constructors or destructors until the
  language supports them for other user defined data types (See:
  [0007](0007-constructors.md)).

## Acknowledgments

Special thanks to [Dan Brown](https://github.com/danbrown-amd), and Meghana
Thatishetti (Unknown GitHub ID), for their contributions to this implementation.
