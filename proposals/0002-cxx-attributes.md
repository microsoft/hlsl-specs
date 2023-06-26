<!-- {% raw %} -->
# C++ Attributes

* Proposal: [0002](0002-cxx-attributes.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

The C++ 11 ISO standard introduced a standard syntax for attribute annotations
which is grammatically unambiguous when annotating a wide variety of language
elements. This syntax has become common, recognized and well known, and is an
ideal addition to HLSL.

## Motivation

HLSL has two syntaxes for specifying source annotations. One, the
Microsoft-style C Attribute syntax, which uses single brackets `[]` to enclose
an attribute and it's arguments:

```c++
[WaveOpsIncludeHelperLanes]
[shader("compute")]
[numthreads(1,1,1)]
```

The second, the HLSL annotation syntax, which annotates variable, field and
parameter declarations using a `:` to separate the name from the specifier:

```c++
SamplerState samp1 : register(s5);
Texture2D<float4> text1 : register(t3);

float4 main(float2 a : A) : SV_Target {
  ...
}
```

The existing syntaxes in HLSL have limitations. With the introduction of
bitfields in HLSL 2021, HLSL semantic syntax on members of a struct or class is
syntactically ambiguous with bitfields. Take the following code example:

```c++
  struct {
    uint i : SV_RenderTargetArrayIndex;
  }
```

In this case the syntax is ambiguous with a bitfield declaration, on
encountering the `:` token the parser must look ahead to see if the next
token is a semantic identifier or an integer constant.

This case is further ambiguous with user-specified semantics where the following
code is ambiguous and currently _not_ interpreted as a bitfield declaration:

```c++
  static int Foo = 1;
  struct {
    uint i : Foo;
  }
```

If we wish to add source annotations to more grammatical elements in the future
we will encounter more ambiguities because the `:` character has other meanings
in C and modern C++ as well. to name a few examples: the ternary operator
(`condition ? a : b`), range-based for syntax (`for (variable : collection)`),
and switch label marking (`case 1:`).

We will also encounter ambiguities with the `[]` syntax. We may encounter issues
with array indexing which valid in contexts where we may wish to annotate
sources in the future. In the future this ambiguity could grow if we incorporate
more C++ features, like lambdas.

## Proposed solution

Adopting C++ attributes enables an unambiguous annotation syntax for all the
cases where HLSL annotations are supported. Using C++11 attributes the example
above can be written as:

```c++
  struct {
    uint i [[hlsl::SV_RenderTargetArrayIndex]];
  }
```

Which has no syntactic ambiguity. As in the example above, C++ attributes can
also be namespaced, which allows for a clearer delineation of the attribute's
applicability. C++ defines that namespaced attributes not supported by the
compiler can be ignored. This enables more robust code sharing in codebases that
contain both C++ and HLSL.

Additionally, introducing C++ 11 attributes enables placing attributes on more
grammatical constructs in the language. C++ 11 attributes can be applied to
statements, declarations and expressions.

Below are a few more examples of C++ attributes that we could support:

```c++
  [[hlsl::layout_attribute]] // applies to the struct type
  struct {
    int x;
    int y;
  };

  Texture2D<float4> Tex [[hlsl::register(1, 0)]]; // applies to `Tex`;

  uint i [[hlsl::SV_RenderTargetArrayIndex]]; // applies to `i`.
  [[hlsl::SV_RenderTargetArrayIndex]] uint j; // applies to `j`.
  uint &[[hlsl::AddressSpace(1)]] Ref = ...;  // applies to the type `uint &`.

  [[hlsl::SV_Target]] // applies to the function `fn`.
  float3 fn( ) {
    [[hlsl::fast]] // applies to the compound expression `{...}`.
    {
      ...
    }
    float f = [[hlsl::strict]](1.0 * 2.0); // applies to the parenthesis expression `(...)`.

    [[hlsl::unroll]] // applies to the for-loop expression.
    for (int x = 0; x < 10; ++x) {
      ...
    }
  }
```
## Detailed design

The simplest explanation of this feature is supporting C++11 attribute syntax on
all shared grammar elements between HLSL and C++. This spec attempts to detail
some of the grammar and parsing implications and will specify the process by
which existing attributes will convert to C++ attributes.
### Attribute Parsing

This proposal introduces new grammar formulations for parsing attributes
matching some formulations from C++ `dcl.attr.grammar`. Specifically:

```ebnf
attribute-specifier-seq:    [ attribute-specifier-seq ], attribute-specifier
attribute-specifier:        "[" , "[" , attribute-list , "]" , "]"
attribute-list:             [ attribute ] ||
                            attribute-list , "," , [attribute] ||
                            { attribute } ||
                            attribute-list ,  "," , { attribute }
attribute:                  attribute-token , [attribute-argument-clause]
attribute-token:            identifier ||
                            attribute-scoped-token
attribute-scoped-token:     attribute-namespace , "::" , identifier
attribute-namespace:        identifier
attribute-argument-clause:  "(" , balanced-token-seq , ")"
balanced-token-seq:         [ balanced-token ] ||
                            balanced-token-seq , balanced-token
balanced-token:             "(" , balanced-token-seq , ")"
                            "[" , balanced-token-seq , "]"
                            "{" , balanced-token-seq , "}"
```

In contrast to existing HLSL annotations and Microsoft-style attributes, these
attribute identifiers are case-sensitive `identifier` tokens.


#### Statements

```ebnf
statement: [ attribute-specifier-seq ] , expression-statement ||
           [ attribute-specifier-seq ] , compound-statement ||
           [ attribute-specifier-seq ] , selection-statement ||
           [ attribute-specifier-seq ] , iteration-statement ||
           [ attribute-specifier-seq ] , jump-statement ||
           declaration-statement
           labeled-statement
labeled-statement: [ attribute-specifier-seq ] , "case" , constant-expression , ":" , statement
                   [ attribute-specifier-seq ] , "default" , ":" , statement
```

#### Declarations

The `attribute-specifier-seq` element supports annotating type declarations. The
following grammar formulations are valid:

```ebnf
class-key: "class" || "struct"
class-declaration: class-key , attribute-specifier-seq , identifier

alias-declaration: "using" , identifier , [ attribute-specifier-seq ] , "=" , type-id , ";"
```

<!-- {% endraw %} -->
