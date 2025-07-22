<!-- {% raw %} -->
# `const`-qualified Non-`static` Member Functions

* Proposal: [0007](0007-const-member-functions.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Review**
* Planned Version: 202y

## Introduction

HLSL does not currently support `const` non-`static` member functions for user-defined data
types. This proposal seeks to add support for `const` non-`static` member functions, and to
adopt const-correct behaviors across the HLSL library objects.

## Motivation

The absence of `const` non-`static` member functions causes some challenges since HLSL
injected ASTs do have `const` and non-`const` non-`static` member functions. Further, since
variables can be `const`-qualified, without the ability to specify `const` there
are some cases that cannot be worked around without breaking
`const`-correctness.

DXC has received a number of issues relating to this. Two recent issues are
listed below:

* https://github.com/microsoft/DirectXShaderCompiler/issues/4340
* https://github.com/microsoft/DirectXShaderCompiler/issues/4706

In the first issue, a user defined data type's functions are basically unusable if
the data type is placed in a `ConstantBuffer`. This results from the
`ConstantBuffer` access returning `const &` objects.

The second issue describes a similar problem, where overloaded operators on
instances of `const`-qualified user-defined types are unusable.

## Proposed solution

Following C++, HLSL will enable support for `const` non-`static` member functions and
instance operator overloads (henceforth collectively referred to as constant
member functions) to allow execution of member functions on `const` objects and
preserve `const` qualifiers.

Updates to HLSL's built-in data types to observe best practices in
const-correctness will follow the introduction of language support. Functions
which return mutable lvalue references will become non-constant member
functions, and functions which return constant lvalue references or object values
will become constant member functions.

## Detailed design
### Syntactic Changes

C++'s existing syntax for declaring constant instance functions is compatible
with HLSL. Adoption of this syntax does not introduce any syntactic ambiguities
with existing HLSL constructs. Adding the `const` keyword to the end of the
function declarator before the optional function body will denote a const
member function function. The `const` keyword applies to the implicit object
argument so it can only be applied to non-`static` member functions. See the
examples below defining both a constant function and a constant overload of the
call `()` operator:

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

Standard HLSL argument promotion rules will apply for the object parameter, but
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

Supporting constant member function overload resolution will break existing code
that calls member functions on `cbuffer`, `tbuffer` or global constant variables.
Consider the following valid HLSL:

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

This code is valid under HLSL 2021 because HLSL ignores the const-ness of the
implicit object parameter. On introducing constant member functions, this code
is ill-formed and will produce a diagnostic.

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

### Language Specification Updates

> The HLSL specification chapter on
> [**Overloading**](https://microsoft.github.io/hlsl-specs/specs/hlsl.html#Overload)
> specifies the overload resolution behavior for HLSL aligning with C++ behavior.
> [microsoft/hlsl-specs#408](https://github.com/microsoft/hlsl-specs/pull/408)
> provides an analysis of the impact of this behavior change on existing HLSL
> sources.

#### **Overload.Res.Sets**

For a given expression, the set of candidate functions may contain both member
and non-member functions. Member functions have an additional _implicit object
parameter_, which represents the object the function is called on. For the
purposes of overload resolution all member functions (static and non-static) are
considered to have implicit object parameters; constructors and destructors are
not.

When appropriate, an _implied object argument_ can be inferred from the context
in which overload resolution is occurring to denote the object being operated on.

The type of the implicit object parameter for non-static member functions of
type `T` is lvalue reference to cv-qualified `T`.

For conversion functions that have an implicit object parameter, the type of the
implicit object parameter will match the type of the implicit object argument in
the unresolved expression. For non-conversion functions that are included in the
candidate set by a _using-declaration_ in a derived class, the implicit object
parameter shall be of the type of the derived class. The implicit object
parameter of a static member function can match any object.

> Note: Conversion functions and _using-declaration_ surfaced member functions
> behave as if they are members of derived classes in overload resolution. The
> wording in the C++ spec is a bit convoluted, but that intent is carried over
> here.

No user-defined conversion sequences may be implicitly applied to an implicit
object parameter during overload resolution. In all other regards, the implied
object argument shall be treated identical to other arguments.

Arguments to the implied object parameter must not be held in temporary objects
and may not have user-defined conversions applied to match the implicit object
parameter type. An rvalue may only be converted to an implicit object parameter
if all other aspects of the type match.

If a candidate function is a function template, template argument deduction
generates a list of candidate function template specializations, which are then
handled the same as non-template function candidates. A single name may both
refer to one or more overloaded non-template functions and one or more function
templates. The candidate set for an unresolved expression shall combine all
function overloads and template function specializations to form a complete
overload set.

### Other Considerations

This change should have no impact on code generation through SPIR-V or DXIL
assuming that the existing parameter mangling for constant implicit object
parameters works as expected.

<!-- {% endraw %} -->
