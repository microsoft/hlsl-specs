* Proposal: [0022](0022-validating-resource-container-elements.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Impacted Project(s): (LLVM)

*During the review process, add the following fields as needed:*

* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues: [#75676](https://github.com/llvm/llvm-project/issues/75676)

## Introduction

There's a specific closed set of types that are valid as element types for an HLSL
resource, which includes int/uint of sizes 16/32/64, half, float, and double. Structs that
contain fields of these primitive types (where all fields in the struct have the same type)
are also allowed as resouce element types. Structs that have structs as fields or arrays of
structs as fields are also allowed, as long as everything can fit in 4 32-bit quantities.
Arrays of these types are not valid as resource element types. Additionally, resource types 
are not allowed as resource element types, even if the underlyinh resource type has a valid
primitive element type. If someone writes `RWBuffer<MyCustomType>` we should reject it 
and give the user a nice diagnostic. 

## Motivation

There currently does not exist any detection for invalid resource element types.
This includes user-defined types. Ideally, a user should be able to
determine how any user-defined structure is invalid as a resource element type.
Some system should be in place to enforce the rules for valid and invalid
resource element types.

For example,
`RWBuffer<bool> b : register(u4);`
will not emit any error, despite the fact that `bool` is not a valid resource element type.

## Proposed solution

The proposed solution is to create a dedicated function to determine whether a given type
is a valid resource element type. The function will recursively examine the given input
type, and determine whether all leaf element types are the set of acceptable primitives
(i.e., int, uint, half, float, or double.) If, for example, the resource element type is
an array of other resources, an error should be emitted. The function will be run in Sema,
when the `register` keyword is detected, and applied to the LHS element type. At that point,
it will be determined whether the element type is valid or not.

## Detailed design

Initially, the function will start with the input resource element type. Due to the nature
of the problem, the function can be recursively reapplied to any vector or matrix-like structures
within the input type. Formally, the resource element type is valid if the function returns true
on the given input type, or if the function returns true on all fields within the given input type.

Firstly, the base case will be checked. The given input type will be compared to the set of acceptable
primitives that are valid for a resource element. (i.e., float, int, etc).
If there are no matches, then the resource element may be a struct. In that case,
the compiler will iterate through all fields of the struct, which may contain primitive members,
arrays, or other structs. The function will be recursively called on each field of the struct,
verifying that the leaf types are valid primitive elements.
If the function never returns false at any point, then the type is valid.

When a field is detected to not have a valid primitive leaf type, the location of the offending
field is saved, and the source location is used in the diagnostic output. 

* Examples:
```
struct x {
	int i;
};

struct a {
   int aa;
   int ab;
};

struct b {
   x bx;
};

struct c {
  a ca;
  float4 cb;
};

struct bad {
	x a;
	bool b;	
};

RWBuffer<int> // valid
RWBuffer<float> // valid
RWBuffer<float4> // valid
RWBuffer<x> // valid
RWBuffer<a> // valid - all fields are valid primitive types
RWBuffer<b> // valid - all fields (the struct) has valid primitive types for all its fields
RWBuffer<c> // valid - combo of above, valid primitive field, and struct that contains valid primitive fields.


// "'bad' is an invalid resource element type because 'b' has type 'bool', which is not a valid primitive 
// bool b;
//      ^ (located here)
RWBuffer<bad> // invalid - bool is not a valid primitive type for resource elements.

```
## Alternatives considered (Optional)

## Acknowledgments (Optional)

<!-- {% endraw %} -->