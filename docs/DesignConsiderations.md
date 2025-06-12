# HLSL Design Considerations

When designing and proposing a feature for HLSL there are some design
considerations that should be taken into account.

## Goal Statement

HLSL seeks to be a powerful portable GPU programming language that enables high
performance applications to target GPUs across a wide variety of end user
devices. HLSL is explicitly not limited to Microsoft hardware and software
environments.

## Core Priorities

The following set of core priorities guides the HLSL design process.

### Portability and safety by default

HLSL language features should be portable and safe by default. HLSL strives to
be portable across APIs, hardware vendors, and hardware versions. Non-portable
features should be explicitly marked as such in the source representations (e.g.
in an API-specific namespace, or otherwise explicitly denoted).

Enhancing portability and safety also means curbing undefined behavior and not
sacrificing portability or safety features for performance.

### Public and open-source by default

HLSL depends on industry collaboration, and must prioritize open and equitable
collaboration. We must continue evolving our process and designs to be fully
open and to treat all participants equitably.

### Principle of least astonishment

We should aim to not surprise our users with unexpected behaviors. This means
recognizing our place in larger tooling ecosystems and considering that as we
adopt changes to HLSL.

Most HLSL users are C++ users. Acknowledging that certain aspects of C++ don't
map efficiently to GPUs (such as `virtual`, RTTI, and exceptions), we should
strive for alignment with C++ wherever possible and follow the [principle of
least astonishment](https://en.wikipedia.org/wiki/Principle_of_least_astonishment).

For example, adopting C++'s best-match algorithm for overload resolution aligns
behavior with C++ user expectations.

Similarly, most HLSL users aren't new to the language. We should avoid changing
the meaning of existing valid HLSL code, unless the benefits outweigh the costs
and we can support the transition with adequate tooling. An example of when we
didn't do as well as we could have here is HLSL 2021's short-circuiting
operators. While we did make some decisions to avoid changing the meaning of
syntax (removing boolean operators for non-scalar types), we didn't provide
diagnostics to catch behavior changes or performance impacting changes.

### We do not exist in a vacuum

Many of the problems we're solving are not unique to HLSL. We will look
to other languages, tools, and ecosystems as we consider how to evolve our own.

Consider python's ["The Zen of Python"](https://peps.python.org/pep-0020/) -
while Python's particular design decisions aren't always applicable to HLSL
many of their principles apply broadly to programming language design. We
should embrace their wisdom where it applies to us.

### Design for users

HLSL exists to serve users. Consider the experience of users and all the ways
HLSL can empower them to be more productive and creative. HLSL inherits a lot of
sharp edges both from its history and from C++; we strive to reduce those cases.

## Style Conventions

HLSL's built-in types and methods should conform to a consistent coding style.

* Data types, methods and built-in functions should all be `CamelCase`.
* Namespaces and keywords are lowercase, `_` separated.
* API-specific functionality should be added to an API namespace (e.g. `dx`,
  `vk`, etc.)
* Microsoft-style attributes interchangably use `CamelCase` and `_` separation,
  but should prefer `CamelCase`
* System Value semantics are case insensitive, should be specified `CamelCase`
  and prefixed `SV_`.

## Versioning

All features should consider how users can adapt to the presence or absence of
support. HLSL has two primary revisioning axis: language version and runtime
version. How the two versions interact is not always a clean and easy line to
see.

### Language Changes

> Language versioning changes the core language of HLSL: syntax, grammar,
> semantics, etc.

HLSL identifies language versions by the year of release (2015, 2016, 2017,
2018, 2021, ...), and future language versions have placeholder years (202x,
202y, ...).

Most language features do not require underlying runtime features so they can be
exposed in HLSL regardless of runtime targeting.

Some HLSL language features are _strictly additive_, and may be retroactively
enabled in older language modes. See the section below on "Exposing versioning"
for more information about retroactively exposing features.

### Runtime Changes

> Runtime versioning changes the library functionality of the language: data
> types, methods, etc.

HLSL's supported runtimes are DirectX and Vulkan. For DirectX versioning of HLSL
is broken down by Shader Model and DXIL version, and for Vulkan versioning is
broken down by Vulkan and SPIR-V version.

When a new runtime version is released and no previous HLSL compilers have
supported it, the feature can be added dependent only on targeting the new
runtime version. When a feature is added to a runtime version that has
previously been supported by a compiler release, the feature should be treated
as a retroactive addition. See the section below on "Exposing versioning" for
more information about retroactively exposing features.

### Exposing versioning

HLSL language and target runtime versions are exposed in the HLSL preprocessor
via the built-in preprocessor macros described below:

* **`__HLSL_VERSION`** - Integer value for the HLSL language version. Unreleased
  or experimental language versions are defined as a number larger than the
  highest released version.
* **`__SHADER_TARGET_STAGE`** - Integer value corresponding to the shader stage.
  Shader stage. The shader stage values are exposed as
  `__SHADER_STAGE_**STAGE**` (i.e. `__SHADER_STAGE_VERTEX`,
  `__SHADER_STAGE_PIXEL`, ...)
* **`__SHADER_TARGET_MAJOR`** - Major version for Shader Model target.
* **`__SHADER_TARGET_MINOR`** - Minor version for Shader Model target.

If these macros are not sufficient for a given feature new macros or other
mechanisms should be added as appropriate for the feature to enable developers
to know if a given compiler release supports the required feature(s).

For features that are added retroactively to an already final runtime or
language version, a `__has_feature` check should be added to allow the user to
query for feature support in the preprocessor instead of forcing the user to
check compiler versions explicitly. The Clang feature checking macros are
documented
[here](https://clang.llvm.org/docs/LanguageExtensions.html#feature-checking-macros).
The `__has_feature` macro is known to work in DXC, and should be used.
