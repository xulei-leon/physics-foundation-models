# Current ATLAS H4l Plan and Legacy v0.4-jet Plan

## Document purpose and comparison boundary

This document compares the active ATLAS four-lepton analysis plan with the
archived `v0.4-jet` plan. The comparison covers the research objective,
baselines, dataset, research method, statistical endpoint, blinding,
systematics, reproducibility, resource demands, risks, and implementation
status.

The two plans address different scientific problems. The legacy plan is a
particle-representation and transfer-learning study for jet tagging. The
active plan is a blinded Higgs-analysis workflow whose main endpoint is an
expected profile-likelihood sensitivity difference. The comparison therefore
does not treat one plan as a drop-in revision of the other.

This document uses three evidence levels:

| Evidence level | Meaning in this document |
|---|---|
| Design | A method, gate, model, or output specified by an authoritative plan or contract |
| Implementation | Code or an automated fixture exists and is covered by retained tests |
| Scientific result | A formal run produced retained predictions, analysis artifacts, and a permitted physics conclusion |

An implementation test is not a scientific result. Neither plan has a
completed formal physics result in the repository state compared here.

## Version and archive record

| Field | Value |
|---|---|
| Comparison date | 2026-07-26 |
| Active baseline | Research Plan `v1.0.0`, software contract `2.0.0` |
| Active Git commit inspected | `40eaaf1c409f83559a442cb2b51792386b26fce7` |
| Legacy state | archived, not completed |
| Final legacy commit | `facaa72c3ad095c2f8aaca7e8dbba6ae164a774c` |
| Legacy Git tree | `e2b546c6016249b58a92d1cbb9fc639a48559bff` |
| Storage | local Git refs, by explicit user decision; not pushed remotely |

**Annotated tag:** `v0.4-jet`

**Archive branch:** `jet`

The tag and branch resolve to the same legacy commit. The tag is the immutable
comparison reference, while the branch provides a named mutable checkout.

## Executive comparison

| Dimension | Legacy `v0.4-jet` | Active ATLAS H4l v1 |
|---|---|---|
| Scientific center | Feature availability and labeled-data efficiency in foundation-model fine-tuning | Expected profile-likelihood sensitivity after validated mass decorrelation |
| Physics task | Generator-matched boosted hadronic top versus QCD jet classification | \(H\rightarrow ZZ^*\rightarrow4\ell\) signal versus background analysis |
| Primary model | Pretrained OmniLearned PET-style particle-set backbone | XGBoost followed by a fixed DDT conditional-CDF mapping |
| Primary comparison | Nested feature configurations A--D | XGBoost-DDT versus a fixed cut-based selection |
| Additional baseline or control | Deep Sets/PFN A-versus-D; optional random-initialized backbone | Logistic Regression linear baseline and scikit-learn MLP neural control |
| Dataset | Public CMS 2015 full-detector simulation only | Public ATLAS 2015+2016 education data and simulation, 36 fb\(^{-1}\) |
| Canonical unit of analysis | One AK8 jet with up to 150 particle constituents | One selected four-lepton event |
| Data representation | Compact ROOT, then one full-D HDF5 particle tensor with nested views | Event-level Parquet with a frozen tabular feature contract |
| Primary endpoint | Paired AUC differences across feature views and training sizes | Expected-significance difference between XGBoost-DDT and cut-based |
| Uncertainty design | Seed variation and paired bootstrap on saved jet predictions | Five formal seeds, simulation statistics, fixed normalization nuisances, and profile likelihood |
| Real-data blinding | Not applicable because the formal corpus was simulation only | Data in 120--130 GeV remain blinded until all freeze gates pass |
| Main operational constraint | Multi-terabyte extraction, legacy CMSSW, checkpoint compatibility, and GPU fine-tuning | Correct event weights, mass decorrelation, sideband validation, template integrity, and freeze authorization |
| Permitted claim | Dataset-record-disjoint cross-corpus adaptation under controlled feature availability | Internally reproducible comparison within an ATLAS education release |
| Repository evidence state | Local implementation and contract tests; formal E0 and training were not completed | Migration implementation and offline fixtures are tested; formal five-seed and physics outputs remain planned |

