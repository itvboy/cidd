# CIDD 0.1 — Hackathon Report

**Meta Global AI Developer Hackathon 2026**  
**Track:** Indie Developer · Push the Frontier  
**Project:** Contract-Isolated Driven Development (CIDD)  
**Demonstration:** TaxiCat Mobile

> **The project grows. The worker's context doesn't.**

## Executive summary

CIDD is a contract-driven software generation engine powered by isolated LLM workers. Its central idea is to separate **deterministic governance** from **probabilistic code generation**. Rather than granting a coding agent access to the whole repository, CIDD supplies each worker with a bounded contract and its permitted dependencies, then handles staging, assembly, and validation outside the model.

For the hackathon, CIDD generated and assembled TaxiCat Mobile, a Flutter/Mapbox taxi application backed by a separate Go HTTP service. A Muse-Wonder-generated build passed Flutter static analysis and ran on an Android emulator. In a cross-implementation test, a passenger using a CIDD-generated Android app requested a ride, and a driver using an independently Muse-Code-generated Android app on another computer accepted, started, and completed that ride through the same backend.

This demonstrates feasibility and interoperability for the **tested ride workflow**. It does not establish universal first-pass correctness, automatic recovery, or an end-to-end cost advantage without normalized measurements.

## The problem

AI coding systems often operate with broad project context, tool access, and iterative repair loops. As a project expands, context management, repeatability, provenance, and generation cost become difficult to control.

CIDD tests a different architectural assumption:

> **The Contract Isolation Hypothesis:** Decoupling AI generation cost from project size by assigning each coding worker only the bounded context needed to implement one contract.

The hypothesis is not that smaller models are always more accurate. It is that a deterministic engine can **make each unit of work smaller and auditable**, while keeping model-generated code within a contract boundary.

## How CIDD works

```text
Human- or externally-authored Application Genome
                       |
                       v
              Validate and expand
                       |
                       v
               Sealed contract graph
                       |
                       v
              Deterministic scheduler
                       |
             +---------+---------+
             |         |         |
             v         v         v
          Worker A  Worker B  Worker C
             |         |         |
             v         v         v
          Source A  Source B  Source C
             +---------+---------+
                       |
                       v
                Source staging
                       |
                       v
            Flutter assembly/bootstrap
                       |
                       v
            Dependency + static analysis
                       |
                       v
               Runtime verification
```

**Worker boundaries:** No repository browsing, arbitrary file writes, shell execution, test execution, delegation, or autonomous control of the development workflow. The orchestrator owns those responsibilities. Genome authorship is outside the core CIDD 0.1 engine.

## Demonstration: TaxiCat

TaxiCat Mobile comprises **13 generated contracts** across four layers:

| Layer | Contracts |
| --- | ---: |
| Domain | 2 |
| Application | 7 |
| Infrastructure | 1 |
| Presentation | 3 |
| **Total** | **13** |

The generated mobile app provides role selection, a passenger interface, and a driver interface, including Mapbox-based maps and an HTTP connection to a separately running TaxiCat Server.

**Important boundary:** The CIDD TaxiCat template generates the mobile client. It does not automatically deploy the Go backend. Mapbox tokens, server reachability, and Android runtime configuration are required for a live demo.

## Recorded generation and validation results

The following figures were recorded during the November 4, 2026 experiments on the same sealed TaxiCat graph with `muse-wonder-1.0`. They represent **generation-stage** tokens, not total end-to-end project expenditure.

| Run / assembly label | Input tokens | Output tokens | Total tokens | Generation time | Initial analyzer result |
| --- | ---: | ---: | ---: | ---: | --- |
| v3 | 12,220 | 27,668 | **39,888** | 167 s | PASS |
| v4 | 12,220 | 32,106 | **44,326** | 201 s | FAIL — Mapbox GeoJSON argument type |
| v5 | 12,220 | 29,044 | **41,264** | 177 s | PASS |
| v6 | 12,220 | 31,434 | **43,654** | 212 s | FAIL under warning-fatal policy; PASS under warning-nonfatal policy |

A separate earlier Muse-Wonder generation used **40,933** generation tokens and took **179 seconds**, with a successful assembly after supplying the missing Flutter starter entry point. This earlier run is not included in the table above to preserve the v3–v6 labeling used in the experimental log.

### Interpreting the failures accurately

- **v4:** The model passed a `Map<String, dynamic>` to `GeoJsonSource.data`, which expected a string. Replacing `LineString(...).toJson()` with `jsonEncode(LineString(...).toJson())` resolved the reported error **manually**. The original CIDD assembly report remains FAIL.
- **v6:** Flutter Analyzer reported an unused private field (`unused_field`) in `presentation.DriverView`. Running `flutter analyze --no-pub --no-fatal-infos --no-fatal-warnings` returned exit code 0 while preserving the warning in its output. Reassembly with CIDD's updated nonfatal-warning policy returned Bootstrap PASS, Pub get PASS, Analyzer PASS, exit code 0, **without editing generated source**.
- **v5:** Passed Bootstrap, dependency resolution, and static analysis with no manual modification to generated contracts. The app was launched on an Android emulator, where the passenger map and backend connection were observed.

**Temperature caveat:** Later experiments were conducted after adding `temperature: 0.0` to the Meta provider request. The v5/v6 outcomes show that a temperature-zero setting does not guarantee warning-free generation. These few runs are **not** a controlled statistical proof that temperature causes higher reliability. Provider configuration, model response variability, and analyzer policy must all be disclosed when comparing runs.

