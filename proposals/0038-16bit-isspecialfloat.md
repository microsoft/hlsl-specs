---
title: 0038 - 16 bit isSpecialFloat DXIL Op
params:
  authors:
  - spall: Sarah Spall
  sponsors:
  - spall: Sarah Spall
  status: Under Consideration
---


 
* Planned Version: Shader Model 6.9
* PRs:
* Issues: [#521](https://github.com/microsoft/hlsl-specs/issues/521)
  [#7496](https://github.com/microsoft/DirectXShaderCompiler/issues/7496)

## Introduction

The IsSpecialFloat DXIL Ops are used to implement operations, 'isinf', 'isnan',
'isfinite', and 'isnormal'. Due to a bug (#7496), the IsSpecialFloat DXIL
operations were never generated for 16-bit types.

## Motivation

Though the IsSpecialFloat class of DXIL ops support 16-bit float overloads,
when float16_t is used with 'isinf', 'isnan', or 'isfinite' HLSL intrinsic
functions, the argument gets implicitly cast to float, since there are no
16-bit overloads for these intrinsics defined in HLSL (bug: [#7496]).
This prevents the expected 16-bit DXIL overload from being used, even though
this overload has existed since SM 6.2.  Even HLK tests for the 16-bit
operations are impacted by this bug, so they do not test the intended overloads.
And, it is know that some Vendor drivers do not support the 16 bit overload
of IsSpecialFloat.
We would like to remove this implicit casting behavior which could impact
performance and prevents 16-bit overload testing.

Additionally, the IsSpecialFloat DXIL OpCodeClass supports the IsNormal
operation, but no HLSL intrinsic exists to target this. The 32-bit IsNormal op
is tested in the HLK through DXIL IR replacement, but this testing method is
awkward and isn't supported by the clang offload test suite, so we would prefer
to expose the isnormal operation as an intrinsic in HLSL.

## Proposed solution

Beginning with SM 6.9 we would like to have DXC be able to generate this
operation, and not extend to 32-bit.  For shader models before 6.9 we want to
emulate the functionality using LLVM IR rather than a DXIL op.

We should also update the DXIL validator to disallow the 16 bit DXIL overloads
for the 'isinf', 'isnan', 'isfinite', and 'isnormal' operations for SM 6.8 and
below.

## Detailed design

### HLSL Additions

Currently there is no 'isnormal' HLSL function, and the plan is to add 'isnormal'
to HLSL.  The 16 bit version of the new 'isnormal' function will be emulated
using LLVM IR for SM6.8 and earlier and will generate the appropriate 16 bit DXIL
Op in SM6.9 and later.
16 bit float overloads for 'isinf', 'isnan', and 'isfinite' will be added to HLSL.
The implementations for 16 bit float 'isinf', 'isnan', and 'isfinite' will use
emulation via LLVM IR for SM6.8 and earlier, and will generate the appropriate
16 bit DXIL Op in SM6.9 and later. For the min16float type, the implementations
will remain unchanged, DXC will continue to use the 32 bit DXIL ops.

### Interchange Format Additions

#### DXIL changes

These are the existing Opcodes for the isSpecialFloat DXIL OpClass.

| Opcode | Opcode name | Description
|:---    |:---         |:---
8        | IsNaN       | Returns true if x is NAN or WNAN, false otherwise.
9        | IsInf       | Returns true if x is +INF or -INF, false otherwise.
10       | IsFinite    | Returns true if x is finite, false otherwise.
11       | IsNormal    | Returns false if x is zero, INF, NAN or subnormal (denormal), true otherwise

Support for the following overload will be added in SM6.9:
```DXIL
declare i1 @dx.op.isSpecialFloat.f16(
    i32,    ; opcode
    half)   ; val
```

#### SPIRV changes

There are the following SPIRV Ops:
OpIsInf, OpIsNan, OpIsFinite, OpIsNormal.

Currently the 32 bit version of these Ops are always used, but they
have 16 bit versions as well.  A possible plan is to always generate these 16
bit SPIRV ops for the 16 bit float overloads of 'isinf', 'isnan', isfinite',
and 'isnormal'.

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
Filecheck based unit tests will verify that the correct validation errors are
produced by the validator in SM6.8 and earlier as well as if 16 bit types are
not enabled.

* How will the execution results be tested?
There are existing SM6.2 HLK tests for 16 bit float 'isinf', 'isnan',
and 'isfinite'. The plan is to copy these tests for the SM6.9 HLK.
A new HLK test for 16 bit float 'isnormal' will need to be written and added
to the SM6.9 HLK.  The existing 32 bit 'isnormal' HLK test should be updated to
use the new HLSL 'isnormal' intrinsic rather than perform an IR modification.

## Open Questions

An open question is if we should always
generate the 16 bit version of the relevant SPIRV ops for the 16 bit overloads,
or if their generation should be gatekept behind some not yet determined condition.


