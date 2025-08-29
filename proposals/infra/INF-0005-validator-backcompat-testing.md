---
title: "INF-0005 - Validator Backwards Compatibility Testing"
params:
  authors:
    - damyanp: Damyan Pepper
  sponsors:
    - damyanp: Damyan Pepper
  status: Under Consideration
---
<!-- {% raw %} -->
 
* Impacted Project(s): DXC

## Introduction

We propose moving the DXC validator backwards compatability tests from a
private, internal, repo to the public one, cleaning up the mechanisms that
enable this as we go.

## Motivation

Currently, internal builds of DXC perform various tests that involve running DXC
against older versions of the validator (dxil.dll). This is to ensure that
modifications to DXC (including modifications to the validator) don't break
backwards compatability with previously released versions. In the past, the
validator was closed source and so these tests were run from internal builds.

We've recently [open sourced the validator](./INF-0004-validator-hashing.md) and
as part of this work we want to make DXC default to using the built-in,
"internal", validator rather than one loaded from a dll, and this breaks these
tests. 

While we're fixing these tests, we're going to take this opportunity to move the
back-compat testing into the public repo and simplify the infrastructure
required to run them.


## Proposed solution

### How it works currently

These tests only run for Windows x64 builds. The internal build pipeline runs
`mm test --validator-backcompat-all`. This script has a list of old dxil.dll
versions to test. The DLL's themselves are checked into the repo. Before running
each test the dxil.dll is copied into directory next to dxc.exe, with the
intention that this is the one that DXC will pick up. (Note: in the past we've
accidentally packaged up and released one of these old dxil.dll.)

The tests themselves are run via lit.

Most of the tests assume that the external validator is used, although a small
number explicitly set `-select-validator internal` so that when that test runs
it uses the internal validator - effectively making the test pointless in the
back compat suite.

There are also TAEF tests that invoke the compiler via the API. We need to
ensure that these continue to work.

### Proposed Changes

The tests run via binaries downloaded from github releases and are integrated
into the cmake build system so they can be run from a single target.


## Detailed design

These tests are integrated into the build system and can be invoked via a cmake
target.  eg `cmake --build . --target check-validator-backwards-compatability`.
This target is not run by default, since most developers won't want to download
the binaries and run these tests.


### Binaries

Rather than check the binaries in to source control, we can download them from
github.com as zip files. `ExternalProject_Add` can be used to do this.

### Specifying which DXIL.dll to use

The `-select-validator` option will be deprecated.  As this is not documented,
it should be ok to just remove it entirely.

A new option, `-dxil-dll-path`, can be used to specify the full path to dxil.dll
to use. Example path: `c:\dxc\build\old-releases\1.7.123\bin\x64\dxil.dll`.

Setting the path to an empty string forces the internal validator to be used.

If a dll path is specified and isn't found then the compiler will fail with an
error.

When invoked via dxc.exe, DXC will check for a new environment variable,
`DXC_DXIL_DLL_PATH`, that specifies the full path to the dll. The command-line
option takes precedance over the environment variable. This environment variable
is not used when invoking the compile via the API since this could be abused to
inject arbitrary DLLs into unsuspecting processes.

When an external validator is used a warning diagnostic is emitted. Since the
only expected use of this option is the backcompat tests, having this always
appear in the test logs should be helpful when diagnosing issues.  


### Invoking the tests

The tests are invoked via `add_custom_command`, using `cmake -E env` to set the
`DXC_DXIL_DLL_PATH` variable.

### New Tests

As well as testing old external validators, we also need to run the same set of
tests against current external validator.

This means we need to test:

* internal validator
* latest external validator
* previouslly released external validators

## Alternatives Considered

### Requirement for full path

We considered allowing relative paths to specify the dll. However, best practice
for loading DLLs is to use absolute paths and since in the expected scenarios
for this functionality we know exactly which DLL we want to use the decision was
made to require an absolute path to the DLL.


### Diagnostic when using External Validator

We considered that we should only show the diagnostic when the compiler is
invoked via dxc.exe and not when it is used via the API, on the basis that
emitting a warning when the API is doing something that the user explicitly
asked it to do is unusual. 

Another consideration was to only output the path to the validator in the case
that validation failed.

Since this API is only intended to be used scenarios for testing the compiler
itself, the decision was made to always emit it in order to help with debugging
via logs.



## Acknowledgments (Optional)

* [Josh Batista](https://github.com/bob80905)
* [Tex Riddell](https://github.com/tex3d)
* [Chris Bieneman](https://github.com/llvm-beanz)

<!-- {% endraw %} -->