## Selective regeneration: bounded work

A controlled micro-context experiment used a previously sealed 13-contract graph and changed one presentation contract, `presentation.RoleSelectionView`. Results:

| Metric | Observed |
| --- | ---: |
| Total contracts | 13 |
| Reused contracts | **12** |
| Regenerated contracts | **1** |
| Input tokens | **963** |
| Output tokens | **1,074** |
| Total tokens | **2,037** |

This demonstrates selective regeneration for the **tested, provenance-verified sealed graph**. It is not evidence that arbitrary application-wide Genome changes always trigger only one contract, or that total model cost remains constant with project size. Broader repeated experiments are needed.

For the complete method and boundaries, see [Micro-Context Regeneration Experiment](microcontext-experiment.md).

## Independent reference: Muse-Code

An independent Muse-Code implementation was generated from the TaxiCat Genome and launched in an Android emulator on a Mac. With a Mapbox token and a network-reachable TaxiCat Server, it displayed the maps and participated successfully in the ride workflow.

**Cross-implementation interoperability demonstration:**

1. **CIDD + Muse-Wonder** passenger client, running in an Android emulator on an MSI Windows laptop, requested a ride.
2. **Muse-Code** driver client, running in an Android emulator on a Mac, received the available ride.
3. The Muse-Code client accepted, started, and completed the ride using the shared Go HTTP backend.

This verifies **cross-client interoperability for one observed transaction**, not implementation equivalence or comprehensive feature parity.

A preliminary Muse-Code usage figure of roughly **3.09 million total tokens**, including approximately **2.85 million cached tokens**, was reported during the project. **Do not interpret this as a direct ratio against CIDD's 39–44k generation-token runs.** The capture boundaries, cached-token accounting, workflow stages, and repair effort differ. No normalized comparative cost or efficiency conclusion is claimed here.

### Fair-comparison protocol for future evaluation

A reproducible comparative study should hold constant: the exact Genome and requirements, expected feature set, backend/API, device target, model-access conditions, environment configuration, and functional acceptance tests. Capture prompt, completion, cached tokens, elapsed time, manual interventions, retries, compilation/analyzer results, and end-to-end runtime outcomes for both systems. Report stage-specific measurements separately from project-total measurements.

## What the prototype demonstrates

- A sealed contract graph can drive isolated LLM implementation of a nontrivial Flutter mobile client.
- Deterministic assembly and static analysis can verify the result without giving workers tool access.
- Per-contract progress, usage metrics, and run manifests make generation observable.
- Selective regeneration can avoid rebuilding unaffected contracts when provenance is compatible.
- Independently generated clients can interoperate through a shared HTTP API for the tested ride workflow.

## What it does not yet demonstrate

- Guaranteed first-pass compilation or warning-free code across repeated runs.
- Automatic repair of all analyzer failures or runtime defects.
- Fully automated deployment of the backend, Mapbox setup, or Android environment.
- A statistically validated improvement from temperature-zero sampling.
- A normalized end-to-end cost saving over Muse-Code.
- Bounded generation cost across arbitrary project sizes and Genome revisions.

**Distribution caveat:** In the recorded clean-template test, the TaxiCat template initially omitted `lib/main.dart`. A standard Flutter starter file had to be supplied for CIDD's bootstrap to recognize the project. The public template must be checked and corrected before claiming a one-command clean reproduction.

## Next steps

1. **Reproducible packaging:** Include the supported Flutter starter entry point in the TaxiCat template and add a regression test for `new-project`.
2. **Contract-local repair loop:** Map analyzer diagnostics to the owning contract, deliver narrow feedback, and selectively regenerate that contract without granting worker tool privileges.
3. **Verified API references:** Improve external dependency skills, especially Mapbox GeoJSON serialization and current SDK APIs.
4. **Expanded evaluation:** Repeat fixed-graph and controlled-change experiments with complete stage-level accounting, variance measurements, and functional acceptance tests.
5. **Optional front-end authoring:** Allow external AI architect tools to help author or revise a Genome, with CIDD retaining deterministic validation and generation governance.

## Reproducibility and documentation

- [README](../README.md) — installation, commands, prerequisites, and TaxiCat execution.
- [Micro-Context Regeneration Experiment](microcontext-experiment.md) — the controlled 12-reused / 1-generated result.
- [Architecture](ARCHITECTURE.md) — planned technical specification of boundaries, graph lifecycle, and validation.

**Artifacts worth retaining:** sealed graph fingerprints, source manifests, contract hashes, analyzer reports, full CLI transcripts, execution screenshots, API compatibility notes, and any Muse-Code usage reports with clear accounting boundaries. Sensitive tokens and API keys must not be committed.

---

> **CIDD doesn't make the model smarter. It makes the problem smaller.**

**Deterministic Governance, Probabilistic Generation.**





### TaxiCat — Comparative Benchmark

To evaluate CIDD's contract-isolated generation approach, we generated the same TaxiCat application using two different workflows: **CIDD + Muse-Wonder 1.0** and **Muse-Code + Muse-Wonder 1.0**.

Both implementations were successfully executed on Android and demonstrated interoperability through a shared Go backend.

The experiment examines token consumption, generation workflow, functional results, and measurement limitations.

**[Read the TaxiCat Comparative Benchmark](TAXICAT_BENCHMARK.md)** for the methodology, recorded metrics, and detailed findings.