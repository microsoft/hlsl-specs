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

DXC releases on NuGet, GitHub, and via the Windows SDK. For Windows, DXC is consumed internally through Microsoft's VPack package management system. These channels already have established release processes and automation. LunarG owns the Vulkan SDK and its release. The HLSL team's role is to *qualify* the build of DXC from a specific commit by validating against the specified SPIRV submodules and tag it, so LunarG can include it in a Vulkan SDK release. This is additive and does not change the existing DXC release channels.

DXC Vulkan SDK qualification begins when LunarG notifies the HLSL team of the [SPIRV-Headers](https://github.com/KhronosGroup/SPIRV-Headers) and [SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) commits to build against. The HLSL team builds DXC against those submodules and validates that it generates valid, correct SPIRV. The DXC commit used to produce a validated binary is a *release candidate*.

Validation is done through testing, which is divided into 2 types:
- **Unit Testing**: The DXC codebase contains a series of lit, TAEF and googletests.
- **Functional Tests**: The [offload-test repository](https://github.com/llvm/offload-test-suite/)
  inside the LLVM org contains the functional tests built by the HLSL team to validate clang
  and DXC generated code.

In order for a release candidate to be considered valid, all tests should pass.
In case of test failures, the person responsible for the release, along side other 
members of HLSL team, have the autonomy to classify a release candidate valid,
after determining that shipping with the failed tests is acceptable.

Once a valid candidate is reached, the commit that generated the candidate should
be tagged and sent back to LunarG, who will be responsible for actually building, packaging
and shipping the DXC binary that goes into the Vulkan SDK.

### Submodule Management

The HLSL team will implement automation to make sure the SPIRV-Headers and SPIRV-Tools
submodules stay up to date. This will allow issues related to such submodules to be detected
before an official qualification run. The details of such automation are not within
the scope of this release strategy.
