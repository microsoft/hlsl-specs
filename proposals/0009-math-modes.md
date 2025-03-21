# Math Modes

* Proposal: [0009](0009-math-modes.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x
* Dependencies: [0002 C++ Attributes](0002-cxx-attributes.md)

## Introduction

Shaders frequently need fine-grained control over the way the compiler optimizes
(or doesn't) math optimizations. To enhance developer control in a more robust
way than the existing `precise` qualifier, HLSL should gain a higher level
concept of math modes.

## Motivation

The `precise` qualifier is particularly gnarly to implement and is wrought with
bugs that are inscrutable to developers. The source of the implementation
challenges come from the fact that the precise attribute is applied to a
declaration, but does not impact the uses of the declaration. Instead it impacts
reverse-propagates and applies to all of the math expressions that are used to
compute the declared variable.

The goal of this proposal is to create a new language feature which allows
shader authors the control they need to replace precise, without the tooling
complexity.

## Proposed solution

First and foremost, since the goal is to _replace_ the `precise` qualifier, this
proposal should deprecate `precise` in the language. Allowing the new feature
and `precise` to exist together for a single language version will ease
adoption, however `precise` will be removed in the future.

### Math Modes

The core of this proposal is to introduce new math modes `strict` and `fast`.
The `strict` math mode prohibits optimizations which may impact the precision of
results. This prevents optimizations like fusing multiply and add instructions.
The `fast` math mode prioritizes speed over precision guarantees. This does not
mean that `fast` math is less precise. In some cases optimal fused operations
are faster, but the results are less consistent across hardware architectures.

As a simplified view, `strict` can be viewed as "execute the math as written in
source", while `fast` is "let the optimizer do its thing".

The new math modes are exposed through a variety of mechanisms described below.

### Attributes

The new `hlsl::math_mode()` attribute can be set to either `strict`, `fast`, or
`default`. The default math mode is `fast`, however this can be changed with the
compiler flag:`math-mode=precise|fast`.

The math attribute can be applied to functions or expressions, but it does not
propagate in the way that the `precise` keyword did.

For example:

```c++
  [hlsl::math_mode(strict)]
  float fma(float x, float y, float z) {
    return x * y + z;
  }

  float fma2(float x, float y, float z) {
    return [hlsl::math_mode(strict)] x * y + z; 
  }
```

In both of the above functions optimization to an FMA instruction is prevented.

### Namespaces

New math namespaces are also added which provide simplified access to math
operations with the expected performance characteristics.

For example:

```c++
  float f = hlsl::strict::fma(1.0, 2.0, 3.0); // strict mode math
  float f = hlsl::fast::fma(1.0, 2.0, 3.0);   // fast mode math
  float f = hlsl::fma(1.0, 2.0, 3.0);         // default mode math
```
