# CIDD 0.1 — Architecture

**Contract-Isolated Driven Development**  
*A contract-driven software generation engine powered by isolated LLM workers.*

> **The project grows. The worker's context doesn't.**

**Status:** Experimental prototype, November 2026. This document describes architectural intent, demonstrated capabilities, and known boundaries. It is not a claim of general-purpose autonomous software development.

## 1. Architectural thesis

CIDD separates **deterministic governance** from **probabilistic generation**. A conventional AI coding agent may inspect a repository, decide what to edit, invoke tools, and iterate over a broad working context. CIDD instead assigns bounded coding tasks to non-agentic LLM workers, with the engine controlling their inputs, outputs, ordering, artifacts, and validation.

The primary abstraction is a **contract**, not a prompt containing the entire codebase. Project scope can increase without requiring every worker to receive all project source code. That is a design objective, not yet a universal complexity bound.

> **CIDD doesn't make the model smarter. It makes the problem smaller.**

## 2. Trust and responsibility boundaries

| Component | Responsibility | Must not do |
| --- | --- | --- |
| Application Genome | Defines intended application structure and requirements | Act as generated application source |
| Genome validation / graph builder | Check input and produce a structured contract dependency graph | Treat unsealed or incompatible graphs as interchangeable |
| Sealed contract graph | Provide the generation plan and contract specifications | Give workers implicit access to the full repository |
| Deterministic orchestrator | Schedule contracts, supply bounded context, stage outputs, record evidence | Delegate workflow control to the model |
| Isolated LLM worker | Produce source code for one assigned contract | Browse files, execute commands/tests, edit arbitrary files, call tools, or coordinate workers |
| Sanitizer / staging | Normalize and store model output under controlled paths | Claim successful compilation merely because code was generated |
| Assembler / bootstrap | Integrate generated files into a supported project template | Silently overwrite arbitrary project entry points |
| External validators | Resolve dependencies and perform static analysis | Prove full runtime behavior from static checks alone |

**Worker isolation is a capability boundary, not a claim that models cannot make mistakes.** The model is given a task-specific contract and allowed dependencies; it is not granted execution or repository tools. File I/O and validation remain engine operations.

## 3. Pipeline

```text
Externally authored Genome
        |
        v
   cidd validate
        |
        v
   cidd build-graph -----> sealed contract graph + fingerprint
        |                              |
        |                              v
        +------------------------> cidd generate
                                       |
                          +------------+------------+
                          |            |            |
                      Contract A   Contract B   Contract C
                       worker       worker       worker
                          |            |            |
                          +------------+------------+
                                       |
                              staged source +
                              per-run manifest
                                       |
                                       v
                                cidd assemble
                                       |
                       project template + bootstrap
                                       |
                                       v
                              Flutter pub get
                                       |
                                       v
                              Flutter Analyzer
                                       |
                                       v
                            runtime tests (external)
```

The diagram is conceptual: it does **not** imply that every phase or every worker runs concurrently. In the demonstrated TaxiCat full-generation loop, each contract was processed and reported as it completed.

### 3.1 Genome: application intent

The Genome is the structured input from which contracts are derived. It can be authored by a human or a separate tool. **Automatic Genome authoring is outside the CIDD 0.1 core engine.** The MVP scopes one application/language per project rather than promising multi-application orchestration.

A repository interface may be derived from the required entities and use cases instead of being manually enumerated in the Genome. The current derivation process should not be confused with a fully implemented deterministic repository generator; that stronger feature was deferred beyond the hackathon.

### 3.2 Contract graph and sealing

`cidd build-graph` expands the Genome into contracts and seals the graph. The resulting graph is the authoritative input for implementation generation. Fingerprints and the exact graph snapshot in each run help constrain subsequent selective reuse.

The development model distinguishes **Locked**, **Draft**, and **Sealed** states. The intended layer discipline requires earlier layers to be sealed before downstream work proceeds. Those lifecycle concepts should not be interpreted as proof that every conceivable graph change is automatically and safely migrated.

