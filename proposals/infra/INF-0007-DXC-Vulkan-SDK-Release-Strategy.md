---
title: "INF-0007 - DXC Vulkan SDK Release Strategy"
params:
  authors:
    - Damyan Pepper
    - João Saffran
  sponsors:
    - Damyan Pepper
    - João Saffran
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

The automation is a single pipeline that: prepares a release candidate; validates
it; and publishes it as a build artifact for further testing. The SDK builders 
do not consume that artifact; they are given the candidate's DXC commit, 
which the manifest records. The dependencies a candidate is built against are 
captured in a checked-in `known_good.json` file, which is the single source of 
truth for which SPIRV-Headers and SPIRV-Tools revisions are shipped.

### Pipeline

The pipeline has two triggers: Creating a `release/vulkan/<version>` branch; 
or manually in the github UI. When creating a new branch, SPIRV-Headers and 
SPIRV-Tools, will automatically update to the most recent commit. When 
triggering manually this step is optional. The pipelines performs the following
actions:

1. **Update dependencies (optional).** SPIRV-Headers and SPIRV-Tools are updated
   to the most common commit and such reference is updated in `known_good.json`.
   This step is executed automatically when creating a release branch, or it can
   be opted in when triggered manually.

2. **Build.** DXC is configured and built with SPIRV code generation and the SPIRV
   tests enabled, it also builds required test dependent tools, such as: `spirv-val`.

3. **Test.** All tests available for SPIRV in DXC repo are run in this stage. 
   This includes: lit tests, google tests and TAEF tests. The generated code is 
   also validated by `spirv-val`. This stage is non blocking, meaning a release
   candidate will be published in the pipeline artifact section even if test fails.
   This is done to not block further testing that might be unaffected by such tests failures.


4. **Publish.** The DXC binary, a machine-readable manifest, and the per-tool test
   reports are published as a single artifact, named `dxc_rc_<version>`.

### Release Manifest

The manifest records the DXC commit, the SPIRV-Headers and SPIRV-Tools commits the
candidate was built against, the per-tool results, and a single `validated` flag
that is true only when every tool passed:

```json
{
  "dxc_commit": "<sha>",
  "spirv_dependencies": {
    "SPIRV-Headers": "<sha>",
    "SPIRV-Tools": "<sha>"
  },
  "test_suites": [
    { "name": "spirv-unit", "passed": 105, "failed": 0 },
    { "name": "spirv-codegen", "passed": 1564, "failed": 0 },
    { "name": "spirv-taef", "passed": 1, "failed": 0 },
    { "name": "spirv-val", "passed": 6, "failed": 0 }
  ],
  "validated": true
}
```

### Release readiness

The following must be true and validated for a release candidate to be considered
ready for the Vulkan SDK.

* It builds against the SPIRV-Headers and SPIRV-Tools commits recorded in
  `known_good.json`.
* Every SPIRV testing tool passes, and the SPIRV the binary emits validates under
  `spirv-val`.
* The manifest records the result, with `validated` set to `true`.
