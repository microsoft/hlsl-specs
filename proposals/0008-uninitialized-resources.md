# Uninitialized Resource Errors

* Proposal: [0008](0008-uninitialized-resources.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

HLSL allows resource objects to be declared as local variables and function
parameters only if they are resolved during optimization to global resources
(either global declarations, or via a static index in `ResourceDescriptorHeap`).

Today this validation is performed post-optimization which code containing
invalid code paths to compile successfully as long as the invalid code is
removed during optimization.

This proposal seeks to move resource analysis earlier in the compiler (before
code generation), and changes the rules around resource validation.

## Motivation

The current implementation has two key problems:

* Quality of diagnostic locations degrades post-optimization
* Seemingly innocuous code changes make code invalid

As an example take the following invalid code:

```c++
RWBuffer<int> In;
RWBuffer<int> Out[2];

void fn(bool Cond) {
  RWBuffer<int> O;
  if (Cond)
    O = Out[1];
  O[0] = In[0]; // error: local resource not guaranteed to map to unique global resource.
}

[numthreads(1,1,1)]
void main() {
  fn(false);
}
```
(see: https://godbolt.org/z/KG5v98s8b)

Note, the comment indicating where the diagnostic is emitted. Because the
analysis is performed after optimization, it is only able to materialize a
location for the use of the unresolved value. In this trivial case it is easy
enough to see where the error lies, but in a more complicated example it might
not be so apparent.

Further, this code compiles successfully if the boolean value passed to `fn` is
`true` instead of `false`. This demonstrates the ability for seemingly unrelated
code changes to impact code correctness.

## Proposed solution

Describe your solution to the problem. Provide examples and describe how they
work. Show how your solution is better than current workarounds: is it cleaner,
safer, or more efficient?

## Detailed design

Building off clang's existing support for uninitialized variable analysis, we
can move this analysis into the Clang control flow graph (CFG) instead of post
optimization, which enables more robust diagnostic generation.

Take the following alternate diagnostics:

```c++
RWBuffer<int> In;
RWBuffer<int> Out[2];

void fn(bool Cond) {
  RWBuffer<int> O; // note: variable 'O' is declared here
  if (Cond) // warning: variable 'O' is used uninitialized whenever 'if' condition is false}}
    O = Out[1];
  O[0] = In[0]; // note: uninitialized use occurs here
}

[numthreads(1,1,1)]
void main() {
  fn(false);
}
```

These diagnostics already exist and are emitted by Clang for uninitialized
variable usage, and provide more actionable and understandable feedback to the
user.

In addition to generating these diagnostics using Clang's CFG, we should make
uninitialized use, or potential uninitialized use, of resource variables an
error during compilation. Making this always an error removes the ability for
seemingly unrelated changes to cascade resulting in unexpected compiler errors.

A potential implementation of this change is posted on LLVM's
[Phabricator](https://reviews.llvm.org/D130055).
