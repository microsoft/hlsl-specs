<!-- {% raw %} -->

* Proposal: [0025](0025-max-records-per-node.md)
* Author(s): [Anupama Chandrasekhar](https://github.com/anupamachandra), [Mike Apodaca](https://github.com/mapodaca-nv)
* Sponsor: Damyan Pepper
* Status: **Under Consideration**

# [MaxRecordsPerNode(count)] Attribute for NodeOutputArray

## Introduction

This specification describes the HLSL and DXIL details for a new [NodeArrayOutput](https://microsoft.github.io/DirectX-Specs/d3d/WorkGraphs.html#node-output-attributes) attribute `[MaxRecordsPerNode(count)]` that specifies the maximum number of records that can be output to a specific node in a node output array. See the [MaxRecordsPerNode]() specifications for more details.

## Motivation

For `NodeArrayOutput`, the node output attribute `[MaxRecords(count)]` specifies the maximum number of records that can
be output across the entire node array.  This attribute alone is insufficient for determining how records are
distributed across an output array.  For example, consider an output node array specification of
`[MaxRecords(N)][NodeArraySize(N)]`. All N records could be sent to one node in the array, or one record could be
sent to each of the N nodes in the array, or the records could be spread in an arbitrary fashion across multiple nodes
in the array.  An implementation cannot distinguish these different use cases.

When determining backing store memory requirements, an implementation must assume the worst-case of `MaxRecords` written
to any single node in the output array.  However, a common use-case is for a small number records to be written to
select nodes in a very large array of nodes.  Some implementations can take advantage of this knowledge to significantly
reduce the backing store memory requirements while maintaining peak performance.

## Proposed solution

We propose a new node output attribute called `MaxRecordsPerNode`. This parameter is only required for output node
arrays.  This attribute specifies the maximum number of records that can be written to any single output node within a
node array.

## Detailed design

### HLSL Additions

Add a new node output attribute:

| Attribute | Required | Description |
|:---       |:--------:|:------------|
| `[MaxRecordsPerNode(count)]` | Y | For `NodeArrayOutput`, specifies the maximum number of records that can be output to a node within the array.  Exceeding this results in undefined behavior.  This attribute can be overridden via the `NumOutputOverrides / pOutputOverrides` option when constructing a work graph.  This attribute has no impact on existing node output limits. |

This attribute will be required starting with a future Shader Model version.
Since this may cause compilation failures with existing Work Graphs, this will
be a `DefaultError` warning assigned to a warning group named
`hlsl-require-max-records-per-node` to allow a command-line override.
The value of `MaxRecordsPerNode` will be set equal to `MaxRecords`.

The compiler will also generate an error if the `MaxRecordsPerNode` value is greater than the `MaxRecords` in a HLSL shader. Note that `pMaxRecordsPerNode` may override this value and the runtime will validate the correctness in that case. See the feature [spec]() for more details.

**Developer's note**: Implementations that do not support or ignore this attribute, will not be functionally impacted.

### Usage

The following trivial example demonstrates using `MaxRecordsPerNode` for a thread launch node which distributes
a single record across an array of 64 consumer thread launch nodes.

```cpp
[Shader("node")]
[NodeLaunch("thread")]
[NodeIsProgramEntry]
void DispatchNode(
    [MaxRecords(64)]       // a maximum of 64 records are written to output node array,
    [MaxRecordsPerNode(1)] // but only 1 record is written to each node in the array
    [NodeArraySize(64)] NodeOutputArray<RECORD> ConsumerNodes )
{
    [unroll] for(uint i = 0; i < 64; ++i)
    {
        ThreadNodeOutputRecords<RECORD> outputRecord = ConsumerNodes[i].GetThreadNodeOutputRecords(1);
        ...
        outputRecord.OutputComplete();
    }
}
```

As mentioned above, some material shading algorithms have a similar pattern: a single node which makes a decision about
which node(s) in a node array (materials) to execute, where the number of possible materials is large, but the number of
records submitted to any specific node is small, relative to the size of the array.

### Interchange Format Additions

A new metadata tag is added for MaxRecordsPerNode.

|Tag                            |Tag Encoding     |Value Type     |Default     |
|:------------------            |:----------------|:--------------|:-----------|
|kDxilNodeMaxRecordsPerNodeTag  |`7`              |`i32`          |Required, See [HLSL Additions](#hlsl-additions) section for backward compatibility with older Shader Models    |  

### Runtime Additions

The `MaxRecordsPerNode` information will be captured to RDAT. Similar to other Node attributes, add a `RDAT::NodeAttribKind` named `MaxRecordsPerNode`.

## Alternatives considered

### Parameter of MaxRecords

Modify the definition for `MaxRecords` node output attribute:

| attribute | required | description |
|:---       |:--------:|:------------|
| `[MaxRecords(count, maxRecordsPerNode)]` | Y (this or below attribute) | Given uint `count` declaration, the thread group can output `0...count` records to this output.  The variant with `maxRecordsPerNode` is required for `NodeArrayOutput`, where `count` applies across all the output nodes in the array and `maxRecordsPerNode` specifies the maximum number of records that can be written to a single output node within the array.  Exceeding these limits results in undefined behavior.  The value of `maxRecordsPerNode` must be less-than or equal to the value of `count`.  These attributes can be overridden via the `NumOutputOverrides / pOutputOverrides` option when constructing a work graph as part of the [definition of a node]().  See [Node output limits](). |

Note: if the specification is `MaxRecords(count, maxRecordsPerNode)`, then multiple outputs that share budget using
`MaxRecordsSharedWith` **must** also share the same value for `maxRecordsPerNode`.  While in many cases this might be
correct, this locks this requirement into the spec and restricts an implementation's ability to distinguish cases where
they are different. We therefore prefer the option of specifying `MaxRecordsPerNode(count)` as a separate attribute.

### Optional Attribute

This attribute could be made optional, for maximum backward compatibility; i.e. existing SM6.8 Work Graphs compile with
the newer Shader Model.  When `MaxRecordsPerNode` is _not_ specified, the implicit value of `MaxRecordsPerNode` is
equal to `MaxRecords`.  This also avoids redundant attribute specifications for those usage models where the values of
`MaxRecords` and `MaxRecordsPerNode` are identical. However, for performance reasons, this was made a required
attribute with a compiler fall back for backward compatibilty.

<!-- {% endraw %} -->