The legacy plan is more ambitious as a machine-learning representation study.
The active plan has a tighter connection between classifier behavior and a
physics-analysis endpoint. These strengths are not interchangeable: the former
prioritizes low-level model and feature questions, while the latter prioritizes
analysis validity, blinding, and statistical inference.

## 1. Research objectives

### 1.1 Legacy v0.4-jet objective

The legacy study asked how nested reconstructed-particle feature sets changed
the performance, data efficiency, and interpretability of a pretrained
OmniLearned PET-style backbone in top-versus-QCD classification. Its three
research questions were:

1. whether performance changed from configuration A through D;
2. whether richer feature sets reached a target AUC or background rejection
   with fewer labeled jets;
3. whether the feature ranking remained stable across seeds, training sizes,
   and a lower-complexity set-model control.

The feature ladder made the scientific intervention explicit:

| Configuration | Particle-level inputs | Intended contrast |
|---|---|---|
| A | Relative kinematics | Four-momentum feature baseline |
| B | A plus electric charge | Incremental value of charge |
| C | B plus reconstructed-particle identity | Incremental value of PID beyond charge |
| D | C plus impact-parameter values and uncertainties | Incremental value of track displacement information |

Each condition required separate fine-tuning. Training one full-feature model
and masking fields only at test time was not accepted as evidence for feature
availability.

This objective has a clear ML contribution: it separates representation
richness from architecture breadth and studies labeled-data efficiency. Its
main limitation is that the conclusion would remain conditional on one
cross-corpus task, one checkpoint boundary, the implemented adapters, and the
quality of the generator-derived labels. The plan explicitly prohibited
unseen-class, cross-detector, universal feature-importance, and architecture-
superiority claims.

### 1.2 Active ATLAS H4l objective

The active study asks:

> Under a fixed \(H\to ZZ^*\to4\ell\) preselection and a validated
> mass-decorrelation protocol, how much does an XGBoost classifier improve
> expected profile-likelihood sensitivity over a cut-based baseline, and is
> the improvement stable across final states, seeds, and limited systematic
> variations?

The primary endpoint is:

```text
expected_significance(XGBoost-DDT) - expected_significance(cut-based)
```

Weighted ROC-AUC, PR-AUC, background rejection, fitted signal strength,
confidence intervals, final-state stability, and five-seed variation are
secondary endpoints. A raw classification improvement is not sufficient:
XGBoost is useful for the analysis only if the improvement survives DDT and
all sculpting gates.

This objective is narrower in model-development terms but stronger as an
analysis question. It connects the classifier to a declared statistical model,
defines a physics baseline, and makes mass-sculpting failure scientifically
consequential. Its limitations follow from the ATLAS education release: the
study cannot support discovery, precision cross-section, coupling, or official
ATLAS performance claims.

### 1.3 Objective-level trade-off

The legacy plan asks what information a pretrained particle-set model can use.
The active plan asks whether a tabular classifier adds usable analysis
sensitivity. The legacy answer would primarily contribute to HEP ML
representation studies. The active answer would primarily demonstrate a
reproducible open-data analysis workflow. A near-null result would be
meaningful in either plan, but for different reasons: it would constrain the
value of richer particle features in the legacy study or the value of
XGBoost-DDT relative to cuts in the active study.

## 2. Models and baselines

### 2.1 Legacy model hierarchy

The authoritative `v0.4-jet` research plan defines a pretrained OmniLearned
PET-style backbone as the main measurement system. Configuration-specific
input adapters and a binary output head are initialized for each feature view,
then the full backbone is fine-tuned end to end.

The word *baseline* has two distinct meanings in this plan:

- **Feature baseline:** configuration A, containing relative constituent
  kinematics. B, C, and D measure incremental information beyond A.
- **Model baseline:** a lightweight Deep Sets/PFN-style permutation-invariant
  network, required at least for A versus D at the largest feasible training
  scale in a publication-strength version.

An OmniLearned backbone with random initialization was an optional
initialization control. ParticleNet, ParT, and broader architecture
comparisons were deferred to prevent the study from becoming an unfocused
benchmark.

