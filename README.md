# CIDD 0.1

**Contract-Isolated Driven Development**  
*A contract-driven software generation engine powered by isolated LLM workers.*

> **The project grows. The worker's context doesn't.**

CIDD is an experimental software generation engine that uses a **deterministic orchestration pipeline** and **isolated, non-agentic LLM workers** to generate source code from a sealed graph of contracts.

Rather than giving an AI coding agent full repository access, CIDD assigns each worker a bounded contract and its permitted dependencies. The engine—not the model—handles orchestration, file operations, source staging, assembly, and validation.

**AI generates the code. CIDD controls the process.**

## What CIDD does

- Validates a structured application **Genome**.
- Expands that Genome into a **sealed contract graph**.
- Generates individual contracts using a configured LLM provider.
- Records per-contract status, token counts, elapsed time, and generation manifests.
- Supports selective reuse and regeneration against compatible, verified sealed graphs.
- Assembles a Flutter project and runs dependency resolution and static analysis.

CIDD workers **do not** inspect repositories, edit arbitrary files, execute tools or tests, delegate to other workers, or autonomously change the architecture.

**CIDD 0.1 is a research prototype, not a general-purpose autonomous app builder.** Its demonstrated end-to-end application is TaxiCat Mobile (Flutter/Dart).

## Prerequisites

For the Windows/PowerShell walkthrough below:

