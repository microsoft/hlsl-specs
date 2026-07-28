---
title: "NNNN - Feature name"
draft: true
params:
  authors:
    - author_username: Author 1
  sponsors:
    - tbd: TBD
  status: Under Consideration
---


## Instructions

> This template wraps at 80-columns. You don't need to match that wrapping, but
> having some consistent column wrapping makes it easier to view diffs on
> GitHub's review UI. Please wrap your lines to make it easier to review.

> When filling out the template below for a new feature proposal, please do the
> following first:

> 1. exclude the "Planned Version", "PRs" and "Issues" from the header.
> 2. Do not spend time writing the "Detailed design" until the feature has been
>    merged in the "Under Consideration" phase.
> 3. Delete this Instructions section including the line below.

---

*During the review process, add the following fields as needed:*

* Planned Version: 20YY
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

_The detailed design is not required until the feature is under review._

This section should grow into a feature specification that will live in the
specifications directory once complete. Each feature will need different levels
of detail here, but some common things to think through are:

* How is this feature represented in the grammar?
* How does it work interact other HLSL features (semantics, buffers, etc)?
* How does this interact with C++ features that aren't already in HLSL?
* Does this have implications for existing HLSL source code compatibility?
* Does this change require DXIL changes?
* Can it be CodeGen'd to SPIR-V?

## Alternatives considered (Optional)

If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing.

## Acknowledgments (Optional)

Take a moment to acknowledge the contributions of people other than the author
and sponsor.

