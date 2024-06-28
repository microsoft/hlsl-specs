<!-- {% raw %} -->

# Resource Representations in Clang and LLVM

* Proposal: [INF-0004](INF-0004-resources.md)
* Author(s): [Justin Bogner](https://github.com/bogner)
* Sponsor: [Justin Bogner](https://github.com/bogner)
* Status: **Under Consideration**
* Impacted Project(s): Clang
* PRs:
  [llvm-project/#90553](https://github.com/llvm/llvm-project/pull/90553)
* Issues:
  [llvm-project/#68006](https://github.com/llvm/llvm-project/issues/68006)

## Introduction

HLSL resources need to go through a few different representations throughout
the compilation flow. This proposal tries to describe the various places where
we will need to represent these and codify how we will go about representing
the resources in those places.

## Motivation

The life cycle of a resource needs to flow from a high level representation
that represents what the user wrote in HLSL source until it eventually is
emitted as DXIL by the DirectX backend in LLVM. We would like to design the set
of intermediate representations such that we can get good diagnostics, good
optimization, and we aren't likely to have to redesign the representation in
the short term. We also need to be mindful of how this will interact with the
SPIR-V backend.

## Proposed solution

At the HLSL level we want to lean on the existing infrastructure in clang as
much as possible, and avoid deviating from the norms unless there's a good
reason. This is different from how resources are handled at the HLSL level in
DXC. On the other end, when we're emitting DXIL we want it to be as compatible
as possible with existing drivers. This means that the DXIL representation
itself needs to be considered more or less fixed.

In LLVM IR we choose to represent resources using the ``TargetExtType``
infrastructure which was largely motivated by the need for target specific
opaque types like those used in SPIR-V code generation. In designing operations
on these types we take motivation from the DXIL representations, but since
we're not locked in to a stable format we're free to simplify and generalize
where it makes sense to do so.

### Clang ASTs

In the clang ASTs we'd rather avoid custom handling of DXIL resource types as
much as possible, and we're motivated by the idea of implementing whatever we
can as-if it was a library implementation of HLSL.

There are two major aspects to how we represent resources in clang:

1. We leverage the internal ``hlsl.h`` where possible and generate ASTs in
   HLSLExternalSemaSource where the expressivity of HLSL isn't sufficient for
   library solutions.
2. We encode side information about special treatment of types in attributes.

That is to say, at the AST level a resource type like ``StructuredBuffer``
should mostly just look like an arbitrary class, albeit one whose methods will
mostly be implemented by calling builtins that will later be translated into
resource specific operations. We decorate the class with ``HLSLResourceAttr``,
which encodes its resource class and kind.

### LLVM IR targeting DirectX

Resources in LLVM IR will be represented using ``TargetExtType``, which allows
us to create mostly opaque types, but they can have a target specific name,
list of types, and list of integer parameters. This lets us define something
like ``target("dx.Buffer", <4 x float>, isWriteable, isROV)`` for a buffer
containing 4 floats and holding information on whether it's writeable and/or an
ROV.

From here, there are two things to design:

1. The set of target types we need.
2. The set of operations on those target types.

Details are available in [llvm-project/#90553], but I'll provide a high level
overview here.

We can represent all buffer types with a single "dx.Buffer" type that's
parametrized. The information we need to represent all possible buffers is the
data type that is stored in the buffer (whether that's just a scalar, a vector,
or a struct type) and a few bits of information such as whether the resource is
writeable or it's in rasterizer order.

Similarly, we can handle constant buffers with some simple parameters regarding
their size and shape, and we can define samplers with just one value that tells
us what kind of sampler it is.

There's a little bit more contention when it comes to textures. Here we need to
deal with not only the type of data that we'll read from the texture, but the
various dimensionalities in how we access this data. There are some obvious
questions that come up here:

- should we represent dimensionality as different target types?
- can we get away with parametrizing the indices in a systematic way?
- what's the best way to talk about texture offsets?

In any case, the ways we can manipulate resources are represented as intrinsics
that largely map to DXIL operations, but they can often be simplified or
generalized using the richer type information we get from the ``target()``
types.

Given this approach, there are a few questions we need to discuss:

1. How do we represent uniformity (or not) of handle access.
2. Alignment requirements of various load/store operations.
3. How to deal with CheckAccessFullyMapped in the least obtrusive way.
4. The ubiquity of operations when we discuss the different texture types.
n
### LLVM IR targeting SPIR-V

Clang currently generates ``target("spirv.Image", ...)`` types when generating
code for OpenCL targetting SPIR-V. It's likely that we'll need to do some work
to handle all of the HLSL resources, but it looks likely that we can leverage
that existing infrastructure for SPIR-V.

There is no detailed plan for this yet, but the implementation experience
targetting DXIL and the existing patterns in the SPIR-V backend should put us
in a good place when we take on that work.

### DXIL

The DXIL representation that we lower to needs to be compatible with the DXIL
that DXC emits and existing drivers.

The representation we're going for is partially documented in [DXIL.rst], but
note that there are shortcomings to that document that make it somewhat
unreliable:

1. Some of the features described were future directions at the time of writing
   that don't exactly map to what we have today, such as the non-legacy
   ``cbufferLoad`` and ``GetBufferBasePtr``
2. Many features, especially form SM6.6 and above, are not documented there at
   all.

We'll need to validate what we're doing against the existing implementation in
DXC and by leveraging the DXIL validator.

[DXIL.rst]: https://github.com/microsoft/DirectXShaderCompiler/blob/main/docs/DXIL.rst#shader-resources

## Detailed design

TBD. Some details are available in [llvm-project/#90553].

[llvm-project/#90553]: https://github.com/llvm/llvm-project/pull/90553

<!-- {% endraw %} -->
