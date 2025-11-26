---
title: "NNNN - Group Wave Index"
params:
    authors:
    - MartinAtXbox: Martin Fuller
    - damyanp: Damyan Pepper
    sponsors:
    - damyanp: Damyan Pepper
    status: Under Consideration
---

* Planned Version: Shader Model 6.10
* Issues: [#645](https://github.com/microsoft/hlsl-specs/issues/645)

## Introduction

The proposal is for two new compute shader constructs:

* `GroupGetWaveCount()`: returns the number of waves in a thread group
* `SV_GroupWaveIndex`: the index of the wave in the thread group

## Motivation

See [this detailed document](NNNN/group-wave-index-background.md) for the
original background and justification for this feature with some detailed use
cases.

Compute shader workloads consist of some number of thread groups, with each
thread group containing some number of waves and there being a number of threads
in the wave. Developers can make better use of shader resources if they can
determine information about how many waves are in the thread group, and which of
those waves the current thread is in.  For example, they may be able to avoid
moving data in and out of thread group shared memory if they know that there's
only one wave involved.


<!--

## Proposed solution

Describe your solution to the problem. Provide examples and describe how they
work. Show how your solution is better than current workarounds: is it cleaner,
safer, or more efficient?

## Detailed design

*The detailed design is not required until the feature is under review.*

This section should grow into a feature specification that will live in the
specifications directory once complete. Each feature will need different levels
of detail here, but some common things to think through are:

### HLSL Additions

* How is this feature represented in the grammar?
* How does it interact with different shader stages?
* How does it work interact other HLSL features (semantics, buffers, etc)?
* How does this interact with C++ features that aren't already in HLSL?
* Does this have implications for existing HLSL source code compatibility?

### Interchange Format Additions

* What DXIL changes does this change require?
* What Metadata changes does this require?
* How will SPIRV be supported?

### Diagnostic Changes

* What additional errors or warnings does this introduce?
* What existing errors or warnings does this remove?

#### Validation Changes

* What additional validation failures does this introduce?
* What existing validation failures does this remove?

### Runtime Additions

#### Runtime information

* What information does the compiler need to provide for the runtime and how?

#### Device Capability

* How does it interact with other Shader Model options?
* What shader model and/or optional feature is prerequisite for the bulk of
  this feature?
* What portions are only available if an existing or new optional feature
  is present?
* Can this feature be supported through emulation or some other means
  in older shader models?

## Testing

* How will correct codegen for DXIL/SPIRV be tested?
* How will the diagnostics be tested?
* How will validation errors be tested?
* How will validation of new DXIL elements be tested?
* How will the execution results be tested?

## Transition Strategy for Breaking Changes (Optional)

* Newly-introduced errors that cause existing shaders to newly produce errors
  fall into two categories:
  * Changes that produce errors from already broken shaders that previously
    worked due to a flaw in the compiler.
  * Changes that break previously valid shaders due to changes in what the compiler
    accepts related to this feature.
* It's not always obvious which category a new error falls into
* Trickier still are changes that alter codegen of existing shader code.

* If there are changes that will change how existing shaders compile,
  what transition support will we provide?
  * New compilation failures should have a clear error message and ideally a FIXIT
  * Changes in codegen should include a warning and possibly a rewriter
  * Errors that are produced for previously valid shader code would give ample
    notice to developers that the change is coming and might involve rollout stages

* Note that changes that allow shaders that failed to compile before to compile
  require testing that the code produced is appropriate, but they do not require
  any special transition support. In these cases, this section might be skipped.

## Alternatives considered (Optional)

If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing. Having these solutions and why they were rejected documented may save
trouble from those who might want to suggest feedback or additional features that
might build on this on. Even variations on the chosen solution can be interesting.

## Acknowledgments (Optional)

Take a moment to acknowledge the contributions of people other than the author
and sponsor.

-->

