# TaxiCat Benchmark — CIDD vs. Muse-Code

**CIDD 0.1 · Meta AI Hackathon · November 4, 2026**  
**Status:** Observational comparison with a verified cross-implementation functional test; **not** a normalized cost or end-to-end token-efficiency benchmark.

> **The project grows. The worker's context doesn't.**

## Executive summary

Two different approaches were tasked with implementing **TaxiCat Mobile**, a Flutter taxi demonstration based on the same project genome:

- **CIDD + Muse-Wonder 1.0:** A deterministic, contract-governed generation engine delegates implementation to isolated, non-agentic LLM workers. The tested graph contains **13 contracts**.
- **Muse-Code + Muse-Wonder 1.0:** An agentic coding workflow generated an independently implemented Flutter application.

**Both approaches produced runnable Android applications.** In a cross-machine test, the **CIDD-generated passenger app** on an Android emulator hosted by an MSI Stealth 18 requested a ride. The **Muse-Code-generated driver app** on an Android emulator hosted by a Mac received the request, accepted it, started the trip, and completed it. Both communicated with the **same Go TaxiCat Server** over HTTP.

A recorded CIDD full contract-generation run used **41,264 tokens** (12,220 input; 29,044 output) in **177 seconds**; its Flutter assembly passed bootstrap, dependency resolution, and static analysis, and it ran on Android. A reported Muse-Code session accumulated **3,088,587 tokens** (3,051,058 input, including 2,850,098 cached input; 37,529 output), across **44 turns**. **These two totals cover different scopes and accounting categories and must not be divided to claim a measured cost reduction.**

## 1. Research question and hypothesis

**Question:** Can a contract-isolated, non-agentic generation workflow produce a functionally comparable application while limiting the context assigned to each code-generation worker?

**CIDD hypothesis:** By governing generation through a sealed contract graph, a project's overall size need not be reflected in each worker's context. A worker receives its assigned contract and approved direct dependencies rather than autonomous access to the full repository.

This benchmark supplies a **feasibility demonstration and descriptive usage measurements**. It does not, by itself, establish a statistically significant advantage in cost, runtime, or reliability.

## 2. Comparison setup

| Dimension | CIDD | Muse-Code |
|---|---|---|
| Starting specification | TaxiCat genome | Same TaxiCat genome (reported) |
| Target | TaxiCat Flutter Android client | TaxiCat Flutter Android client |
| Model family | Muse-Wonder 1.0 | Muse-Wonder 1.0 |
| Reasoning setting | **Medium intended; verify saved provider/session configuration** | **Medium reported; verify session export** |
| Workflow | Deterministic orchestration; isolated, non-agentic workers | Agentic coding workflow |
| Application scope | Passenger and driver screens, Mapbox, Go HTTP backend integration | Passenger and driver screens, Mapbox, Go HTTP backend integration |
| Runtime platform tested | Android emulator on MSI Stealth 18 (Windows) | Android emulator on Mac |
| Backend | Shared TaxiCat Server (Go) | Same shared TaxiCat Server (Go) |

**Environmental prerequisites:** Both clients require a Mapbox access token and a reachable TaxiCat Server endpoint. On the Mac, the server was accessed at `http://192.168.1.9:8080` on the local network; `10.0.2.2` instead refers to the Android emulator's *own* host machine. Supplying these values and selecting an Android emulator are environment-setup actions, **not proof of defects in either generator's output**.

### Control conditions and deviations

The shared genome and model family make the comparison informative, but the experiment was **not completely controlled**:

1. CIDD measurements below refer primarily to **contract generation** after a sealed graph already existed; Muse-Code's session counters are **session-level**.
2. Muse-Code input includes cached tokens; caching changes billing and may change the interpretation of processing cost.
3. Human approvals and environment setup were not measured in an equivalent intervention ledger.
4. Exact **reasoning-effort settings**, prompt/version identifiers, API billing rates, and reproducibility seeds must be confirmed from primary logs before publication as tightly matched conditions.
5. CIDD also performed an LLM-assisted graph-expansion step in the broader workflow, which is **not included** in the 41,264-token contract-generation figure.

## 3. Recorded token measurements

### 3.1 CIDD + Muse-Wonder 1.0

The project used a sealed graph with **13 contracts**: seven application use cases, two domain contracts, one HTTP repository adapter, and three presentation views.

