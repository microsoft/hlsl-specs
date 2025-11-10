<!-- {% raw %} -->

# Formalized Memory and Execution Model

* Proposal: [NNNN](NNNN-filename.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* PRs: [hlsl-specs#321](https://github.com/microsoft/hlsl-specs/pull/321)
* Status: **Under Consideration**

## Introduction

This proposal seeks to define the memory and execution models for HLSL. The goal
is to define a memory and execution model that is understandable to users,
portable across a wide variety of GPU hardware, and strikes a balance between
full portability and performance.

## Motivation

The HLSL and DXIL memory and execution model have never been fully defined. This
forces reliance on Windows device certification for behavior conformance, and a
general approach that the implementation defines the behavior.

This state is not ideal from the start, however as HLSL becomes more widely
portable, and DirectX moves to SPIRV the lack of a documented memory and
execution model makes it near impossible to ensure portability across byte code
formats.

The SPIRV-defined memory and execution model is constantly evolving and seeking
to address some of the specific problems discussed in this proposal, however
SPIRV is not designed to be written by humans. It is not a requirement that
HLSL's memory and execution models match SPIRV, just that SPIRV is expressive
enough to model programs in the model defined by HLSL.

This proposal is structured with multiple proposed solutions. Those will become
_Alternatives Considered_ as they are eliminated from consideration. There are
also two groupings of proposals to capture the execution and memory models
separately although they are tightly connected in the final representation.

## Execution Model Proposals

All execution model proposals assume behaviors documented in
[SPV_KHR_maximal_reconvergence](https://github.com/KhronosGroup/SPIRV-Registry/blob/main/extensions/KHR/SPV_KHR_maximal_reconvergence.asciidoc),
as well as additional reconvergence requirements for `OpSwitch` to match the
DXIL `switch` behavior such that tangles are formed by branch target (not
selector value), and tangles are expected to reconverge at labels in the event
of fall through.

### Proposed solution #1 : Full Lockstep

A full lockstep execution model is the simplest to understand. Under full
lockstep, all the threads in a warp must behave as if they share the same
program counter whether they are in the same tangle or not.

This execution model provides some of the strictest guarantees for memory
ordering and behavior. Consider the following code snippet:

<a name="example1"></a>

```hlsl
groupshared int X;

[numthreads(4,1,1)]
void main(uint GI : SV_GroupIndex) {
  if (GI == 0)
    X = 0;
  else if (GI == 2)
    X = 2;
}
```

In full lockstep this program is well-defined. Because all threads must act
as-if they share a program counter, no thread can execute the `else if`
condition or its block until thread 0 has executed the body of the `if`. This
enforces strict ordering of memory operations to `groupshared`.

### Proposed solution #2 : Lockstep Within A Tangle

The lockstep within a tangle execution model is a slightly relaxed variant of
the full lockstep model. It allows each tangle to have an independent program
counter. In this model the [example from solution #1](#example1) is undefined
because once thread 0 splits to form its own tangle, the second tangle can
continue executing until it reaches a reconvergence point. This creates a data
race writing to X between thread 0 and 2.

This model requires more precise definition of reconvergence points, however it
provides some ordering guarantees that make it safe. For example, the following
adjusted program is well-defined in this model.

<a name="example2"></a>

```hlsl
groupshared int X;

[numthreads(4,1,1)]
void main(uint GI : SV_GroupIndex) {
  if (GI == 0)
    X = 0;
  if (GI == 2) // Reconverges here because this is a new statement, not an else.
    X = 2;
}
```

### Proposed solution #3 : Independent Threads

This model is the most complicated, but also most flexible for compiler backend
optimization. In this model threads are allowed to have fully independent
program counters which only need to synchronize across tangles at designated
sync points (e.g. wave operations, barriers, etc).

Under this model the [example from solution #2](#example2) is undefined because
the program contains no synchronization points, so each thread can execute
independently and the memory ordering is not guaranteed.

To illustrate a particular challenge with this model, consider the following
example:

<a name="example3"></a>

```hlsl
groupshared int X;

[numthreads(4,1,1)]
void main(uint GI : SV_GroupIndex) {
  if (GI == 0)
    X = 0;
  GroupMemoryBarrierWithGroupSync(); // sync point!
  if (X == 0)
    X = 2; // How many threads are in the tangle here?
}
```

One problem with this model is not having clearly defined memory ordering which
can impact tangle formation. If a thread is allowed to execute the second `if`
body before all threads have finished evaluating the condition, tangle formation
becomes unintuitive and potentially undefined.

This can be made slightly stricter by requiring that branch statements (`if`,
`else`, `switch`, `for`, `while`, etc.) are thread sync points. It also likely
requires atomic operations to behave a sync points as well.

## Memory Model Proposals

Basically all modern GPUs implement some version of the [Heterogeneous Systems
Architecture
(HSA)](https://en.wikipedia.org/wiki/Heterogeneous_System_Architecture)
standards. This makes it reasonable that HLSL's memory model derive from HSA.

Specific concerns that must be addressed:
* What are the ordering requirements, if any, for memory operations to aliasing
  memory across a wave?
* What are the ordering requirements, if any, for memory operations to aliasing
  memory across a set of tangled threads?

## Appendix 1: Magic Decoder Ring

| DirectX Term | Khronos Term | Description |
| ------------ | ------------ | ----------- |
| thread, lane | invocation   | The computation performed on a single element as described in the program. |
|              | tangle       | A grouping of co-executing threads. |
| wave         | subgroup     | A group of threads which may form one or more tangles and are executed on a shared SIMD or other compute unit. |
| threadgroup  | workgroup    | A group of threads which may be subdivided into one or more waves and comprise a larger computation. |

<!-- {% endraw %} -->
