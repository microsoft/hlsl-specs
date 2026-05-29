---
title: "INF-0007 - DXC Vulkan SDK Release Strategy"
params:
  authors:
    - damyanp: Damyan Pepper
  sponsors:
    - damyanp: Damyan Pepper
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

TODO

<!-- Describe your solution to the problem. Provide examples and describe how
they work. Show how your solution is better than current workarounds: is it
cleaner, safer, or more efficient? -->


<!--

## Detailed design

_The detailed design is not required until the feature is under review._

This section should grow into a full specification that will provide enough
information for someone who isn't the proposal author to implement the feature.
It should also serve as the basis for documentation for the feature. Each
feature will need different levels of detail here, but some common things to
think through are:

* Is there any potential for changed behavior?
* Will this expose new interfaces that will have support burden?
* How will this proposal be tested?
* Does this require additional hardware/software/human resources?
* What documentation should be updated or authored?

## Alternatives considered (Optional)

If alternative solutions were considered, please provide a brief overview. This
section can also be populated based on conversations that occur during
reviewing.

## Acknowledgments (Optional)

Take a moment to acknowledge the contributions of people other than the author
and sponsor.


