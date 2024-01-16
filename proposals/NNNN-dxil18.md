<!-- {% raw %} -->

# DXIL 1.8

* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8

## Introduction

Shader Model 6.8 introduces new features to HLSL which need representations in
DXIL. This proposal captures an abbreviated version of the DXIL changes.

## Detailed design

### Address Space 6

DXIL 1.8 reserves address space 6 for storage of work graph record data. This is
used in some of the new DXIL intrinsics.

### DXIL Constant additions

DXIL 1.8 introduces a new enumeration to the `DXIL::ShaderKind` enumeration and
a new enumeration type `DXIL::NodeLaunchType` as described in the table below:

```
┌────────────────────────┬──────────────────┬──────────────────┐
│       Enum Type        │       Name       │      Value       │
├────────────────────────┼──────────────────┼──────────────────┤
│DXIL::ShaderKind        │Node              │        15        │
├────────────────────────┼──────────────────┼──────────────────┤
│DXIL::NodeLaunchType    │Invalid           │        0         │
├────────────────────────┼──────────────────┼──────────────────┤
│DXIL::NodeLaunchType    │Broadcasting      │        1         │
├────────────────────────┼──────────────────┼──────────────────┤
│DXIL::NodeLaunchType    │Coalescing        │        2         │
├────────────────────────┼──────────────────┼──────────────────┤
│DXIL::NodeLaunchType    │Thread            │        3         │
└────────────────────────┴──────────────────┴──────────────────┘
```

### New DXIL Types

DXIL 1.8 adds new opaque object types for interacting with Work Graph types.

```
%dx.types.NodeHandle = type { i8* }
%dx.types.NodeRecordHandle = type { i8* }
```

DXIL 1.8 also adds new property types for Work Graph types.

```
%dx.types.NodeInfo = type { i32, i32 }
%dx.types.NodeRecordInfo = type { i32, i32 }
```

### New DXIL Opcodes

