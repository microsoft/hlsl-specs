<!-- {% raw %} -->
# `const`-qualified Instance Methods

* Proposal: [0007](0007-const-instance-methods.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: TBD
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

HLSL does not currently support `const` instance methods for user-defined data
types. This proposal seeks to add support for `const` instance methods, and to
adopt const-correct behaviors across the HLSL library objects.

## Motivation

The absence of `const` instance methods causes some challenges since HLSL
injected ASTs do have `const` and non-`const` instance methods. Further, since
variables can be `const`-qualified, without the ability to specify `const` there
are some cases that cannot be worked around without breaking
`const`-correctness.

DXC has received a number of issues relating to this. Two recent issues are
listed below:

* https://github.com/microsoft/DirectXShaderCompiler/issues/4340
* https://github.com/microsoft/DirectXShaderCompiler/issues/4706

In the first issue, a user defined data type's methods are basically unusable if
the data type is placed in a `ConstantBuffer`. This results from the
`ConstantBuffer` access returning `const &` objects.

The second issue describes a similar problem, where overloaded operators on
instances of `const`-qualified user-defined types are unusable.

## Proposed solution

Following C++, HLSL will enable support for `const` instance methods and
instance operator overloads (henceforth collectively referred to as constant
member functions) to allow execution of member functions on `const` objects and
preserve `const` qualifiers.

Updates to HLSL's built-in data types to observe best practices in
const-correctness will follow the introduction of language support. Functions
which return mutable lvalue references will become non-constant member
functions, and method which return constant lvalue references or object values
will become constant member functions.

## Detailed design
### Syntactic Changes

C++'s existing syntax for declaring constant instance functions is compatible
with HLSL. Adoption of this syntax does not introduce any syntactic ambiguities
with existing HLSL constructs. Adding the `const` keyword to the end of the
function declarator before the optional function body will denote a const
instance function. See the examples below defining both a constant method and a
constant overload of the call `()` operator:

```c++
struct Pupper {
  void Wag() const { /* body omitted */ }
  void operator() const { /* body omitted */ }
};
```

### Semantic Changes

In a const member function, the implicit object parameter (`this`) becomes a
constant lvalue reference (`const &`). Code modifying any field of the `this`
object is ill-formed and will produce a diagnostic. Calls to non-constant member
functions are also ill-formed and will produce a diagnostic.

This change requires modifications to HLSL's overload resolution rules to
account for the const-ness of object parameters. When performing lookup of
possible overload candidates, overloaded functions with non-constant implicit
object parameters are invalid candidates when the implicit object is constant.

Standard HLSL argument promotion rules will apply for the object method, but
they cannot remove the `const` qualifier and shall not convert from a constant
lvalue to a non-constant rvalue by copying the implicit argument as is valid for
other arguments.

### HLSL Data Type Changes

Introducing constant member functions provides an opportunity to revisit the
const-correctness patterns of existing HLSL data types. With this change we will
perform an audit of existing data types to provide constant and non-constant
member functions as appropriate for the data type.

When applied to HLSL intangible types, the `const` qualifier will apply as if to
the handle, not the data the handle grants access to. For example, a `const
RWBuffer<T>` will still allow writes to the underlying resource, however the
resource variable itself cannot be re-assigned.

### Impact on Existing Code

Two of the changes described above have breaking impact on existing code. First,
supporting constant member function overload resolution will break existing code
that calls methods on `cbuffer`, `tbuffer` or global constant variables. Take
the following valid HLSL:

```c++
struct Hat {
  int getFeathers() {
    return Feathers;
  }
  int Feathers;
};

cbuffer CB {
  Hat H;
};

export int GetFeatherCount() {
  return H.getFeathers();
}
```

This code is currently valid because HLSL ignores the const-ness of the implicit
object parameter. On introducing constant member functions, this code is
ill-formed and will produce a diagnostic.

The code is ill-formed because these declarations inside a `cbuffer` are
implicitly constant. Today we ignore the `const`-ness of the object parameter
and resolve the function.

### Const-correct Resources

Implementing const-correct member functions on built-in HLSL data types should
have no disruption to users.

Consider the following code:

```c++
void setValue(RWBuffer<int> R, int Val, int Index) {
  R[Index] = Val;
}
void setValueConst(const RWBuffer<int> R, int Val, int Index) {
  setValue(R, Val, Index);
}
```

In `setValueConst`, the `const` qualifier applies to the _instance_ of the
`RWBuffer` parameter. A new `RWBuffer<T>` variable can be created from a `const
RWBuffer<T>` via copy-initialization (standard copy construction), allowing
`setValueConst` to call `setValue`. This does not violate const-correctness
since the handle is treated as const while the data it references is not.

### Detailed Description of Overload Resolution Rules

TBD: HLSL's current overload resolution rules are not fully codified anywhere
I'm aware of. For this design to be complete we need to fully specify the
overload resolution and standard argument conversions.

### Other Considerations

This change should have no impact on code generation through SPIR-V or DXIL
assuming that the existing parameter mangling for constant implicit object
parameters works as expected.

<!-- {% endraw %} -->
