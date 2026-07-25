# Software Requirements 2.0.0

Requirement status is one of `implemented`, `tested`, or `planned`. `Tested`
requires an automated retained test; it does not imply a completed physics
analysis.

| ID | Requirement | Status |
|---|---|---|
| DATA-001 | Accept only frozen direct-HTTPS catalog entries with SHA-256 | implemented |
| DATA-002 | Read ROOT in chunks and publish event-level Parquet in GeV | implemented |
| DATA-003 | Apply fixed four-lepton selection and deterministic pairing | tested |
| DATA-004 | Preserve canonical event identity and data/simulation separation | tested |
| DATA-005 | Compute strict yield/train weights and fail on missing metadata | tested |
| SPLIT-001 | Assign 70/10/10/10 by SHA-256 within every dataset | tested |
| FEAT-001 | Reject mass, identity, process, truth, and weight model inputs | tested |
| MODEL-001 | Provide cut-based, Logistic, XGBoost, and sklearn MLP paths | implemented |
| MODEL-002 | Align five fixed-seed predictions and publish an ensemble mean | tested |
| DDT-001 | Fit conditional CDF on calibration-background simulation only | tested |
| DDT-002 | Enforce correlation, acceptance, and spurious-signal gates | tested |
| FIT-001 | Build six-channel 1 GeV pyhf model with fixed nuisances | tested |
| BLIND-001 | Refuse observed fit without explicit flag and matching freeze | tested |
| ART-001 | Publish formal outputs atomically with completion records | tested |
| CLI-001 | Expose the breaking v2 command surface | tested |
| DOC-001 | Validate documentation links, versions, statuses, and stale terms | tested |
| SCI-001 | Produce formal five-seed and expected-fit results | planned |
| SCI-002 | Create an analysis freeze after all real sideband gates pass | planned |
| SCI-003 | Perform an authorized observed fit | planned |

## Cross-cutting constraints

- Unknown configuration keys are errors.
- Network access is HTTPS only and always checksum-verified.
- Real data never have a training target or training split.
- Model input field lists are serialized and hashed.
- Formal outputs are immutable and content-addressed.
- Python 3.10--3.12 and no-network fixture tests are supported.
