---
title: "NNNN - Work Graph Loops"
draft: true
params:
  authors:
    - mapodaca-nv: Mike Apodaca
  sponsors:
    - amarpMSFT: Amar Patel
  status: Under Consideration
---

## Introduction

This proposal addresses practical limitations in expressing recursive and
iterative algorithms within Work Graphs, eliminating the need to partition deep
graphs into multiple shallow graphs with intermediate buffering. The proposal
introduces loop constructs where multiple nodes can share a single loop entry
node that controls iteration behavior. The maximum node depth limit is
increased, and recursion depth no longer counts against this limit. Loop
iterations also do not count against the graph's node depth limit, enabling
complex iterative algorithms without artificial depth constraints.

## Motivation

First non-trivial workloads are being implemented using the GPU Work Graphs
feature and are already running into practical limitations due to the fixed
maximum graph depth of 32 included in the original specification. This maximum
depth is especially limiting for expressing recursive algorithms, as the maximum
recursion of a node counts towards the overall graph depth. For example, mesh
rendering preview samples have reached the depth limit, and workloads that
perform some form of tree traversal embedded in broader scope work within the
same graph are noticeably limited. Multi-node loops that iterate multiple times
also contribute to applications hitting these limits when they must be unrolled.

Currently, developers must partition deep graphs into separate shallow graphs
that are launched one after the other with barriers in between. Records sent
across the boundaries between these partial graphs must be buffered up in GPU
memory. An allocation for such records has to be sized for the worst-case
output each partial graph can produce. This workaround has detrimental
side-effects for performance due to the added barriers and associated draining
of the GPU.

The workaround also increases memory footprint due to worst-case intermediate
buffers needed and requires more code with complexity that is not intrinsic to
the problem being solved. Applications need a way to express deep recursive
algorithms and multi-iteration loops within a single Work Graph without
artificial depth constraints. The current specification provides no mechanism
for loops that iterate an unbounded or large number of times without consuming
proportional depth budget.

## Proposed solution

This proposal introduces two key changes to Work Graphs:

1. Increasing the maximum node depth and removing the maximum recursion depth
   from counting towards this limit.
2. Introducing explicit loop constructs.

### Maximum Node Depth and Recursion Limit

The maximum node depth increases from `32` to `48`. Nodes that target themselves
recursively now count the same as non-recursive nodes, and the maximum
recursion level does not count against the node depth limit.

For example, a simple graph with a recursive node:

```cpp
// Note: some attributes and details intentionally excluded for clarity
[Shader("node")]
[NodeLaunch("thread")]
void MyEntryNode(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myRecursiveNode)
{
    // ... dispatch records to MyRecursiveNode
}

[Shader("node")]
[NodeLaunch("thread")]
[NodeMaxRecursionDepth(100)]
void MyRecursiveNode(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myRecursiveNode,
    NodeOutput<RECORD> myLeafNode)
{
    // ... may dispatch records to itself or MyLeafNode
}

[Shader("node")]
[NodeLaunch("thread")]
void MyLeafNode(ThreadNodeInputRecord<RECORD> input)
{
    // ... no records dispatched
}
```

Regardless of MyRecursiveNode's maximum recursion level, this graph's total node
depth is three. The recursion depth does **not** add to the node depth count.

### Loops

A loop is a construct where a set of nodes share a single loop entry node. The
loop entry node controls the loop's iteration behavior using two new attributes:
`NodeMaxLoopIterations` and `NodeMaxRecordsPerLoopIteration`.

A loop begins when a node outside the loop dispatches a record to the loop
entry node. The loop iteration counter starts at `0` and increments when a node
inside the loop dispatches a record back to the loop entry node. The loop
terminates when either no records are fed back to the loop entry node or the
maximum loop iteration count is reached. Loop iterations do **not** count
against the graph's node depth limit.

#### Simple Loop Example

```cpp
// Note: some attributes and details intentionally excluded for clarity
[Shader("node")]
[NodeLaunch("thread")]
[NodeMaxLoopIterations(MAX_ITERATIONS)]
[NodeMaxRecordsPerLoopIteration(1)]
void MyLoopEntry(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myLoopBody)
{
    // ... dispatch records to MyLoopBody
}

[Shader("node")]
[NodeLaunch("thread")]
void MyLoopBody(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myLoopEntry,
    NodeOutput<RECORD> myOtherNode)
{
    // MyLoopBody invokes the next loop iteration when it outputs records to MyLoopEntry
    // MyLoopBody exits the loop when it outputs records to MyOtherNode
}

[Shader("node")]
[NodeLaunch("thread")]
void MyOtherNode(ThreadNodeInputRecord<RECORD> input)
{
    // MyOtherNode is **not** part of the loop
}
```

Regardless of the maximum loop iteration count, this graph's total node depth
is three.

#### Loop with Inner Node