- Git.
- Python **3.11 or newer** (the project's declared minimum).
- Flutter SDK and Android SDK configured for Android development.
- An Android emulator or compatible device.
- Access to **one** generation provider: Meta API credentials for `muse-wonder-1.0`, or a local Ollama server with an installed compatible model.
- To **run TaxiCat**: a Mapbox public access token and a reachable TaxiCat HTTP backend.

The instructions below reflect the Windows/PowerShell workflow used for the TaxiCat demonstration. Other platforms may work, but are not documented here as verified CIDD installations.

## Install

```powershell
git clone https://github.com/itvboy/cidd.git
cd cidd

py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

.\.venv\Scripts\cidd.exe --help
```

For subsequent commands, either activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

or invoke the executable with its full path. In the examples below, `cidd` assumes the virtual environment is activated.

## Quick start: generate TaxiCat Mobile

### 1. Create the project

From the parent directory of the cloned CIDD repository:

```powershell
cd ..
cidd new-project taxicat_demo --from-template taxicat
cd taxicat_demo
cidd validate
```

**Template readiness note:** The current TaxiCat template packaging must be checked for `lib/main.dart`. During the hackathon reproduction, the new project initially omitted this file and the bootstrap failed. The tested workaround was to supply a standard Flutter starter `lib/main.dart` containing `MyApp` and `MyHomePage` before assembly. The published template should include this file before the quick start can be considered fully reproducible without manual intervention.

### 2. Configure a provider

For Meta, set your API key **in your local shell**; never commit or paste it into source files:

```powershell
$env:MODEL_API_KEY = "<YOUR_META_API_KEY>"
```

Use a valid Meta model identifier, such as `muse-wonder-1.0`, when your account has access. For Ollama, start its local service and ensure that your chosen model is already available.

### 3. Build a sealed contract graph

```powershell
cidd build-graph `
  --genome .\genome\genome.yaml `
  --output .\.cidd\contract-graph.json `
  --provider meta `
  --model muse-wonder-1.0
```

This step expands and seals the application's contracts. It may consume model tokens.

### 4. Generate implementations

```powershell
cidd generate `
  --graph .\.cidd\contract-graph.json `
  --output .\.cidd\generated-runs `
  --provider meta `
  --model muse-wonder-1.0
```

CIDD displays per-contract progress. At the end, record the `Staging:` path printed by the CLI, for example:

```text
Staging: .cidd\generated-runs\20261104_144607_725986
```

The run directory is unique to your execution; **do not reuse the illustrative timestamp**.

### 5. Assemble and analyze

```powershell
cidd assemble `
  --graph .\.cidd\contract-graph.json `
  --run .\.cidd\generated-runs\<YOUR_RUN_ID> `
  --project . `
  --output .\.cidd\assembled\taxicat_demo
```

Replace `<YOUR_RUN_ID>` with the directory name from the previous `Staging:` output.

Expected report stages:

```text
Bootstrap: PASS
Pub get: PASS
Analyzer: PASS
```

**Interpretation:** `GENERATED` means source was produced; it does **not** mean that source compiled or passed validation. The demonstrated standard analyzer policy allows warnings and informational diagnostics but still rejects analyzer errors. Review `cidd-assembly-report.json` for details. Static analysis alone does not establish runtime correctness.

### 6. Run on Android

**Start a compatible TaxiCat HTTP server first.** The mobile template does not deploy the backend. Set the Mapbox public token locally:

```powershell
$env:MAPBOX_ACCESS_TOKEN = "<YOUR_PUBLIC_MAPBOX_TOKEN>"
```

For an Android emulator running on the **same computer as the HTTP backend**:

```powershell
cd .\.cidd\assembled\taxicat_demo
flutter devices
flutter run -d emulator-5554 `
  --dart-define=MAPBOX_ACCESS_TOKEN="$env:MAPBOX_ACCESS_TOKEN" `
  --dart-define=TAXICAT_API_URL=http://10.0.2.2:8080
```

`emulator-5554` is only an example; use the device ID shown by `flutter devices`.

If the server runs on **another machine on your LAN**, use that machine's reachable address instead of `10.0.2.2`, for example `http://192.168.1.9:8080` on the network used in the original demonstration. Check server binding and firewall settings; do not assume the sample IP is valid on your network.

This launch configuration assumes the generated app reads the environment names `MAPBOX_ACCESS_TOKEN` and `TAXICAT_API_URL` through Dart defines. Confirm the names in the application's entry point when adapting another template.

## Architecture at a glance

```text
Application Genome
        |
        v
Genome validation
        |
        v
Contract graph expansion and sealing
        |
        v
Deterministic CIDD orchestrator
        |
        +--> Isolated LLM worker: Contract A --> Source A
        +--> Isolated LLM worker: Contract B --> Source B
        +--> Isolated LLM worker: Contract C --> Source C
        |
        v
Generation manifest + source staging
        |
        v
Flutter assembly / bootstrap
        |
        v
Dependency resolution + static analysis
        |
        v
Android execution and functional testing
```

Workers receive constrained context. They do **not** operate as autonomous coding agents. The Genome can be authored externally by a human or another tool; automatic Genome authorship is outside CIDD 0.1's core engine.

## Experimental results and scope

During the November 2026 development and demonstration, CIDD generated the **13-contract TaxiCat Mobile** app with Muse-Wonder and ran an assembled version on an Android emulator with Mapbox and a Go/HTTP backend. A separate implementation generated with Muse-Code also completed a cross-application ride workflow against that backend: the CIDD-generated client requested a ride and the Muse-Code-generated client accepted and completed it.

One documented selective-regeneration experiment reused **12 of 13** contracts and regenerated only `presentation.RoleSelectionView`, consuming **2,037 model tokens**. That result applies to a **controlled, unchanged sealed graph except for one contract**; it does not prove the same isolation across an arbitrary end-to-end Genome rebuild. See [Micro-Context Regeneration Experiment](docs/microcontext-experiment.md).

Generation outcomes varied across identical-graph runs. Some assemblies required correction or a non-fatal-warning analyzer policy. CIDD does **not** claim that every model output compiles on the first attempt, or that a PASS in static analysis guarantees correct runtime behavior.

## Development checks

From the CIDD repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

At the hackathon checkpoint, the local test suite reported **138 passing tests**. This is a recorded checkpoint, not a guarantee about every subsequent commit.

## Documentation

- [Micro-Context Regeneration Experiment](docs/microcontext-experiment.md) — a controlled selective-regeneration result.
- **Architecture report** — planned as `docs/ARCHITECTURE.md`.
- **Hackathon methodology and findings** — planned as `docs/HACKATHON.md`.

## Philosophy

**Deterministic Governance, Probabilistic Generation.**

> CIDD doesn't make the model smarter. It makes the problem smaller.

The goal is to bound each model task, track its provenance and cost, and validate the output using deterministic tooling rather than giving the model unrestricted control of the development environment.

## Project context

Built for the **Meta Global AI Developer Hackathon 2026**, Indie Developer / Push the Frontier track. CIDD's experimental claims should be evaluated using its run manifests, analyzer reports, source artifacts, and clearly stated comparison boundaries.





### TaxiCat — Comparative Benchmark

To evaluate CIDD's contract-isolated generation approach, we generated the same TaxiCat application using two different workflows: **CIDD + Muse-Wonder 1.0** and **Muse-Code + Muse-Wonder 1.0**.

Both implementations were successfully executed on Android and demonstrated interoperability through a shared Go backend.

The experiment examines token consumption, generation workflow, functional results, and measurement limitations.

**[Read the TaxiCat Comparative Benchmark](TAXICAT_BENCHMARK.md)** for the methodology, recorded metrics, and detailed findings.