---
title: "NNNN - Feature name"
draft: true
params:
  authors:
    - author_username: Author 1
  sponsors:
    - tbd: TBD
  status: Accepted
---
<!-- {% raw %} -->

## Instructions

> This template is a guideline for documenting a platform or vendor extension.
> For a feature to be a conforming extension it must not change language
> behaviors. It can introduce new builtin functions, data types, and annotating
> attributes, but cannot introduce new language behaviors or rules.
>
> This template wraps at 80-columns. You don't need to match that wrapping, but
> having some consistent column wrapping makes it easier to view diffs on
> GitHub's review UI. Please wrap your lines to make it easier to review.
>
> Delete this Instructions section including the line below.

---

## Introduction

10,000 ft view of the change being proposed. Try to keep to one paragraph and
less than 10 sentences.

## Motivation

Describe the problems users are currently facing that this feature addresses.
Include concrete examples, links to related issues, and any relevant background.

The point of this section is not to convince reviewers that you have a solution,
but rather that HLSL has a problem that needs to be resolved.

If there is an existing extension that solves a similar use case explain why it
is insufficient, and how this extension is an improvement.

## High-level description

Describe your solution to the problem. Provide examples and describe how they
work. Show how your solution is better than current workarounds: is it cleaner,
safer, or more efficient?

## Detailed design

This section should describe the feature in enough technical detail that someone
other than the author could implement it. Each feature will need different levels
of detail here, but some common things to think through are:

### HLSL Additions

* What new APIs and data types are added?
* How does it interact with different shader stages?
* How does it work interact other HLSL features (semantics, buffers, etc)?
* Does this have implications for existing HLSL source code compatibility?
* How will users detect if the compiler supports this feature?

### Interchange Format Additions

* What DXIL and/or SPIR-V changes does this change require?
* What Metadata changes does this require?
* How will each new API and data type be lowered to the target format?

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

* How does it interact with other platform or vendor extension options?
* What underlying target requirements are prerequisite for the feature?
* What portions are require an existing or new optional feature?
* Can this feature be supported through emulation or some other means
  in older drivers/runtimes?

## Testing

* How will correct codegen for DXIL/SPIRV be tested?
* How will the diagnostics be tested?
* How will validation errors be tested?
* How will validation of new DXIL elements be tested?
* How will the execution results be tested?

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
