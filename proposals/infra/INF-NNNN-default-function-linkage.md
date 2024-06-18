# Default Function Linkage

* Proposal: [INF-NNNN](INF-NNNN-function-linkage.md)
* Author(s): [Helena Kotas](https://github.com/hekota)
* Sponsor: [Helena Kotas](https://github.com/hekota)
* Status: **Under Consideration**
* Planned Version: 202y (Clang-only)

## Introduction

This document maps the current default linkage of functions in DXC and discusses how it could be implemented in Clang.

## Existing Behavior in DXC

In DXC today functions have internal linkage by default unless they are shader entry point functions or library export functions marked with an `export` keyword.

### Shader entry point functions

Compute shader compiled with `-T cs_6_6` generates entry point function with external linkage and un-mangled name:

```
[numthreads(4,1,1)]
void main() {}
```
DXIL:
```
define void @main()
```

This is the same in if the shader entry point function is defined in a library and compiled with `-T lib_6_6`:

```
[shader("compute")]
[numthreads(4,1,1)]
void main() {}
```
DXIL:
```
define void @main()
```

If the function is just declared without body it is not included in the final DXIL at all.

### Exported library functions

Shader library with an `export` function  generates DXIL function with _external linkage_ and _mangled_ name (compiled with `-T lib_6_6`):

```
export void f() {}
```

DXIL:

```
define void @"\01?f@@YAXXZ"()
```

### Other functions

HLSL functions that are not entry points or exported are most likely going to be inlined. This can be prevented by disabling optimizations, making sure the function is called and putting `[noinline]` attribute on the function, and the generated DXIL function it will have an _internal linkage_ and a _mangled_ name.

However, if such function is just declared without a definition, the generated DXIL will include the function declaration with _external linkage_ and _mangled_ name:


```
[noinline]
void f() {}

void g();

[shader("compute")]
[numthreads(4,1,1)]
void main() { f(); g(); };
```

DXIL:

```
define internal fastcc void @"\01?f@@YAXXZ"()

declare void @"\01?g@@YAXXZ"()

define void @main()
```

## Implementation in Clang

In Clang it is assumed linkage of functions can be determined during semantic analysis and that it does not change. The linkage is calculated based on many parameters and the results are cached for performance reasons. 

Identifying a shader entry point or exported function during parsing is straightforward and such function can be assigned correct linkage right from the beginning.

However, in case of functions that are not entry points or exported, if we want to keep on par with DXC, the final linkage cannot be determined until the whole translation unit is parsed and it is known whether the function is defined (has a body) or if it is just a declaration.

In order to implement DXC behavior there are two options:
1. Assign _internal linkage_ to non-entry and non-export functions by default while in Clang semantic analysis phase and change it to _external linkage_ during CodeGen phase in case the function does not have a body.

2. Assign _internal linkage_ to functions that are guaranteed to stay _internal_ in the final DXIL, such as the functions in unnamed namespace. For all other functions assume _external linkage_ for Clang semantic analysis and change it to _internal linkage_ in CodeGen phase for non-entry and non-export function definitions.

