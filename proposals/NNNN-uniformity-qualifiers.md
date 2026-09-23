<!-- {% raw %} -->

# Uniformity Qualifiers

* Proposal: [NNNN](NNNN-uniformity-qualifiers.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)

* Status: **Under Consideration**

## Introduction

The HLSL Single Program Multiple Data (SPMD) programming model defines a program
in terms of how it operates on a single element of data. An SPMD program may be
executed on a traditional scalar processor or a Single Instruction Multiple Data
(SIMD) processor. When executing on a SIMD processor the program may execute
where a single instruction produces results for multiple threads of execution
from the source programming model. This is sometimes referred to as Single
Instruction Multiple Threads (SIMT).

Under HLSL's execution model, groups of threads form hierarchical scopes:
* A _dispatch_ represents the full set of threads spawned from a CPU API
  invocation.
* A _thread group_ represents a subset of a dispatch that can execute
  concurrently.
* A _wave_ represents a subset of a thread group that represents in a single
  SIMD processor.
* A _quad_ represents a grouping of four adjacent threads in a wave.

When a shader is executing threads concurrently on one or more processing cores,
an emergent property of _uniformity_ exists within the thread group, wave and
quad scopes.

Uniformity can refer to data or control flow. If a variable has the same value
across all threads in a scope, it is said to be _uniform_ across that scope.
Similarly if all threads within a scope are actively executing instructions
within a control flow block, the control flow is said to be _uniform control
flow_ across that scope.

## Motivation

Uniformity of data and control flow are central concepts to SIMT execution
models, and is required for correct execution of shader programs. Despite
the importance of this fundamental property it is not represented in any
explicit way in the HLSL language.

This proposal, seeks to address that by introducing core concepts around
uniformity to HLSL's type system and programming model.

## Proposed solution

### Uniformity as a Type Qualifier

This proposal introduces a new set of type qualifiers to represent the different
scopes of uniformity:
* `group_uniform`
* `simd_uniform`
* `quad_uniform`
* non-uniform (default state with no associated keyword)

`group_uniform` is the highest scoping of uniformity, and implies all other
scopes. `simd_uniform` implies `quad_uniform`.

A new "UniformityReduction" cast will reduce the uniform scope allowing
conversion of one uniformity scope to another uniformity scope as long as the
source scope has a greater uniformity scope.

Any GLValue with a uniformity scope can be implicitly converted to a GLValue
with reduced uniform scope or no uniformity scope.

Any PRValue with a uniformity scope can be implicitly converted to a PRValue
with reduced uniform scope or no uniformity scope.

No implicit or explicit cast can increase uniformity scope.

HLSL library functionality that produces uniform results will be updated to
produce appropriately qualified uniform types. These functions can produce
uniform values from non-uniform inputs. For example:

```hlsl
simd_uniform bool WaveActiveAllTrue(bool);
quad_uniform bool QuadAny(bool);
```

Compile-time constants and Groupshared variable declarations imply
`group_uniform` uniformity.

Builtin operators will produce uniform result values based on the uniformity of
the intersection of the uniformity of the arguments.

Vector and matrix component access expressions and structure member expressions
will produce result values with the same uniformity of the base object.

```hlsl
groupshared int SomeData[10];
simd_uniform int WaveReadLaneFirst(int);

void fn(int Val) {
  simd_uniform Idx = WaveReadLaneFirst(Val); // produces a simd_uniform value.
  // group_uniform indexed by simd_uniform produces simd_uniform value.
  simd_uniform GSVal = SomeData[Idx];
  // group_uniform with group_uniform index produces group_uniform value.
  group_uniform GSVal2 = SomeData[SomeData[0]];
  // Binary operator of group_uniform and simd_uniform values produces a
  // simd_uniform value.
  if (GSVal > GSVal2) { // This control-flow can be defined as simd_uniform

  }
}
```

Uniformity qualifiers may be applied on shader inputs. When applied to an input
the compiler will diagnose known cases where the qualifier mismatches, and it
will trust the user in other cases. A runtime validation may be added to catch
incorrect source annotations.

### Uniformity Requirements for Functions

This proposal introduces a new set of attributes for defining the control flow
uniformity requirements of functions. These new attributes take the form:

```hlsl
[[hlsl::required_uniform(group|simd|quad)]]
```

With these annotations applied to function declarations the compiler can produce
diagnostics when functions with a required uniformity are called in contexts
with insufficient uniformity. For example, a quad or derivative method called in
non-uniform control flow can become an error that is trivially identified on the
AST.

<!-- {% endraw %} -->
