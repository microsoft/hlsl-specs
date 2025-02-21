# Overload Resolution

HLSL supports argument dependent lookup of function overload candidates, and an
algorithm to determine the best match from a set of possible candidates.

## DXC's Approach

The algorithm used in DXC is different for resolving user-defined functions than
for HLSL standard library functions which are compiler intrinsics rather than
true functions.

For true-functions, when processing a call expression, DXC generates a list of
all functions with the specified name. Any functions with an incorrect number of
parameters for the provided argument list are discarded as invalid. For each
remaining function, a conversion sequence is generated from each argument to its
corresponding parameter. The conversion sequences are scored, and the sum of all
conversion sequences for a given overload are compared against the sums of the
conversion sequences for other overloads. If one overload has the lowest score,
it is the best match.

The scoring based solution works based on assigning certain conversions as being
an order of magnitude worse than other conversions. For example, the score for a
float to integer conversion is orders of magnitude greater than the score for a
float to float-vector extension, so an overload candidate with two
float to float-vector extension conversion sequences will be chosen over an
overload candidate with one float to integer conversion.

```hlsl
bool fn(int, float) {
    return true;
}

bool fn(float2, float2) {
    return false;
}

export bool call() {
    float F = 1;
    return fn(F, F); // resolves to fn(float2,float2)
}
```
[Compiler Explorer](https://godbolt.org/z/KnKePeqob)

The second part of DXC's approach is how DXC selects truncated overload sets for
standard library functions. DXC processes overload candidates for intrisncs
outside the overload sets, and only puts one matching overload candidate in
the set (note the [function returning after encountering a
match](https://github.com/microsoft/DirectXShaderCompiler/blob/main/tools/clang/lib/Sema/SemaHLSL.cpp#L4828)).
This prevents ambiguous cases, where ambiguity would exist in standalone
functions. In the example below, `WaveActiveMax` is a standard library function
with both `float` and `int` overloads (among others). Both should be valid in
the overload set, however only the `float` overload is added to the set.

```hlsl
export bool callW() {
    bool B = true;
    return WaveActiveMax(B); // resolves float.
}

bool fn(int) {
    return true;
}

bool fn(float) {
    return false;
}

export bool call() {
    bool B = true;
    return fn(B); // Ambiguous
}
```
[Compiler Explorer](https://godbolt.org/z/ccTM63GGs)

### Problems With DXC's Approach

First and foremost the inconsistency between standard library functions and
user-defined functions is a source of confusion and bugs.

DXC's custom overload resolution also does not handle cases that can arise in
HLSL like constant implicit objects in member functions, non-member overloaded
operators, and user-defined conversion functions.

Additionally, an algorithm that depends on scores is subject to computing
limitations like numeric precision and overflow. As such the algorithm cannot
solve some case when a large number of parameters are involved.

## Specified Behavior: Clang Approach

In the draft language specification and in Clang's implementation, HLSL adopts
C++'s best match algorithm and candidate selection algorithms. HLSL extends the
set of conversion ranks defined by C++ to included vector and matrix dimension
and element conversions. The conversions are ranked in accordance with how DXC
assigned scores. With this approach for a given overload set, any overload that
Clang resolves will match the overload that DXC resolves.

Clang will not always resolve an overload in cases that DXC would, this is true
of user-defined functions, but even more true when the difference in standard
library function resolution is taken into account.

### Problems with the Specified Behavior

The specified behavior reports ambiguity in more cases than DXC. While in some
cases this is a benefit, and adapting existing code is generally simple, it
may impose a significant burden for some adopters.

## Experiment!

A clear impediment to decision making is insufficient data about the impact of
these changes on user code. Compiling proprietary HLSL sources give us
visibility into how these decisions may impact users.

The codebase used to test is comprised of 188 base shaders which are
compiled to 4757 unique shader variants making heavy use of the C preprocessor
to differentiate shader variations. The shaders contain cumulatively over 400000
lines of HLSL. Important caveat: these sources may not be representative of a
majority of HLSL users as these shaders do not come from video games.

Migration of these shaders to build with Clang with updates to both the shader
source and Clang's defined HLSL intrinsics header took about half a day of
concerted effort. Expectation is that would be reduced for software developers
due to mitigations implemented in Clang, although the degree of reduction
depends on the mitigation strategy.

This effort identified three classes of overload failures:

* Missing overloads in Clang that DXC supports.
* Overloads that DXC implicitly resolves to reasonable results.
* Overloads that DXC implicitly resolves to potentially bad results.

### Missing Overloads

An example of a missing overload is the unsigned integer overloads for `abs`.
The [official
docs](https://learn.microsoft.com/en-us/windows/win32/direct3dhlsl/dx-graphics-hlsl-abs)
define support for `abs` overloads for `float` and `int`, however in practice
DXC supports valid lowering for all 16, 32 and 64 bit arithmetic types signed
and unsigned. The unsigned integer case is a no-op.

```hlsl
export uint call(uint I) {
    return abs(I); // no-op
}
```
[Compiler Explorer](https://godbolt.org/z/MsrEceM4E  )

### Implicitly resolved; reasonable results

In DXC, math operations which are only supported for floating point types where
DXC will resolve the type as `float` when integer types are provided. Some
examples of such operations are `rcp`, `exp`, `pow` and `sqrt`. None of these
operations really make sense on integers, so it is unlikely that the user
expected integer lower.

One important note here is that these operations produce implicit conversions,
which DXC may not warn about:

```hlsl
export float call(int I) {
    return sqrt(I); // calls sqrt(float)
}
```
[Compiler Explorer](https://godbolt.org/z/cf8W7455s)

Another good example of reasonable results are cases like `max`, `min`,
`select`, and `clamp` when applied to mixes of vector and scalar operands:

```hlsl
export int4 call(int4 I, int Min, int Max) {
    return clamp(I, Min, Max); // calls clamp(int4, int4, int4)
}
```
[Compiler Explorer](https://godbolt.org/z/9jTe1Pq4x)

### Implicitly resolved; potentially bad results

Some math operations where DXC matches intrinsics come with significant
performance impacts. For example consider the `lerp` intrinsic which only has
floating point implementations. This case also emits no user diagnostics, and
produces _a lot_ of implicit conversions:

```hlsl
export float call(int I, int J, int K) {
    return lerp(I, J, K); // calls lerp(float, float, float)
}
```
[Compiler Explorer](https://godbolt.org/z/aWET9WTEc)

## Possible Solutions

Any solution should involve adding missing overloads that DXC lowers to valid
and efficient IR. The absence of those overloads should be viewed as a bug in
Clang. The following possible solutions should be viewed as applying only to
cases where DXC resolves overloads through implicit conversion of arguments to
cases that Clang identifies as ambiguous.

### DXC-like scoring algorithm

One potential "full" mitigation strategy is to align Clang with DXC's best-match
resolution algorithm. This could be done in a less-invasive method than DXC's
implementation however it has significant drawbacks. Since this is unlikely to
be the correct path for the language long-term it would be a significant
investment for a short-lived solution.

### Make all builtins argument independent templates

Another possible "full" mitigation strategy is to use C++ templates to more
flexibly design intrinsic declarations. This would likely involve declaring
intrinsics as open-ended templates where the return type and argument types
could be resolved independently, and relying on builtin function validation and
codegen to generate legalized IR.

This is the worst possible solution both in terms of the additional accrued
technical debt in both semantic analysis and codegen, and because it would
dramatically reduce cases where Clang could emit useful diagnostics for implicit
conversions.

This option is included only because it is technically feasible, not because it
is a good idea.

### Careful Curation of Overloads

A more measured partial mitigation is to add additional overloads to builtin
functions to resolve ambiguity in some but not all cases. Following this model
overloads are grouped into three categories:

* Overloads that can be lowered to efficient IR (e.g. `select`, `clamp`, `min`
  and `max` for mixed vectors and scalars).
* Overloads that can be applied predictably to reasonable IR with conversion
  diagnostics (e.g. `rcp`, `exp`, `pow` and `sqrt`).
* Overloads that resolve to significantly inferior IR (e.g. `lerp`, `step`).

This proposal suggests that:
* The first category of overloads should be added to HLSL as official language
  overloads.
* The second category of overloads should be added as HLSL 202x features to be
  removed in HLSL 202y, and Clang should diagnose the implicit conversions and
  warn about deprecation in 202x pending removal in 202y.
* The third category of overloads should be left out from Clang and produce
  errors when migrating from DXC to Clang.
