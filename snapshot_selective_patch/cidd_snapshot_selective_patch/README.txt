CIDD validated snapshot -> SelectiveEngine integration

Copy src/cidd/engine/snapshot_selective.py into your installed CIDD checkout.
This implementation does NOT change selective.py, snapshot.py, or assembly.py.

Run from your TODO project:
python -m cidd.engine.snapshot_selective --graph .cidd/contract-graph.json --snapshot .cidd/snapshots/todo-v1 --output .cidd/generated-runs/e01_validated --model muse-glimmer

Take the EXACT printed Run: path (a timestamped child directory), and use it as --run in python -m cidd.engine.assembly with a new --output.

Safeguards: verifies all hashes and historical graph evidence, checks contract input signatures, uses existing SelectiveEngine, writes provenance to run manifest. Does not claim runtime validation.
