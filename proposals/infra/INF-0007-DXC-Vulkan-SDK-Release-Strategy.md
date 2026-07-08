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

Currently, DXC releases through GitHub, NuGet, and via the Windows SDK. Within Windows, 
DXC is consumed through Microsoft's VPack package management system. All of these release 
channels already have established release processes and automation. The Vulkan SDK release 
process is additive and does not modify or replace the existing DXC release channels. 
Instead, it validates a DXC release candidate and produces an additional distribution for 
inclusion in the Vulkan SDK.

A Vulkan SDK release should start with LunarG reaching out to the HLSL team, informing them of the
[SPIRV-Headers](https://github.com/KhronosGroup/Spirv-headers) and [SPIRV-Tools](https://github.com/KhronosGroup/Spirv-tools) 
commits that shall be used to create a release from. From that point onwards, the Vulkan SDK release is 
just a process used to build and validate that a DXC binary is generating valid and correct SPIRV 
from those submodules. The commit within the DXC repository used to generate such valid binary
will be considered as a release candidate.

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
and shipping the binary that goes into the Vulkan SDK.

### Submodule Management

The HLSL team will implement automation to make sure the SPIRV-Headers and SPIRV-Tools
submodules stay up to date. This will allow issues related to such submodules to be detected
earlier than an actual release date. The details of such automation are not within
the scope of this release.
