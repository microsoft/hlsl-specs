<!-- {% raw %} -->

# Feature name

## Instructions

> This template is a guideline for documenting a shader model feature.
> Unlike language-only features, these require DXIL changes and thereby if not
> hardware support, then at least hardware driver support.
> The section titles are meant to be retained in the final product,
> but the descriptions are to outline what should be in those sections
> and should be replaced by the feature-specific text.
> However, not all sections may be required for all features.
{}
> This template wraps at 80-columns. You don't need to match that wrapping, but
> having some consistent column wrapping makes it easier to view diffs on
> GitHub's review UI. Please wrap your lines to make it easier to review.
>
> When filling out the template below for a new feature proposal, please do the
> following first:
>
> 1. Exclude the "Planned Version", "PRs" and "Issues" from the header.
> 2. Do not spend time writing the "Detailed design" until the feature has been
>    merged in the "Under Consideration" phase.
> 3. Delete this Instructions section including the line below.

---

* Proposal: [NNNN](NNNN-filename.md)
* Author(s): [Author 1](https://github.com/author_username)
* Sponsor: TBD
* Status: **Under Consideration**

*During the review process, add the following fields as needed:*

* Planned Version: Shader Model X.Y
* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues:
  [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/issues/NNNN)

## Introduction

10,000 ft view of the change being proposed. Try to keep to one paragraph and
less than 10 sentences.

## Motivation

Describe the problems users are currently facing that this feature addresses.
Include concrete examples, links to related issues, and any relevant background.

The point of this section is not to convince reviewers that you have a solution,
but rather that HLSL has a problem that needs to be resolved.

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

<!-- {% endraw %} -->