The demonstration uses the conventional dependency direction:

```text
Presentation ---> Application ---> Domain
     |                  ^
     +----> Infrastructure adapters implementing Domain interfaces
```

This is a simplified logical view. The actual dependency set is specified per contract in the sealed graph; implementation imports must be checked against those contracts.

### 3.3 Context isolation

Each worker receives the contract to implement and context allowed for its **direct dependencies**, rather than an unrestricted snapshot of the repository. The orchestrator, not the worker, selects this context.

Benefits under investigation include smaller task-specific prompts, reduced accidental cross-component editing, more localized regeneration, and clearer token accounting. None by itself guarantees valid source or an application-wide constant token budget.

### 3.4 Generation, normalization, and evidence

`cidd generate` invokes the configured provider (demonstrated with Meta Muse-Wonder and local Ollama), normalizes supported generated source, writes files in a unique staging directory, and persists an incremental `manifest.json` after each contract. The CLI reports each contract's status and available token usage as it completes.

Observed statuses include `GENERATED`, `REUSED`, and `FAILED`. A `GENERATED` result means source was produced and staged; it does **not** mean it compiled or passed a runtime test.

A run records the sealed-graph provenance together with contract results, token counts, elapsed times, and output paths. Where available, source hashes are checked before accepting prior outputs for reuse. These are audit and reproducibility mechanisms, not an assumption that sampling is perfectly deterministic.

### 3.5 Assembly, bootstrap, and validation

`cidd assemble` places source into a Flutter project and creates the supported bootstrap wiring. It then runs dependency resolution and Flutter static analysis, emitting `cidd-assembly-report.json`.

The original clean TaxiCat template test exposed a **packaging deficiency**: `lib/main.dart` was missing. The demonstrated bootstrap required a supported Flutter starter entry point with `MyApp` and `MyHomePage`. A manually crafted entry point in the source project was correctly rejected by the conservative bootstrap safety rules. Packaging that starter entry point and regression-testing `new-project` remain necessary for a clean public reproduction.

The demonstrated standard analysis invocation is:

```powershell
flutter analyze --no-pub --no-fatal-infos --no-fatal-warnings
```

This policy **reports** warnings and informational diagnostics but does not let them alone cause nonzero analyzer exit status. Actual analyzer errors still block acceptance. `Analyzer: PASS` therefore means *no fatal analyzer diagnostics under the configured policy*, **not** warning-free code, successful mobile execution, or complete behavioral correctness.

CIDD 0.1 does not yet demonstrate an automatic loop that maps arbitrary analyzer errors back to one contract, supplies bounded repair feedback, and revalidates until success. That is planned work.

## 4. Incremental generation and provenance

Selective generation is different from a fresh full generation:

1. Compare a current sealed contract graph with a compatible earlier run.
2. Determine which contract outputs remain eligible for reuse.
3. Verify earlier source provenance, where recorded, before copying output.
4. Reuse unchanged outputs; generate changed contracts.
5. Persist the new run, with explicit `REUSED`/`GENERATED` outcomes and token metrics.

**Demonstrated controlled experiment:** for a 13-contract TaxiCat graph, 12 contracts were reused and only `presentation.RoleSelectionView` was regenerated. The single regenerated contract consumed **963 input + 1,074 output = 2,037 tokens**. See [Micro-Context Regeneration Experiment](microcontext-experiment.md).

**Scope limit:** This is evidence of selective regeneration in that test's provenance-compatible sealed-graph conditions. Rebuilding the Genome and expanding it again can change dependencies or signatures and invalidate additional contracts; no universal 12/13 reuse rate is claimed.

## 5. TaxiCat reference implementation

TaxiCat Mobile is the end-to-end Flutter/Dart demonstration and contains 13 generated contracts:

