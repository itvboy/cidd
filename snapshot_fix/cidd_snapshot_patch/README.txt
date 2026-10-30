CIDD Validated Snapshot MVP v0.1
================================
Install src/cidd/engine/snapshot.py and tests/test_snapshot.py under CIDD's project root.
Do not overwrite other modules; no changes to workers, AssemblyEngine or SelectiveEngine.

Commands (from TODO root, with editable CIDD venv active):

python -m cidd.engine.snapshot promote --graph .cidd\contract-graph.json --assembly .cidd\assembled\bootstrap_test_01 --output .cidd\snapshots\todo-v1 --source-run 20261029_180527_706588

python -m cidd.engine.snapshot verify --snapshot .cidd\snapshots\todo-v1 --graph .cidd\contract-graph.json

Promotion requires matching graph fingerprint, complete assembly, pub get PASS, bootstrap PASS, analyzer PASS.
Snapshot contains copies of all 7 generated Dart files + main.dart, SHA256 hashes, graph and report evidence.
Runtime tests are NOT_VERIFIED; no automatic Flutter build/run or functional validation.
This v0.1 DOES NOT integrate reuse of snapshots into SelectiveEngine. That is the next change, after we verify this checkpoint.

Security / audit caveat: Verifying files protects their integrity relative to the captured manifest. No cryptographic signature or trusted independent attestation is provided. Source files manually modified after the analyzer result may still be promoted, because the analyzer report does not bind individual source hashes. A later release should bind hashes at the moment of validation and support signed attestations.