The archived model-selection page retains some earlier `OmniLearn/PET`
terminology, while the authoritative v0.4 research plan, requirements, and
experiment matrix specify an OmniLearned PET-style boundary. This comparison
follows the research plan. The terminology drift is itself a documentation
risk because it can blur the distinction between an architecture family and a
specific pretrained artifact.

### 2.2 Active model hierarchy

The active hierarchy is simpler:

| Model | Role | Main value | Main limitation |
|---|---|---|---|
| Cut-based | Primary physics baseline | Transparent and independent of training | Cannot learn nonlinear interactions |
| Logistic Regression | Linear ML baseline | Tests whether nonlinear structure adds value | Limited interaction modeling |
| XGBoost | Primary classifier | Well matched to compact tabular inputs | Can sculpt \(m_{4\ell}\) through correlated inputs |
| scikit-learn MLP | Neural control | Tests whether a small dense network changes the conclusion | More sensitive to scaling and initialization |

All learned models share the split, feature contract, training weights, seeds,
and evaluation events. Seed 42 is used for one-time validation tuning; the
frozen settings are reused for formal seeds 17, 42, 314, 2026, and 2718. The
event-aligned mean prediction is the formal classifier output, with
seed-to-seed variation reported separately.

The active design gives the cut-based result a more direct baseline role than
the legacy design gave Deep Sets/PFN. It answers whether ML improves a familiar
analysis strategy. The cost is reduced ML novelty: it does not test a
pretrained particle representation, variable-length constituent model, or
transfer-learning hypothesis.

## 3. Datasets

### 3.1 Legacy CMS simulation corpus

The legacy plan froze one inclusive CMS 2015 TT production for signal and five
same-campaign QCD records for background. The source snapshot contained 2,789
unique online PFNs and 3.542 TiB:

| Component | Records | Planned role |
|---|---|---|
| TT simulation | Record 19980, 3.051 TiB | Source of generator-matched fully hadronic top jets |
| QCD simulation | Records 18373, 18376, 18377, 18355, and 18358 | Source of declared QCD background jets |

