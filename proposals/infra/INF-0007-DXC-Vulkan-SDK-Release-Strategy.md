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

We automate this as a single pipeline that prepares a release candidate, validates
it, and publishes it as a build artifact for the SDK builders to consume. We
capture the dependencies a candidate is built against in a checked-in
`known_good.json` file, which is the single source of truth for which SPIRV-Headers
and SPIRV-Tools revisions we ship. The pipeline keeps that file current
automatically when a new release branch is cut, so candidates track the latest
SPIRV changes without a manual submodule bump.

### Pipeline

The pipeline has two triggers. Creating a `release/vulkan/<version>` branch starts
it automatically; it can also be started manually against an existing branch. The
trigger only affects how the SPIRV dependencies are resolved (step 1); the
remaining steps are identical. It performs the following steps:

1. **Update dependencies.** We take SPIRV-Headers and SPIRV-Tools to the commits
   recorded in `known_good.json`. When a `release/vulkan/<version>` branch is
   created we first advance `known_good.json` to the latest upstream commit of
   each dependency, so a freshly cut candidate always picks up the most recent
   SPIRV changes. On a manual run this update is optional and off by default: we
   use the commits already recorded in `known_good.json` unchanged, so a specific
   candidate can be reproduced or re-tested, unless the run asks for a refresh. In
   every case we write the resolved commits back to `known_good.json` and record
   them in the manifest, which keeps the build deterministic and the choice of
   revisions reviewable.

2. **Build.** We configure and build DXC with SPIRV code generation and the SPIRV
   tests enabled, together with the SPIRV-Tools validator (`spirv-val`) that we use
   to independently check the generated SPIRV. A build failure is fatal — there is
   no release candidate without a binary.

3. **Test.** After a successful build, we run the SPIRV tests using all of the
   testing tools the DXC repo provides — the lit tests, the TAEF tests, and the
   googletest unit tests — and we additionally validate the SPIRV the binary emits
   with `spirv-val`. All of these run against that single build, on the worker that
   produced it, and we run every SPIRV test regardless of which tool hosts it so
   that "the SPIRV tests" means the complete set rather than one tool's subset.

4. **Publish.** We publish the DXC binary, a machine-readable manifest, and the
   per-tool test reports as a single artifact, named `dxc_rc_<version>` after the
   SDK version the release branch targets, for downstream consumption.

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

The manifest is the handoff to the SDK builders: it is the automated replacement
for manually communicating the commit identifiers.

### Release readiness

The following must be true and validated for a release candidate to be considered
ready for the Vulkan SDK.

* It builds against the SPIRV-Headers and SPIRV-Tools commits recorded in
  `known_good.json`.
* Every SPIRV testing tool passes, and the SPIRV the binary emits validates under
  `spirv-val`.
* The manifest records the result, with `validated` set to `true`.

The `validated` flag is the single, machine-readable gate. An SDK builder consumes
a candidate only when it is `true`.

### Key decisions

* **Determinism through `known_good.json`.** Whatever revisions a run resolves —
  the recorded commits or a fresh upstream bump — we write back to
  `known_good.json`, so every candidate is reproducible from that file alone and
  the choice of SPIRV revisions stays an explicit, reviewable record rather than a
  moving branch tip.

* **Dependency refresh is tied to the trigger.** Cutting a release branch
  refreshes the SPIRV dependencies to the latest upstream commits automatically,
  so new candidates track upstream without a manual bump. Manual runs instead
  default to the recorded commits — so any candidate can be reproduced or
  re-tested exactly — and can opt into a refresh when wanted. The recorded
  `known_good.json` keeps both paths auditable.

* **Test failures do not block publication.** Only build failures stop the
  pipeline. We record test failures in the manifest and surface them through the
  `validated` flag, but still publish the candidate. The decision to release a
  candidate rests with the team making the release, not with the CI/CD tooling:
  the pipeline reports the results, and the team gates on `validated` when deciding
  whether a candidate is acceptable.

* **A single build feeds every test tool.** DXC's SPIRV coverage is spread across
  multiple testing tools. The build is the expensive step, and CMake's outputs are
  tied to the worker that produced them, so we run all of the tools against that
  one build on the same worker rather than distributing them across runners. Being
  otherwise independent, they can be run concurrently on that worker.

* **The handoff goes through the manifest.** The handoff to the SDK builders and
  the readiness decision are both driven by the manifest, so the integration does
  not depend on out-of-band communication of commit identifiers.

## Detailed design

### Changed behavior

This proposal adds release automation around DXC and does not change the
compiler's behavior or any of its interfaces. The only repository additions are
the `known_good.json` dependency pin, the pipeline definition, and the helper
scripts that drive build, test, and validation.

### How this is tested

The pipeline is self-validating: its test step is the regression gate for SPIRV
generation against the pinned dependencies, covering every SPIRV testing tool plus
an independent `spirv-val` check of the SPIRV the binary emits. The
`validated` flag in the manifest is the single signal both humans and downstream
automation read.

### Resources

The pipeline requires CI capacity for a DXC build plus the SPIRV test run on the
platform DXC ships from. No additional hardware or human resources are required,
and no per-release manual coordination is expected beyond reviewing a
`known_good.json` update.
