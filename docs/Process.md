---
title: Proposal Process
---

The primary purpose of this repository is to provide visibility into the feature
development process for HLSL and solicit feedback from the wider community.
Despite the openness of this process there are two significant caveats that
should be noted:

1. Final decisions about what features are included or excluded from HLSL are
   made by the MSFT HLSL Team. Our goals are to make HLSL the best programming
   language across all supported runtime targets, not just DirectX or Vulkan.
2. Some HLSL features may instead go through a

   [Fast-track](#fast-track-for-extensions) process. This process is reserved
   for platform and vendor extensions and is not suitable to all features.

Feature proposals from outside the HLSL team will be interpreted as requests,
and may be considered or rejected based on team and release priorities. You
should not create a pull request against this repository if you're not committed
to at least making a best effort to navigate the process as described below.

If you want to request a feature but not get involved in the process, the best
way to request features for HLSL is to file GitHub issues rather than creating
pull requests against this repository.

This process draws heavily from
[Rust's RFC process](https://github.com/rust-lang/rfcs), and from
[Swift's Evolution process](https://github.com/apple/swift-evolution/), and is
further tweaked to align with the HLSL team's goals and priorities.

Significant project infrastructure or implementation details will also use this
process to refine and document the design process.

## Making a Proposal

The best way for an external contributor to propose a feature is through GitHub
issues (See the section below on "Filing Issues").

If you write a proposal yourself you must find a member of the HLSL team to act
as a _Sponsor_ for the change. The _Sponsor_ is responsible for tracking and
helping change proposals through the proposal life cycle. For Vulkan-specific
features we require at least one _Sponsor_ from the HLSL team and one _Sponsor_
from the Khronos Vulkan Working Group. If you need assistance finding a
_Sponsor_ for a proposal reach out to the [HLSL Team](Contact.md).

All feature proposals are evaluated against the goals for the next HLSL language
revision. The goals for the upcoming HLSL language version can be found
[here](HLSL202x.md).

When writing a feature proposal you should also familiarize yourself with the
HLSL [Design Considerations](DesignConsiderations.md).

## Proposal Lifecycle

Draft proposals are first provided as pull requests. They should be written
following one of the templates in the `proposals/templates` directory.

Add new proposals for language or runtime features directly in the `proposals`
directory. Add new proposals for project infrastructure or implementation
details of the compilers in the `proposals/infra` directory.

Proposals that follow the most simplified path from idea to feature will move
through the following states in order:

* **Under Consideration** - All proposed features start in this state. While
  under consideration features are reviewed by members of the HLSL team and
  feedback is solicited from users and hardware vendors.

* **Under Review** - If a feature is deemed to be in alignment with the release
  goals, and of value to the community a feature may be promoted to being under
  review. During this time, a feature specification must be drafted, revised,
  and accepted.

* **Accepted** - Once a feature is accepted it becomes a planned feature for the
  release. At this time changes to enable the feature under the new language
  mode can begin landing in the HLSL compiler. The Accepted state does not mean
  the feature will ship in the planned release. There are a variety of reasons
  why features may not make the final release, but it does signify an intent to
  bring the feature into the release.

* **Completed** - Once a feature is fully implemented in the main compiler
  branch under the appropriate language version, the proposal completed.

Additionally feature proposals may end up in the **Rejected** or **Deferred**
states.

**Rejected** features are features that will not be included in HLSL. All
rejected features will be appended with a detailed reasoning explaining the
rationale behind why the feature was rejected.

**Deferred** features can occur for a variety of reasons. Features that are
deferred may be provided with some justification for the deferral although the
requirements for justification are not high and could be as simple as
"insufficient resources".

### Differences for Infrastructure Proposals

Infrastructure proposals may skip the **Under Review** phase and go straight
from **Under Consideration** to **Accepted**. This flow is expected in cases
where the proposal does not impact end users, and may garner little to no
feedback from outside the core developers.

In cases where contributions are being made to the LLVM-Project, the **Under
Review** phase may be useful for communicating when a proposal has been posted
as an RFC to [LLVM's Discourse](https://discourse.llvm.org/). In this case the
proposal header should be updated to include a link to the Discord post.

### Moving Through States

#### Merging a New Proposal

The bar for a proposal to be merged should be kept low. The proposal must have a
sponsor prior to being merged, and must be approved by the sponsor. A PR
introducing a new proposal should be reviewed for obvious mistakes (typos,
grammar, etc). Reviewers may provide feedback on aspects of the design, however
the author(s) need not address all feedback in the PR before merging. Filing an
issue to follow-up on comments from the initial PR is an acceptable response to
feedback and should be done by the author(s) when resolving comments on the PR.

New proposals should be merged as **Under Consideration**. After assigning a
number and merging the PR the author(s) should file issues tracking the work to
flesh out and complete the detailed design.

PRs introducing new proposals for language features will be reviewed at the
[Design Meeting](/docs/DesignMeeting.md). PRs introducing new proposals for
DirectX or DXIL features will be reviewed by Microsoft on a regular cadence.

#### Completing the Detailed Design

As the proposal authors and sponsors work through issues with the proposal and
flesh out a complete design each change to the proposal will be reviewed.

#### Final Review

Once the authors and sponsors feel that all outstanding issues are resolved a
sponsor will file an issue to propose a review period, and create a PR to mark
the proposal as **Under Review**.

During the review period the sponsor will reach out to stakeholders (users,
partners, etc) to collect feedback about the proposal. Any issues that need to
be addressed will be filed and tracked.

If there are outstanding issues at the end of the scheduled review period, the
review period will be extended by one week. The extensions will continue
week-by-week until all outstanding issues are addressed.

#### Accepting a Proposal

After the review period concludes and all outstanding issues are addressed, a
sponsor will create a PR to mark the proposal as **Accepted**, at which time we
will accept PRs to begin implementation.

#### Implementation

During implementation a proposal may need to further evolve as the implementors
discover issues. Those issues will be addressed with PRs to the proposal and
reviewed.

Once the implementation is complete and all associated issues are resolved, a
sponsor will create a PR to mark the proposal as **Completed**.

## Filing Issues

Issues in this repository publicly tracks feature requests for the HLSL language
and HLSL runtime interfaces as well as issues with proposals and specifications
contained within the repository.

Please direct tooling feature requests to the
[DirectXShaderCompiler](https://github.com/microsoft/DirectXShaderCompiler/issues/new),
or [Clang](https://github.com/llvm/llvm-project/issues/new) as appropriate.

> Note: a tooling feature would be a feature that does not impact HLSL source
> representations in any way (no added syntax, APIs, or altered
> interpretations), and instead exposes new ways to use the DXC compiler or
> library.

This repository provides three custom issue templates:

1. Feature Request
2. Proposal
3. Spec

When filing feature requests please use the _Feature Request_ template. The more
detailed information you can provide in a feature request the easier it is for
our team to scope, prioritize, design and implement the requested feature.

When filing issues relating to a currently in-progress proposal (i.e. any proposal not
**Completed** or **Rejected**), use the _Proposal Follow-up_ template.

When filing issues relating to a completed feature or specification document
please use the _Spec_ template.

## Fast-Track for Extensions

Some features for HLSL expose new hardware capabilities and require years of
development before they can be made public. For these features we have a
fast-track process to incorporate platform-specific and vendor-specific
extensions to HLSL as long as they are _conforming extensions_. Extension
proposals should use the [Extension
Template](/proposals/templates/extension-template.md).

### Conforming Extensions

Conforming extensions are language features which do not add new language
behavior or syntax. They cannot remove or deprecate functionality, and they
cannot be breaking changes. They can add new builtin function declarations,
builtin data types, and attributes as long as the added features do not change
the rules of the language. All added declarations must be under a namespace, and
cannot be under the `hlsl`, `std` or global namespaces which are reserved for
core language features.

#### Extension Attribute Restrictions

Additionally there are limitations specifically for attributes. Added attributes
may not modify canonical types, or otherwise change how HLSL code is
interpreted. They can compile down to metadata that produces annotations, and
they can be used for analysis and verification. Adding attributes that change
language behavior must be done through the full review process. As some concrete
examples:

* Type attributes like `precise` and `groupshared` _can not_ be added as
  extension attributes, because they (1) modify underlying canonical types, and
  (2) are not namespaced.
* Type attributes like `[vk::ext_reference]` _can not_ be added as extension
  attributes, because it modifies the underlying canonical type.
* Parameter attributes like `[vk::ext_literal]` _can_ be added as an extension
  attribute, because it does not modify the type or behavior of the language it
  just annotates a declaration for additional verification.
* Entry attributes like `[NodeIsProgramEntry]` _can not_ be added as an extension
  attribute, because it is not namespaced. If instead it were spelled
  `[dx::NodeIsProgramEntry]` it would comply since it does not modify the code
  generation of the function it only changes generated metadata.

### Fast-Track Process

Features that meet the definition of a conforming extension can be merged
directly as **Accepted** features with only a PR review. During that review a
feature will only be rejected if it does not meet the restrictions of a
conforming extension, in which case it will need to either be revised to meet
that definition or go through the full review process.

### Extension Deprecation Process

If a significant number of user bugs arise with an extension and the platform or
vendor who contributed the feature abandons maintenance and no other party takes
up the maintenance an extension may be deprecated and removed following a
deprecation period of no less than 6 months.

Decisions to deprecate an extension will not be taken lightly, however carrying
broken features in the compiler will cause more harm to users than good.
