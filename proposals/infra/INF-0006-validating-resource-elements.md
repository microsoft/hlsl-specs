* Proposal: [0006](0006-validating-resource-container-elements.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Impacted Project(s): (LLVM)

*During the review process, add the following fields as needed:*

* PRs: [#NNNN](https://github.com/microsoft/DirectXShaderCompiler/pull/NNNN)
* Issues: [#75676](https://github.com/llvm/llvm-project/issues/75676)

## Introduction
Resources are often used in HLSL, with various resource element types (RETs).
For example:
```
RWBuffer<float> rwbuf: register(u0);
```
In this code, the RET is `float`, and the resource type is `RWBuffer`.

There's a specific closed set of RETs that are valid for an HLSL
resource, which include basic types (ints and uints of sizes 16, 32, 64, as well as half,
float, and double). Structs that contain fields of these basic types 
(where all fields in the struct have the same type) are also allowed as RETs. 
Structs that either have structs as fields or arrays of structs as fields are also allowed,
as long as everything can fit in 4 32-bit quantities. Additionally, resource types are
not allowed within an RET, even if the underlying resource type has a primitive RET. 
If someone writes `RWBuffer<MyCustomType>` and MyCustomType is not a valid RET, there 
there should be infrastructure to reject this RET and emit a message explaining
why it was rejected as an RET.

## Motivation

Currently, in `clang\lib\CodeGen\CGHLSLRuntime.cpp`, there is a whitelist of valid
RETs. Anything that is not an int, uint, nor a floating-point type, will be rejected.
The whitelist isn't broad enough, because it doesn't include the case where the RET 
is user-defined. Ideally, a user should be able to determine how any user-defined 
structure is invalid as an RET. Some system should be in place to more completely 
enforce the rules for valid and invalid RETs, as well as provide useful information
on why they are invalid.

For example, `RWBuffer<bool> b : register(u4);` will not emit any error in DXC, 
but will in clang-dxc, despite the fact that `bool` is a valid RET.

## Proposed solution

The proposed solution is to use some type_traits defined in the std library, create
some custom type_traits that aren't defined there, and join them together to define a 
set of conceptual constraints for any RET that is used. These conceptual constraints
will be applied to every resource type that is defined, so that all HLSL resources 
have the same rules about which RETs are valid. Validation will occur upon resource
type instantiation.

## Detailed design

In `clang\lib\Sema\HLSLExternalSemaSource.cpp`, `RWBuffer` is defined, along with `RasterizerOrderedBuffer`.
It is at this point that the type_traits should be incorporated into these resource declarations.
All of the type_traits will be applied on each and every legal HLSL resource type. For every type_trait
that is not true for the given RET, an associated error message will be emitted.

The list of type_traits that define a valid RET are descsribed below:
| type_trait | Description|
|-|-|
| `__is_complete_type` | An RET should either be a complete type, or a user defined type that has been completely defined. |
| `__is_intangible_type` | An RET should not contain any handles with unknown sizes, i.e., should not be intangible. So, we should assert this type_trait is false. |
| `__is_homogenous_aggregate` | RETs may be basic types, but if they are aggregate types, then all underlying basic types should be the same type. |
| `__is_contained_in_four_groups_of_thirty_two_bits` | RETs should fit in four 32-bit quantities |



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
   int i;
};

struct c;

struct d {
  a ca;
  float4 cb;
};

struct e {
  int a;
  int b;
};

struct f {
  e x[2];
  e y[2];
};


RWBuffer<int> r1; // valid
RWBuffer<float> r2; // valid
RWBuffer<float4> r3; // valid

RWBuffer<x> r4; // valid
RWBuffer<a> r5; // valid - all fields are valid primitive types
RWBuffer<b> r6; // valid - all fields (the struct) has valid primitive types for all its fields

RWBuffer<c> r7;// invalid - the RET isn't complete, the definition is missing. 
// the type_trait that would catch this is `__is_complete_type`

RWBuffer<d> r8; // invalid - struct `a` has int types, and this is not homogenous with the float4 contained in `c`. 
// the type_trait that would catch this is `__is_homogenous_aggregate`

RWBuffer<f> r9; // invalid - the struct f cannot be grouped into 4 32-bit quantities.
// the type_trait that would catch this is `__is_contained_in_four_groups_of_thirty_two_bits`

```
## Alternatives considered (Optional)
We could instead implement a diagnostic function that checks each of these conceptual constraints in
one place, either in Sema or CodeGen, but this would prevent us from defining a single header where 
all resource information is localized.

## Acknowledgments (Optional)

<!-- {% endraw %} -->