Jets came from `slimmedJetsAK8` with corrected
\(500\le p_T<1000\) GeV and \(|\eta|<2.0\). A signal jet required a unique
last-copy top within \(\Delta R<0.8\), a fully hadronic decay, and separate
containment of the \(b\), \(q\), and \(q'\) daughters. Other jets in TT events
were excluded rather than labeled as QCD.

The dataset supports a low-level particle study because it exposes packed
candidate kinematics, charge, PID, and track displacement information. It also
creates substantial risks:

- the production path depends on CMSSW `7_6_7`, its historical global tag, and
  correct daughter-reference and generator traversal behavior;
- signal labels depend on generator truth and decay containment;
- impact-parameter units, primary-vertex semantics, and charged-candidate
  missingness must be validated before configuration D is interpretable;
- preliminary yield evidence was insufficient to freeze the planned
  \(10^5\) jets per class;
- measured local access rates were unsuitable for production, so extraction
  required CERN-adjacent, institutional, or cloud infrastructure.

No real collision data were part of the formal study, so the plan did not
include an observed-data blinding or unblinding decision.

### 3.2 Active ATLAS education corpus

The active plan uses the public ATLAS 13 TeV, 2015+2016, 36 fb\(^{-1}\)
education release:

- [`exactly4lep` data, record `atlas-93924`](https://opendata.cern.ch/record/atlas-93924);
- [`exactly4lep` simulation, record `atlas-93928`](https://opendata.cern.ch/record/atlas-93928).

The frozen catalog is generated through direct HTTPS requests and records
explicit URLs, sizes, and SHA-256 checksums. ROOT files are read in chunks,
MeV inputs are converted once to GeV, and selected events are published as
event-level Parquet. Unknown process mappings, invalid normalization metadata,
non-HTTPS inputs, and checksum mismatches fail closed.

The fixed event selection requires exactly four electrons or muons, ordered
lepton-\(p_T\) thresholds, acceptance and identification requirements, valid
triggers, zero total charge, deterministic same-flavour opposite-sign pairing,
and dilepton-mass requirements. The analysis range is
\(105\le m_{4\ell}<160\) GeV. Data in 120--130 GeV are blinded; only the
105--120 and 130--160 GeV sidebands may be used before a valid freeze.

This corpus gives the active plan a real-data validation path and a
physics-analysis context that the legacy simulation-only study lacked. The
trade-off is a substantial claim boundary. The education ntuples do not expose
the complete calibrations, object definitions, systematic variations, or
collaboration validation of an experiment-grade analysis. Reducible
backgrounds use simulation with a pedagogical 50% normalization uncertainty
rather than a full data-driven fake estimate.

### 3.3 Dataset-level comparison

| Property | Legacy v0.4-jet | Active ATLAS H4l v1 |
|---|---|---|
| Experiment and period | CMS 2015 | ATLAS 2015+2016 |
| Collision energy | 13 TeV | 13 TeV |
| Data type | Full-detector simulation | Education-release data and simulation |
| Label source | Generator-matched top and declared QCD process | Simulated signal/background process groups; real data have no target |
| Object granularity | AK8 jets and particle constituents | Four-lepton events and derived event features |
| Canonical data | Full-D HDF5 particle tensor after compact ROOT extraction | Event-level Parquet |
| Formal data volume issue | 3.542 TiB candidate corpus and uncertain selected-top yield | Smaller derived ntuples but limited four-lepton event statistics |
| Access boundary | Online PFNs streamed through EOS/XRootD on a qualified host | Explicit HTTPS URLs with checksum verification |
| Real-data safeguard | Not applicable | 120--130 GeV blinded window and mandatory freeze |

The legacy dataset is richer per object but substantially harder to qualify and
process. The active dataset is more tractable for an end-to-end portfolio
analysis, while its educational simplifications prevent experiment-grade
interpretation.

## 4. Research methods

### 4.1 Legacy workflow

```text
Frozen CMS record and PFN manifest
  -> CMSSW 7_6_7 EDAnalyzer
  -> AK8 selection and generator-matched labels
  -> compact flat ROOT
  -> full-D HDF5 tensor with at most 150 constituents
  -> identical A--D column views
  -> configuration-specific OmniLearned fine-tuning
  -> paired test predictions, bootstrap intervals, and controls
```

The split was deterministic at source-file level:

```text
bucket = integer(SHA256(exact canonical PFN bytes)) mod 10
bucket 0 -> test
bucket 1 -> validation
bucket 2-9 -> training
```

The experiment was stage-gated:

| Stage | Purpose | Blocking condition |
|---|---|---|
| E0 | Validate extraction, labels, yields, confounds, leakage, cost, and storage | No training until schema, label, yield, split, and cost gates pass |
| E0.5 | Qualify checkpoint and A--D adapters | No pilot until all views produce finite forward/backward passes and a tiny loss decrease |
| E1 | Pilot A and D at \(10^3\) and \(10^4\) jets per class | No core matrix until runtime and GPU budget are measured |
| E2 | Run A--D at three sizes and three seeds | Preserve paired evaluation and complete planned seeds |
| E3 | Add Deep Sets/PFN and optional initialization controls | Prevent expansion into a broad architecture benchmark |

The provisional E2 matrix contained 36 runs:

```text
4 feature configurations x 3 training sizes x 3 seeds
```

Primary reporting used paired AUC differences. Physics-facing secondary
metrics were background rejection at signal efficiencies of 0.30 and 0.50,
plus `auc_gap_fraction` for data efficiency. Uncertainty combined independent
training-seed variation with at least 1,000 paired bootstrap replicates on
stable test-jet predictions.

This method has strong internal controls for a feature-ablation question.
Identical jets, ordering, masks, splits, and paired predictions reduce
irrelevant variation between A--D. Its weakness is the number of prerequisites
before the scientific matrix can start: source access, extraction correctness,
label validation, checkpoint qualification, adapter behavior, selected yield,
compute, and storage all sit on the critical path.

### 4.2 Active workflow

```text
Frozen direct-HTTPS catalog with SHA-256
  -> chunked ROOT ingestion and fixed four-lepton selection
  -> event-level Parquet with signed yield weights
  -> deterministic 70/10/10/10 simulation split
  -> cut-based, Logistic Regression, XGBoost, and MLP predictions
  -> DDT fitted on calibration-background simulation only
  -> decorrelation, sideband-acceptance, and spurious-signal gates
  -> six-channel binned pyhf workspace
  -> expected fit, analysis freeze, and separately authorized observed fit
```

Simulation events are assigned within each dataset to 70% training, 10%
calibration, 10% validation, and 10% test using a SHA-256 digest of dataset
identifier, file checksum, and entry index. Real events have no target and
cannot enter training. Calibration is reserved for DDT, validation is reserved
for the one-time hyperparameter decision, and the test split remains untouched
until frozen evaluation.

Signed event weights are used only for yields and templates. Training uses the
absolute yield weight followed by class normalization, with signal and
background each contributing total training weight 0.5. Model inputs exclude
four-lepton mass, identities, process labels, truth, and weights.

The DDT score is:

\[
s_\mathrm{DDT}=F_B(s_\mathrm{raw}\mid m_{4\ell},\mathrm{channel}),
\]

where the conditional background CDF is fitted only on calibration-background
simulation. The low and high categories are `[0,0.8)` and `[0.8,1]`. Analysis
freeze is blocked unless:

- background simulation and data sidebands each satisfy
  \(|\rho_\mathrm{Spearman}(s_\mathrm{DDT},m_{4\ell})|<0.05\);
- every valid sideband bin has high-category background acceptance in
  `[0.15,0.25]`;
- the background-only spurious signal is below \(0.2\sigma\).

The active method is less demanding in model architecture but adds analysis
constraints absent from the legacy plan. A classifier can have favorable AUC
and still be rejected because it sculpts mass or produces a spurious signal.
This makes the endpoint more relevant to the intended inference while also
creating a real possibility that the primary ML method cannot pass the frozen
gates.

## 5. Statistical inference, blinding, and systematics

| Topic | Legacy v0.4-jet | Active ATLAS H4l v1 |
|---|---|---|
| Main statistic | Paired AUC delta across feature configurations | Expected profile-likelihood significance difference |
| Additional metrics | ROC AUC, background rejection, `auc_gap_fraction`, auxiliary accuracy | Expected-significance ratio, \(\hat\mu\), confidence interval, weighted ROC-AUC, PR-AUC, background rejection |
| Seed policy | Three seeds for the core matrix; five only for preregistered close comparisons | Five fixed formal seeds for every learned model |
| Resampling | At least 1,000 paired bootstrap replicates | Seed mean, standard deviation, and standard error; likelihood-based fit quantities |
| Likelihood model | None in the core design | Six channels: \(4e\), \(4\mu\), and \(2e2\mu\), each split into low/high DDT |
| Mass templates | Not part of the jet-classification design | 1 GeV bins from 105 through 160 GeV |
| Systematic model | Confound controls for \(p_T\), \(\eta\), and pileup; no physics-yield likelihood | Simulation statistics plus luminosity 2.1%, signal theory 5%, irreducible background 10%, reducible background 50% |
| Blinding | No real-data signal region | 120--130 GeV data window blinded |
| Release gate | Complete E0--E3 evidence and paired predictions | Explicit `--unblind`, valid freeze, matching hashes, and all DDT/spurious-signal gates passed |

The legacy statistical design is appropriate for a controlled classifier
comparison but does not translate performance into expected signal
sensitivity. The active design makes that translation explicit. Its likelihood
is deliberately pedagogical: the uncertainty model is limited and must not be
presented as the full detector and theory treatment of an ATLAS analysis.

The active plan also has a stronger safeguard against data-driven
over-optimization. Real data cannot enter training, the signal window is
blinded, sidebands are restricted to decorrelation validation, and observed
inference requires content-matched freeze evidence. The cost is procedural and
scientific: a failed gate blocks unblinding and cannot be silently repaired by
retuning the model or threshold.

## 6. Reproducibility and engineering

Both plans require deterministic splits, stable event or jet identity, saved
predictions, hashed artifacts, run records, and evidence-derived reports. The
implementation boundaries differ:

| Area | Legacy v0.4-jet | Active ATLAS H4l v1 |
|---|---|---|
| Runtime stack | CMSSW `7_6_7`, compact ROOT/HDF5 conversion, PyTorch-dependent model path, GPU training | Python 3.10--3.12, ROOT-to-Parquet ingestion, scikit-learn/XGBoost, pyhf |
| Environment risk | Historical compiler/container, qualified extraction host, checkpoint license/hash/schema, GPU image | Python package versions, input metadata, weight correctness, DDT and pyhf contracts |
| Formal identity | PFN, run/lumi/event/jet identity | Dataset ID, file checksum, entry index, event ID |
| Artifact chain | Manifest, compact dataset, feature views, checkpoint audit, run records, predictions | Catalog, dataset and split manifests, run record, predictions, DDT calibration, templates, freeze, fit result |
| Failure policy | Stage gates block later experiments | Unknown configuration and data conditions fail closed; failed analysis gates block freeze |
| Publication source | Figures and tables generated from run records | Claims trace to config, catalog, manifests, predictions, freeze, and fit result |

The legacy plan records unusually detailed extraction and checkpoint
provenance for a student-scale ML project. Its reproducibility burden is also a
feasibility burden because reproducing the environment and raw extraction is
part of reproducing the result.

The active plan reduces the model and environment surface and standardizes
event-level Parquet as the canonical data format. It adds stronger controls for
atomic publication, schema validation, completion records, and observed-fit
authorization. Reproducing a formal result still requires external data
ingestion and retained physics artifacts; passing the offline fixture suite
does not satisfy that requirement.

## 7. Resource profile and risk comparison

### Legacy strengths

- The particle-level A--D ladder provides a direct and interpretable
  representation ablation.
- A pretrained backbone, label-efficiency study, and initialization control
  offer higher ML-method novelty than the active tabular study.
- One full-D tensor with nested views and paired predictions minimizes
  preprocessing and test-sample differences between conditions.
- The plan treats extraction cost, checkpoint loading, missing tracks,
  confounds, leakage, and negative results as first-class evidence.

### Legacy limitations

- The 3.542 TiB source boundary, low preliminary selected-top yield, and poor
  local throughput made extraction infrastructure a blocking dependency.
- CMSSW `7_6_7`, the historical global tag, candidate references, and
  generator traversal create a wide qualification surface before training.
- Checkpoint compatibility and configuration-specific adapters can confound
  the intended feature comparison.
- The core matrix requires GPU fine-tuning across features, sizes, and seeds
  before the required model control is added.
- Simulation-only classification cannot validate behavior in real sidebands
  or support an observed physics inference.

### Active strengths

- The research question, cut-based baseline, DDT stage, and profile-likelihood
  endpoint form one coherent analysis chain.
- Real events remain outside training, the signal window is blinded, and
  explicit gates control mass sculpting and spurious signal.
- Compact tabular features and the absence of a deep-learning dependency make
  the formal model matrix easier to run and audit.
- Five fixed seeds, strict weight separation, event alignment, and immutable
  artifact contracts strengthen comparability and traceability.
- The workflow includes expected inference, limited systematic variations, and
  final-state stability rather than stopping at classifier metrics.

### Active limitations

- The education release is not sufficient for an experiment-grade
  measurement and omits parts of the official calibration and systematic
  model.
- Four-lepton event counts are limited, which constrains both training and
  sideband validation.
- The reducible-background treatment is simulated and uses a broad
  pedagogical normalization uncertainty instead of a data-driven estimate.
- XGBoost on engineered event features is less novel as an ML contribution
  than a pretrained particle-cloud representation study.
- DDT can reduce discrimination, and any failed decorrelation,
  sideband-efficiency, or spurious-signal gate blocks the analysis freeze.

## 8. Implementation and evidence status

### 8.1 Legacy status

The pre-migration software baseline recorded:

```text
157 passed, 1 skipped in 9.49s
```

The skip was an optional PyTorch-dependent baseline test. These tests showed
that local implementation and contract layers existed. They did not establish
that the CMS production path or formal experiments had completed.

Formal E0 extraction had not passed. The project produced no retained E1--E3
training matrix, no formal paired prediction result, and no physics
conclusion. The correct status is **archived, not completed**.

### 8.2 Active status

As of 2026-07-26, the active migration implementation and offline fixtures
were rechecked with:

```text
72 passed
documentation validation passed (7 checks)
```

The Python run also emitted non-fatal pyhf deprecation and scikit-learn MLP
convergence warnings. There were no test failures. The current requirements
classify the model, DDT, fit, blinding, artifact, and CLI paths as implemented
or tested.

The following scientific steps remain `planned`:

1. produce the formal five-seed predictions and expected-fit results;
2. create an analysis freeze after all real-sideband gates pass;
3. perform an explicitly authorized observed fit.

The observed 120--130 GeV window remains blinded. No expected or observed
physics result is claimed by this document.

### 8.3 Why test counts are not comparable

The legacy and active suites test different applications, dependencies,
schemas, and contract boundaries. The migration intentionally removed the
CMSSW, particle-view, checkpoint, and legacy experiment modules and added
four-lepton selection, weights, decorrelation, inference, blinding, and new
artifact contracts. The counts `157` and `72` therefore cannot rank scientific
maturity, test quality, or completeness. They only describe the retained suite
for each frozen repository state.

## 9. Overall assessment

The legacy plan is the stronger option if the intended contribution is a
foundation-model and particle-representation study and the required data,
CMSSW, checkpoint, and GPU infrastructure are available. It offers a more
distinctive ML question but places much of the project's risk before the first
formal training result.

The active plan is the stronger option for a bounded computational-physics
portfolio analysis. It trades low-level model novelty for a clearer physics
baseline, real-data blinding, mass-decorrelation validation, profile-likelihood
inference, and a shorter implementation path. Its conclusions must remain
limited to the ATLAS education release and its simplified nuisance model.

The migration is therefore a change in research emphasis:

```text
feature-representation and transfer-learning evidence
  -> classifier utility inside a blinded statistical analysis
```

It should not be described as an empirical victory of one model or dataset.
Neither plan has produced the formal scientific evidence needed for such a
claim.

## 10. Evidence basis

### Active sources

| Source | Evidence used |
|---|---|
| [Research Plan v1.0.0](../research/research-plan.md) | Research question, endpoint, dataset, selection, split, models, DDT gates, and claim boundary |
| [Model Selection](../research/model-selection.md) | Model roles, tuning policy, and interpretation rule |
| [Dataset and Backgrounds](../research/dataset-and-backgrounds.md) | Authoritative records, HTTPS boundary, process policy, weights, and dataset limitations |
| [Statistical Analysis Plan](../research/statistical-analysis-plan.md) | Six-channel likelihood, mass bins, nuisances, endpoints, and unblinding requirements |
| [Software Requirements 2.0.0](../software/requirements.md) | Implemented, tested, and planned status distinctions |
| [ATLAS H4l v1 Migration Plan](../plans/2026-07-25-atlas-h4l-v1-migration-plan.md) | Migration scope, implementation milestones, and clean-break intent |

### Legacy sources pinned to `v0.4-jet`

| Git object path | Evidence used |
|---|---|
| `v0.4-jet:docs/research/research-plan.md` | Authoritative legacy research questions, dataset, A--D features, models, stages, metrics, budget, risks, and claim boundary |
| `v0.4-jet:docs/research/model-selection.md` | Model-role rationale and retained terminology differences |
| `v0.4-jet:docs/research/assessments/cms-2015-miniaodsim-feasibility.md` | Source-corpus, schema, yield, access, and feasibility evidence |
| `v0.4-jet:docs/software/requirements.md` | Legacy software and evidence contracts |
| `v0.4-jet:README.md` | Final archived implementation boundary and deferred formal execution |

Tables and direct plan descriptions in this document are repository facts.
Statements about relative novelty, feasibility, interpretability, and
analysis relevance are comparative assessments derived from those facts. They
are not measured performance results.

## Reproducing the legacy repository state

```powershell
git switch --detach v0.4-jet
python -m pip install --requirement requirements-ci.lock
python -m pip install --no-deps --editable .
python -m pytest -q
```

Use `git switch jet` only when a mutable legacy checkout is required. Do not
force-update or delete either local archive ref.
