---
title: "NNNN - printf"
params:
  authors:
    - llvm-beanz: Chris Bieneman
  sponsors:
    - llvm-beanz: Chris Bieneman
  status: Under Consideration
---

## Introduction

This proposal introduces an implementation of `printf` portable to Shader Model
6.0+. The implementation is purely software capturing format arguments from the
GPU and performing string formatting on the CPU.

## Motivation

The ability to log strings and data from HLSL shaders has been a frequently
requested feature for debugging and other use cases. The FXC compiler supported
printf and DXC supports it for SPIR-V:

```printf
#if __hlsl_dx_compiler
#define CONST const
#else
#define CONST
#endif

CONST string first = "first string";
string second = "second string";

[numthreads(1,1,1)]
void main() {
#if __hlsl_dx_compiler
  // FXC doesn't allow using global strings.
  printf(first);
  printf(second);
#endif
  printf("please print this message.");
  printf("Variables are: %d %d %.2f", 1u, 2u, 1.5f);
  printf("Integers are: %d %d %d", 1, 2, 3);
#if __hlsl_dx_compiler
  // FXC limits to 9 parameters.
  printf("More: %d %d %d %d %d %d %d %d %d %d", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
#endif
}
```
([Compiler Explorer](https://godbolt.org/z/TTvz1YrYo))

With the introduction of variadic templates in [TC57 proposal
0010](https://hlsl-tc57.github.io/tc57/proposal/0010/), we can now implement
`printf` in a portable way for Shader Model 6.0 and later.

## Proposed solution

> This proposal is based on a [blog
> post](https://www.abolishcrlf.org/2025/12/31/Printf.html) I wrote last year,
> which has a functional proof-of-concept.

This proposal requires four key changes to DXC:

1. Variadic templates - proposed in [TC57-0010 Moder C++
   Features](https://hlsl-tc57.github.io/tc57/proposal/0010/)
2. Clarified `string` type rules.
3. A method to convert a string to an implementation-specific integer identifier.
4. DXIL container additions for a string table and subsequent validation rules.
5. A `printf` GPU and CPU header implementation.

### Clarified `string` type rules

Today in DXC a `string` type exists, and can be assigned by constant literal
character strings. Implementing `printf` as a function requires allowing
`string` objects to be assigned by other `string` instances and passed into
functions. This can be accomplished by treating `string` objects as intangible
objects the same as resource handles.

The built-in `string` type in HLSL should have no built-in operators, and should
only be assignable and copyable. It should be intangible and unable to be stored
in memory.

### String to Identifier

In the prototype implementation a string is converted at compile-time to an
offset into a string table, this conversion is the only real thing a user can
use a string for. The conversion can apply to the earliest use of a string in
the IR, and all uses of the string can be repalced with the integer value (or
its stored value). This makes it trivial to feed strings through functions, and
through control flow (a `phi` on strings becomes a `phi` on integers).

The 32-bit unsigned integer identifier (in DXIL's case an offset) can be written
to a UAV buffer in place of the actual string. The offset can be converted the
string by the CPU.

### DXIL Container

The DXIL container will gain a string table part. The string table will begin
with a null byte (so that offset 0 is a null string), and contain packed
null-terminated strings. The DXIL validator will be updated to allow the
presence of the string table, but will perform no validation of its contents.

### `printf` implementation

The printf implementation is two parts, a GPU encoder and a CPU decoder. The GPU
encoder will encode a "message" in a self-describing format that includes
per-thread string formatting information.

The CPU decoder will walk the output buffer decoding each message and producing
a formatted string output.
