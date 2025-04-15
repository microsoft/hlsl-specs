<!-- {% raw %} -->

# 202x Feature Deprecations

* Proposal: [NNNN](NNNN-202x-deprecations.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: TBD
* Status: **Under Consideration**
* Planned Version: 202x
* Issues: [#300](https://github.com/microsoft/hlsl-specs/issues/380),
  [#291](https://github.com/microsoft/hlsl-specs/issues/291),
  [#259](https://github.com/microsoft/hlsl-specs/issues/259),
  [#135](https://github.com/microsoft/hlsl-specs/issues/135),
  [LLVM #117715](https://github.com/llvm/llvm-project/issues/117715)

## Introduction

HLSL 2021 supports syntaxes and features that either do nothing, or are
potentially confusing. This proposal tracks a set of minimal breaking changes
for HLSL to remove misleading or confusing functionality.

## Motivation

This proposal is part of a larger effort to reduce carried forward technical
debt in HLSL compiler implementations.

## Proposed solution

### Removal of Effects Syntax

DXC supports parsing much of the legacy FXC effects syntax, however it emits
warnings and does not provide any behavior associated with the effects syntax.

In HLSL 202x we should disable effects parsing support and allow those parsing
failures to generate errors as would otherwise occur in HLSL.

### Removal of `interface` Keyword

DXC supports `interface` declarations, however the semantic utility of
interfaces is limited. Instances of interfaces cannot be created or passed
around to functions. They can only be used as a static-verification that all
required methods of an object are implemented.

Template-based polymorphic patterns available in HLSL 2021 and later enable many
of the code patterns that `interface` declarations would have previously been
used for and should be the supported path going forward.

### Removal of `uniform` Keyword

In DXC the `uniform` keyword is parsed and ignored. This may lead users to
believing it has some impact when it does not. We should remove it.

## Stricter restrictions on cbuffer Members

DXC's implementation of `cbuffer` declarations allows all sorts of declarations
inside the scope of a `cbuffer`, and does not interoperate well with C++
namespaces.

In HLSL 202x we should disallow any declaration that isn't a variable
declaration to be a member of a cbuffer, and we should seek to clearly define
the relationship between cbuffer declarations and their enclosing scope (i.e.
namespace).

<!-- {% endraw %} -->
