<!-- {% raw %} -->

# Default Function Inlining

* Proposal: [INF-NNNN](INF-NNNN-default-function-inlining.md)
* Author(s): [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**
* Impacted Project(s): DXC, DXC-Clang

## Introduction

By default all functions called within an HLSL shader are inlined
at each call site.
This allows for additional optimizations, legalization, and flexibility.

## Motivation

Inlining called functions avoids having to fully define a calling convention
outside of entry point functions whose interface concerns how they interact
with the runtime rather than a calling convention internal to HLSL.

This allows optimizations specific to the call site.
For example, where a function parameter takes a constant value,
constant folding could precalculate values available at compile time that were
calculated in the function using those parameters.
Additionally, dead code that results from impossible control flow branches could
be eliminated.

It allows the elimination of redundant copying of parameters.
Inlined functions lose their parameters, exposing the copies into and out
of those parameters as redundant copies that optimization passes can eliminate.

It allows code that is only legalizable because of inlining.
This includes called functions that take resourced parameters that need
to map to unique, non-static global resources.
As parameters, that mapping can't be resolved.

## Proposed solution

All functions that are not entry functions will be inlined at the call site.
During code generation, all non-entry functions' linkage is set to external
and the `AlwaysInline` attribute is added for called functions.

The `always-inline` pass then inlines these functions.
It is called early in the process to accommodate the dependent passes.
These passes rely on only external functions being present and/or
that there is no parameter passing.
It does need to come after parameters are legalized.

If lifetime markers are enabled, the inlined function will add them for the
static allocas,
scoping them to the inlined function.

After inlining, the HLPreprocess step erases stacksave and stackrestore
intrinsics along with any users thereof and moves all allocas in non-entry
functions into the entry function entry block.

This leaves functions that have no runtime interface without any callers.
Functions with a runtime interface include entry, patch constant, node, and
ray tracing functions.
Other functions having no callers will get removed from the final output.

### Attributes and Flags

Most inlining-related attributes and flags won't have any effect on the inlining
results as the AlwaysInline attribute tends to override any others.
The exception would be the NoInline attribute, but that is beyond the scope of this
document.

The `inline` attribute has no effect as is is meant as a hint to the compiler
and the compiler is already always inlining all called functions.

Even when optimization is disabled using -Od or -O0, inlining is performed for HLSL.
However, lifetime markers are not added in this case.

### Compiler dependencies on inlining

Various parts of compilation depend on allocas all being in the same place at
the top of the entry block of the entry function.
This is only possible because allocas from any subfunctions get moved there
as part of the inlining process.

Various passes and other operations iterate through blocks of externally linked
functions such as library exports or the entry function.
Identification of operations invalid to the current stage are also propagated
to a single entry point or `shader` attribute function.

In some instances, the constant folding enabled by inlining can serve to
eliminate invalid overloads that would otherwise cause compilation to fail.

As mentioned in the example above, resource parameters are only valid when they
can resolve to a common global.
The only way to determine this is by inlining the functions to match the resources
used at the call site with their usage in the subfunction.

<!-- {% endraw %} -->