| Layer | Contract(s) | Count |
| --- | --- | ---: |
| Domain | `Ride`, `RideRepository` | 2 |
| Application | `AcceptRide`, `CancelRide`, `CompleteRide`, `GetRideStatus`, `ListAvailableRides`, `RequestRide`, `StartRide` | 7 |
| Infrastructure | `HttpRideRepository` | 1 |
| Presentation | `RoleSelectionView`, `PassengerView`, `DriverView` | 3 |
| **Total** | | **13** |

The mobile app uses Mapbox and communicates with an **independently running** Go HTTP TaxiCat Server. The server is **not** automatically produced or deployed by the mobile template. At runtime the app needs a Mapbox public token, a reachable HTTP backend, and an Android device or emulator. `10.0.2.2` refers to the host from the standard Android emulator, not an arbitrary computer elsewhere on the LAN.

A cross-implementation experiment also tested a CIDD-generated passenger client on Windows and a Muse-Code-generated driver client on a Mac. The first requested a ride, and the second received, accepted, started, and completed it through the shared backend. This establishes interoperability for that observed transaction; it does not establish full code equivalence or feature parity.

## 6. Reliability and deterministic controls

CIDD's determinism is chiefly in **governance**: contract boundaries, file placement, graph checks, reporting, and validation steps. The LLM remains a probabilistic source generator.

The Meta provider was tested with an explicit `temperature: 0.0` configuration. Repeated fixed-graph runs still differed in output length and analyzer diagnostics. Temperature zero is not a guarantee of identical source or first-pass validity.

Examples recorded in the hackathon:

- **v4:** `presentation.DriverView` passed a GeoJSON map where `GeoJsonSource.data` required a string. The analyzer found the error; it was fixed manually for a later runtime test. The original assembly failed.
- **v6:** the analyzer reported an unused field in `DriverView`. Its initial warning-fatal assembly failed; under the standard nonfatal-warning policy, reassembly passed **without changing generated source**.
- **v5:** an unmodified generated assembly passed bootstrap, dependency resolution, and analyzer checks, and was observed running on an Android emulator.

These cases show the importance of **verified external API references**, severity-aware validation, and preserving the difference between generated source, validated source, and runtime-tested application behavior.

## 7. Security and operational boundaries

- Do not commit Meta credentials, Mapbox tokens, or production secrets to the Genome, prompts, manifests, generated source, or documentation.
- Treat generated code as **untrusted until validated and reviewed**. Static analysis alone is not a security assessment.
- Run and expose the Go backend only with appropriate local-network and firewall controls.
- Retain sealed graph snapshots, manifests, analyzer reports, and relevant test evidence for reproducibility; do not equate a run directory with a formally released software artifact.
- Any model-derived dependency, API usage, or platform-specific integration may require verified references and execution testing.

## 8. Known limitations and roadmap

**Current limitations:** support is concentrated on the demonstrated Flutter client workflow; clean-template packaging needs a regression-tested starter entry point; automatic contract-local repair is not complete; the backend is managed separately; multi-app/full-stack Genome generation and broad platform portability have not been established.

**Planned research:**

1. Repair the distributable TaxiCat template and test project creation from a fresh installation.
2. Associate analyzer diagnostics with owning contracts and enable bounded feedback/retry with preserved provenance.
3. Expand verified dependency/API skills, including Mapbox GeoJSON serialization.
4. Measure full pipeline consumption (Genome/graph expansion, generation, reuse, validation, retries, and runtime checks) against explicitly equivalent baselines.
5. Explore an *external* AI architect that helps a user author a Genome, while keeping Genome validation and source generation governed by CIDD's deterministic engine.

## 9. Related documentation

- [README](../README.md) — installation, supported CLI flow, and Android launch instructions.
- [Hackathon Report](HACKATHON.md) — experiments, measured results, and comparison caveats.
- [Micro-Context Regeneration Experiment](microcontext-experiment.md) — selective-regeneration methodology and numbers.

---

**Deterministic Governance, Probabilistic Generation.**

> **The project grows. The worker's context doesn't.**
