* Proposal: [0013](0013-semantic-index-assignment.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8
* PRs: [#6108](https://github.com/microsoft/DirectXShaderCompiler/pull/6108)
* Issues:
  [#5827](https://github.com/microsoft/DirectXShaderCompiler/issues/5827)

## Introduction

Shaders with entry point functions may have semantics attached to the function's parameters.
This spec specifies how legal semantic usage is checked on entry point shaders. 
The purpose of the spec is to properly define how diagnostics get emitted in Sema for 
higher-dimensional parameters with semantics, that later get flattened in SROA. 
Although the DXIL spec specifies how semantic indices are assigned in 
https://github.com/Microsoft/DirectXShaderCompiler/blob/main/docs/DXIL.rst#semantic-index-assignment,
there is no indication of how the indices are used to generate diagnostics.
So, the compiler will need to take the implementation in SROA for parameter flattening, and
bring it over to Sema, so that diagnostics are properly emitted there.

## Motivation

Currently, the compiler does not emit any diagnostics for semantic index collisions in Sema.
Such collisions are detected and diagnosed in SROA, much later. Additionally, due to the complexity
of SROA, it is difficult to understand, maintain, and extend the code that handles semantic index collision. 
For example, in https://github.com/microsoft/DirectXShaderCompiler/issues/5827, there was
no existing infrastructure to check for SV conflicts. For compiler developers, there should already
exist an infrastructure for adding SV conflict detection based on known semantic indices.

## Proposed solution

The proposed solution is to copy and perhaps simplify the infrastructure in SROA for semantic
index collision detection, and move it into Sema. 
For compiler developers, it would be beneficial to define an infrastructure for semantic index
collision detection, so that as new semantics get added, it becomes easy to add the necessary logic
that would prevent conflicts with other attributes, or index collisions of the same attribute.
Also, by moving this infrastructure to Sema, it can be made cleaner, and more efficient.
For HLSL developers, moving these diagnostics earlier to Sema will provide more information, and
the information will be provided sooner, decreasing compile time.

## Detailed design

* Entry function selection (specifics outside scope of this proposal)
The compiler will find the entry function requested by the compilation option, 
or for a library profile, visit all entry functions in the library. 
For each function, all parameters are analyzed, along with the return type and any semantic applied to
the function for the return value. Each parameter is handled depending on some classification.  
Depending on the shader kind, the qualifiers and special HLSL types are used to determine the 
interpretation and rules for the parameter.  
This can mean determining whether the parameter is an input (in, default), an output (out), 
or both (inout), and determining which specific signature point(s) the parameter belongs to,
for applicable shader stages. 
The parameter type for recursive flattening and semantic assignment is determined here as well,
potentially from the template type of a special HLSL object parameter, such as InputPatch<>.
* Parameter classification for diagnostics (IDENTIFYING SIGNATURE POINT):
The compiler will interpret parameters depending on entry type, qualifiers,
and special HLSL object types, then dispatch to a parameter handling function
with initial top-level details. 
For node parameters, the compiler can detect whether the parameter is an input node record
or an output node record, and further, detect the type of input or output record
(Dispatch, RWDispatch, Thread, etc.) At the top level, there will be a switch statement
to determine the parameter type.
If there is a node parameter type detected, then the logic that already exists 
to validate node parameters and assign semantic indices will be tweaked 
to prevent duplicate semantic assignment. Otherwise, the logic described below will be used
to assign semantic indices. 
Additionally, there will be a top-level map, where the key is the signature point identifier,
and the value is a pair, where the pair types are the two data structures defined below,
Sems and pairsAssigned. As signature points are identified, this map will be constructed.
* How semantic indices are assigned per parameter type once sigpoints are assigned
Basic HLSL types (scalar, vector, matrix), and arrays of such:
⦁	Determine number of rows based on array size * matrix rows, 
	assign this many consecutively increasing indices starting from the start index.
Struct or class type:
⦁	recursively traverse base types if any
⦁	traverse fields, with the starting index following the last index used by a prior field
	or base type. Each field gets assigned the next index value after the last one
	used for any prior fields. 
  Every Basic  HLSL type requires a semantic + index pair if the type is found within a "regular" argument,
  and if there is no possible semantic to assign, semantic index assignment halts and an error is emitted.
Array of struct or class type:
⦁	Iterate array elements, assigning the semantic + index pair, 
	but incrementing the index to the next unused index for each subsequent array entry.
Separately, after semantic indices are assigned here, a structure will be constructed 
that contains the type information and hierarchical relationships between all types, 
to represent the structure of the parameter that was analyzed.
It will be easy to extract the number of semantic indices that were assigned to the parameter itself, 
or the number of semantic indices that were assigned to any sub-type of the parameter
(at any field or structure contained within the parameter). 
This structure will be useful in SROA to validate that assignment took place correctly.

* Parameter handling functions:
A parameter handling function already exists for Work Graphs to handle record type
and look for a particular system value.  Since the record is not flattened into signature elements,
the approach is different compared to entries with signature elements.
This spec requires a new parameter handling function for node types that applies 
parameter flattening to determine the set of signature elements, and semantics+indices,
that a parameter defines. 
The way in which parameters are flattened into signature elements is described here: 
https://github.com/Microsoft/DirectXShaderCompiler/blob/main/docs/DXIL.rst#vertex-shader-hlsl. 
This example shows how semantic index assignment works with struct fields and array elements. 
Diagnostic logic will need to compute the signature elements from a structure
to match this flattening for diagnostics.

* Signature element diagnostics
Diagnosis on first detection of duplicate semantic assignment is possible with these data structures:
```c++
std::map<std::pair<semanticNameLowercased StringRef, int semanticIndex>, SourceLocation> pairsAssigned;
std::map<std::string semanticName, std::map<semanticIndex, SignatureElement* > >  Sems;
```
The first structure is a map from lower-case canonicalized semantic names and an associated index, 
to a source location. The map is useful in detecting whenever a duplicate semantic name is detected. 
Whenever another semantic index pair is being assigned, we first check this map to see
if an assignment like this has already been made (that matches semantic name and index). 
If a duplicate was found, then we have access to the SourceLocation that the original assignment
took place in. At this point, given the semantic name and the index that the compiler is inserting, 
and the source location where the pair originated from, a diagnostic can be emitted, which looks like:
```c++
"Error: Duplicate semantic  index pair detected: {semantic Name} {semantic Index}, 
first applied from pairsAssigned[{semantic Name after lower-casing}][{semantic Index}].SourceLocation, 
and then applied from {current SourceLocation}."  
```
If no duplicate was found, we insert into this map and then move onto the second structure.
In this structure, the key is a semantic name. 
The value is a map of all the instances where that semantic name appears 
in the current signature point (a group of relevant parameters to check for duplication within a function parameter list). 
For this inner map, the key is a semantic index for the specified semantic name,
and the value is a pointer to the signatureElement object associated with that semantic + index pair. 
During the assignment of semantic + index pairs, both of these structures will be constructed.

* To determine the set of parameters involved in the same signature point context, 
hctdb.py will be used. 
Depending on the shader kind and other factors, diagnostics will be emitted 
only for parameters that are within the same signature point subcontext, 
among all the parameters in the entry point function parameter list. 
A new sig point kind will need to be added to specify the subcontext of node object parameters,
that would allow node record type parameters.

### HLSL Additions
* How is this feature represented in the grammar?
This feature won't be represented in the language.
* How does it interact with different shader stages?
The feature will take into account different shader stages to determine what available
signature point kinds to consider when parsing the parameters to entry point functions, to determine
whether there are semantic index collisions or not.
* How does it interact other HLSL features (semantics, buffers, etc)?
The implementation of this feature will improve and speed up diagnostics on semantics, specifically,
semantics on high-dimensional parameters.
* How does this interact with C++ features that aren't already in HLSL?
No interaction.
* Does this have implications for existing HLSL source code compatibility?
No, because the logic is simply being moved early and improved and simplified, but shouldn't change.

### Interchange Format Additions

* What DXIL changes does this change require?
None
* What Metadata changes does this require?
None
* How will SPIRV be supported?
No need


### Diagnostic Changes

* What additional errors or warnings does this introduce?
There may be some upgrades on diagnostic messages indicating collisions on a semantic index within a 
signature point. However, these shouldn't be additional errors, rather they are improvements 
on information contained within the diagnostic. 
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
The implementation bolsters diagnostic emission, the current tests for correct codegen regarding 
semantic index assignment should be already sufficient.
* How will the diagnostics be tested?
Diagnostics will be tested on a wide range of shader kinds.
For each shader kind, there will be an entry point that takes in high-dimensional parameters.
The parameters will contain a decent mixture of structs / arrays, from which we can reasonably imply
that any user-defined construct will be correctly parsed and semantics will be correctly assigned.
Due to the different shader kinds, different signature point kinds will be expected, and so tests will
need to examine whether semantic index collisions happen within the same signature point set of parameters.
There should also be tests for semantic index collisions between parameters belonging to different
signature points.
* How will validation errors be tested?
There won't need to be any validation tests because no new validation errors will be produced
* How will validation of new DXIL elements be tested?
No need, there are no new DXIL elements.
* How will the execution results be tested?
No changes to execution results, so no need for tests.

If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing. Having these solutions and why they were rejected documented may save
trouble from those who might want to suggest feedback or additional features that
might build on this on. Even variations on the chosen solution can be intresting.

## Acknowledgments (Optional)
Tex Riddell
Greg Roth
