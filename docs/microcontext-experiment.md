# CIDD 0.1 — Micro-Context Regeneration Experiment

## Objective

Measure whether CIDD can regenerate a single changed contract
without regenerating unrelated contracts.

## Environment

- Engine: CIDD 0.1
- LLM: Muse-Glimmer (Ollama, local)
- Application: TaxiCat Mobile
- Language: Dart / Flutter
- Contract count: 13

## Experimental Method

1. Start from a historical sealed contract graph.
2. Modify only the specification of presentation.RoleSelectionView.
3. Preserve the other 12 contracts, dependencies, and skills.
4. Recompute and verify the graph fingerprint.
5. Execute CIDD selective generation against the historical run.

## Results

| Metric | Value |
|---|---:|
| Total contracts | 13 |
| Generated | 1 |
| Reused | 12 |
| Failed | 0 |
| Input tokens | 963 |
| Output tokens | 1,074 |
| Total tokens | 2,037 |
| Token counts complete | True |

Changed contract: presentation.RoleSelectionView

Historical baseline: 20261104_031956_950448

Experimental run: 20261104_052012_847274

## Findings

The selective generation engine regenerated only the modified
contract and reused the other 12 implementations without
additional LLM tokens.

The experiment verified planning and selective generation.
Compilation and runtime validation of the newly generated
assembly were not performed.

An earlier end-to-end genome rebuild introduced additional
contract changes through probabilistic repository expansion
and differences in skill content.

Consequently, this experiment demonstrates selective
regeneration from a controlled sealed graph, not isolation
across every stage of the genome-to-application pipeline.

## Positioning

CIDD is a micro-context-oriented software generation engine
governed by isolated contracts.

"The project grows. The worker's context doesn't."