```cpp
// Note: some attributes and details intentionally excluded for clarity
[Shader("node")]
[NodeLaunch("thread")]
[NodeMaxLoopIterations(MAX_ITERATIONS)]
[NodeMaxRecordsPerLoopIteration(1)]
void MyLoopEntry(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myLoopBody)
{
    // ... dispatch records to MyLoopBody
}

[Shader("node")]
[NodeLaunch("thread")]
void MyLoopBody(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myLoopTerminal)
{
    // ... dispatch records to MyLoopTerminal
    // MyLoopBody is within MyLoopEntry's loop as it is within a path back to MyLoopEntry
}

[Shader("node")]
[NodeLaunch("thread")]
void MyLoopTerminal(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myLoopEntry)
{
    // MyLoopTerminal is within MyLoopEntry's loop as it is within a path back to MyLoopEntry
    // MyLoopTerminal invokes the next loop iteration when it outputs records to MyLoopEntry
}
```

#### Nested Loop Example

```cpp
// Note: some attributes and details intentionally excluded for clarity
[Shader("node")]
[NodeLaunch("thread")]
[NodeMaxLoopIterations(MAX_OUTER_ITERATIONS)]
[NodeMaxRecordsPerLoopIteration(1)]
void MyOuterLoopEntry(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myInnerLoopEntry)
{
    // ... dispatch records to MyInnerLoopEntry
}

[Shader("node")]
[NodeLaunch("thread")]
[NodeMaxLoopIterations(MAX_INNER_ITERATIONS)]
[NodeMaxRecordsPerLoopIteration(1)]
void MyInnerLoopEntry(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myLoopTerminal)
{
    // ... dispatch records to MyLoopTerminal
    // MyInnerLoopEntry is an inner loop entry node, within MyOuterLoopEntry
}

[Shader("node")]
[NodeLaunch("thread")]
void MyLoopTerminal(
    ThreadNodeInputRecord<RECORD> input,
    NodeOutput<RECORD> myInnerLoopEntry,
    NodeOutput<RECORD> myOuterLoopEntry)
{
    // MyLoopTerminal invokes MyInnerLoopEntry's next iteration when it outputs records to MyInnerLoopEntry
    // MyLoopTerminal invokes MyOuterLoopEntry's next iteration when it outputs records to MyOuterLoopEntry
    // MyLoopTerminal is considered part of MyInnerLoopEntry's loop (inner-most loop)
}
```

Regardless of the maximum loop iteration counts, this graph's total node depth
is three.

## Detailed design

### HLSL Additions

#### Maximum Node Depth

The maximum node depth increases from `32` to `48`. The constant
`D3D12_WORK_GRAPHS_MAX_NODE_DEPTH` remains at `32` for backward compatibility.
A new constant `D3D12_WORK_GRAPHS_TIER_1_X_MAX_NODE_DEPTH` is defined as `48`.

Nodes that target themselves recursively count the same as non-recursive nodes.
The maximum recursion level does not count against the node depth limit.

#### Shader Function Attributes

Two new shader function attributes are added to support loop entry nodes:

| Attribute | Required | Description |
|:----------|:--------:|:------------|
| `[NodeMaxLoopIterations(count)]` | Y (for loop entry nodes) | Declares that this node is a loop entry node and specifies the maximum number of loop iterations (uint `count`). Exceeding this results in immediate loop termination. |
| `[NodeMaxRecordsPerLoopIteration(count)]` | Y (for loop entry nodes) | Specifies the maximum number of records (uint `count`) that can be fed back to the loop entry node on each loop iteration. Exceeding this results in undefined behavior. |

A node is a loop entry node if and only if it has the `NodeMaxLoopIterations`
attribute specified with a value greater than zero. Both attributes must be
specified together for a loop entry node.

The maximum value for `NodeMaxLoopIterations` is limited by the maximum node
count limit, currently `2^24-1`. Specifically, the maximum value for this
attribute is `2^24-2` for a graph that only contains a single loop entry node
targeting itself. In general, the total number of nodes within the loop
multiplied by its maximum number of loop iterations, in combination with all
other nodes including unrolled recursive nodes and other loops in the graph,
must be less than `2^24-1`.

The maximum value for `NodeMaxRecordsPerLoopIteration` is `256`. This value
represents the maximum number of records that can be fed back to the loop entry
node on any single loop iteration, calculated per thread group for broadcast
and coalescing loop entry node types, or per thread for thread loop entry node
types.

If multiple nodes might dispatch records back to the loop entry node on a
single loop iteration, then the count is the sum of the maximum records from
each of these node paths. The count must also take into account any expansion
due to broadcast nodes within the loop.

#### Loop Semantics

All nodes within the path back to the loop entry node are considered part of
the current loop. Nodes that do not have a path back to the loop entry node are
not considered part of the loop. Nodes within a loop can dispatch records to
nodes outside of the loop. However, nodes outside the loop cannot dispatch
records to nodes within the loop except through the loop entry node.