| Recorded run / assembly label | Input tokens | Output tokens | Total generation tokens | Time | Original analyzer outcome | Notes |
|---|---:|---:|---:|---:|---|---|
| Initial Wonder run | — | — | **40,933** | **179 s** | Passed after starter `main.dart` was supplied | The initial template lacked a Flutter entry point; do not count this as an entirely unattended clean run |
| v3 | 12,220 | 27,668 | **39,888** | **167 s** | **PASS** | Assembled; Android run confirmed |
| v4 | 12,220 | 32,106 | **44,326** | **201 s** | **FAIL** | Mapbox `GeoJsonSource.data` received a map instead of a JSON string; a one-line **manual correction** subsequently passed analysis and the app ran |
| v5 | 12,220 | 29,044 | **41,264** | **177 s** | **PASS** | `temperature=0.0` reported; no generated-code correction; Android run confirmed |
| v6 | 12,220 | 31,434 | **43,654** | **212 s** | **FAIL** under warnings-fatal policy; **PASS** under warnings-nonfatal policy | Only reported issue was `unused_field` in DriverView; no generated-code edit required for standard validation |

**Generation counts:** All five recorded full-generation runs generated 13 of 13 contracts; that is **generation completion**, not an automatic guarantee of compilation or runtime correctness.

**Graph expansion in the earlier clean workflow:** 753 input + 2,121 output = **2,874 additional LLM tokens** to build the sealed graph. This is a separately recorded step and should not be silently folded into every generation run or characterized as a complete end-to-end ledger.

**No automatic repair claim:** v4 required manual source repair; v6 passed only after the analyzer acceptance policy was changed to treat warnings as non-fatal. CIDD's current results establish detection and isolation, **not a demonstrated autonomous repair loop**.

### 3.2 Muse-Code + Muse-Wonder 1.0

Recorded from the reported Muse-Code session summary:

| Counter | Tokens / value |
|---|---:|
| Total tokens reported | **3,088,587** |
| Input tokens, including cached input | **3,051,058** |
| Cached input tokens (subset of input) | **2,850,098** |
| Non-cached input tokens (calculated) | **200,960** |
| Output tokens | **37,529** |
| Non-cached input + output (calculated) | **238,489** |
| Turns | **44** |
| Observer completions | **27 reported**; precise semantics unverified |

Accounting identities:

```text
3,051,058 input + 37,529 output = 3,088,587 total
3,051,058 input - 2,850,098 cached input = 200,960 non-cached input
200,960 non-cached input + 37,529 output = 238,489 non-cached-input-plus-output
```

The last number is an **accounting subtotal, not a billable-token or dollar-cost estimate**. Cached input may still carry a charge at a different rate, and some usage categories could require separate treatment. Muse-Code was reported to have requested permissions during execution; the user approved them, with no separate technical code corrections reported for that run. A full intervention log and timestamps are not available here.

**Scope note:** Another, earlier Muse-Code run was reported with **2,082,424 total tokens**, **1,883,606 cached input**, **32,830 output**, and **41 turns**. It is a **different recorded session** and is **not combined** with the 3,088,587-token measurement.

## 4. Why the headline token totals are not directly comparable

| Measurement boundary | CIDD figure of 41,264 | Muse-Code figure of 3,088,587 |
|---|---|---|
| Contract/code generation | Included | Included in broader session |
| LLM genome-to-graph expansion | **Excluded** | Not isolated in session counter |
| Iterative agent planning / tool activity | No agentic worker workflow; engine overhead not represented as LLM tokens here | Potentially included; precise categories unavailable |
| Cached input | Not separately identified in cited CIDD run | **2,850,098 included** |
| Build / analyzer runtime | Not included in LLM-token count | Not separately measured |
| Human interventions | Not normalized | Not normalized |
| Billing cost | Not established | Not established |
| Equivalent start/stop criteria | Not established | Not established |

**Do not describe `3,088,587 / 41,264` as an experimentally validated efficiency multiplier.** It is the ratio of different reported counters, not a fair end-to-end measurement.

A future normalized benchmark should start from an identical frozen genome and reference dependencies, use matching model/reasoning settings, record **all** LLM invocations and cached/uncached usage from the start, account for iterations and fixes, end at the same functional acceptance test, and compute monetary cost using the provider's actual pricing for each token class.

## 5. Functional acceptance: one cross-implementation ride

