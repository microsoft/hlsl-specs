<!-- {% raw %} -->

# Strict Initializer Lists

* Proposal: [0005](0005-strict-initializer-lists.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202y

## Introduction

HLSL should adopt C and C++ initializer list formatting rules, rather than
custom rules that are unintuitive and error prone.

## Motivation

HLSL supports flattened brace initialization such that the structure of the
bracket initializer on the right hand side of an initialization is ignored, and
only the number of initialization arguments matters. Further, vector and matrix
arguments are implicitly expanded.

This feature likely results in a variety of common errors as HLSL will attempt
to fit an initializer list to a structure regardless of the underlying structure
of the members.

In HLSL the following code is valid:

```c++
  struct A {
    int a;
    double b;
  };
  struct B {
    A a[2];
    int c;
  };
  B b = {{1, 1.2}, {2, 2.2}, 3};   // Array elements specified as members
  B b2 = {1, 2, 3, 4, 5};          // each field initialized separately
  B b3 = {{1, {2, 3}}, {4, 5}};    // Completely random grouping of arguments
  int4 i4 = {1,2,3,4};             // valid int4 in C-syntax
  B b4 = {i4, 5};                  // int4 implicitly expanded to 4 arguments
```

Formalizing this code to comply with C/C++ initializer list rules will likely
break existing code, however following C/C++ rules will allow error checking and
validation of initializer lists which is likely to catch bugs which may be
difficult to identify otherwise. Additionally in order to ease developer
adoption we can implement a clang fix-it to transform flattened initializers
into conformant initializer lists.

## Proposed solution

Adopt C & C++ initializer list rules, and remove HLSL-specific initialization
list behaviors. Specifically, this will remove implicit vector and structure
element extraction, and enforce type system rules for data types passed into
initializer lists.

This will also introduce C rules for zero-initialization including zero
initialization for structure members omitted from the initialization list.

This change will be forward source breaking, and backwards compatible with some
caveats. Current code that takes advantage of HLSL initialization semantics will
produce an error that the compiler can generate a Fix-It for. Code with applied
Fix-It will be backwards compatible to prior HLSL versions.

New code that takes advantage of C & C++'s zero-initialization behavior, will
not be backwards compatible to older HLSL versions.

## Detailed Design

HLSL 202y shall adopt specification language aligned with the [ISO C++
specification (ISO/IEC
14882:2011)](https://timsong-cpp.github.io/cppwp/n3337/dcl.init).

The language in the next subsection will replace the **Decl.Init.Agg** section
of the HLSL specification.

### Specification Language

An _aggregate_ is a vector, matrix, array, or class which contains
* no user-declared or inherited constructors
* no non-public non-static data members, and
* no non-public base classes

The subobjects of an aggregate have a defined _subobject order_. For vectors and
arrays the order is increasing subscript order. For matrices it is increasing
subscript order with the subscript nesting such that in the notation
`Mat[M][N]`, the ordering is `Mat[0][0]...Mat[0][N]... Mat[M][0]...Mat[M][N]`.
For classes the order is recursively the order of the base class, followed by
member subobjects in declaration order. Anonymous bitfields are not included in
the subobject ordering.

When initialized by an initializer list the elements of the initializer list are
initializers for the members of the aggregate in subobject order. Each member is
copy-initialized from the corresponding initializer-clause. If the
initializer-clause is an expression which requires a narrowing conversion to
convert to the subobject type, the program is ill-formed.

An aggregate that is a class can also be initialized by a single expression not
enclosed in braces.

An array of unknown size may be initialized by a brace enclosed
initializer-list. For arrays of unknown size the initializer list shall contain
`n` initializers where `n > 0` and will produce a one-dimensional array containing `n`
elements.

If an initializer-list contains more initializer-clauses than the number of
subbjects being initialized, the program is ill-formed.

If an initializer-list contains fewer initializer-clauses than the number of
subobjects being initialized, each member not explicitly initialized shall be
initialized as if by an empty initializer list.

If an aggregate class contains a subobject member that has no members in its
subobject order, the initializer-clause for the empty subobject shall not be
omitted from an initializer list for the containing class unless the
initializer-caluses for all following members of the class are also omitted.

An initializer-list that is part of a braced-init-list may elide braces for
initializing subobjects. If braces are elided, a number of initializer-clauses
equal to the subobject's number of elements initializes the subobject. If braces
are present, it forms a braced-init-list which initializes the subobject
following the rules of this section.

A multi-dimensional array may be initialized using a single braced-initializer
list or with nested initializer lists. When initializing with a single
braced-initializer the order of initialization matches the memory layout.

```hlsl
int x[2][2] = {1, 2, 3, 4};      // [0][0] = 1, [0][1] = 2,
                                 // [1][0] = 3,[1][1] = 4
int y[3][2] = {{1,2}, {3}, {4}}; // [0][0] = 1, [0][1] = 2,
                                 // [1][0] = 3, [1][1] = 0,
                                 // [2][0] = 4, [2][1] = 0
```

Element initialization behaves as if an assignment-expression is evaluated
from the initializer-clause to the initialized member. All implicit conversions
are applied as appropriate to convert the initializer to the member type. If the
assignment-expression is ill-formed and the element is a subobject, brace
elision is assumed and an assignment-expression is evaluated as if initializing
the first element of the subobject. If both assignment-expressions are
ill-formed the program is ill-formed.

When a union is initialized with an initializer-list, the initializer-list will
contain only one initializer-clause which will initialize the first non-static
data member of the union.

## Unanswered Questions

### Should we support initialization constructors (i.e. `uint4 i4{}`)?

This syntax conflicts with the effects annotation syntax which DXC supports
parsing but is unsupported in code generation. Should we just stop parsing it?

<!-- {% endraw %} -->
