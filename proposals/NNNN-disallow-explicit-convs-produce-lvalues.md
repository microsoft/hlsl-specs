---
title: "NNNN - Disallow all explicit conversions in inout parameters"
params:
  authors:
    - spall: Sarah Spall
  sponsors:
    - spall: Sarah Spall
  status: Approved
---

* Issues: https://github.com/microsoft/hlsl-specs/issues/639

## Introduction

DXC inconsistently allows some C style explicit casts to produce LValues and be
used as arguments for inout parameters.  However, C style explicit casts do not
produce LValues and inout parameters require LValues. We would like HLSL to follow
C++ and not allow C style casts to produce LValues.

## Motivation

It is inconsistent in DXC which C Style casts are allowed to produce LValues
for an inout parameter.

DXC allows explicitly casting an array of type T to a vector of type T as an inout parameter.
```
void fn(inout float4 F) {}

export void call() {
    float V[4] = {1.xxxx};
    fn((float4)V);
}
```
https://godbolt.org/z/ezzjj6dWo

And vice-versa (vector to array).
```
void fn(inout float F[]) {}

export void call() {
    float4 V = {1.xxxx};
    fn((float[4])V);
}
```
https://godbolt.org/z/xsfGhbW5P

DXC also allows the explicit casts in the following example.

```
struct FourFloats {
    float4 F;
};

struct AlsoFourFloats {
    float4 F;
};

struct AlsoAlsoFourFloats {
    float F[4];
};

void fn(inout FourFloats F) {}

[numthreads(1,1,1)]
void main() {
    AlsoFourFloats tmp1 = {1,2,3,4};
    fn((FourFloats)tmp1); // Allowed
    fn(tmp1); // Allowed under HLSL 2018.

    AlsoAlsoFourFloats tmp2 = {1,2,3,4};
#if __HLSL_VESRION == 2021
    fn((FourFloats)tmp2); // hangs the compiler under HLSL 2018.
#endif
}
```
https://godbolt.org/z/15q3rjY3Y

The following explicit casts are not allowed.
```
void fn(inout float4 F) {}

export void call() {
    int4 tmp = {1,2,3,4};
    fn((float4)tmp);
}
```
https://godbolt.org/z/aK3EadTKP
This is allowed if done as an implicit cast.
https://godbolt.org/z/7d7YK5TGb

Also disallowed.
```
struct FourFloats {
    float F1;
    float F2;
    float F3;
    float F4;
};

void fn(inout float4 F) {}

[numthreads(1,1,1)]
void main() {
  FourFloats FF = {1,2,3,4};
  fn((float4)FF);
}
```
https://godbolt.org/z/evMbq39nf

## Proposed solution

The proposed solution is that in Clang all explicit casts be disallowed
from producing lvalues.