**Verified user-observed scenario**

```text
MSI Stealth 18 / Android emulator
  CIDD + Muse-Wonder passenger app
                 |
                 | POST ride request
                 v
       Shared TaxiCat Server (Go)
                 |
                 | Available ride / status updates
                 v
Mac / Android emulator
  Muse-Code + Muse-Wonder driver app
  ACCEPTED -> IN_PROGRESS -> COMPLETED
```

The user reported and demonstrated this sequence:

1. **CIDD passenger** submitted a ride request on the MSI emulator.
2. The new ride appeared in **Muse-Code driver** on the Mac emulator.
3. The driver accepted the request, started the trip, and completed it.
4. Both applications communicated with the shared Go HTTP backend.

**What this establishes:** Both generated applications can participate in a real end-to-end workflow using the same backend and interoperable API behavior for the scenario tested.

**What it does not establish:** Entire-codebase equivalence, comprehensive test coverage, production readiness, security certification, or a comparative ranking of developer experience.

## 6. Repeatability and analyzer acceptance

CIDD regeneration results varied despite using the same sealed graph and model family. A Mapbox type mismatch occurred in v4; v6 produced an unused private field. This is consistent with variability in generated code, but the available sample is too small to attribute outcomes to any one sampling parameter.

For Flutter analysis, CIDD subsequently adopted:

```powershell
flutter analyze --no-pub --no-fatal-infos --no-fatal-warnings
```

This preserves reporting of `info` and `warning` diagnostics while allowing a successful exit when no fatal analysis errors are present. It is a **validation policy choice**, not proof that the generated source contains zero warnings. The original v6 FAIL under the previous policy remains valid historical evidence.

**Sampling caveat:** `temperature=0.0` was configured for later Muse-Wonder runs, but a successful compile on one run and a warning on another do not establish deterministic outputs or a causal improvement in correctness.

## 7. Secondary experiment: selective micro-context regeneration

A **separate** CIDD/Muse-Glimmer (Ollama local) experiment changed only `presentation.RoleSelectionView` in an otherwise stable sealed 13-contract graph:

| Metric | Result |
|---|---:|
| Contracts regenerated | **1** |
| Contracts reused | **12** |
| Input tokens | **963** |
| Output tokens | **1,074** |
| Total tokens | **2,037** |
| Failed contracts | **0** |

That experiment verified selective planning and regeneration, **not** compilation/runtime of the modified assembly or isolation across a fresh genome rebuild. It is documented independently in [`microcontext-experiment.md`](microcontext-experiment.md) and must **not** be confused with the full-app Muse-Wonder vs. Muse-Code comparison.

## 8. Limitations and evidence still needed

| Evidence item | Current status |
|---|---|
| CIDD generation manifests and run IDs | Available in local CIDD project; attach/export if publishing reproducible raw evidence |
| Muse-Code detailed usage/session export | Summary reported; raw export and exact timestamps needed |
| Exactly matched **Medium** reasoning configurations | **Needs confirmation in both sets of primary logs** |
| Identical genome hash / freeze point | **Needs archival hash / copy from both workflows** |
| End-to-end token ledgers with the same measurement boundary | **Not yet available** |
| Cached-token pricing and dollar costs | **Not established** |
| Comparable wall-clock duration for Muse-Code | **Not established** |
| Formal intervention count | **Not established** |
| Cross-client ride on shared backend | **Observed and reported successful** |
| Production-grade functional/security testing | Outside the scope of this experiment |

## 9. Conclusion

**Both CIDD and Muse-Code generated Android TaxiCat clients that participated in a shared, successful ride workflow.** This demonstrates that CIDD's deterministic, contract-isolated, non-agentic architecture is a viable way to build a working application with an LLM.

CIDD's recorded full-generation runs used roughly **40–44 thousand LLM tokens** for the 13-contract code-generation stage; a reported Muse-Code session accumulated **3.09 million total session tokens, most of them cached input**. Those figures are **descriptive, not a normalized comparative efficiency or pricing result**.

The strongest supported claim is architectural and functional: **CIDD can generate and assemble a usable application through isolated contracts, and its generated client can interoperate with a separately agent-generated client.** A rigorous cost-reduction claim remains future work.

---

**CIDD — Contract-Isolated Driven Development**  
*Deterministic Governance, Probabilistic Generation.*  
*The project grows. The worker's context doesn't.*
