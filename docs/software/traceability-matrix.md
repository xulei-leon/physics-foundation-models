# Traceability Matrix 2.0.0

| Requirement | Configuration or schema | Implementation | Test evidence |
|---|---|---|---|
| DATA-001 | `catalog-sources.yaml`, dataset-catalog schema | `catalog.py` | `test_catalog.py` |
| DATA-002 | dataset-manifest schema | `ingestion.py` | `test_ingestion.py` |
| DATA-003 | `analysis-v1.yaml` | `physics.py` | `test_physics.py` |
| DATA-004 | dataset/split schemas | `ingestion.py`, `splits.py` | `test_ingestion.py`, `test_splits.py` |
| DATA-005 | `analysis-v1.yaml` | `weights.py` | `test_weights.py` |
| SPLIT-001 | split-manifest schema | `splits.py` | `test_splits.py` |
| FEAT-001 | run-record schema | `features.py` | `test_features.py` |
| MODEL-001 | model config | `models.py` | `test_models.py` |
| MODEL-002 | prediction schema | `models.py` | `test_models.py` |
| DDT-001 | DDT config | `decorrelation.py` | `test_decorrelation.py` |
| DDT-002 | analysis-freeze schema | `decorrelation.py`, `blinding.py` | `test_decorrelation.py`, `test_blinding.py` |
| FIT-001 | fit-result schema | `inference.py` | `test_inference.py` |
| BLIND-001 | analysis-freeze schema | `blinding.py`, `cli.py` | `test_blinding.py`, `test_cli.py` |
| ART-001 | completion record contract | `artifacts.py` | `test_artifacts.py` |
| CLI-001 | command specification | `cli.py` | `test_cli.py` |
| DOC-001 | documentation contract | `validate_software_docs.py` | CI documentation job |

Rows for formal science results remain absent until retained artifacts exist.
Implementation tests establish behavior, not physics performance.
