---
title: "0054 - Maximal Reconvergence Compiler Testing"
draft: true
params:
  authors:
    - luciechoi: Lucie Choi
  sponsors:
    - s-perron: Steven Perron
    - Keenuts: Nathan Gauër
  status: Under Consideration
---

* PRs: [Testing in offload-test-suite (Draft)](https://github.com/llvm/offload-test-suite/pull/620)
* Issues:
  [Implementation in Clang](https://github.com/llvm/llvm-project/issues/136930)

## Introduction

This proposal seeks to add comprehensive conformance tests for the maximal reconvergence feature in HLSL compilers (DXC and Clang).

## Motivation

Graphics compilers often perform aggressive optimizations that can unexpectedly alter the convergence behavior of threads within a wave. This is a critical issue for shaders containing operations dependent on control flow, such as wave intrinsics, as invalid transformations can lead to wrong or indeterminate results.

Maximal reconvergence is a set of compiler guarantees designed to prevent these unintended changes, ensuring that divergent threads reconverge at expected merge points and that wave operations execute in lockstep where intended.

This feature is fully implemented in DirectXCompiler and LLVM, and testing for correct convergence behavior is critical for reliability. Currently, only a few unit tests exist. We need to extend this coverage to include complex and highly divergent cases.

## Proposed solution

We propose implementing a comprehensive test suite in the offload-test-suite repository that mirrors the logic of the Vulkan Conformance Testing Suite (Vulkan-CTS). This involves generating shaders with random control flows (mixes of if/switch statements, loops, and nesting) and verifying the results.

### Shader Generation

Approximately `N` HLSL shaders will be generated. These shaders use fixed input buffers and write to output buffers, where randomness is derived from branching logic.

### CPU Simulation

A CPU simulation will track active thread indices and calculate the expected result of wave operations based on specific subgroup sizes.


### Verification

The generated shaders will follow the offload-test-suite format. The shaders will be executed on the GPU, and the resulting output buffers will be compared against the CPU-simulated expectations to verify correctness.

## Detailed design

### Test Generation and Simulation
The shaders will be generated when the test pipeline starts. Since each GPU has different subgroup sizes, each machine will have a version for every power-of-2 wave size between 4 and 32 (e.g., 4, 8, 16, 32). The tests that do not match the subgroup size of the running GPU will be skipped (`UNSUPPORTED`).

### Translation

Logic from [Vulkan CTS GLSL generation](https://github.com/KhronosGroup/VK-GL-CTS/blob/main/external/vulkancts/modules/vulkan/reconvergence/vktReconvergenceTests.cpp) will be ported to produce HLSL. This includes translating intrinsics such as `subgroupElect()` to `WaveIsFirstLane()` and `subgroupBallot()` to `WaveActiveBallot()`, etc.

### Execution Pipeline
Only the **HLSL test generator** will reside in the offload-test-suite repository.

### Latency

The entire Vulkan-CTS test (~1500 shaders) takes ~10 seconds to complete, so the test generation + execution time should be similar and should not significantly affect the current pipeline duration. We may also choose to start with smaller iterations (~100 shaders).

### Reporting

Results of the reconvergence tests will be aggregated. Failing shaders will be logged separately or made available via YAML artifacts to avoid diluting logs with excessive data.

### Debugging

Debugging a failed test will be hard, as a randomly generated shader will not be so intuitive for readers to calculate the expected result at a given line. There are several ways to help pinpoint a bug:

- Reducing the workgroup size and/or nesting level.
- Comparing the results with other GPUs and/or backends.
- Writing a reducer for the randomly generated shaders.

It is worth noting that the failures may also originate from the driver compilers rather than the frontend compilers.

### Sanity Check

A small subset of pre-generated tests will be included in the repository to allow developers to sanity-check without triggering the full pipeline.

## Alternatives considered (Optional)

The proposed solution is the hybrid of the two alternatives considered.

### Option 1: Pre-generate and store all shaders in YAML

This approach involves generating all shaders offline and storing them in the repository. Although this is a straightforward implementation, it's not necessary to maintain the physical copies of the random shaders. We may later want to change the parameters of the generator (e.g. seed, nesting level).

### Option 2: Generation and execution in a separate test pipeline

This approach mimics Vulkan-CTS by doing the shader generation, CPU simulation, and GPU execution in its own test pipeline, without storing any physical copies at any point in time. However, this requires implementing the entire pipeline from scratch for multiple backends, including DirectX and Metal.

## Acknowledgments

Steven Perron and Nathan Gauër for reviewing the initial planning and documentation.
