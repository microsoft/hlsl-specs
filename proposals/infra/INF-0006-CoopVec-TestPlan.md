# Cooperative Vector DirectX Feature - Test Plan

<a name="top"></a>

## Executive Summary

**DISCLAIMER: This is based on the WIP cooperative vector spec. Some details may change.**

**TODO: Update naming once spec is finalized.**

**Current status is: UNDER EXTERNAL REVIEW**

This test plan outlines the comprehensive validation strategy for the DirectX
Cooperative Vector feature, which enables hardware-accelerated vector-matrix
operations within DirectX 12 shaders using HLSL. The feature supports neural
network computations and other machine learning workloads through optimized
HLSL intrinsics for matrix-vector operations.

The plan defines a systematic testing approach covering:
- **Functionality validation** for all HLSL cooperative vector intrinsics
- **Type support testing** for both mandatory and optional combinations
- **Comprehensive matrix/vector parameter testing** across layouts, dimensions
  and memory patterns
- **Execution environment verification** across shader stages and control flow
  patterns
- **Precision validation** to ensure correctness within defined tolerances

The test methodology incorporates feature detection and conformance testing
on supported hardware. The document serves as a comprehensive reference for
implementing, validating, and maintaining HLK execution tests for the DirectX
Cooperative Vector feature through Microsoft's ExecTest/HLK framework.

## Table of Contents

