# particleML: Blinded Four-Lepton Higgs ML

This site is the authoritative research and software record for a
portfolio-grade analysis of public ATLAS 2015+2016 education data. The study
tests whether a mass-decorrelated XGBoost classifier improves expected
profile-likelihood sensitivity over a fixed cut-based baseline.

## Current evidence state

| Item | Status |
|---|---|
| Research question and protocol | frozen in Research Plan v1.0.0 |
| Software and schemas | implementation under contract 2.1.0 |
| Jetson Docker environment | verified for ARM64, CUDA, and offline checks |
| Offline synthetic pipeline | verified in the Jetson development container |
| Full public-data catalog | planned; must be frozen through direct HTTPS |
| Formal five-seed training | planned |
| Expected physics result | not yet produced |
| Real-data signal window | blinded |

## Start here

- [Research plan](research/research-plan.md)
- [Dataset and backgrounds](research/dataset-and-backgrounds.md)
- [Model selection](research/model-selection.md)
- [Statistical analysis plan](research/statistical-analysis-plan.md)
- [Software architecture](software/architecture.md)
- [Jetson Orin Nano development guide](engineering/jetson-orin-nano-development-guide.md)
- [Analysis run guide](engineering/analysis-run-guide.md)
- [Offline synthetic demo](engineering/offline-demo-guide.md)
- [Migration plan](plans/2026-07-25-atlas-h4l-v1-migration-plan.md)

The code and tests implement analysis mechanics. They do not turn planned
experiments into verified scientific results.
