# Constructors

* Proposal: [NNNN](NNNN-constructors.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202y

## Introduction

As user defined data structures get more common and complex, the absence of
constructors and destructors is more and more awkward. This proposal seeks to
bring the full features of C++ initialization and destruction into HLSL.

## Motivation

Constructors are incredibly useful for ensuring data initialization and
implementing common patterns like Resource-Acquisition-Is-Initialization (RAII).

## Proposed solution

Introduce the following features to HLSL:
* C++ Constructors and Destructors
* C++ 11 Delegating Constructors
* C++ 11 Default and Deleted methods
* C++ 11 Default initializers
* Clang __attribute__((constructor)) and __attribute__((destructor))

Constructor syntax will match C++ 11 constructor syntax including support for
delegating constructors. It will be available on all user-defined data types
that support constructors in C++.

## Detailed design

### Global Construction

HLSL global constructors will be ordered following C++ conventions.
Constant-evaluated initializers occur first, followed by non-constant
initializers which are ordered by declaration order in the translation unit.

Each entry function will call the global constructors before executing any
further instructions and the global destructor immediately before returning.

In library shaders, the entry translation unit's global constructors are
executed after the linked library global constructors, and the entry's global
destructors are executed before linked library global destructors.

Non-trivial global constructors **will not** be stripped from library shaders.
Meaning, an unused global with a non-trivial constructor will be linked into the
final linked shader binary. This conforms to the C++ standard definitions for
static storage duration (see: ISO C++ Standard _basic.stc.static_).

Due to the inherent performance drawbacks of global construction, warnings will
be issued by default for any code that introduces a non-trivial global
constructor.

### Constructing Groupshared

Constructor initialization of `groupshared` objects will be followed by a memory
barrier and group sync. This comes with inherent performance costs, so shader
authors should use constructors with `groupshared` objects sparingly.

A `groupshared` user defined object that does not have a constructor, or has a
constructor that does not initialize any of its fields, will not incur the
memory barrier.

Due to the inherent performance drawbacks of `groupshared` construction,
warnings will be issued by default for any code that introduces a `groupshared`
object constructor.

### Constructors and Semantic Annotations

When a user defined data type contains members which are annotated with semantic
attributes and the data structure is initialized as a global or as a parameter
to the entry function, the semantic will be applied to the field after the
default constructor executes.

For example:

```c++
  struct VSIn {
    uint ID : SV_VertexID;
    float F;

    VSIn() : ID(0), F(1.0) {}
  };

  float4 main(in  VSIn  In) : SV_Position
  {
    // In.vid is SV_VertexID, In.f is 1.0
    VSIn In2;
    // In2.vid is 0, In.f is 1.0
  }
```

Currently HLSL requires that all members of a user defined data type passed into
an entry function must have semantic annotations to initialize the structure.
With the addition of constructors and default value initialization, HLSL will
instead require that every field either have a semantic annotation, or a default
initialization through either a default constructor or a default initializer.

HLSL will also introduce default initialization and defaulted and deleted
constructors. Default initialization is incompatible with HLSL annotations, and
can only be used on variable declarations that either use C++ attributes for
annotations, or have no annotation (see:
[proposal for C++ Attributes](0002-cxx-attributes.md)).

HLSL will adopt C++ rules for implicitly defining special member functions as
defined in the C++ 11 specification under
[`[special]`](https://timsong-cpp.github.io/cppwp/n3337/#special). This will
include a default constructor, destructor, copy constructor, move constructor,
and copy assignment operator, and move assignment operator.

For example:

```c++
  struct VSIn {
    uint ID : SV_VertexID = 2; // invalid
    uint ID = 2 : SV_VertexID; // invalid
    [[hlsl::SV_VertexID]] uint ID = 2; // valid
    float F = 1.0; // valid

    VSIn() = default;
  };

  float4 main(in  VSIn  In) : SV_Position
  {
    // In.vid is SV_VertexID, In.f is 1.0
    VSIn In2;
    // In2.vid is 0, In.f is 1.0
  }
```