```
┌───────────────────────────────┬────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│             Name              │ opcode │                                                     IR Signature                                                      │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│allocateNodeOutputRecord       │  226   │%dx.types.NodeRecordHandle @dx.op.allocateNodeOutputRecords(i32, %dx.types.NodeHandle, i32, i1)                        │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│getNodeRecordPtr               │  227   │<type> addrspace(6)* @dx.op.getNodeRecordPtr.<type>(i32, %dx.types.NodeRecordHandle, i32)                              │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│incrementOutputCount           │  228   │void @dx.op.incrementOutputCount(i32, %dx.types.NodeHandle, i32, i1)                                                   │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│outputComplete                 │  229   │void @dx.op.outputComplete(i32, %dx.types.NodeRecordHandle)                                                            │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│getInputRecordCount            │  230   │ i32 @dx.op.getInputRecordCount(i32, %dx.types.NodeRecordHandle)                                                       │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│getInputRecordCount            │  231   │ i32 @dx.op.getInputRecordCount(i32, %dx.types.NodeRecordHandle)                                                       │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│finisedCrossGroupSharing       │  232   │i1 @dx.op.finishedCrossGroupSharing(i32, %dx.types.NodeRecordHandle)                                                   │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│barrierByMemoryType            │  233   │void @dx.op.barrierByMemoryType(i32, i32, i32)                                                                         │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│barrierByNodeRecordHandle      │  234   │call void @dx.op.barrierByNodeRecordHandle(i32, %dx.types.NodeRecordHandle, i32)                                       │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│createNodeOutputHandle         │  235   │%dx.types.NodeHandle @dx.op.createNodeOutputHandle(i32, i32)                                                           │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│indexNodeHandle                │  236   │%dx.types.NodeHandle @dx.op.indexNodeHandle(i32, %dx.types.NodeHandle, i32)                                            │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│annotateNodeHandle             │  236   │%dx.types.NodeHandle @dx.op.annotateNodeHandle(i32, %dx.types.NodeHandle, %dx.types.NodeInfo)                          │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│createNodeInputRecordHandle    │  237   │%dx.types.NodeRecordHandle @dx.op.createNodeInputRecordHandle(i32, i32)                                                │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│annotateNodeRecordHandle       │  238   │%dx.types.NodeRecordHandle @dx.op.annotateNodeRecordHandle(i32, %dx.types.NodeRecordHandle, %dx.types.NodeRecordInfo)  │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│nodeOutputIsValid              │  239   │i1 @dx.op.nodeOutputIsValid(i32, %dx.types.NodeHandle)                                                                 │
├───────────────────────────────┼────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│getRemainingRecursionLevels    │  240   │call i32 @dx.op.getRemainingRecursionLevels(i32)                                                                       │
└───────────────────────────────┴────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### New DXIL Metadata

Node shader entry metadata can contain the following tagged entries:

```
┌─────────────────────────────────────────┬──────────┬──────────────────────────┐
│                   Tag                   │ Constant │          Value           │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNumThreadsTag                       │    4     │MDList: (i32, i32, i32)   │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeLaunchTypeTag                   │    13    │MDList: (i32)             │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeIsProgramEntryTag               │    14    │MDList: (i1)              │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeIdTag                           │    15    │MDList: (MDString, i32)   │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeLocalRootArgumentsTableIndexTag │    16    │MDList: (i32)             │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilShareInputOfTag                     │    17    │MDList: (MDString, i32)   │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeDispatchGridTag                 │    18    │MDList: (i32, i32, i32)   │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeMaxRecursionDepthTag            │    19    │MDList: (i32)             │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeInputsTag                       │    20    │MDList: (MDList[])        │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeOutputsTag                      │    21    │MDList: (MDList[])        │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeMaxDispatchGridTag              │    22    │MD list: (i32, i32, i32)  │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilRangedWaveSize                      │    23    │MD list: (i32, i32, i32)  │
└─────────────────────────────────────────┴──────────┴──────────────────────────┘
```

All entries in the table above except `kDxilNumThreadsTag` are new constants
introduced in DXIL 1.8.

The `kDxilNodeInputsTag` and `kDxilNodeOutputsTag` values are lists of node
metadata entries, where each node is an MDList of sub metadata entries based on
the following index table:

```
┌─────────────────────────────────────────┬──────────┬──────────────────────────┐
│                   Tag                   │  Index   │          Value           │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeOutputIDTag                     │    0     │MDList: (MDString, i32)   │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeIOFlagsTag                      │    1     │MDList: (i32)             │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeRecordTypeTag                   │    2     │MDList: (MDList[])        │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeMaxRecordsTag                   │    3     │MDList: (i32)             │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeMaxRecordsSharedWithTag         │    4     │MDList: (MDString, i32)   │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeOutputArraySizeTag              │    5     │MDList: (i32)             │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeAllowSparseNodesTag             │    6     │MDList: (i1)              │
└─────────────────────────────────────────┴──────────┴──────────────────────────┘
```

`kDxilNodeRecordType` is a tagged metadata list based on the following tags:

```
┌─────────────────────────────────────────┬──────────┬──────────────────────────┐
│                   Tag                   │ Constant │          Value           │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeRecordSizeTag                   │    0     │MDList: (i32)             │
├─────────────────────────────────────────┼──────────┼──────────────────────────┤
│kDxilNodeSVDispatchGridTag               │    1     │MDList: (i32, i32, i32)   │
└─────────────────────────────────────────┴──────────┴──────────────────────────┘
```

The `kDxilNodeIOFlagsTag` is based on the `DXIL::NodeIOFlags` and
`DXIL::NodeIOKind` enumerations as described below:

```c++
enum class NodeIOFlags : uint32_t {
    None = 0x0,
    Input = 0x1,
    Output = 0x2,
    ReadWrite = 0x4,
    EmptyRecord = 0x8, // EmptyNodeOutput[Array], EmptyNodeInput
    NodeArray = 0x10,  // NodeOutputArray, EmptyNodeOutputArray

