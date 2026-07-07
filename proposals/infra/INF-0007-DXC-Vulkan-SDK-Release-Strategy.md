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

Currently, DXC releases on NuGet and GitHub. For Windows, DXC is consumed internally through Microsoft's VPack package management system. There is
infrastructure in place to make sure those releases are happening. The Vulkan SDK
will not modify those releases, it will just append to them.

A Vulkan SDK release should start with LunarG reaching out to the HLSL team, informing them of the
SPIRV-Headers and SPIRV-Tools commits that shall be used to create a release from. From that point
onwards, the Vulkan SDK release is just a process used to build and validate that a
DXC binary is generating valid and correct SPIRV from those submodules.

Validation is done through testing, which is divided into 2 types:
- **Unit Testing**: The DXC codebase contains a series of lit, TAEF and googletests.
- **Functional Tests**: The offload-test repository inside the LLVM org contains the
functional tests built by the HLSL team to validate clang and DXC generated code.

In order for a release candidate to be considered valid, all tests should pass.

Once a valid candidate is reached, the commit that generated the candidate should
be tagged and sent back to LunarG, who will be responsible for actually building, packaging
and shipping the binary that goes into the Vulkan SDK.

### Submodule Management

The HLSL team will implement automation to make sure the SPIRV-Headers and SPIRV-Tools
submodules stay up to date. This will allow issues related to such submodules to be detected
earlier than an actual release date. The details of such automation are not within
the scope of this release.
