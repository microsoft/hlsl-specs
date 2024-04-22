<!-- {% raw %} -->

# packoffset attribute

* Proposal: [INF-0003](INF-0003-packoffset.md)
* Author(s): [Xiang Li](https://github.com/python3kgae)
* Sponsor: 
* Status: **Under Consideration**
* Planned Version: 

## Introduction

packoffset attribute is used to change the layout of a cbuffer.

```
packoffset( c[Subcomponent][.component] )
```

It will overwrite the layout of a cbuffer with the packoffset attributes on
the constants.

Here are several examples of manually packing shader constants.

```
cbuffer MyBuffer
{
    float4 Element1 : packoffset(c0);
    float1 Element2 : packoffset(c12);
    float1 Element3 : packoffset(c1.y);
}
```
without the packoffset, Element2 will be in c1.x.


### Limitations

There're some limitations when apply packoffset on a constant.

1. packoffset is only allowed in a constant buffer.
```
float c : packoffset(c0); // invalid for apply packoffset on a global constant.
```

2. cannot mix packoffset elements with nonpackoffset elements in a cbuffer.
```
cbuffer A {
  float a : packoffset(c0);
  float b;  // invalid for mix packoffset elements and nonpackoffset elements.
}
```
3. Pack subcomponents of vectors and scalars whose size is large enough to prevent crossing register boundaries.
```
cbuffer A {
  float2 a : packoffset(c0.w); // invalid for a.x in c0.w and a.y in c1.x 
                               // which crossed register boundary.
}
```
4. struct, matrix, array cannot have component.
```
struct S {
  float a;
};

cbuffer A{
  S s : packoffset(c2.y); // invalid for offset to component y
  int a[2] : packoffset(c3.z); // invalid for offset to component z
  float2x2 m : packoffset(c6.z); // invalid for offset to component z
  S s2 : packoffset(c12); // valid
  int a2[2] : packoffset(c13); // valid
  float2x2 m2 : packoffset(c16); // valid
}
```

## Motivation

To support all HLSL features available in compute profile.

## Proposed solution

### AST

A new attribute HLSLPackOffsetAttr will be created with:
```
def HLSLPackOffset: HLSLAnnotationAttr {
  let Spellings = [HLSLAnnotation<"packoffset">];
  let LangOpts = [HLSL]
  let Args = [IntArgument<"RegNum">, IntArgument<"Component", /*optional*/ 1>]
}
```

The AST for MyBuffer example will be
```
HLSLBufferDecl cbuffer MyBuffer
  VarDecl Element1 float4
    HLSLPackOffsetAttr   0 0
  VarDecl Element2 float
    HLSLPackOffsetAttr  12 0
  VarDecl Element3 float
    HLSLPackOffsetAttr   1 1
  
```

### llvm IR

#### Layout struct for cbuffer
In HLSL, constants inside a cbuffer have the cbuffer as their declaration 
context. 
However, the variable scope of these constants is similar to a regular 
global variable. For instance, in the MyBuffer example, the constants are 
accessed as Element1 instead of MyBuffer::Element1. 
These constants are treated as global variables in clang AST.
At the end of Clang’s code generation, cbuffer will be translated into a 
global variable layout the cbuffer as a struct and replace the use of all 
the constants with fields for the global variable.
If translate into C,
 ```
 cbuffer A {
   float a;
   float b;
 }
 float foo() { return a + b; }
```
 will be translated into
```
 struct A {
   float a;
   float b;
 } cbuffer_A;
 float foo() { return cbuffer_A.a + cbuffer_A.b; }
```
struct A will created as the layout struct.
The use of a and b will be replaced with cbuffer_A.a and cbuffer_A.b.

#### packoffset on layout struct
To apply the packoffset to a cbuffer, the layout of the struct constructed for 
the cbuffer requires reordering of its fields, and padding should be introduced
if any gaps exist between the fields.
```
cbuffer CB {
  float a : packoffset(c2);
  float b : packoffset(c4);
  float2 c : packoffset(c2.z);
}
```
will get layout struct like
```
struct CBLayout {
  float4 padding0[2]; // c0/c1
  float a;         // c2.x
  float padding1;  // c2.y
  float2 c;        // c2.zw
  float4 padding;  // c3
  float b;         // c4.x
}
```

cbuffer llvm IR is not finalized yet.
llvm IR example will be added once cbuffer llvm IR is ready.

### metadata for reflection

Reflection reqire cbuffer offer the name, type, offset for each constant inside it.
This will be send to DirectX backend with metadata.
The reflection data is tracked with https://github.com/llvm/llvm-project/issues/89292.
Once that issue is resolved, packoffset only need to update the offset part of the 
metadata for cbuffer.

## Unresolved issue

How to support 16bit types.
The offset like c0.y is 32bit.