- [1. Test Scope](#1-test-scope)
  - [1.1 Feature Components](#11-feature-components)
  - [1.2 Target Environment](#12-target-environment)
  - [1.3 Test Types](#13-test-types)
- [2. Test Methodology](#2-test-methodology)
  - [2.1 Feature Detection](#21-feature-detection)
  - [2.2 Functionality Testing for Matrix-Vector Operations](#22-functionality-testing-for-matrix-vector-operations)
    - [2.2.1 MatrixVectorMul/MulAdd Tests](#221-matrixvectormuladd-tests)
    - [2.2.2 OuterProductAccumulate Tests](#222-outerproductaccumulate-tests)
    - [2.2.3 VectorAccumulate Tests](#223-VectorAccumulate-tests)
    - [2.2.4 Input Vector Interpretation Tests](#224-input-vector-interpretation-tests)
  - [2.3 Matrix Conversion Testing](#23-matrix-conversion-testing)
    - [2.3.1 GetCooperativeMatrixVectorConversionDestinationInfo](#231-getcooperativematrixvectorconversiondestinationinfo)
    - [2.3.2 CooperativeVectorConvertMatrix](#232-cooperativevectorconvertmatrix)
  - [2.4 Control Flow Tests](#24-control-flow-tests)
  - [2.5 Shader Stages to Test](#25-shader-stages-to-test)
  - [2.6 Multi-Layer Neural Network Tests](#26-multi-layer-neural-network-tests)
  - [2.7 Non-mandatory Configuration Testing](#27-non-mandatory-configuration-testing)
- [3. Test Infrastructure](#3-test-infrastructure)
  - [3.1 Test Framework](#31-test-framework)
  - [3.2 Shader Generation](#32-shader-generation)
  - [3.3 Result Validation](#33-result-validation)

## 1. Test Scope

### 1.1 Feature Components
**Mandatory Operations for `D3D12_COOPERATIVE_VECTOR_TIER_1_0`**
- `MatrixVectorMul` - Matrix-Vector Multiply
- `MatrixVectorMulAdd` - Matrix-Vector Multiply-Add
- `ID3D12Device::GetCooperativeMatrixVectorConversionDestinationInfo` - API to
  query destination buffer size for matrix conversion
- `ID3D12CommandList::CooperativeVectorConvertMatrix` - API for matrix layout
  and type conversion

**Mandatory Operations for `D3D12_COOPERATIVE_VECTOR_TIER_1_1`**
- `OuterProductAccumulate` - Vector-Vector Outer Product and Accumulate
- `VectorAccumulate` - Add all components of a vector component-wise atomically
  to memory

### 1.2 Target Environment 
- **OS Versions**: Windows 11, Windows 10 (latest versions)
- **Hardware**: All GPUs supporting `D3D12_COOPERATIVE_VECTOR_TIER_1_0`,
  optional features in `D3D12_COOPERATIVE_VECTOR_TIER_1_1`

### 1.3 Test Types
- Functionality tests
  - Basic functionality tests for all mandatory operations and type
    combinations in the minimum support set for
    `D3D12_COOPERATIVE_VECTOR_TIER_1_0`
  - Basic functionality tests for all mandatory operations and type
    combinations in the minimum support set for
    `D3D12_COOPERATIVE_VECTOR_TIER_1_1`
- Extended functionality tests
  - Extended functionality tests for other type combinations supported by the
    driver
- Edge case tests
  - Test with values that are at the edge of representable values for the given
    type
  - Test with special values (NaN, Infinity, Denormal)
  - Test with various control flow patterns
- Multi-Layer tests
  - Test a subset of test variable configurations with more complex/realistic
    use cases. IE: MatrixVectorMul with interleaved activation functions.

[Back to Top](#top)

## 2. Test Methodology

### 2.1 Feature Detection

- For devices reporting `D3D12_COOPERATIVE_VECTOR_TIER_1_0` all mandatory 
operations and type combinations in the minimum support set must be supported.
- For devices reporting `D3D12_COOPERATIVE_VECTOR_TIER_1_1` all mandatory 
operations and type combinations in the minimum support set must be supported.

- When performing each test, check that the driver reports the operation and
  its type combinations are supported.
  - If the driver reports that a mandatory test configuration is not supported,
    the test should fail.
  - If the driver reports that an optional test configuration is supported, a
    test failure would result in failing the conformance test even though the
    operation is optional. The driver should correctly report support.
  - Otherwise skip the test.

### 2.2 Functionality Testing for Matrix-Vector Operations

#### 2.2.1 MatrixVectorMul/MulAdd Tests
- Test all mandatory type combinations in the minimum support set
- Test various optional type combinations if driver reports support
- Test with and without matrix transposition if driver reports support
- Test with all matrix layouts
- Test matrices of different dimensions (small, ML common, non-power of 2)
- Test different values for `MatrixOffset` and `MatrixStride` parameters
- Test out-of-bounds `Matrix` loads
- Test out-of-bounds `Bias` loads

#### 2.2.2 OuterProductAccumulate Tests
- Test mandatory type combination: `FP16`→`FP16`
- Test various optional type combinations if driver reports support
- Test with various matrix layouts
- Test matrices of different dimensions (small, ML common, non-power of 2)
- Test different values for `ResultMatrixOffset` and `ResultMatrixStride`
  parameters
- Test atomic accumulation behavior with multiple threads/waves
- Test out-of-bounds `Matrix` accumulate

#### 2.2.3 VectorAccumulate Tests
- Test mandatory type combination: `FP16`→`FP16`
- Test various optional type combinations if driver reports support
- Test vectors of different lengths (small, ML common, non-power of 2)
- Test different values for `ResultOffset` parameter
- Test atomic accumulation behavior with multiple threads/waves
- Test out-of-bounds `Vector` accumulate

#### 2.2.4 Input Vector Interpretation Tests
- The functionality tests should cover the conversion of input vector type
  to input interpretation type.
  - Test arithmetic conversions that preserve values (EX: fp16->fp8)
  - Test bitcast conversions that do not affect values
    (EX: HLSL packed type/uint -> SignedInt8x4Packed)

### 2.3 Matrix Conversion Testing

#### 2.3.1 GetCooperativeMatrixVectorConversionDestinationInfo
- Test queries for all destination layouts (row-major, column-major,
  inferencing-optimal, training-optimal) and types in the minimum support set
- Verify returned sizes are sufficient for subsequent conversion operations
- Validate that returned sizes match the actual required size when performing
  conversion

#### 2.3.2 CooperativeVectorConvertMatrix
- Test all mandatory source and destination type combinations in the minimum
  support set
- Test all source and destination layout combinations
- Test with various matrix dimensions
- Test with different stride values for row/column major layouts
- Test multiple conversions in a single API call, i.e., multiple
  `D3D12_COOPERATIVE_VECTOR_MATRIX_CONVERSION_INFO` objects passed in.

### 2.4 Control Flow Tests

The vector-matrix tests should cover the following control flow patterns:

| Pattern Type          | Description                                      |
|-----------------------|--------------------------------------------------|
| Uniform execution     | All lanes in wave execute the same code path     |
| Divergent execution   | 50% of lanes take a different branch             |
| Non-uniform offsets   | Different lanes use different matrix offsets     |

### 2.5 Shader Stages to Test

- Tests must cover all supported shader stages: 
  - Compute: CS
  - Graphics: PS, VS, GS, TS, HS
  - Ray Tracing: Ray Generation, Miss, Closest Hit, Any Hit, Intersection Hit.
- Test in compute shaders comprehensively with all type combinations and
  dimensions
- For other shader stages, use a more limited set of tests with:
  - A subset of key types
  - A subset of key dimensions
  - Only basic functionality tests (no advanced or special cases)
  - For PS include test with helper pixels.

This approach ensures we cover all shader stages without combinatorial
explosion of test cases.

### 2.6 Multi-Layer Neural Network Tests

- Test chained MatrixVectorMul(Add)? operations with interleaved activation
  functions
- Test with different number of layers

### 2.7 Non-mandatory Configuration Testing

This section outlines the approach for testing optional type combinations that
go beyond the mandatory requirements.
**REMINDER**: If the driver reports that an optional type combination is
supported, a test failure would result in failing the conformance test.

These conformance tests are focused on the mandatory configurations, but we
should have tests that cover the optional configurations.
The optional configurations will be tested using the parametrized shader
generator and use the basic functionality tests.
To prevent combinatorial explosion, the optional configurations will be more
limited in scope and will not be required to cover all of the test variables,
but they should at least cover the allowed types in a representative subset
of the test variables used for basic functionality tests.

[Back to Top](#top)

## 3. Test Infrastructure

### 3.1 Test Framework
- Tests will be implemented using the DirectX ExecTest/HLK testing framework
- Parameterized test generation will be used to cover the extensive range of
  configuration space

### 3.2 Shader Generation
- Create a shader generator framework that can produce test shaders with
  configurable parameters
- Shader generator should be able to produce shaders for all above tests

### 3.3 Result Validation

When implementing result validation for the DirectX Cooperative Vector feature,
use the following approaches:

- **Validate Using Reference Implementations**:
  - Create CPU reference implementations for each intrinsic that provide
    reference results for comparison

- **Define Precision Requirements by Type and Operation**:
  - Use value patterns that are exactly representable to allow bit-exact
    comparison for basic functionality and special value handling tests.
  - Use relative error thresholds for more complex operations like multi-layer
    tests.

- **Focus on Key Special Value Handling**:
  - **NaN Propagation**: Test that NaN inputs lead to NaN outputs across
    operations
  - **Infinity Handling**: Test basic infinity handling according to DirectX
    rules
  - **Basic Denormal Handling**: Test denormal input and output behavior
    according to precision requirements

This approach ensures that tests validate functional correctness while
accommodating reasonable implementation-specific variations in precision,
particularly for lower-precision formats or operations that involve multiple
calculation steps.

[Back to Top](#top)