---
title: "INF-0007 - DXC Vulkan SDK Release Strategy"
params:
  authors:
    - damyanp: Damyan Pepper
    - joaosaffran: João Saffran
  sponsors:
    - damyanp: Damyan Pepper
    - joaosaffran: João Saffran
  status: Under Consideration
---

* Impacted Projects: DXC

## Introduction

DXC is included in the Vulkan SDK. Before each SDK release, the DXC submodule references
(SPIRV-Headers and SPIRV-Tools) need to be updated and the product needs to be tested.
This has previously been done mostly by hand. This document describes the strategy for
ensuring DXC is ready for inclusion in the Vulkan SDK. It is concerned with the policy
for how we manage these releases, not with the details of how the tests are run.

## Motivation

SPIRV-Headers and SPIRV-Tools need to be kept up to date so that the most recent SPIRV
features are available in DXC. We need to verify that DXC generates valid SPIRV and that
there are no regressions. The process needs to be documented and automated enough that it
does not rely on individuals with special knowledge. We also want to align the version
included in the Vulkan SDK with a formal DXC release, so that it matches the GitHub and
NuGet releases and can be ingested into Godbolt.

## Proposed solution

This proposal describes how the SPIRV dependencies are kept current, which dependency
versions a release is built against, when a build is considered ready, and how the Vulkan
SDK release relates to the other DXC releases. 

The guiding principle is that the Vulkan SDK is not a new release process. It is an
additional consumer of the existing DXC release, with one extra constraint on which SPIRV
commits the build is pinned to. The sections below first summarize how DXC releases work
today, then describe where the Vulkan SDK fits.

### How DXC releases work today

DXC currently ships as a GitHub release, a NuGet package, and Windows/DirectX Vpacks. The
GitHub release is produced from a release branch in GitHub, while the NuGet package and the
Vpacks are produced from a release branch in Azure DevOps.

A release starts by preparing these release branches: the DXC version is bumped, the
release notes are labelled, the branch is cut from main, the shader model is set, and the
branch policies are locked down. The submodules are pinned on the branch at this point. The
build, submodule-update, report, and release pipelines are then pointed at the new branch
so that subsequent builds run against it.

The release builds run from those branches and are marked for retention. The build and
report pipelines that run here are what we today treat as the validation that gates the
release. Once the builds pass, the artifacts are published: the GitHub release is drafted
and published, the NuGet package is uploaded, the Windows and DirectX Vpacks are updated,
the VCPKG mapping is updated, and the new compiler is registered in Compiler Explorer
(Godbolt).

### Where the Vulkan SDK fits

The Vulkan SDK build is the same DXC release described above, with a single added
constraint: it is built against the specific SPIRV-Headers and SPIRV-Tools commits that
LunarG specifies for that SDK, rather than against whatever the branch happened to pin.
We keep the two pinning cases separate:

* Continuous integration builds against the latest SPIRV-Headers and SPIRV-Tools, so
  regressions against upstream are found early. This is independent of any release.
* A release is built against pinned SPIRV commits. For the Vulkan SDK those commits are
  the ones LunarG gives us; we do not choose them, we validate DXC against them.

Concretely this adds one decision to "Prepare the release branch" — pin the SPIRV
submodules to the LunarG-specified commits — and one step to "Publish" — submit the
validated build to LunarG for inclusion in the SDK. Everything else in the existing
process is unchanged.

### Validation

A build is included in the Vulkan SDK only after it passes validation against the
LunarG-specified SPIRV commits. That validation is the full DXC test suite — everything we
already run today for a release — plus the offload tests run against lavapipe. The Vulkan
SDK is therefore a superset of the existing release validation, not a separate process:
the same tests we already run, on the LunarG-pinned submodules, with the lavapipe offload
tests added. 

## Decisions and remaining actions

This strategy makes the Vulkan SDK fit the existing process rather than introduce a new
one. The decisions that follow from that, and the actions still outstanding, are below.

1. **Validation is unified.** The Vulkan SDK reuses the existing release validation rather
   than introducing a separate one. The only outstanding action is to write down, in one
   place, the validation currently run for the NuGet and Vpack releases so it can be confirmed sufficient for the Vulkan SDK. 

2. **The releases are aligned.** The Vulkan SDK version is a formal DXC release: the same
   artifact shipped to GitHub, NuGet, and Vpacks, built against the LunarG-specified SPIRV
   commits. 

3. **Broader submodule automation is out of scope.** CI keeping the SPIRV submodules
   current is enough for this proposal. 
