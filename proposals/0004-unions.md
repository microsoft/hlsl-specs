# Unions

* Proposal: [0004](0004-unions.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202y

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
* Union members and objects cannot have HLSL semantics applied to them.
  * As such, unions may not be used as input arguments to shaders.
* Union objects may not be stored in constant buffers.
* Union objects in buffer layouts are aligned as elements of their
  most-restrictive member type.
* Union objects in struct layouts behave as defined in C++.
* Union's cannot have user-defined constructors or destructors until the
  language supports them for other user defined data types (See:
  [0032](0032-constructors.md)).

## Detailed Design

This proposal depends on the adoption of [Strict Initializer
Lists](0005-strict-initializer-lists.md) because initialization of a union type
is incompatible with HLSL's object initialization rules.

> Note: With current rules which member of the union should be initialized is
> ambiguous in all cases and unions with differing numbers of scalar members
> would result in the whole initializer list being ambiguous.

HLSL unions will adopt the behavior defined in the [ISO C++ specification
(ISO/IEC 14882:2011)](https://timsong-cpp.github.io/cppwp/n3337/class.union),
except with the following additions and clarifications.

### Proposed Spec Language

A union is a class defined with the `union` keyword.

Non-static members of a union share overlapping storage. As such, a union may
only store the value of one non-static data member at a time. The lifetime of a
non-static data member begins when the member is initialized, and ends either
when the value is destroyed via an explicit destructor call, a different
non-static data member is initialized, or the union's lifetime ends.

A union may not contain any non-static data members of intangible type.

If a union contains more than one standard-layout structures which share a
common initial sequence of non-static members, the common initial sequence may
be accessed through any non-static union member containing the sequence.

The size of a union is sufficient to contain the largest of its non-static data
members, and each non-static data member is allocated at the union's base
address. The required alignment of a union object is the most restrictive
alignment of its non-static data members.

> Note: Next paragraph written assuming [Constructors](0032-constructors.md).

A union can have constructors, destructors and member functions. A union cannot
have base classes or be used as a base class. At most one non-static data member
of a union may have a default initializer specified as a
_brace-or-equal-initializer_ on the member declaration.

A union without a specified type or object name is an _anonymous union_. It
defines an unnamed object of unnamed type. Anonymous unions may only contain
non-static data members. Anonymous unions shall not have private or protected
members. The names of members of an anonymous union are defined in the scope
that encloses the union declaration, as such, the names of members of an
anonymous union must be distinct from all names declared in the enclosing
entity's scope.

Anonymous unions must be declared with an appropriate storage class for their
enclosing scope. When declared in namespaces scope an anonymous union must be
declared `static`, when declared in block scope they shall be declared in any
allowed storage class for the block or no storage class.

Members of union types may not be annotated with semantic annotations or other
attributes. No union type or class containing non-static data members of union
types shall be used as an input to an entry function.

Objects of union type, or of classes which contain non-static union members may
not be stored in constant buffers.

## Acknowledgments

Special thanks to [Dan Brown](https://github.com/danbrown-amd), and Meghana
Thatishetti (Unknown GitHub ID), for their contributions to this implementation.
