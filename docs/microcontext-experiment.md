# CIDD 0.1 — Micro-Context Regeneration Experiment

## Objective

Evaluate the **Contract Isolation Hypothesis** by measuring whether CIDD can regenerate a single modified contract without regenerating unrelated contracts or expanding the LLM worker's context to the entire application.

> **The project grows. The worker's context doesn't.**

## Environment

| Parameter | Value |
|---|---|
| Engine | CIDD 0.1 |
| LLM | Muse-Glimmer (Ollama, local) |
| Application | TaxiCat Mobile |
| Language | Dart / Flutter |
| Total contracts | 13 |
| Generation mode | Selective |
| Graph state | Sealed |

## Experimental Method

1. Start from a historical sealed contract graph and its completed generation run.
2. Modify only the specification of `presentation.RoleSelectionView`.
3. Preserve the other 12 contracts, their dependencies, and their skills.
4. Recompute and verify the contract graph fingerprint.
5. Execute CIDD selective generation against the historical run.
6. Examine the resulting manifest to verify generation decisions, reuse, and token consumption.

The experiment deliberately isolates the regeneration stage from probabilistic genome expansion.

## Results

| Metric | Value |
|---|---:|
| Total contracts | 13 |
| Generated contracts | 1 |
| Reused contracts | 12 |
| Failed contracts | 0 |
| Input tokens | 963 |
| Output tokens | 1,074 |
| **Total LLM tokens** | **2,037** |
| Token counts complete | True |

**Modified contract:** `presentation.RoleSelectionView`

**Historical baseline:** `20261104_031956_950448`

**Experimental run:** `20261104_052012_847274`

### Contract Processing Distribution

| Decision | Contracts | Percentage |
|---|---:|---:|
| GENERATED | 1 | 7.7% |
| REUSED | 12 | 92.3% |
| FAILED | 0 | 0% |

All 12 unchanged implementations were reused without additional LLM generation.

## Findings

The selective generation engine successfully:

- Identified the modified contract.
- Regenerated only `presentation.RoleSelectionView`.
- Reused the remaining 12 implementations.
- Preserved the historical generation baseline.
- Recorded the completed operation with 2,037 LLM tokens.

This demonstrates that, under a controlled sealed graph, **the number of contracts regenerated can be independent of the total number of unchanged contracts in the application**.

The experiment does not establish that token consumption is independent of project size for every possible application, graph structure, or modification.

## Experimental Limitations

The experiment verified selective generation and reuse decisions.

**Compilation, Flutter Analyzer validation, and runtime execution of this specific regenerated assembly were not performed.**

An earlier genome-to-graph reconstruction introduced additional contract changes through probabilistic repository expansion and differences in skill content.

Consequently, this experiment demonstrates selective regeneration **from a controlled sealed contract graph**, not guaranteed isolation across every stage of the genome-to-application pipeline.

The 2,037-token measurement represents the recorded selective generation operation, not the total cost of reconstructing an application from its genome.

## Architectural Significance

Traditional project-wide generation workflows may expose an LLM to substantial portions of an existing codebase when implementing a change.

CIDD instead assigns a bounded contractual task to an isolated worker, with the deterministic engine responsible for dependency governance, reuse decisions, artifact management, and validation.

The worker does not require arbitrary repository access or agentic capabilities to generate its assigned implementation.

This experiment provides concrete evidence for that design at the selective generation stage.

## Conclusion

**CIDD regenerated 1 of 13 contracts while reusing the other 12, consuming 2,037 LLM tokens.**

The result supports the feasibility of contract-isolated selective generation under a stable sealed graph.

Further experiments are required to evaluate scaling behavior, dependency invalidation, end-to-end token cost, compilation success, and runtime correctness.

---

**CIDD — Contract-Isolated Driven Development**

*Deterministic Governance, Probabilistic Generation.*

*The project grows. The worker's context doesn't.*