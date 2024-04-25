* Proposal: [0022](0022-validating-resource-container-elements.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8
* PRs:
* Issues:
  [#75676](https://github.com/llvm/llvm-project/issues/75676)

## Introduction

There's a specific closed set of types that are valid as element types for an HLSL resource, 
which includes int/uint of sizes 16/32/64, half, float, and double. If someone writes 
`RWBuffer<MyCustomType>` we should reject it and give the user a nice diagnostic. 

## Motivation
There currently does not exist any design for how to detect invalid resource element types.
The compiler will need to analyze resource element types to determine whether the element type
is valid and acceptable. This includes user-defined types. Ideally, a user should be able to
determine how any user-defined structure is invalid as a resource element type. 

## Proposed solution

The proposed solution is to create a dedicated function to determine whether a given type
is a valid resource element type. The function will  recursively examine the given input
type, and determine whether all leaf element types are the set of acceptable primitives
(i.e., int, uint, half, float, or double.) If, for example, the resource element type is
an array of other resources, an error should be emitted.

## Detailed design

Initially, the function will start with the input resource element type. Due to the nature
of the problem, the function can be recursively reapplied to any vector or matrix-like structures
within the input type. Formally, the resource element type is valid if the function returns true
on the given input type, or if the function returns true on all fields within the given input type.

Firstly, the base case will be checked. The given input type will be compared to the set of acceptable
primitives that are valid for a resource element. (i.e., float, int, etc).
If there are no matches, then the resource element type may be an array. In that case, the function
checks the array element type, and if it contains an element type in the set of acceptable primitives,
then the array is valid.
If the resource element was not an array, then the resource element may be a struct. In that case,
the compiler will iterate through all fields of the struct, which may contain primitive members,
arrays, or other structs. The function will be recursively called on each field of the struct,
verifying that the leaf types are valid primitive elements.
If the function never returns false at any point, then the type is valid.


### HLSL Additions
* How is this feature represented in the grammar?
This feature won't be represented in the language.
* How does it interact with different shader stages?
The feature is independent of shader stages, since resource type validation
doesn't depend on the shader stage.
* How does it interact other HLSL features (semantics, buffers, etc)?
The implementation of this feature will add diagnostics on resources.
* How does this interact with C++ features that aren't already in HLSL?
No interaction.
* Does this have implications for existing HLSL source code compatibility?
Possibly, if we decide that the valid set of primitive element types is different
than what was decided with DXC, or if the validation method significantly differs
from DXC.

### Interchange Format Additions

* What DXIL changes does this change require?
None
* What Metadata changes does this require?
None
* How will SPIRV be supported?
No need


### Diagnostic Changes

* What additional errors or warnings does this introduce?
When a user defines a resource with an invalid element type, a diagnostic
will be emitted specifying what component of the resource element type is invalid.
* What exisiting errors or warnings does this remove?
No errors or warnings should be removed.

#### Validation Changes

* What additional validation failures does this introduce?
None
* What existing validation failures does this remove?
None

### Runtime Additions

#### Runtime information

* What information does the compiler need to provide for the runtime and how?
None

#### Device Capability

* How does it intereact with other Shader Model options?
It doesn't.
* What shader model and/or optional feature is required for the bulk of this feature to be present?
Shader models that allow for semantic index assignment will be affected by this feature.
* What portions are only available if an existing or new optional feature is present?
This implementation isn't dependent on present features


## Testing

* How will correct codegen for DXIL/SPIRV be tested?
This feature won't change codegen for DXIL/SPIRV.
* How will the diagnostics be tested?
Diagnostics will be tested on a wide range of resource element types.
All valid resource element types will be tested, and invalid resource
element types will be tested. The diagnostics should point to exactly what
part of the given resource element makes it invalid.
* How will validation errors be tested?
There won't need to be any validation tests because no new validation errors will be produced
* How will validation of new DXIL elements be tested?
No need, there are no new DXIL elements.
* How will the execution results be tested?
No changes to execution results, so no need for tests.

## Acknowledgments (Optional)

