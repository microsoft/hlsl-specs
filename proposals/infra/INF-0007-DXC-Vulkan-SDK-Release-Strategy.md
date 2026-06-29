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
locked down. The build, submodule-update, report, and release pipelines are then pointed at
the new branch so that subsequent builds run against it.

Submodules are not otherwise part of this process. A submodule stays at whatever commit it
is already set to; advancing SPIRV-Headers and SPIRV-Tools is a manual step, done the same
way on main and on release branches — there is no automatic update. The submodule-update
pipeline updates the submodules on the internal branch, which is how changes from GitHub
are picked up.

The release builds run from those branches and are marked for retention. The build and
report pipelines that run here are what we today treat as the validation that gates the
release. Once the builds pass, the artifacts are published: the GitHub release is drafted
and published, the NuGet package is uploaded, the Windows and DirectX Vpacks are updated,
the VCPKG mapping is updated, and the new compiler is registered in Compiler Explorer
(Godbolt).

### Where the Vulkan SDK fits

The Vulkan SDK does not get its own binaries. It ships the same DXC release described
above; there is no separate build artifact for it. What the SDK does add is a handful of
optional stages in the nightly build, created to accommodate the release — mainly running
the offload-tests against the build (see [Validation](#validation)).

The other difference is which SPIRV-Headers and SPIRV-Tools commits the release is built
against: for the Vulkan SDK, the submodules are advanced to the specific commits LunarG
specifies for that SDK before the release branch is built. This is a deliberate, manual
submodule update — the same kind of update already done on main — the only difference being
that the target commits come from LunarG rather than being chosen by us. It is worth keeping
two cases distinct:

* Continuous integration builds against the latest SPIRV-Headers and SPIRV-Tools, so
  regressions against upstream are found early. This is independent of any release.
* A Vulkan SDK release is built against the SPIRV commits LunarG gives us. We do not choose
  them; we update the submodules to them and validate DXC against them.

Concretely this adds one step to preparing the release branch — update the SPIRV submodules
to the LunarG-specified commits — and one step to publishing — submit the validated release
to LunarG for inclusion in the SDK. Everything else in the existing process is unchanged.

### Validation

A release is included in the Vulkan SDK only after it passes validation against the
LunarG-specified SPIRV commits. That validation is the full DXC test suite — everything we
already run today for a release — plus the offload tests run against lavapipe. The Vulkan
SDK is therefore a superset of the existing release validation, not a separate process:
the same tests we already run, on the submodules set to the LunarG-specified commits, with
the lavapipe offload tests added. 

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
