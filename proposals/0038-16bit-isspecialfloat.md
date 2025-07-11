<!-- {% raw %} -->

# 16 bit isSpecialFloat DXIL Op

* Proposal: [0038](0038-16bit-isspecialfloat.md)
* Author(s): [Sarah Spall](https://github.com/spall)
* Sponsor: [Sarah Spall](https://github.com/spall)
* Status: **Under Consideration**

* Planned Version: Shader Model 6.9
* PRs:
* Issues: [#521](https://github.com/microsoft/hlsl-specs/issues/521)
  [#7496](https://github.com/microsoft/DirectXShaderCompiler/issues/7496)

## Introduction

The IsSpecialFloat DXIL Op is used to implement operations, 'isinf', 'isnan',
'isfinite', and 'isnormal'. Due to a bug (#7496), the IsSpecialFloat DXIL
operations were never generated for 16-bit types.

## Motivation

The 'isinf', 'isnan', and 'isfinite' functions (there is no 'isnormal' function)
, support fp16 but instead of generating a 16 bit IsSpecialFloat DXIL Op,
DXC extends to the 32 bit float op. See
(https://github.com/microsoft/DirectXShaderCompiler/issues/7496).
Some Vendor drivers support the 16 bit IsSpecialFloat op, but some do not. 

## Proposed solution

Beginning with SM 6.9 we would like to have DXC be able to generate this
operation, and not extend to 32-bit.  For shader models before 6.9 we want to
emulate the functionality using LLVM IR rather than a DXIL op.

We should also update the DXIL validator to disallow the 16 bit DXIL overloads
for the 'isinf', 'isnan', and 'isfinite', operations for SM 6.8 and below.
We do not plan to update the 'isnormal' operation because it is not reachable
via HLSL.

## Detailed design

### HLSL Additions

There are no HLSL Additions.  The implementations for 16 bit float 'isinf',
'isnan', and 'isfinite' will be updated to use emulation via LLVM IR for
SM6.8 and earlier, and will generate the appropriate 16 bit DXIL Op in SM6.9
and later.

### Interchange Format Additions

#### DXIL changes

These are the existing Opcodes for the isSpecialFloat DXIL OpClass.

| Opcode | Opcode name | Description
|:---    |:---         |:---
8        | IsNaN       | Returns true if x is NAN or WNAN, false otherwise.
9        | IsInf       | Returns true if x is +INF or -INF, false otherwise.
10       | IsFinite    | Returns true if x is finite, false otherwise.

The following overload will be added:
```DXIL
declare i1 @dx.op.isSpecialFloat.f16(
    i32,    ; opcode
    half)   ; val
```

#### SPIRV changes

There are the following SPIRV Ops:
OpIsInf, OpIsNan, OpIsFinite.

Currently the 32 bit version of these Ops are being used, but they
have 16 bit versions as well.  The open question is if we should always
generate the 16 bit version of these ops, or if the generation should be
gatekept behind some yet determined condition.

#### Validation Changes

The DXIL validator will need to be updated to retroactively disallow 16 bit DXIL
overloads for the isSpecialFloat DXIL operations in Shader Models 6.8 and
earlier, as well as if 16 bit types are not enabled.  The validator currently
allows the 16 bit overloads for SM6.2 and later.

### Runtime Additions

#### Runtime information

There doesn't need to be any runtime info changes.

#### Device Capability

The device must support the Half type.
Additionally, to use the 16 bit isSpecialFloat dxil Ops, SM6.9 and support for
16 bit types are required. This feature can be emulated in SM6.8 and earlier by
emulating with LLVM IR.

## Testing

* How will correct codegen for DXIL/SPIRV be tested?
Unit tests will verify the correct codegen for both DXIL and SPIRV.

* How will validation errors be tested?
Unit tests will verify that the correct validation errors are produced by the
validator in SM6.8 and earlier as well as if 16 bit types are not enabled.

* How will the execution results be tested?
There are existing SM6.2 HLK tests for 16 bit float 'isinf', 'isnan',
and 'isfinite'. The plan is to copy these tests for the SM6.9 HLK.

<!-- {% endraw %} -->
