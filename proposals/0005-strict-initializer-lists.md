<!-- {% raw %} -->

# Strict Initializer Lists

* Proposal: [0005](0005-strict-initializer-lists.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

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

## Unanswered Questions

### Should we support initialization constructors (i.e. `uint4 i4{}`)?

This syntax conflicts with the effects annotation syntax which DXC supports
parsing but is unsupported in code generation. Should we just stop parsing it?

<!-- {% endraw %} -->
