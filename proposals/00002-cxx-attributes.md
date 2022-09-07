# C++ Attributes

* Proposal: [0002](0002-cxx-attributes.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

The C++ 11 ISO standard introduced a standard syntax for attribute annotations
which is grammatically unambiguous when annotating a wide variety of language
elements. This syntax has become common, recognized and well know, and is an
ideal addition to HLSL.

## Motivation

With the introduction of bitfields in HLSL 2021, HLSL semantic syntax on members
of a struct or class is syntactically ambiguous with bitfields. Take the
following code example:

```c++
  struct {
    uint i : SV_RenderTargetArrayIndex;
  }
```

In this case the syntax is ambiguous with a bitfield declaration, on
encountering the `:` token the parser must look ahead to see if the next
token is a semantic identifier or if it is an integer constant.

Additionally, if we wish to extend the use of attribute annotations we will
encounter more ambiguities because the `:` character has other meanings in C and
modern C++ as well. to name a few examples: the ternary operator (`<boolean> ?
<a> : <b>`), range-based for syntax (`for (<var> : <collection>)`), and switch
label marking (`case 1:`).

## Proposed solution

Adopting C++ attributes enables an unambiguous annotation syntax for all the
cases where HLSL Annotations are currently used. Using C++11 attributes the
example above can can alternatively be written as:

```c++
  struct {
    uint i [[hlsl::SV_RenderTargetArrayIndex]];
  }
```

Which has no syntactic ambiguity. As in the example above, C++ attributes can
also be namespaced, which allows for a clearer delineation of the attribute's
applicability. This could enable more robust code sharing in codebases that
contain both C++ and HLSL.

Additionally, introducing C++ 11 attributes enables placing attributes on more
grammatical constructs in the language. C++ 11 attributes can be applied to
statements, declarations and expressions.
