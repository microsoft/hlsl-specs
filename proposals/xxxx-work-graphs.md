<!-- {% raw %} -->

# Work Graphs

* Proposal: [NNNN](NNNN-work-graphs.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Greg Roth](https://github.com/pow2clk), [Tex
  Riddell](https://github.com/tex3d)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8

## Introduction

This document describes Work Graphs, a new feature for GPU-based work generation
built on new Shader Model 6.8 DXIL features.

Full documentation of the Work Graphs feature including DirectX runtime, HLSL,
and DXIL documentation is available in the [Work Graphs Spec on
GitHub](https://microsoft.github.io/DirectX-Specs/d3d/WorkGraphs.html). This
document subsumes that document specifically as it relates to HLSL and the
compiler features.

## Motivation

Current language and runtime limitations make generating work on GPU threads
insufficient to meet the needs of some workloads. If existing GPU features (like
ExecuteIndirect) can't sufficiently generate work the application must generate
the work from the CPU resulting in unnecessary round-tripping between the GPU
and CPU. Work Graphs solves this problem by enabling more robust GPU-based work
creation APIs.

## Proposed solution

Work graphs allows an application to specify a set of tasks as _nodes_ in a
graph representing a more complex workload. Each _node_ has a fixed shader which
takes one or more _input records_ as input and can produce one or more _output
records_ as output.

### Launch Modes

_Node_ shaders have one of three _launch modes_:

* Thread
* Broadcasting
* Coalescing

_Thread launch_ nodes represent an individual thread of work that processes a
single _input record_. Thread launch nodes use a thread group size of `(1,1,1)`.

_Broadcasting launch_ nodes represent a grid of work operating on a single
_input record_. Each input record to a broadcasting node launches a full
dispatch grid. The size of the dispatch grid can either be fixed for the node or
specified in the input.

_Coalescing launch_ nodes represent a thread group operating on a shared array
of _input records_. The shader declares the maximum number of records per thread
group.

### Records

_Input records_ represent inputs to node shaders, and _output records_ represent
outputs from node shaders. Records can be singular or arrays. _Input records_
can be read-only or read-write, while _output records_ are read-write but
uninitialized when created.

## Detailed design

### Node Entry Functions

Node shaders are compute shaders built into library targets. Shader entries
annotated as `[shader("node")]` are usable as work graph nodes.

A broadcasting launch mode node entry may also be a compute entry (annotated
with `[shader("compute")]`). In this case the node's input is an empty input
record.

#### Function Attributes

All node shaders except _thread launch_ nodes must specify the thread group size
using the `[numthreads(<x>, <y>, <z>)]` attribute.

Node shaders support all compute shader function annotations, but also have new
annotations unique to node shaders.

> Consistent with HLSL grammar attribute names are case-insensitive. Any
> attributes that take string arguments, the string argument values are
> case-sensitive.

##### **`[NodeLaunch("<mode>")]`**
Valid values for node launch mode are `broadcasting`, `coalescing`, or `thread`.
If the `NodeLaunch` attribute is not specified on a node entry the default
launch mode is `broadcasting`.

##### **`[NodeIsProgramEntry]`**

Shaders that can receive input records from both inside and outside the work
graph (i.e. from a command list) require this attribute. Graphs can have more
than one entry shaders that receive inputs from outside the graph. Nodes which
do not have other nodes targeting them do not need to apply this attribute to
receive input from outside the work graph.

##### **`[NodeID("<name>", <index> = 0)]`**
If present the shader represents a node with the provided name. If present, the
index parameter specifies the index into the named node array. If this attribute
is not present the function name is the node name, and the index is `0`.

##### **`[NodeLocalRootArgumentsTableIndex(<index>)]`**
The specified index indicates the record index into the local root arguments
table bound to the work graph. If this attribute is not specified and the shader
has a local root signature the index defaults to an unallocated table location.

##### **`[NodeShareInputOf("<name>", <index> = 0 )]`**
Share the inputs for the node specified by name and optional index with this
node. Both nodes must have identical input records and the same launch mode and
dispatch grid size (if fixed).

##### **`[NodeDispatchGrid(<x>, <y>, <z>)]`**
Specifies the size of the dispatch grid. Broadcast launch nodes must specify
either the dispatch grid size or maximum dispatch grid size in source. The `x`
`y` and `z` parameters individually cannot exceed 2^16-1 (65535), and `x*y*z`
cannot exceed 2^24-1 (16,777,215).

##### **`[NodeMaxDispatchGrid(<x>, <y>, <z>)]`**
Specifies the maximum dispatch grid size when the dispatch grid size is
specified on the input record using the `SV_DispatchGrid` semantic. The `x` `y`
and `z` parameters individually cannot exceed 2^16-1 (65535), and `x*y*z` cannot
exceed 2^24-1 (16,777,215).

##### **`[NodeMaxRecursionDepth(<count>)]`**
Specifies the maximum recursion depth for a node. This attribute is required if
one of the outputs of a node is the ID of the node itself.

#### Entry Parameters

Specific types for input parameters depend on the node launch mode, but all node
shaders support two categories of parameters:

* Zero or one Node Input Parameter.
* Zero or more Node Output Parameter(s).

Broadcast and Coalescing Launch shaders also support optional system value
parameters.

##### Node Input Objects

Node input objects come in three categories, one for each launch mode, with
read-only and read-write variants:

* `{RW}ThreadNodeInputRecord<RecordTy>` - for thread launch nodes.
* `{RW}DispatchNodeInputRecord<RecordTy>` - for broadcasting launch nodes.
* `{RW}GroupNodeInputRecord<RecordTy>`- for coalescing launch nodes.

The pseudo-HLSL code below describes the basic interface of the
`{RW}{Thread|Dispatch|Group}NodeInputRecord<RecordTy>` classes:

```c++
namespace detail {
///@brief Common interfaces for Thread and Dispatch node input record types.
template <typename RecordTy, bool IsRW> class NodeInputRecordInterface {
  /// @brief Get a copy of the underlying record.
  RecordTy Get() const;

  /// @brief Get a writable reference to the underlying record.
  ///
  /// Only available for non-RW object variants. The non-const Get() returns a
  /// reference to the underlying data.
  std::enable_if_t<IsRW, RecordTy>::type &Get();
};

/// @brief Interface for GroupNodeInputRecord and RWGroupNodeInputRecord
template <typename RecordTy, bool IsRW = false> class GroupNodeInputRecordBase {
  /// @brief Returns the number of records that have been coalesced into the
  /// current thread group.
  ///
  /// Returns 1..._MaxCount_, where _MaxCount_ is specified by the
  /// `[MaxRecords(_MaxCount_)]` attribute applied to the parameter declaration.
  uint Count() const;

  /// @brief Get a copy of the underlying record at the specified index.
  RecordTy Get(uint Index) const;

  /// @brief Get a writable reference to the underlying record.
  /// @param Index The record index to access.
  ///
  /// Only available for non-RW object variangs. The non-const Get() returns a
  /// reference to the underlying data.
  std::enable_if_t<IsRW, RecordTy>::type &Get(uint Index);

  /// @brief Get a copy of the underlying record at the specified index.
  /// @param Index The record index to access.
  RecordTy operator[](uint Index) const;

  /// @brief Get a writable reference to the underlying record.
  /// @param Index The record index to access.
  ///
  /// Only available for non-RW object variants. The non-const operator[]
  /// returns a reference to the underlying data.
  std::enable_if_t<IsRW, RecordTy>::type &operator[](uint Index);
};

} // namespace detail

template <typename RecordTy>
using ThreadNodeInputRecord = detail::NodeInputRecordInterface<RecordTy, false>;

template <typename RecordTy>
using RWThreadNodeInputRecord =
    detail::NodeInputRecordInterface<RecordTy, true>;

template <typename RecordTy>
using DispatchNodeInputRecord =
    detail::NodeInputRecordInterface<RecordTy, false>;

template <typename RecordTy>
class RWDispatchNodeInputRecord
    : public detail::NodeInputRecordInterface<RecordTy, true> {
  /// @brief Allows thread groups to coordinate reading and writing to a shared
  /// set of records.
  /// @returns Returns `false` for thread groups that are not the last to finish
  /// and `true` for the last thread group to call this method.
  ///
  /// This method must be called by all threads in a dispatch or not called at
  /// all. The call must be in dispatch grid uniform control flow. The callsite
  /// must be uniform across all threads in all thread groups in the dispatch
  /// grid. This method may be called at most once per thread.
  ///
  /// Any violation of these requirements is undefined behavior.
  ///
  /// This method returns `false` for thread groups that are not the last to
  /// finish and these thread groups are not allowed to read or write to the
  /// input. Reading or writing the input after this call on a thread that
  /// returned `false` is undefined behavior.
  ///
  /// This method returns `true` for the last thread group to finish. That
  /// thread group can continue reading and writing to the input.
  bool FinishedCrossGroupSharing();
};

template <typename RecordTy>
using GroupNodeInputRecord = detail::GroupNodeInputRecordBase<RecordTy, false>;

template <typename RecordTy>
using RWGroupNodeInputRecord = detail::GroupNodeInputRecordBase<RecordTy, true>;
```

Coalescing launch nodes also accept the `EmptyNodeInput` input object for cases
without record data. The pseudo-HLSL interface for `EmptyNodeInput` is:

```c++
class EmptyNodeInput {
  /// @brief Returns the number of records that have been coalesced into the
  /// current thread group.
  ///
  /// Returns 1..._MaxCount_, where _MaxCount_ is specified by the
  /// `[MaxRecords(_MaxCount_)]` attribute applied to the parameter declaration.
  uint Count() const;
};
```

##### Node Output Objects


Node output objects are either records or empty. The following pseudo-HLSL
defines the interfaces for the `NodeOutput` and `EmptyNodeOutput` objects:

```c++
template <typename RecordTy> class NodeOutput {
  /// @brief Allocate a new ThreadNodeOutputRecords for this thread.
  /// @returns A handle that collects a set of thread output records.
  /// @param NumRecords The number of records to return for the calling thread.
  ///
  /// ThreadNodeOutputRecords are per-thread output records. Each thread can
  /// produce a different number of outputs which are each unique per thread.
  ///
  /// Must be called in thread group uniform control flow. The value of
  /// `NumRecords` is not required to be uniform. If the value of `NumRecords`
  /// is `0`, the object returned is zero-sized and cannot be indexed on that
  /// thread.
  ThreadNodeOutputRecords<RecordTy> GetThreadNodeOutputRecords(uint NumRecords);

  /// @brief Allocate GroupNodeOutputRecords for this thread group.
  /// @returns A handle that collects a set of group node output records.
  /// @param NumRecords The number of records to return.
  ///
  /// GroupNodeOutputRecords are per-group output records. The output record set
  /// is shared across the thread group and the threads work cooperatively to
  /// produce the output records.
  ///
  /// Must be called in thread group uniform control flow. The value of
  /// `NumRecords` and `this` must be uniform across the thread group. If the
  /// value of `NumRecords` is `0`, the object returned is zero-sized and cannot
  /// be indexed.
  ///
  /// This method may not be called from _thread launch_ shaders since they do
  /// not have a thread group.
  GroupNodeOutputRecords<RecordTy> GetGroupNodeOutputRecords(uint NumRecords);

  /// @brief Returns true if the specified output node is in the work graph.
  bool IsValid() const;
};

class EmptyNodeOutput {
  /// @brief Adds `Count` empty output records to the thread node outputs.
  ///
  /// Must be called in thread group uniform control flow.
  void ThreadIncrementOutputCount(uint Count);

  /// @brief Adds `Count` empty output records to the group node outputs.
  ///
  /// Must be called in thread group uniform control flow. The value of
  /// `Count` and `this` must be uniform across the thread group.
  void GroupIncrementOutputCount(uint Count);

  /// @brief Identifies if the output node is valid to write to.
  /// @returns True if the specified output node is in the work graph, or for
  /// recursive nodes if the maximum recursion limit has not been reached.
  bool IsValid() const;
};
```

Array variations of the node output objects also exist exposing subscript
operators to index the individual output. The following pseudo-HLSL defines the
interfaces for the `NodeOutputArray` and `EmptyNodeOutputArray` objects:

```c++
namespace detail {
template <typename NodeOutputTy> class NodeOutputArrayBase {
  /// @brief Returns the node output for the specified index.
  /// @param Index The record index to access.
  NodeOutputTy &operator[](uint Index);
};
} // namespace detail

template <typename RecordTy>
using NodeOutputArray = detail::NodeOutputArrayBase<NodeOutput<RecordTy>>;

using EmptyNodeOutputArray = detail::NodeOutputArrayBase<EmptyNodeOutput>;
```

Each node output can contain zero or more thread or group node output records
which feed into other nodes for processing.

The following pseudo-HLSL defines the interfaces for the
`ThreadNodeOutputRecords` and `GroupNodeOutputRecords` objects:

```c++
namespace detail {
template <typename RecordTy> class NodeOutputRecordsBase {
  /// @brief Get a copy of the underlying record.
  RecordTy &Get(uint Index);

  /// @brief Mark the output node as completed.
  ///
  /// Each thread producing an output must call `OutputComplete` at least once.
  /// Calling `OutputComplete()` signals to the runtime that the node output
  /// memory is finalized. The behavior of writes to the output after this call
  /// is undefined.
  ///
  /// Calls to `OutputComplete` must be in thread group uniform control flow
  /// otherwise the behavior is undefined.
  void OutputComplete();
};
} // namespace detail

template <typename RecordTy>
using ThreadNodeOutputRecords = detail::NodeOutputRecordsBase<RecordTy>;

template <typename RecordTy>
using GroupNodeOutputRecords = detail::NodeOutputRecordsBase<RecordTy>;
```

##### Entry Parameter Attributes

> Consistent with HLSL grammar attribute names are case-insensitive. Any
> attributes that take string arguments, the string argument values are
> case-sensitive.

###### **`[MaxRecords(<count>)]`**
Applies to node inputs in coalescing launch nodes or outputs for any node mode.

Required for node inputs for coalescing launch nodes, this attribute restricts
the maximum number of records per thread group. Implementations are not required
to fill to the specified maximum.

When applied to node outputs, this attribute restricts the maximum number of
records produced to the output. When applied to a `NodeOutputArray`, the maximum
applies as the sum of all records across the output array, not per-node.

Node outputs require either the `MaxRecords` or `MaxRecordsSharedWith`
attribute.

###### **`[MaxRecordsSharedWith("<name>")]`**
This attribute applies to node outputs. The named node must have the
`MaxRecords` attribute applied to its entry. This attribute and the `MaxRecords`
attribute are mutually exclusive.

The node that this attribute is applied to shares a maximum record allocation
with the named node.

Node outputs require either the `MaxRecords` or `MaxRecordsSharedWith`
attribute.

###### **`[NodeID("<name>", <index> = 0)]`**
This attribute applies to output nodes and defines the name and index of the
output node. If not provided, the default index is 0.

If this attribute is not present on an output, the default node ID for the
output is the name of the parameter, and the index is the default index (0).

###### **`[AllowSparseNodes]`**
This attribute applies to outputs and allows the work graph to be created even
if there is not a node defined for the specified output.

###### **`[NodeArraySize(<count>)]`**
Specifies the output array size for `NodeOutputArray` or `EmptyNodeOutputArray`
objects.

### New Built-in Functions

#### GetRemainingRecursionLevels

```c++
/// @brief Returns the number of recursion levels remaining against the declared
/// `NodeMaxRecursionDepth`.
///
/// Returns 0 for leaf nodes and if the current node is not recursive.
uint GetRemainingRecursionLevels();
```

For nodes that recurse, the `GetRemainingRecursionLevels()` function returns the
number of remaining recursion levels before reaching the node's maximum
recursion depth.

#### Barrier

```c++
enum class MEMORY_TYPE_FLAG : uint {
  UAV_MEMORY = 0x00000001,
  GROUP_SHARED_MEMORY = 0x00000002,
  NODE_INPUT_MEMORY = 0x00000004,
  NODE_OUTPUT_MEMORY = 0x00000008,
};

enum class ACCESS_FLAG : uint {
  DEVICE_VISIBLE = 0x00000001, // implies group visible (smaller scope)
  GROUP_VISIBLE = 0x00000002,
};

enum class SYNC_FLAG : uint {
  GROUP_SYNC = 0x00000001,
};

/// @brief Request a barrier for a set of memory types and/or thread group
/// execution sync.
/// @param MemoryTypeFlags Flag bits as defined by MEMORY_TYPE_FLAG.
/// @param AccessFlags Flag bits as defined by ACCESS_FLAG.
/// @param SyncFlags FlagBits as defined by SYNC_FLAG.
///
/// If `GROUP_SYNC` is specified in the sync flags, `Barrier` must be called
/// from thread group uniform control flow.
void Barrier(uint MemoryTypeFlags, uint AccessFlags, uint SyncFlags);

/// @brief Request a barrier for just the memory used by an object.
/// @param TargetObject The object or resource which owns the memory to apply
/// the barrier to.
/// @param AccessFlags Flag bits as defined by ACCESS_FLAG.
/// @param SyncFlags FlagBits as defined by SYNC_FLAG.
///
/// The TargetObject parameter can be a particular node input/output record
/// object or UAV resource. Groupshared variables are not currently supported.
///
/// If `GROUP_SYNC` is specified in the sync flags, `Barrier` must be called
/// from thread group uniform control flow.
void Barrier(Object TargetObject, uint AccessFlags, uint SyncFlags);
```

Work graphs introduces a new more flexible implementation of the memory barrier
functions. This function is available in all shader types (including non-node
shaders).

The new `Barrier` function implements a superset of the existing memory barrier
functions which are still supported (i.e. `AllMemoryBarrier{WithGroupSync}()`,
`GroupMemoryBarrier{WithGroupSync}()`, `DeviceMemoryBarrier{WithGroupSync}()`).

In the context of work graphs, `Barrier` enables requesting a memory barrier on
input and/or output record memory specifically, while the implementation is free
to store the data in any memory region.

The pseudo-code below shows implementing the existing HLSL memory barrier
functions using the new `Barrier` function.

```C++
void AllMemoryBarrier() {
  Barrier(UAV_MEMORY | GROUP_SHARED_MEMORY | NODE_INPUT_MEMORY |
              NODE_OUTPUT_MEMORY,
          DEVICE_VISIBLE, 0);
}

void AllMemoryBarrierWithGroupSync() {
  Barrier(UAV_MEMORY | GROUP_SHARED_MEMORY | NODE_INPUT_MEMORY |
              NODE_OUTPUT_MEMORY,
          DEVICE_VISIBLE, GROUP_SYNC);
}

void DeviceMemoryBarrier() { Barrier(UAV_MEMORY, DEVICE_VISIBLE, 0); }

void DeviceMemoryBarrierWithGroupSync() {
  Barrier(UAV_MEMORY, DEVICE_VISIBLE, GROUP_SYNC);
}

void GroupMemoryBarrier() { Barrier(GROUP_SHARED_MEMORY, GROUP_VISIBLE, 0); }

void GroupMemoryBarrierWithGroupSync() {
  Barrier(GROUP_SHARED_MEMORY, GROUP_VISIBLE, GROUP_SYNC);
}

```

### New Structure Attributes

> Consistent with HLSL grammar attribute names are case-insensitive. Any
> attributes that take string arguments, the string argument values are
> case-sensitive.

#### **`[NodeTrackRWInputSharing]`**

If a `RWDispatchNodeInputRecord<T>` is used for cross-group sharing and calls
`FinishedCrossGroupSharing`, the struct type `T` must have the
`[NodeTrackRWInputSharing]` attribute applied to it. This allocates memory in
the record allocation to track thread completion.

## Alternatives considered (Optional)

If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing.

## Acknowledgments

This spec is an extensive collaboration between the Microsoft HLSL and Direct3D
teams and IHV partners.

Special thanks to Claire Andrews, Amar Patel, Tex Riddell, and Greg Roth.

<!-- {% endraw %} -->
