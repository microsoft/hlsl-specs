---
title: "NNNN - Automatic Differentiation in DXC"
params:
  authors:
    - llvm-beanz: Chris Bieneman
  sponsors:
    - tbd: TBD
  status: Under Consideration
---

## Introduction

This proposal adds compiler-assisted automatic differentiation support to DXC
through HLSL header libraries and a source-to-source transformation in the DXC
rewriter. Authors annotate ordinary HLSL functions to request forward-mode or
reverse-mode variants, which are emitted as HLSL and compiled through the
existing shader compilation pipeline. Authors can also supply custom reverse
derivatives, exclude computations from differentiation, and provide reference
implementations for use only in differentiated code. Authors should not have to
maintain a second implementation of each function's derivatives by hand.

## Motivation

Differentiable rendering, material fitting, inverse problems, and GPU-based
optimization need derivatives of shader computations with respect to parameters
such as material properties, coordinates, and texture values.

Today an application can maintain analytic derivatives by hand, evaluate finite
differences, or move the computation into an external differentiation system.
Handwritten derivatives must track every change to the original shader and
compose correctly across function calls. Finite differences require additional
evaluations and introduce a step-size tradeoff between approximation error and
floating-point cancellation. An external system can require a separate
representation of computations already expressed in HLSL.

Users training neural networks for texture compression, or working on other
differentiable rendering tasks, face similar challenges. Some have turned to the
Slang shading language, which provides built-in [automatic
differentiation](https://shader-slang.org/slang/user-guide/autodiff).

Real shaders also combine differentiable arithmetic with operations that need
application-specific treatment. A texture lookup may need to accumulate
derivatives into a separate resource, while address calculations and discrete
sampling decisions should remain ordinary computations. Authors need a way to
express these boundaries without rewriting the surrounding shader or pretending
that resource handles themselves have numerical derivatives.

## Proposed solution

The rewriter generates derivative code alongside the original functions, which
remain unchanged. The author chooses which functions are differentiated and how
derivatives propagate. Every derivative computation appears in the generated
HLSL, where it can be read and debugged.

### Scope and implementation model

The proposal has two complementary parts:

* Header libraries implementing differentiated values, derivative propagation,
  and gradient storage.
* A rewriter transformation that converts annotated functions into
  differentiated variants using those libraries.

This proposal adopts a DXC-specific extension and developer workflow that relies
on compiler-specific annotations and the DXC rewriter infrastructure. This
proposal does not make automatic differentiation a core language feature.

The command line usage for the proposed rewriter is:

```text
dxr -generate-differentials input.hlsl > generated.hlsl
```

The output can either be just the set of generated differential variants or the
original source with generated differentials added. Generate code is inserted
into the `user` namespace (tooling may provide options to customize this), and
differentiated variants are organized under the `user::ad` namespace with
separate namespaces for forward and reverse modes. Forward-mode variants are
placed under `user::ad::fwd` and reverse-mode variants under `user::ad::bwd`.
The rewriter emits the required `#include <ad/fwd>` and/or `#include <ad/bwd>`
directives. The headers will ship as part of the DXC distribution and are found
in the standard include paths and embedded in the binary for easy usage by
applications.

Applications compile the generated HLSL, together with callers of the generated
variants, using the normal DXC interfaces. Ordinary compilation accepts the
annotations but does not itself generate differentiated variants. Generation is
a separate step, so the transformed code can be inspected before compilation.

The design is intended to lower to ordinary HLSL arithmetic, local storage, and
resource operations rather than require new differentiation-specific DXIL
operations. The initial design targets HLSL 2026 or later. Version and profile
requirements beyond that baseline are listed under open questions.

### Requesting derivatives

Use `[[dxc::AutoDiff(fwd)]]`, `[[dxc::AutoDiff(bwd)]]`, or
`[[dxc::AutoDiff(fwd, bwd)]]` to request variants:

```hlsl
[[dxc::AutoDiff(fwd, bwd)]]
float Square(float x) {
  return x * x;
}
```

Forward mode propagates an input tangent alongside each active input's value.
For a function `f`, the result contains the primal value `f(x)` and the
directional derivative `J_f(x) * tangent`. The proposed API represents these
pairs with `ad::fwd::Value<T>`, whose fields are `value` and `derivative`.

For example, after rewriting the function above, a caller can use:

```hlsl
ad::fwd::Value<float> x = ad::fwd::Value<float>::Create(3.0f, 1.0f);
ad::fwd::Value<float> result = user::ad::fwd::Square(x);
// result.value is 9; result.derivative is 6.
```

Reverse mode propagates an output cotangent, or seed, back to active inputs.
For a function `f`, it computes `transpose(J_f(x)) * seed`. This is useful for
loss functions with many inputs and few outputs; a scalar loss typically uses
an output seed of one. A vector-valued result takes a seed of that vector type,
allowing the caller to choose the weighted combination of result components.
Neither mode implicitly constructs a full Jacobian.

The proposed API represents active reverse-mode inputs with
`ad::bwd::Variable<T>` and stores their accumulated cotangents in
`ad::bwd::GradientContext<T>`. The generated function returns the primal result:

```hlsl
ad::bwd::GradientContext<float> context =
    (ad::bwd::GradientContext<float>)0;
ad::bwd::Variable<float> x = ad::bwd::Variable<float>::Create(context, 3.0f);
float result = user::ad::bwd::Square(context, x, 1.0f);
float gradient = x.Gradient(context);
// result is 9; gradient is 6.
```

These are call-site fragments to place inside shader functions after generation.
For heterogeneous active parameter types, the proposed API uses separate typed
contexts; inactive parameters retain their original types. The precise generated
calling convention and its stability remain design questions.

### Controlling differentiation

Use `[[dxc::no_diff]]` to identify a parameter, expression, or statement that is
not to participate in differentiation:

```hlsl
[[dxc::AutoDiff(fwd, bwd)]]
float Adjust(float x, [[dxc::no_diff]] float scale) {
  return x * scale + [[dxc::no_diff]] floor(x);
}
```

The primal computation still evaluates `scale` and `floor(x)`. The generated
variant treats them as inactive: the input `scale` has no derivative slot, and
the annotated `floor(x)` contributes no derivative through `x`. The derivative
with respect to `x` in this example is therefore `scale`.

This marks a derivative boundary it does not claim that the annotated
computation is mathematically constant. It gives authors control over discrete
choices and operations outside the supported differentiation subset.

### Custom reverse derivatives

Use `[[dxc::BackwardDerivative(Name)]]` to associate an operation with an
author-provided reverse derivative, also called a pullback:

```hlsl
void SquarePullback(float x, float resultSeed, out float xGradient) {
  xGradient = 2.0f * x * resultSeed;
}

[[dxc::BackwardDerivative(SquarePullback)]]
float CustomSquare(float x) {
  return x * x;
}

[[dxc::AutoDiff(bwd)]]
float Loss(float x) {
  return CustomSquare(x);
}
```

For this example, the pullback receives the primal argument and result seed,
and produces the argument cotangent. The rewriter composes that pullback with
the surrounding differentiated computation. The proposed design also supports
custom member pullbacks and operations with only inactive arguments, where the
pullback can send result cotangents directly to an application-managed resource
sink.

Resource objects, samplers, and resource-containing carriers are passed as
passive values rather than wrapped in numerical gradient types. Custom pullbacks
can accumulate gradients into buffers directly, including through atomics.
This does not automatically differentiate arbitrary resource accesses or define
a synchronization or accumulation policy for the application.

### Reference implementations for differentiation

Some operations have an efficient rendering implementation but require a
different implementation for differentiation. Use
`[[dxc::PrimalSubstituteOf(Original)]]` to associate a reference
implementation with an original function. For example, an author can choose a
smooth reference for a function that quantizes its result:

```hlsl
float Evaluate(float x) {
  return floor(16.0f * x * x) / 16.0f;
}

[[dxc::PrimalSubstituteOf(Evaluate)]]
[[dxc::AutoDiff(bwd)]]
float EvaluateReference(float x) {
  return x * x;
}

[[dxc::AutoDiff(bwd)]]
float Objective(float x) {
  return Evaluate(x);
}
```

Ordinary calls continue to use `Evaluate`, returning the quantized value. In the
generated reverse computation, the rewriter uses `EvaluateReference` for both
primal evaluation and derivative propagation: the result is the unquantized
`x * x`, and the input cotangent is `2 * x * seed`. This deliberately computes
the derivative of the smooth reference, not of the original quantized function.
A substitute can name a custom backward derivative. Authors are responsible for
the relationship between the original and reference implementations:
substitution is not proof of numerical equivalence, and the primal result of the
differentiated path can differ from the original path.

### Initial capabilities and boundaries

The header libraries will provide forward and reverse rules for arithmetic and a
range of HLSL math intrinsics, including trigonometric, exponential, geometric,
and matrix operations. The rewriter composes supported operations and annotated
user calls, including functions with differing input and output shapes. Library
and transformation coverage may differ. This proposal does not commit to every
intrinsic overload or HLSL type. Efforts will be focused on the most commonly
used operations and types.

The proposed transformation also handles selected local assignments, component
operations, and loops. Reverse-mode loops may save earlier primal values in a
statically sized tape, or replay pure computation when a suitable static tape
bound is not available. Replay trades storage for extra computation and must not
be assumed safe for arbitrary side effects.

Unsupported cases must be diagnosed rather than silently produce zero or
incorrect derivatives. Diagnostics should explain the unsupported operation and
identify the affected source code. The exact supported subset and diagnostic
mechanism remain questions for review.

### Impact on Clang Migration

Because the rewriter generates derivative code which is then compiled by the
HLSL compiler, this tooling should work with the existing Clang-based HLSL
compilation pipeline without requiring modifications to the compiler itself.
Longer term, as the DXC codebase is deprecated, this code could be ported to
Clang to work as a refactoring tool on top of Clang's libTooling infrastructure,
or it could be migrated into MLIR where it could leverage existing
differentiation passes and infrastructure. These are outstanding questions which
need not be addressed by this proposal.

### Open questions

The following questions should be answered before or during full design drafting
and review:

* Which header APIs, attribute spellings, and generated names are public
  contracts, and how should their naming align with the repository's preferred
  public API capitalization?
* Which types, intrinsics, control-flow forms, methods, and parameter directions
  belong in the initial supported subset? Are higher-order derivatives in scope?
* How are derivative rules defined at discontinuities, ties, singularities,
  and for exceptional floating-point values?
* How should generation errors report original source locations, and should
  unsupported input fail the rewriter directly rather than downstream compilation?
* What restrictions make replay and primal substitution safe in the presence of
  resource reads, writes, atomics, and other observable side effects?
* How are gradient storage, initialization, reuse, and capacity checked, and
  how should capacity exhaustion be diagnosed or handled?
* How should authors select tape versus replay strategies, understand their
  storage and execution costs, and debug generated shaders?
* Beyond the HLSL 2026 baseline, which shader stages and target profiles are
  supported, and what feature-detection mechanism will be provided?
* What validation is needed for DXIL and SPIR-V portability, numerical
  correctness, runtime behavior, and performance?
* What packaging and build integration should make the headers and generation
  step available without exposing compiler implementation details?

## Detailed design

_Deferred until this proposal has entered the appropriate review phase, following
the proposal process. The proposed interfaces above establish discussion
material rather than a complete specification._

## Alternatives considered

* **Handwritten analytic derivatives.** The do-nothing approach. Retain full
  author control, but require a separately maintained implementation. Custom
  pullbacks preserve this option at selected boundaries without imposing it on
  the whole shader.
* **Header library alone.** The minimal approach. Allows direct use of
  differentiated types and expression builders, but requires authors to adapt
  ordinary HLSL themselves. The rewriter automates that adaptation while keeping
  the result in HLSL.
* **Full compiler-integrated differentiation.** The "magic" approach. Could
  avoid an explicit generation step and operate on compiler IR, but would need a
  separate design for integration, diagnostics, and derivative customization.
  This also makes debugging harder for users compared to an inspectable
  source-to-source workflow. This proposal instead adopts an inspectable
  source-to-source workflow; that choice does not rule out future tighter
  compiler integration.
