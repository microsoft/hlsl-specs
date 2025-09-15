---
title: 0036 - 202x Feature Deprecations
params:
  authors:
  - llvm-beanz: Chris Bieneman
  sponsors:
  - llvm-beanz: Chris Bieneman
  status: Under Review
---


 
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

#### Examples of effects syntax

```hlsl
< int foo=1; >
<
  string Name = "texa";
  int ArraySize = 3;
>;

sampler S : register(s1) = sampler_state {texture=tex;};
Texture2D l_tex { state=foo; };

int foobar2 {blah=foo;} = 5;

texture tex1 < int foo=1; > { state=foo; };


technique T0
{
  pass {}
}
Technique
{
  pass {}
}

int foobar5[] {1, 2, 3};
int foobar6[4] {1, 2, 3, 4};
```

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

## Disallow `cbuffer` initializers

DXC allows variables within a `cbuffer` to have initializer clauses. The
initializer clauses are ignored, and DXC does not issue a diagnostic. In HLSL
202x initializer clauses on declarations placed into an implicit or explicit
`cbuffer` declaration are illegal and will produce an error.


