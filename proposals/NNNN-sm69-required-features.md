---
title: "NNNN - SM69 Required Features"
params:
  authors:
    - damyanp: Damyan Pepper
  sponsors:
    - damyanp: Damyan Pepper
  status: Under Consideration
---


## Instructions

* Planned Version: SM 6.9

## Introduction

This proposal makes the following optional features required features for Shader Model 6.9:

* D3D12_FEATURE_DATA_D3D12_OPTIONS4.Native16BitShaderOpsSupported
* D3D12_FEATURE_DATA_D3D12_OPTIONS1.WaveOps
* D3D12_FEATURE_DATA_D3D12_OPTIONS1.Int64ShaderOps

## Motivation

Shader Model 6.9 introduces vectorized DXIL ([0030](0030-dxil-vectors.md)) which
means that we need to add new conformance tests for all DXIL operations that now
accept vectors. Some of these operations are optional, and so we'd need to test
combinations of these features.

In practice every device that supports SM 6.9 is expected to support these
operations, so we can simplify the testing matrix by assuming that these operations are supported.

## Proposed solution

A new HLK test will be added that verifies that for SM 6.9 the optional features listed above are supported.

The other tests will be written assuming that these features are supported.

