<!-- {% raw %} -->

# Validator Hashing

* Proposal: [INF-0004](INF-0004-validator-hashing.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Accepted**

## Introduction

The HLSL compiler includes a post-compile binary analysis tool, the validator.
The validator verifies the validity of the generated program in accordance to
rules defined for each Shader Model, and on successful execution embeds a hash
within the binary. The hash is then used by the runtime to assert that the
binary has not been modified since the validator processed it.

This proposal includes several changes to this flow including changes to how the
validator is packaged. The proposal also includes some proposed changes to the
D3D runtime that change when the validator is run and when the hash is verified.

## Motivation

Validation fulfills a critical role in the HLSL compiler. The HLSL compiler is
able to generate bytecode sequences that are not valid, and we rely on the
validator to catch and surface those errors. This is a foundational design
consideration in DXC. This proposal does not seek to diminish the importance of
validation.

The HLSL team wants developers to run the DXIL validator. The HLSL team believes
that developers want the assurances that the validator provides. However, cases
exist today where developers circumvent the validator because it obstructs their
ability to get things done. Other cases exist where running the validator poses
too great of a performance penalty.

This proposal recognizes the reality that the validator isn't perfect, that
circumventing it is possible (and commonplace), and that we need a different
approach. The goal of this proposal is to provide users with the protections
that validation provides, while also getting the validator out of the way.

The goal of this proposal is to alleviate pain that causes legitimate use cases
to circumvent validation, and allow the validator flow to be smoother for users
that want to run the validator.

### Current State

Today, after the DXIL validator successfully validates a binary it computes a
hash using a modified MD5 hash algorithm, which then gets encoded into the
shader binary. This acts as a weak form of tamper verification allowing the
runtime to check that a shader has not been tampered with after the validator
scanned the binary to ensure it conformed to the target Shader Model's
definition.

The only assurances given to the runtime and driver that a shader's DXIL has
been validated comes from the fact that the hashing algorithm is not published,
so it is assumed that the hash is only computed after validation succeeds. This
assumption is weak and can be proven incorrect since the algorithm has been
published by other entities and is available on GitHub today
[1](#renderdoc-source)[2](#hexops-source).

### Legitimate Reasons Users Circumvent Validation

One of the reasons that developers have circumvented DXIL hashing is to
statically link DXC as a single binary [3](#hexops-devlog). This has benefits
for process launch time which can significantly impact overall compiler
performance.

Another reason users bypass the hashing algorithm is for portability. Users have
wanted to be able to compile shaders for Windows on Linux and macOS for years
[4](#macos-builds). DXC's Linux releases have been troubled and unusable without
modification. DXC still has no official release for macOS, and the investment to
produce one is unlikely to be worthwhile.

Lastly, users circumvent validation in cases where the validator is
prohibitively slow to run. Three examples where this is a motivation for
bypassing validation are:

* Platform mapping layers where other shader bytecodes (i.e. DXBC or SPIR-V) are
  translated to DXIL at runtime.
* Developer tooling scenarios where tools need to rewrite shaders at runtime for
  performance instrumentation.
* Developer tooling scenarios where embedding extra data in the container is
  helpful.

## Proposed solution

The minimum effort initial step is to merge the current implementation of
DXIL.dll into the public DXC source tree. This immediately unblocks users with
portability concerns, and eases our own developer workflows as testing
validation workflows has been restricted due to the current architecture.

As we look to the future we should build the DXIL validator library both as a
dynamic and static library to allow full flexibility. The static library can be
directly linked into dxcompiler.dll and dxv.exe. This will allow simplified
distributions and faster execution of the DXIL validator both for users of DXC
and users of Clang.

We should also evaluate statically linking dxcompiler.dll with dxc.exe. While
this will increase the size of our binary distributions, it may produce a
significant performance increase for users of dxc.exe.

### Reserved Static Hash Values

Due to the nature of the MD5 hash algorithm there are some digest values that
are impossible to compute from message content. We reserve some of these values
to act as known sentinel values for communication with the runtime.

The D3D runtime passes shader hashes to drivers via the device driver interface.
To prevent breaking this use case, the runtime must compute a replacement hash
for the DDI for any shader that contains a sentinel value for its hash.

The table below describes the initial proposed sentinel values:

| Name       | Hash                             |
|------------|----------------------------------|
| BYPASS     | 01010101010101010101010101010101 |
| PREVIEW    | 02020202020202020202020202020202 |

### Hashing for Pre-release Shader Models

When DXC includes the sources for the validator hash, the default compiler flow
should be that all shaders are validated and hashed using what is today the
internal validator.

For pre-release shader models DXC should run the validator, but it should not
apply the hash. Instead it should apply the `PREVIEW` sentinel value from the
table above. This allows us to differentiate between shaders validated by a
"final" validator.

### D3D Runtime Behavior

Starting with AgilitySDK version TBD, the runtime adopts new behavior for how 
and when the shader hash is validated, including support for bytecode validation 
in the debug layer and runtime.

For shaders with the `PREVIEW` hash, the shader is allowed to execute only if
developer mode and the experimental feature D3D12ExperimentalShaderModels is
enabled, otherwise the runtime will produce an error.

For shaders with the `BYPASS` hash, shaders can run without validating the hash 
regardless of whether the machine is in developer mode as long as the shader 
targets a supported non-experimental shader model.

All other values of the hash are assumed to be real hash values.

For shaders that contain a real hash value, the behavior is unchanged. The hash
is verified and the shader executes as it does with existing versions of the 
runtime.

> Note: an important behavior change here is that shaders with zero'd hash data
> will always be treated as invalid by the runtime and rejected.
> 
> An exception is for a period of time already existing preview shaders that used 
> zero'd hash data will be treated as equivalent to having the `PREVIEW` hash 
> until those preview shaders are no longer supported in new preview runtimes.

#### D3D Runtime Validation Control

Apps can configure how the runtime validates bytecode passed to it. 

The validation referred to here is implementation exposed by `dxcompiler.dll` 
or `dxil.dll`.  This is the same validation used when the compiler
endorses bytecode at compile time by applying a hash.  So it would typically be 
redundant to validate again  But it can be useful to validate shaders that have 
the `BYPASS` hash, or have the option to force validation for whatever reason. 

If there is bytecode to validate, the runtime and/or debug layer attempt to 
load one of these dlls, `dxcompiler.dll` first. If either is available, 
bytecode validation is possible. 

The following flags in `d3d12.h` show the validation control options.  
`ID3D12Device` exposes `ID3D12BytecodeOptions` to set the flags, shown 
further below.


```C++
typedef enum D3D12_BYTECODE_FLAGS
{
    D3D12_BYTECODE_FLAG_VALIDATION_DISABLED = 0x1,
    D3D12_BYTECODE_FLAG_VALIDATE_BYTECODE_WITH_BYPASS_HASH = 0x2,
    D3D12_BYTECODE_FLAG_VALIDATE_ALL_RELEASE_BYTECODE = 0x4,
    D3D12_BYTECODE_FLAG_VALIDATE_ONLY_IF_DEBUG_LAYER_ENABLED_NO_FAILING = 0x8,
    D3D12_BYTECODE_FLAG_SKIP_VALIDATION_IF_VALIDATOR_NOT_AVAILABLE = 0x10,
    D3D12_BYTECODE_FLAGS_DEFAULT = 
        D3D12_BYTECODE_FLAG_VALIDATE_BYTECODE_WITH_BYPASS_HASH | 
        D3D12_BYTECODE_FLAG_VALIDATE_ONLY_IF_DEBUG_LAYER_ENABLED_NO_FAILING |
        D3D12_BYTECODE_FLAG_SKIP_VALIDATION_IF_VALIDATOR_NOT_AVAILABLE
} D3D12_BYTECODE_FLAGS;
DEFINE_ENUM_FLAG_OPERATORS( D3D12_BYTECODE_VALIDATION_FLAGS )
```

Flag | Definition
---|---
`D3D12_BYTECODE_FLAG_VALIDATION_DISABLED` | Never invoke bytecode validation.
`D3D12_BYTECODE_FLAG_VALIDATE_BYTECODE_WITH_BYPASS_HASH` | Only validate bytecode that has the `BYPASS` hash.
`D3D12_BYTECODE_FLAG_VALIDATE_ALL_RELEASE_BYTECODE` | Validate all bytecode, hashed or `BYPASS`, except `PREVIEW`.  `PREVIEW` is excluded since that bytecode doesn't support validation at all.  Forcing validation for all release bytecode (hashed or `BYPASS`) could be useful to root out shaders that are hashed (implying validation ran on them), but there is an updated valdiator that catches issues that might have been missed.  Or the app might want validation on shaders that might have been hashed manually without the compiler's validator.
`D3D12_BYTECODE_FLAG_VALIDATE_ONLY_IF_DEBUG_LAYER_ENABLED_NO_FAILING` | Only the debug layer performs bytecode validation.  If errors are found, it reports debug messages without failing the shader.  Accordingly if the debug layer isn't enabled no validation is done. Without this flag, the runtime validates bytecode and errors produce failure (e.g. shader creation failure), and if the debug layer is enabled it will also print a corresponding message.
`D3D12_BYTECODE_FLAG_SKIP_VALIDATION_IF_VALIDATOR_NOT_AVAILABLE` | Regardless of how the other flags request validation, if the runtime or debug layer can't load `dxcompiler.dll` or `dxil.dll` and find a validation implementation they skip validation without failing.  If this flag is not set, the runtime will fail if it needs to validate bytecode and can't find a validator implementation.
`D3D12_BYTECODE_FLAGS_DEFAULT` | By default validation is only done on bytecode with the `BYPASS` hash, only from the debug layer, and only if a validator implementation can be found.  Equivalent to the three flags: `D3D12_BYTECODE_FLAG_VALIDATE_BYTECODE_WITH_BYPASS_HASH`, `D3D12_BYTECODE_FLAG_VALIDATE_ONLY_IF_DEBUG_LAYER_ENABLED_NO_FAILING` and `D3D12_BYTECODE_FLAG_SKIP_VALIDATION_IF_VALIDATOR_NOT_AVAILABLE` |

The first three flags above are mutually exclusive and one must be chosen.

Flags are set via `ID3D12BytecodeOptions`:

```C++
[uuid(9291ad45-9a10-43a5-9c06-f5aa558e89a7), object, local, pointer_default(unique)]
interface ID3D12BytecodeOptions
    : IUnknown
{
    // Returns S_OK if flags are valid, E_INVALIDARG otherwise
    HRESULT SetBytecodeFlags(
        [annotation("_In_")] D3D12_BYTECODE_FLAGS flags
    );
    D3D12_BYTECODE_FLAGS GetBytecodeFlags();
};
```
The above methods are not thread safe or synchronized with other device methods 
such as creating shaders where the options would apply.  Apps must do their 
own synchronization around changing bytecode options and making calls to any 
other device methods if necessary.

Usage example:

```C++
CComPtr<ID3D12BytecodeOptions> pBytecodeOptions;
pDevice->QueryInterface(&pBytecodeOptions);
pBytecodeOptions->SetBytecodeValidationFlags(D3D12_BYTECODE_FLAG_VALIDATE_ALL_RELEASE_BYTECODE);

// All subsequent bytecode passed to he runtime and debug layer for creating state objects / PSOs etc. 
// will be validated.  If a validator implementation can't be located, the state creation will fail.
```

### Compatibility

This proposal is fully backwards compatible to older shader models since the
existing runtime hash validation applies except when experimental shader models
are enabled.

When this change is introduced to DXC all shaders compiled by DXC will either
contain a valid hash, contain the `PREVIEW` hash, or fail validation and not
produce an output.

The only exception will be the case where validation is intentionally disabled
(as with the `-Vd`) flag. In that case the hash data in the container will be
zero'd.

### Concerns About Invalid DXIL

As this proposal has been discussed concerns have been raised about allowing
invalid DXIL into the runtime. Due to existing use cases that bypass validation
and the ready availability of the DXIL hash, non-validated DXIL is already going
into the runtime and drivers.

The primary concern expressed from external partners was that driver developers
would needlessly spend time chasing bugs that prove to be caused by invalid
DXIL. The concerned parties agreed that the D3D runtime running DXIL validation
in the debug layer would provide sufficient tooling to mitigate that concern.

A separate concern was raised about the possibility that pre-release shader
model features could infiltrate production shaders. While the changes in this
proposal may seem to make that more likely, this is unlikely to be a significant
concern. Adoption of new shader model features in production software generally
takes years. It is extremely unlikely that a product would use a
multiple-year-old preview compiler for generating final compiled shaders for a
title. The high rate of bugs in preview compilers contributes to making this
even less likely.

## Appendix 1: DXIL Hashing Algorithm

The DXIL hashing algorithm is derived from a public domain implementation of
[RFC 1321](#rfc1321). This appendix breaks the code into four separate segments
which provide full implementation of the three related hash algorithms.

### Base MD5 Utilities

This code is a set of base utilities and constants used by all three algorithms
which are derived from the original MD5 RFC. 

```c
#define S11 7
#define S12 12
#define S13 17
#define S14 22
#define S21 5
#define S22 9
#define S23 14
#define S24 20
#define S31 4
#define S32 11
#define S33 16
#define S34 23
#define S41 6
#define S42 10
#define S43 15
#define S44 21

const BYTE padding[64] = 
{
    0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
       0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
       0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
       0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
};

void FF( UINT& a, UINT b, UINT c, UINT d, UINT x, UINT8 s, UINT ac )
{
    a += ((b & c) | (~b & d)) + x + ac;
    a = ((a << s) | (a >> (32-s))) + b;
}

void GG( UINT& a, UINT b, UINT c, UINT d, UINT x, UINT8 s, UINT ac )
{
    a += ((b & d) | (c & ~d)) + x + ac;
    a = ((a << s) | (a >> (32-s))) + b;
}

void HH( UINT& a, UINT b, UINT c, UINT d, UINT x, UINT8 s, UINT ac )
{
    a += (b ^ c ^ d) + x + ac;
    a = ((a << s) | (a >> (32-s))) + b;
}

void II( UINT& a, UINT b, UINT c, UINT d, UINT x, UINT8 s, UINT ac )
{
    a += (c ^ (b | ~d)) + x + ac;
    a = ((a << s) | (a >> (32-s))) + b;
}
```


### Base MD5 Implementation

This is an implementation of the original MD5 RFC.

```c
// **************************************************************************************
// **** DO NOT USE THESE ROUTINES TO PROVIDE FUNCTIONALITY THAT NEEDS TO BE SECURE!!! ***
// **************************************************************************************
void ComputeM_D_5Hash( const BYTE* pData, UINT byteCount, BYTE* pOutHash )
{
    UINT leftOver = byteCount & 0x3f;
    UINT padAmount;
    bool bTwoRowsPadding = false;
    if( leftOver < 56 )
    {
        padAmount = 56 - leftOver;
    }
    else
    {
        padAmount = 120 - leftOver;
        bTwoRowsPadding = true;
    }
    UINT padAmountPlusSize = padAmount + 8;
    UINT  state[4] = {0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476};
    UINT N = (byteCount + padAmountPlusSize) >> 6;
    UINT offset = 0;
    UINT NextEndState = bTwoRowsPadding ? N-2 : N-1;
    const BYTE* pCurrData = pData;
    for(UINT i = 0; i < N; i++, offset+=64, pCurrData+=64)
    {
        assert(byteCount - offset <= byteCount); // prefast doesn't understand this - no underflow will happen
        assert(byteCount < 64*i+65); // prefast doesn't understand this - no overflows will happen in any memcpy below
        assert(byteCount < leftOver+64*i+9); 
        assert(byteCount < leftOver+64*i+1); 
        UINT x[16];
        const UINT* pX;
        if( i == NextEndState )
        {
            if( !bTwoRowsPadding && i == N-1 )
            {
                UINT remainder = byteCount - offset;
                memcpy(x,pCurrData, remainder); // could copy nothing
                memcpy((BYTE*)x + remainder, padding, padAmount);
                x[14] = byteCount << 3;  // sizepad lo
                x[15] = 0; // sizepad hi
            }
            else if( bTwoRowsPadding )
            {
                if( i == N-2 )
                {
                    UINT remainder = byteCount - offset;
                    memcpy(x,pCurrData, remainder); 
                    memcpy((BYTE*)x + remainder, padding, padAmount-56);
                    NextEndState = N-1;
                }
                else if( i == N-1 )
                {
                    memcpy(x, padding + padAmount-56, 56);
                    x[14] = byteCount << 3;  // sizepad lo
                    x[15] = 0; // sizepad hi
                }
            }
            pX = x;
        }
        else
        {
            pX = (const UINT*)pCurrData;
        }

        UINT a = state[0];
        UINT b = state[1];
        UINT c = state[2];
        UINT d = state[3];

         /* Round 1 */
        FF( a, b, c, d, pX[ 0], S11, 0xd76aa478 ); /* 1 */
        FF( d, a, b, c, pX[ 1], S12, 0xe8c7b756 ); /* 2 */
        FF( c, d, a, b, pX[ 2], S13, 0x242070db ); /* 3 */
        FF( b, c, d, a, pX[ 3], S14, 0xc1bdceee ); /* 4 */
        FF( a, b, c, d, pX[ 4], S11, 0xf57c0faf ); /* 5 */
        FF( d, a, b, c, pX[ 5], S12, 0x4787c62a ); /* 6 */
        FF( c, d, a, b, pX[ 6], S13, 0xa8304613 ); /* 7 */
        FF( b, c, d, a, pX[ 7], S14, 0xfd469501 ); /* 8 */
        FF( a, b, c, d, pX[ 8], S11, 0x698098d8 ); /* 9 */
        FF( d, a, b, c, pX[ 9], S12, 0x8b44f7af ); /* 10 */
        FF( c, d, a, b, pX[10], S13, 0xffff5bb1 ); /* 11 */
        FF( b, c, d, a, pX[11], S14, 0x895cd7be ); /* 12 */
        FF( a, b, c, d, pX[12], S11, 0x6b901122 ); /* 13 */
        FF( d, a, b, c, pX[13], S12, 0xfd987193 ); /* 14 */
        FF( c, d, a, b, pX[14], S13, 0xa679438e ); /* 15 */
        FF( b, c, d, a, pX[15], S14, 0x49b40821 ); /* 16 */

        /* Round 2 */
        GG( a, b, c, d, pX[ 1], S21, 0xf61e2562 ); /* 17 */
        GG( d, a, b, c, pX[ 6], S22, 0xc040b340 ); /* 18 */
        GG( c, d, a, b, pX[11], S23, 0x265e5a51 ); /* 19 */
        GG( b, c, d, a, pX[ 0], S24, 0xe9b6c7aa ); /* 20 */
        GG( a, b, c, d, pX[ 5], S21, 0xd62f105d ); /* 21 */
        GG( d, a, b, c, pX[10], S22, 0x2441453 ); /* 22 */
        GG( c, d, a, b, pX[15], S23, 0xd8a1e681 ); /* 23 */
        GG( b, c, d, a, pX[ 4], S24, 0xe7d3fbc8 ); /* 24 */
        GG( a, b, c, d, pX[ 9], S21, 0x21e1cde6 ); /* 25 */
        GG( d, a, b, c, pX[14], S22, 0xc33707d6 ); /* 26 */
        GG( c, d, a, b, pX[ 3], S23, 0xf4d50d87 ); /* 27 */
        GG( b, c, d, a, pX[ 8], S24, 0x455a14ed ); /* 28 */
        GG( a, b, c, d, pX[13], S21, 0xa9e3e905 ); /* 29 */
        GG( d, a, b, c, pX[ 2], S22, 0xfcefa3f8 ); /* 30 */
        GG( c, d, a, b, pX[ 7], S23, 0x676f02d9 ); /* 31 */
        GG( b, c, d, a, pX[12], S24, 0x8d2a4c8a ); /* 32 */

        /* Round 3 */
        HH( a, b, c, d, pX[ 5], S31, 0xfffa3942 ); /* 33 */
        HH( d, a, b, c, pX[ 8], S32, 0x8771f681 ); /* 34 */
        HH( c, d, a, b, pX[11], S33, 0x6d9d6122 ); /* 35 */
        HH( b, c, d, a, pX[14], S34, 0xfde5380c ); /* 36 */
        HH( a, b, c, d, pX[ 1], S31, 0xa4beea44 ); /* 37 */
        HH( d, a, b, c, pX[ 4], S32, 0x4bdecfa9 ); /* 38 */
        HH( c, d, a, b, pX[ 7], S33, 0xf6bb4b60 ); /* 39 */
        HH( b, c, d, a, pX[10], S34, 0xbebfbc70 ); /* 40 */
        HH( a, b, c, d, pX[13], S31, 0x289b7ec6 ); /* 41 */
        HH( d, a, b, c, pX[ 0], S32, 0xeaa127fa ); /* 42 */
        HH( c, d, a, b, pX[ 3], S33, 0xd4ef3085 ); /* 43 */
        HH( b, c, d, a, pX[ 6], S34,  0x4881d05 ); /* 44 */
        HH( a, b, c, d, pX[ 9], S31, 0xd9d4d039 ); /* 45 */
        HH( d, a, b, c, pX[12], S32, 0xe6db99e5 ); /* 46 */
        HH( c, d, a, b, pX[15], S33, 0x1fa27cf8 ); /* 47 */
        HH( b, c, d, a, pX[ 2], S34, 0xc4ac5665 ); /* 48 */

        /* Round 4 */
        II( a, b, c, d, pX[ 0], S41, 0xf4292244 ); /* 49 */
        II( d, a, b, c, pX[ 7], S42, 0x432aff97 ); /* 50 */
        II( c, d, a, b, pX[14], S43, 0xab9423a7 ); /* 51 */
        II( b, c, d, a, pX[ 5], S44, 0xfc93a039 ); /* 52 */
        II( a, b, c, d, pX[12], S41, 0x655b59c3 ); /* 53 */
        II( d, a, b, c, pX[ 3], S42, 0x8f0ccc92 ); /* 54 */
        II( c, d, a, b, pX[10], S43, 0xffeff47d ); /* 55 */
        II( b, c, d, a, pX[ 1], S44, 0x85845dd1 ); /* 56 */
        II( a, b, c, d, pX[ 8], S41, 0x6fa87e4f ); /* 57 */
        II( d, a, b, c, pX[15], S42, 0xfe2ce6e0 ); /* 58 */
        II( c, d, a, b, pX[ 6], S43, 0xa3014314 ); /* 59 */
        II( b, c, d, a, pX[13], S44, 0x4e0811a1 ); /* 60 */
        II( a, b, c, d, pX[ 4], S41, 0xf7537e82 ); /* 61 */
        II( d, a, b, c, pX[11], S42, 0xbd3af235 ); /* 62 */
        II( c, d, a, b, pX[ 2], S43, 0x2ad7d2bb ); /* 63 */
        II( b, c, d, a, pX[ 9], S44, 0xeb86d391 ); /* 64 */
        
        state[0] += a;
        state[1] += b;
        state[2] += c;
        state[3] += d;
    }

    memcpy(pOutHash,state,16);
}

```

### Retail Hash Diffs

This is a diff that applies to the original MD5 implementation to produce the
retail hash algorithm.

```diff
--- MD5.c	2024-03-06 11:06:55.242457994 -0600
+++ Retail.c	2024-03-06 11:07:12.502457929 -0600
@@ -1,7 +1,7 @@
 // **************************************************************************************
 // **** DO NOT USE THESE ROUTINES TO PROVIDE FUNCTIONALITY THAT NEEDS TO BE SECURE!!! ***
 // **************************************************************************************
-void ComputeM_D_5Hash( const BYTE* pData, UINT byteCount, BYTE* pOutHash )
+void ComputeHashRetail( const BYTE* pData, UINT byteCount, BYTE* pOutHash )
 {
     UINT leftOver = byteCount & 0x3f;
     UINT padAmount;
@@ -23,10 +23,6 @@
     const BYTE* pCurrData = pData;
     for(UINT i = 0; i < N; i++, offset+=64, pCurrData+=64)
     {
-        assert(byteCount - offset <= byteCount); // prefast doesn't understand this - no underflow will happen
-        assert(byteCount < 64*i+65); // prefast doesn't understand this - no overflows will happen in any memcpy below
-        assert(byteCount < leftOver+64*i+9); 
-        assert(byteCount < leftOver+64*i+1); 
         UINT x[16];
         const UINT* pX;
         if( i == NextEndState )
@@ -34,31 +30,38 @@
             if( !bTwoRowsPadding && i == N-1 )
             {
                 UINT remainder = byteCount - offset;
-                memcpy(x,pCurrData, remainder); // could copy nothing
-                memcpy((BYTE*)x + remainder, padding, padAmount);
-                x[14] = byteCount << 3;  // sizepad lo
-                x[15] = 0; // sizepad hi
+                x[0] = byteCount << 3;  
+
+                assert(byteCount - offset <= byteCount); // check for underflow
+                assert(pCurrData + remainder == pData + byteCount);
+                memcpy((BYTE*)x+4,pCurrData, remainder); // could copy nothing
+                memcpy((BYTE*)x+4 + remainder, padding, padAmount);
+                x[15] = 1 | (byteCount << 1); 
             }
             else if( bTwoRowsPadding )
             {
                 if( i == N-2 )
                 {
                     UINT remainder = byteCount - offset;
-                    memcpy(x,pCurrData, remainder); 
+
+                    assert(byteCount - offset <= byteCount); // check for underflow
+                    assert(pCurrData + remainder == pData + byteCount);
+                    memcpy(x,pCurrData, remainder);
                     memcpy((BYTE*)x + remainder, padding, padAmount-56);
                     NextEndState = N-1;
                 }
                 else if( i == N-1 )
                 {
-                    memcpy(x, padding + padAmount-56, 56);
-                    x[14] = byteCount << 3;  // sizepad lo
-                    x[15] = 0; // sizepad hi
+                    x[0] = byteCount << 3;  
+                    memcpy((BYTE*)x+4, padding + padAmount-56, 56);
+                    x[15] = 1 | (byteCount << 1); 
                 }
             }
             pX = x;
         }
         else
         {
+            assert(pCurrData + 64 <= pData + byteCount);
             pX = (const UINT*)pCurrData;
         }

```

### Debug Hash Diff

This is a diff that applies to the original MD5 implementation to produce the
debug hash algorithm. Shaders hashed with the debug hash are only allowed to run
if the debug layer is enabled.

For example, GPU-based validation may patch shader binaries to inject validation
code and then apply the debug hash to make the shader only when the debug layer
is enabled.

```diff
--- MD5.c	2024-03-06 11:06:55.242457994 -0600
+++ Debug.c	2024-03-06 11:07:40.042457409 -0600
@@ -1,7 +1,7 @@
 // **************************************************************************************
 // **** DO NOT USE THESE ROUTINES TO PROVIDE FUNCTIONALITY THAT NEEDS TO BE SECURE!!! ***
 // **************************************************************************************
-void ComputeM_D_5Hash( const BYTE* pData, UINT byteCount, BYTE* pOutHash )
+void ComputeHashDebug( const BYTE* pData, UINT byteCount, BYTE* pOutHash )
 {
     UINT leftOver = byteCount & 0x3f;
     UINT padAmount;
@@ -23,10 +23,6 @@
     const BYTE* pCurrData = pData;
     for(UINT i = 0; i < N; i++, offset+=64, pCurrData+=64)
     {
-        assert(byteCount - offset <= byteCount); // prefast doesn't understand this - no underflow will happen
-        assert(byteCount < 64*i+65); // prefast doesn't understand this - no overflows will happen in any memcpy below
-        assert(byteCount < leftOver+64*i+9); 
-        assert(byteCount < leftOver+64*i+1); 
         UINT x[16];
         const UINT* pX;
         if( i == NextEndState )
@@ -34,31 +30,37 @@
             if( !bTwoRowsPadding && i == N-1 )
             {
                 UINT remainder = byteCount - offset;
-                memcpy(x,pCurrData, remainder); // could copy nothing
-                memcpy((BYTE*)x + remainder, padding, padAmount);
-                x[14] = byteCount << 3;  // sizepad lo
-                x[15] = 0; // sizepad hi
+                x[0] = byteCount << 4 | 0xf;  
+
+                assert(byteCount - offset <= byteCount); // check for underflow
+                assert(pCurrData + remainder == pData + byteCount);
+                memcpy((BYTE*)x+4,pCurrData, remainder); // could copy nothing
+                memcpy((BYTE*)x+4 + remainder, padding, padAmount);
+                x[15] = (byteCount << 2) | 0x10000000; 
             }
             else if( bTwoRowsPadding )
             {
                 if( i == N-2 )
                 {
                     UINT remainder = byteCount - offset;
-                    memcpy(x,pCurrData, remainder); 
+                    assert(byteCount - offset <= byteCount); // check for underflow
+                    assert(pCurrData + remainder == pData + byteCount);
+                    memcpy(x,pCurrData, remainder);
                     memcpy((BYTE*)x + remainder, padding, padAmount-56);
                     NextEndState = N-1;
                 }
                 else if( i == N-1 )
                 {
-                    memcpy(x, padding + padAmount-56, 56);
-                    x[14] = byteCount << 3;  // sizepad lo
-                    x[15] = 0; // sizepad hi
+                    x[0] = byteCount << 4 | 0xf;
+                    memcpy((BYTE*)x+4, padding + padAmount-56, 56);
+                    x[15] = (byteCount << 2) | 0x10000000;
                 }
             }
             pX = x;
         }
         else
         {
+            assert(pCurrData + 64 <= pData + byteCount);
             pX = (const UINT*)pCurrData;
         }

```

## Appendix 2: References

<h3 id="renderdoc-source"></h3>
1. Karlsson, Baldur. "RenderDoc," GitHub, accessed March 5, 2024. https://github.com/baldurk/renderdoc/blob/v1.x/renderdoc/driver/shaders/dxbc/dxbc_container.cpp#L891.

<h3 id="hexops-source"></h3>
2. Gutekanst, Stephen. "hexops/DirectXShaderCompiler," GitHub, accessed March 5, 2024. https://github.com/hexops/DirectXShaderCompiler/commit/7a0138d6eab5ce712e6dc70d3dc200eb2193574f.

<h3 id="hexops-devlog"></h3>
3. "Building the DirectX shader compiler better than Microsoft?," HexOps' devlog (blog), February 9, 2024. https://devlog.hexops.com/2024/building-the-directx-shader-compiler-better-than-microsoft/.

<h3 id="macos-builds"></h3>
4. Malyshau, Dzmitry. "Binary release artifacts for Linux/macOS," GitHub, accessed March 5, 2024. https://github.com/microsoft/DirectXShaderCompiler/issues/3686.

<h3 id="rfc1321"></h3>
5. The MD5 Message-Digest Algorithm. R. Rivest. April 1992. (Format: TXT, HTML) (Updated by RFC6151) (Status: INFORMATIONAL) (DOI:10.17487/RFC1321) 


<!-- {% endraw %} -->