A loop entry node may not be a recursive node. However, a loop entry node may
output records back to itself, providing the same effective behavior as a
recursive node.

Loops are allowed to contain recursive nodes. The recursion depth within loops
does not count towards the loop's maximum iteration count or the graph's node
depth limit.

Loops may be nested. A node is considered to be part of the inner-most loop for
which there is a path to a loop entry node, even if it outputs directly to an
outer loop's nodes. Inner loops have their own independent maximum iteration
count and maximum number of records fed back to it.

If the loop entry node is bound within an output node array, each loop entry
node in the array is a singular loop. Loops cannot invoke additional nodes
including other loops in a node array on subsequent iterations.

#### Node Input Declaration

If a node within the loop uses `EmptyNodeInput`, then the `MaxRecords`
attribute on the `EmptyNodeOutput` from the calling node is limited by the
output node type's output limits. For example, a broadcast node may output
`256` records across all outputs, including any `EmptyNodeOutput` outputs.

#### Shader Intrinsic Functions

##### GetCurrentLoopIterationIndex

```cpp
uint GetCurrentLoopIterationIndex()
```

For a node within a loop, returns the current loop iteration index, starting
from `0`, limited by the `NodeMaxLoopIterations` declared function attribute.
Returns `0` if the current node is not within a loop at all.

The maximum value returned by this function is `2^24-1`.

#### Limits Summary

| Name | Type | Limit |
|:-----|:-----|:------|
| Maximum node depth | Graph property | `48` |
| `[NodeMaxRecursionDepth(count)]` | Node attribute | `(2^24)-2`, `0x00FF FFFE` <br> _The maximum value for a graph with only a single recursive node._ |
| `GetRemainingRecursionLevels()` | Intrinsic function | `(2^24)-1`, `0x00FF FFFF` |
| `[NodeMaxLoopIterations(count)]` | Node attribute | `(2^24)-2`, `0x00FF FFFE` <br> _The maximum value for a graph with only a single loop entry node, targeting itself._ |
| `[NodeMaxRecordsPerLoopIteration(count)]` | Node attribute | `256` <br> _This is the same maximum value for MaxRecords on node outputs._ |
| `GetCurrentLoopIterationIndex()` | Intrinsic function | `(2^24)-1`, `0x00FF FFFF` |

### Interchange Format Additions

#### DXIL Metadata

Two new metadata tags are added for loop entry node attributes:

| Tag | Tag Encoding | Value Type | Default |
|:----|:-------------|:-----------|:--------|
| NodeMaxLoopIterations | `i32 TBD` | `i32` | 0 |
| NodeMaxRecordsPerLoopIteration | `i32 TBD` | `i32` | 0 |

When `NodeMaxLoopIterations` is `0`, the node is not a loop entry node. When
`NodeMaxLoopIterations` is greater than `0`, both `NodeMaxLoopIterations` and
`NodeMaxRecordsPerLoopIteration` must be specified.

#### DXIL Intrinsic

The `GetCurrentLoopIterationIndex` function is represented in DXIL as follows:

```llvm
i32 @dx.op.getCurrentLoopIterationIndex(i32 %Opcode)
```

Where `%Opcode` is the operation code for the intrinsic.

#### RDAT Additions

The `NodeMaxLoopIterations` and `NodeMaxRecordsPerLoopIteration` information
will be captured to RDAT. Similar to other node attributes, add RDAT node
attribute kinds named `NodeMaxLoopIterations` and
`NodeMaxRecordsPerLoopIteration`.

### SPIR-V Considerations

Work Graphs are currently a DirectX-specific feature with no equivalent in
SPIR-V. This proposal does not include SPIR-V code generation support.

## Alternatives considered

Increasing the maximum graph depth limit beyond `48` has negative performance
consequences for implementations that have accelerated Work Graph scheduling.
This proposal addresses the core issues which caused applications to hit the
depth limit without other negative side effects.

This specification introduces undefined behavior for exceeding
`NodeMaxRecordsPerLoopIteration`, consistent with existing behavior for
exceeding `MaxRecords` on node outputs. Guaranteeing specific behavior for
exceeding this limit would add significant overhead to all well-behaved
applications. Since Work Graphs are an unordered system, applications cannot
rely upon consistent behavior across multiple graph executions anyway.

An alternative solution would be to add an attribute flag such as
`NodeMaxRecordsPerLoopIteration(count, flag)` that requires an implementation
to discard any records once the limit is reached. This flag could be restricted
to only be enabled via an explicit compile time argument, just to allow
developers the ability to debug whether they are exceeding these limits.

## Acknowledgments

This proposal builds upon a proposal from Fabian Wildgrube, Dominik Baumeister,
and Jefferson Montgommery at AMD, that just increases Work Graph depth limits,
which addresses similar use cases for expressing recursive and iterative
algorithms within Work Graphs.
