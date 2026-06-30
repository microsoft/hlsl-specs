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

DXC is included in the Vulkan SDK. Before each SDK release, the DXC submodule
references (SPIRV-Headers, SPIRV-Tools) need to be updated and the product needs
to be tested. This process has previously been mostly performed manually. This
document details the requirements for ensuring DXC is ready for inclusion in the
Vulkan SDK and proposes the changes required in order to satisfy them.

## Motivation

SPIRV-Headers and SPIRV-Tools need to be kept up to date so that the most recent
SPIRV features are available in DXC. We need to verify that DXC is generating
valid SPIRV code and that there are no regressions. The process needs to be
documented and automated enough so that it does not rely on individuals with
special knowledge. Additionally, we want to align the version included in the
Vulkan SDK with a formal DXC release so that it matches up with GitHub and NuGet
releases and can be ingested into Godbolt.

## Proposed solution

This proposal describes how the SPIRV dependencies are kept current, which dependency
versions a release is built against, when a build is considered ready, and how the Vulkan
SDK release relates to the other DXC releases. 

The guiding principle is that the Vulkan SDK is not a new release process. It is an
additional consumer of the existing DXC release, with one extra constraint: which
SPIRV-Headers and SPIRV-Tools commits the release is built against. The sections below
first summarize how DXC releases work today, then describe where the Vulkan SDK fits.

### How DXC releases work today

DXC currently ships as a GitHub release, a NuGet package, and Windows/DirectX Vpacks. All
of these are produced from an internal Azure DevOps (ADO) release branch.

A release starts by preparing that branch: the DXC version is bumped, the release notes are
labelled, the branch is cut from main, the shader model is set, and the branch policies are
locked down. The build, report, and release pipelines are then pointed at the new branch so
that subsequent builds run against it.

Submodules are not otherwise part of this process. A submodule stays at whatever commit it
is already set to; advancing SPIRV-Headers and SPIRV-Tools is a manual, optional step, not
something the release does on its own. We assume here that the submodules are left as they
are unless they are deliberately updated.

The release builds run from those branches and are marked for retention. The build and
report pipelines that run here are what we today treat as the validation that gates the
release. Once the builds pass, the artifacts are published: the GitHub release is drafted
and published, the NuGet package is uploaded, the Windows and DirectX Vpacks are updated,
the VCPKG mapping is updated, and the new compiler is registered in Compiler Explorer
(Godbolt).

### Where the Vulkan SDK fits

DXC does not build or ship the Vulkan SDK binary. Our deliverable is a validated commit,
not an artifact: once a build passes validation, the commit is tagged as a release
candidate (RC) and that tag is reported to LunarG. LunarG build DXC from that tag and ship
the resulting binary as part of the Vulkan SDK.

The build we validate is the same one that validates every PR — there is no special Vulkan
SDK build. The only addition is a handful of optional stages, created to accommodate the
release — mainly running the offload-tests against the build (see [Validation](#validation)).

The other difference is which SPIRV-Headers and SPIRV-Tools commits the build is built against:
for the Vulkan SDK, the submodules are advanced to the specific commits LunarG specifies
for that SDK before the build is validated. This is a deliberate, manual submodule update. 

### Validation

A commit is tagged as a Vulkan SDK release candidate and reported to LunarG only after it
passes validation against the LunarG-specified SPIRV commits. That validation is the full 
DXC test suite — everything we already run today for a release — plus the offload tests 
run against lavapipe. 
