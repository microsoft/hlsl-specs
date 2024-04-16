<!-- {% raw %} -->

# C interface for HLSL compiler as a library - Work item breakdown #1
## (Adoption by ML team and ability to compile compute shader using library)

* Parent Proposal: [0016](../0016-c-interface-compiler-library.md)
* Author(s): [Cooper Partin](https://github.com/coopp)
* Sponsor: [Cooper Partin](https://github.com/coopp)
* Status: **Under Consideration**
* Impacted Project(s): (Clang)

## Introduction

An effort is underway to modernize compilation of HLSL based shaders by adding
HLSL compilation to clang. This document is a sub proposal for 
[0016](../0016-c-interface-compiler-library.md) to break down the work
required to achieve the first milestone of adopotion by the ML team and
ability to compile a compute shader using clang as a library.

The Issues created here will be ordered to help contruct a roadmap that can be
leveraged towards defining a realistic timeline to completion.

## Issues

Implementation work in this list is assumed to include tests!

[] Design and spec where the library will be built/exposed in the llvm-project
   source tree and how a developer would consume the library.

[] Design and spec the minimal entrypoints/function signatures and types
   for compiling a shader.

[] Validate design with ML team adopters to ensure that supported functionality
   being built meets their needs.
   The following discussion will help drive if the additional feartures will need
   to be added:
   * Add include handler support?
   * Expose linker support? (Might be included with clang from other work)
   * Expose optmizer support? (Might be include with clanga from other work)
   * Expose tooling featrures like container reflection, and other output inspection
     features?

[] Add skeleton library to llvm-project build system. This includes adding code
   that builds/links/calls into to the library ensuring that it is configured
   properly.

[] Add documentation for defined library entrypoints to llvm-project docs with
   information on how to use/compile a HLSL shader and pass outputs to the 
   D3D12 runtime.
   * Is there a way to put these docs under an 'experimental' grouping?

[] Design and spec out-of-process compile library architecture.
   * May not be needed to meet this first milestone, but thoughts should be
     captured early somewhere.

[] Wire compiler library entrypoints to produce bytecode/output data.
   * This item may need to be broken down further depending on the refactor
     work involved in connecting up clang outputs to library outputs.

[] Provide drops to ML team for integration and work through any issues found.

[] Refine documentation with updated details matching any changes
   * This is probably an on-going item, because the library might go through
     some edits/refactors along the way.  In any case, we should ensure that
     the docs remain 'source of truth' to what is being built by the 
     llvm-project repo.

<!-- {% endraw %} -->
