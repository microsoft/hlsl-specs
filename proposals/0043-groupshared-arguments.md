---
title: "0043 - `groupshared` Arguments"
params:
  authors:
    - llvm-beanz: Chris Bieneman
    - spall: Sarah Spall
  sponsors:
    - spall: Sarah Spall
  status: Accepted
---

* Planned Version: 202x

## Introduction

This proposal introduces a new use of the `groupshared` keyword for function
arguments to allow passing `groupshared` arguments by address rather than by
value or copy-in/copy-out.

## Motivation

DXC's implementation of HLSL includes a set of Interlocked functions
implementing atomic operations on `groupshared` memory. These functions are not
expressible in HLSL and rely on special case implementation in DXC.

## Proposed solution

HLSL 202x will allow the `groupshared` type annotation keyword on function
parameter declarations. The keyword when applied to a parameter declaration of
type `T`, alters the qualified type of the parameter to a `groupshared T &`
(a reference to `groupshared` memory of type `T`).

```c++
void fn(groupshared uint4 A) {}
```

No implicit or explicit conversion can change the memory space of an object. To
perform such a conversion, a user must declare a new object in the destination
memory space and initialize it appropriately. For overload resolution, the
parameter type must be an exact match in order for overload resolution to
succeed since no conversions will be valid.

Allowed:
```c++
void fn(groupshared uint4 A) {
  float4 LocalA = (float4) A;
  doesSomething(LocalA);
  A = (uint4) LocalA;
}
```

Not Allowed:
```c++
void fn(groupshared uint4 A) {}
void fn2() {
  float4 B = 1.0.xxxx;
  fn(B); // Error:
  fn((uint4)B); // Error:
}
```

There is a mostly working proof of concept which includes test cases showing
valid cases and error cases. From my tests on this proof of concept it
appears this feature can safely
be enabled in all earlier language modes, but a warning should be added to let
users know they are using a language feature added in a newer language mode and
it might not be portable to older HLSL compilers.

It also looks like all types can be supported as groupshared arguments, including
user-defined data types.

## Alternatives considered

[Reference
types](https://github.com/microsoft/hlsl-specs/blob/main/proposals/0006-reference-types.md)
is an obvious alternative. This proposal introduces a slightly conflicting
syntax from what we would prefer with reference types available.

This more minimal feature has material benefit today for both DXC and Clang, and
can avoid Clang requiring special case handling for library functions. As such,
this proposal is preferred to waiting until references can be finalized.

## Detailed Design

Any type which is valid for a `groupshared` variable is valid as a
`groupshared` function parameter declaration.

### Overloads

```c++
void fn(groupshared uint shared);
void fn(inout uint u);

groupshared uint Shared;

void caller() {
  fn(Shared); // ambiguous

  uint Local;
  fn(Local); // Not ambiguous
}
```

```c++
void fn(groupshared uint shared);
void fn(uint u);

groupshared uint Shared;

void caller() {
  fn(Shared); // ambiguous

  uint Local;
  fn(Local); // Not ambiguous
  fn(5); // Not ambiguous
}
```

The above overload sets will result in an error that the call is ambiguous
when the call site argument is a `groupshared` variable.  They will not result
in an error at the call site if the argument is a local varible or a literal value.

A new warning will be added and will be emitted when a program calls a function
with an `inout` arg using a `groupshared` variable.  This warning will alert the
user to the existence of the new `groupshared` parameter annotation.

```c++
void fn(inout uint u);

groupshared uint Shared;
void caller() {
  fn(Shared); // warning will be produced at this callsite.
}
```

### Errors and Warnings

The `groupshared` type annotation keyword will be allowed on function parameter
declarations.  In language modes before HLSL 202x, a warning will be produced,
but it should still be supported if the compiler supports HLSL 202x.  If the
compiler does not support HLSL 202x an error should be produced.

```
error: 'groupshared' is not a valid modifier for a parameter
```

A function annotated with either `export` or `[noinline]` will not be allowed to
have function parameter declarations annotated with `groupshared`.  Doing so
will produce an error.

The argument to a `groupshared` function parameter must be a `groupshared`
variable.  If it is not, an error will be produced.

The argument to a `groupshared` function parameter must be of the same exact
type as the function parameter.  No implicit or explicit conversions are
allowed.  If they are not exactly the same, an error will be produced.

## Open Questions

Can this be supported in SPIRV?