    // Record granularity (enum in 2 bits)
    ThreadRecord = 0x20,   // [RW]ThreadNodeInputRecord, ThreadNodeOutputRecords
    GroupRecord = 0x40,    // [RW]GroupNodeInputRecord, GroupNodeOutputRecords
    DispatchRecord = 0x60, // [RW]DispatchNodeInputRecord
    RecordGranularityMask = 0x60,

    NodeIOKindMask = 0x7F,

    TrackRWInputSharing = 0x100, // TrackRWInputSharing tracked on all non-empty
                                 // input/output record/node types

    // Mask for node/record properties beyond NodeIOKind
    RecordFlagsMask = 0x100,
    NodeFlagsMask = 0x100,
  };

  enum class NodeIOKind : uint32_t {
    Invalid = 0,

    EmptyInput =
        (uint32_t)NodeIOFlags::EmptyRecord | (uint32_t)NodeIOFlags::Input,
    NodeOutput =
        (uint32_t)NodeIOFlags::ReadWrite | (uint32_t)NodeIOFlags::Output,
    NodeOutputArray = (uint32_t)NodeIOFlags::ReadWrite |
                      (uint32_t)NodeIOFlags::Output |
                      (uint32_t)NodeIOFlags::NodeArray,
    EmptyOutput =
        (uint32_t)NodeIOFlags::EmptyRecord | (uint32_t)NodeIOFlags::Output,
    EmptyOutputArray = (uint32_t)NodeIOFlags::EmptyRecord |
                       (uint32_t)NodeIOFlags::Output |
                       (uint32_t)NodeIOFlags::NodeArray,

    DispatchNodeInputRecord =
        (uint32_t)NodeIOFlags::Input | (uint32_t)NodeIOFlags::DispatchRecord,
    GroupNodeInputRecords =
        (uint32_t)NodeIOFlags::Input | (uint32_t)NodeIOFlags::GroupRecord,
    ThreadNodeInputRecord =
        (uint32_t)NodeIOFlags::Input | (uint32_t)NodeIOFlags::ThreadRecord,

    RWDispatchNodeInputRecord = (uint32_t)NodeIOFlags::ReadWrite |
                                (uint32_t)NodeIOFlags::Input |
                                (uint32_t)NodeIOFlags::DispatchRecord,
    RWGroupNodeInputRecords = (uint32_t)NodeIOFlags::ReadWrite |
                              (uint32_t)NodeIOFlags::Input |
                              (uint32_t)NodeIOFlags::GroupRecord,
    RWThreadNodeInputRecord = (uint32_t)NodeIOFlags::ReadWrite |
                              (uint32_t)NodeIOFlags::Input |
                              (uint32_t)NodeIOFlags::ThreadRecord,

    GroupNodeOutputRecords = (uint32_t)NodeIOFlags::ReadWrite |
                             (uint32_t)NodeIOFlags::Output |
                             (uint32_t)NodeIOFlags::GroupRecord,
    ThreadNodeOutputRecords = (uint32_t)NodeIOFlags::ReadWrite |
                              (uint32_t)NodeIOFlags::Output |
                              (uint32_t)NodeIOFlags::ThreadRecord,
  };
```

### Reading and Writing Node Records

Unlike memory operations in earlier versions of DXIL, reading and writing node
record memory uses LLVM's load and store instructions. DXIL 1.8 reserves address
space 6 for node memory. The `getNodeRecordPtr` DXIL operation returns a pointer
to node record memory in address space 6.

## Acknowledgments

This spec is an extensive collaboration between the Microsoft HLSL and Direct3D
teams and IHV partners.

Special thanks to:
Claire Andrews
Nick Feeney
Amar Patel
Tex Riddell
Greg Roth


<!-- {% endraw %} -->
