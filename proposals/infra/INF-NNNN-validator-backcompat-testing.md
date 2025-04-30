<!-- {% raw %} -->

# Feature name

## Instructions

* Proposal: [INF-NNNN](INF-NNNN-validator-backcompat-testing.md)
* Author(s): [Damyan Pepper](https://github.com/damyanp)
* Sponsor: [Damyan Pepper](https://github.com/damyanp)
* Status: **Under Consideration**
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
to use. DXC will also be modified to check for a new environment variable,
`DXC_DXIL_DLL_PATH`, that also specifies the full path to the dll.  Example
path: `c:\dxc\build\old-releases\1.7.123\bin\x64\dxil.dll`.

The command-line option takes precedance over the environment variable. Setting
the path to an empty string forces the internal validator.

If a dll path is specified and isn't found then DXC will fail with an error.

Note that the environment variable is used for both API as well as command-line
invocation of the compiler.

### Invoking the tests

The tests are invoked via `add_custom_command`, using `cmake -E env` to set the
`DXC_DXIL_DLL_PATH` variable.






## Acknowledgments (Optional)

* [Josh Batista](https://github.com/bob80905)
* [Tex Riddell](https://github.com/tex3d)
* [Chris Bieneman](https://github.com/llvm-beanz)

<!-- {% endraw %} -->
