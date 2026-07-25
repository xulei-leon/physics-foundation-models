---
name: academic-research-suite
description: >
  Project-specific Academic Research Suite router for particleML research,
  computational physics, four-lepton Higgs classification, HEP machine learning,
  literature review, experiment planning, benchmark interpretation, manuscript
  drafting, paper revision, citation verification, reviewer simulation, and
  research-to-paper workflows. Use when the user asks for research question
  refinement, paper topic scoping, related work synthesis, four-lepton
  experiment design, model-comparison framing, reproducibility planning,
  statistical interpretation, academic writing, reviewer responses, citation or
  integrity checks, or Claude-style ARS aliases such as /ars-plan, ars-plan,
  /ars-outline, /ars-abstract, /ars-lit-review, /ars-citation-check,
  /ars-disclosure, /ars-format-convert, /ars-revision-coach, /ars-revision, and
  /ars-full.
---

# Academic Research Suite for particleML

Use this skill as the Codex entry point for research and writing support in the
particleML project. The vendored Academic Research Skills suite lives under
`ars/`; keep those files as upstream source material and route through this file
first.

## Operating Rules

1. Do not load the whole ARS suite by default.
2. Select one workflow from the router below.
3. Read that workflow's `WORKFLOW.md`.
4. Read only the agents, references, templates, or shared files needed for the
   current stage.
5. Keep all project artifacts, prose, comments, and code in English unless the
   user explicitly asks for a separate translated user-facing summary.
6. Treat upstream Claude Code wording as source material; adapt it to Codex
   behavior using the runtime mapping below.

The internal workflow entry files are named `WORKFLOW.md`, not `SKILL.md`, so
Codex registers only this root router skill instead of exposing every vendored
upstream workflow as a separate skill.

## Project Context

Assume the project is a computational physics research portfolio focused on a
blinded four-lepton Higgs analysis using the ATLAS 2015+2016 education release.

Core project frame:

- Research goal: compare cut-based, linear, boosted-tree, and small neural
  classifiers under a fixed selection and validated mass-decorrelation protocol.
- Primary endpoint: expected profile-likelihood significance improvement of
  XGBoost-DDT relative to the cut-based baseline.
- Dataset: public 13 TeV, 36 fb\(^{-1}\), `exactly4lep` data and simulation,
  ingested from frozen direct-HTTPS manifests into event-level Parquet.
- Statistical model: three final states by low/high DDT category, with binned
  four-lepton mass and limited pedagogical systematic uncertainties.
- Reproducibility: deterministic event hashing, five formal seeds, immutable
  artifacts, schema-validated provenance, and a mandatory analysis freeze.
- Scientific boundary: never present planned experiments as results or describe
  the education release as an experiment-grade discovery or precision analysis.
- Researcher profile: undergraduate computational physics researcher building
  collider-physics ML and statistical-inference expertise.

When giving research advice, connect recommendations to this project frame
instead of producing generic academic-writing advice.

## Workflow Router

Choose the workflow by intent:

| User intent | Read first |
|---|---|
| Research question scoping, literature discovery, systematic review, meta-analysis, fact-checking, HEP ML background synthesis | `ars/deep-research/WORKFLOW.md` |
| Paper outline, abstract, introduction, related work, methods/results prose, citation formatting, AI disclosure, LaTeX/DOCX/PDF formatting guidance | `ars/academic-paper/WORKFLOW.md` |
| Peer review simulation, reviewer calibration, editorial decision, paper critique, re-review after revision | `ars/academic-paper-reviewer/WORKFLOW.md` |
| End-to-end research-to-paper pipeline, staged gates, integrity checks, review/revision/finalization workflow | `ars/academic-pipeline/WORKFLOW.md` |
| Experiment planning, ablation design, code experiment execution plan, statistical interpretation, reproducibility validation | `ars/experiment-agent/WORKFLOW.md` |

If a request spans multiple workflows, start with
`ars/academic-pipeline/WORKFLOW.md` unless the user clearly asks for one phase.

## particleML Routing Overrides

Apply these before the general router:

- If the user has a vague paper topic, tentative title, broad research direction,
  or graduate-portfolio research idea without a clear answerable research
  question, route to `ars/deep-research/WORKFLOW.md` in `socratic` mode.
- If the user asks how to design or compare model experiments, route to
  `ars/experiment-agent/WORKFLOW.md` before drafting prose.
- If the user asks to interpret training curves, AUC tables, Wasserstein
  distances, ablations, or seeded-run results, route to `ars/experiment-agent/WORKFLOW.md`
  and then, only if needed, `ars/academic-paper/WORKFLOW.md` for prose.
- If the user asks for literature on four-lepton Higgs classification,
  mass-decorrelated classifiers, profile likelihoods, or public collider data,
  route to `ars/deep-research/WORKFLOW.md` in literature-review mode.
- If the user asks for a manuscript, proposal, or paper but lacks either a clear
  research question, experiment plan, or preliminary results, do not draft a full
  paper. First produce the missing research plan or evidence checklist.
- If the user asks to prepare application-facing research material, keep the
  output technically honest: distinguish completed work, planned experiments,
  inferred significance, and speculative future direction.

## Paper Topic Scoping Override

If the user says they want to write a paper, thesis, proposal, article, journal
article, or manuscript, but provides only a broad topic, tentative title,
research interest, or "topic/direction" without a clear answerable research
question, route to `ars/deep-research/WORKFLOW.md` in `socratic` mode first.

First response in this path:

1. State that the request is being routed to `deep-research` `socratic` mode
   because the research question is not yet precise.
2. Ask 3-5 narrowing questions using `socratic_mentor_agent` and
   `research_question_agent` guidance.
3. Do not produce an outline, draft, literature review, or full pipeline
   dashboard until the user has converged on at least one candidate research
   question.

Route directly to `ars/academic-paper/WORKFLOW.md` only when the user already
has a clear research question, approved study frame, data/results, literature
matrix, draft, or explicitly asks to skip scoping and proceed to outline or
drafting.

## Claude-Style Alias Router

Codex does not install Claude slash commands, but this package emulates their
intent. If the user's request starts with a slash alias (`/ars-plan`) or a plain
alias (`ars-plan`), strip the alias token, read the matching command recipe, then
route to the workflow below.

The `model:` field in command frontmatter is a Claude routing hint only. Codex
uses the current model unless the user explicitly requests another model.

| Alias | Read command recipe | Then route to |
|---|---|---|
| `/ars-plan`, `ars-plan` | `ars/commands/ars-plan.md` | `ars/academic-paper/WORKFLOW.md` in `plan` mode |
| `/ars-outline`, `ars-outline` | `ars/commands/ars-outline.md` | `ars/academic-paper/WORKFLOW.md` in `outline-only` mode |
| `/ars-abstract`, `ars-abstract` | `ars/commands/ars-abstract.md` | `ars/academic-paper/WORKFLOW.md` in `abstract-only` mode |
| `/ars-lit-review`, `ars-lit-review` | `ars/commands/ars-lit-review.md` | `ars/academic-paper/WORKFLOW.md` in `lit-review` mode; if source discovery and synthesis are required, route to `ars/deep-research/WORKFLOW.md` in `lit-review` mode |
| `/ars-citation-check`, `ars-citation-check` | `ars/commands/ars-citation-check.md` | `ars/academic-paper/WORKFLOW.md` in `citation-check` mode |
| `/ars-disclosure`, `ars-disclosure` | `ars/commands/ars-disclosure.md` | `ars/academic-paper/WORKFLOW.md` in `disclosure` mode |
| `/ars-format-convert`, `ars-format-convert` | `ars/commands/ars-format-convert.md` | `ars/academic-paper/WORKFLOW.md` in `format-convert` mode |
| `/ars-revision-coach`, `ars-revision-coach` | `ars/commands/ars-revision-coach.md` | `ars/academic-paper/WORKFLOW.md` in `revision-coach` mode |
| `/ars-revision`, `ars-revision` | `ars/commands/ars-revision.md` | `ars/academic-paper/WORKFLOW.md` in `revision` mode |
| `/ars-full`, `ars-full` | `ars/commands/ars-full.md` | `ars/academic-pipeline/WORKFLOW.md` |

If the request body after the alias is a vague topic, tentative title, or broad
direction without a clear research question, defer to the paper-topic scoping
override before routing to the alias target mode.

If the Codex client reserves slash-prefixed input before it reaches the model,
tell the user to use the plain alias form, for example `ars-plan my topic`.

## Codex Runtime Mapping

Apply these mappings when using upstream ARS files:

| Upstream wording | Codex behavior |
|---|---|
| Agent Team, agent, dispatch, handoff | Read the referenced `agents/*.md` file as a role or phase prompt and perform that phase inline. |
| Agent tool, Task tool, subagent | Do not spawn agents automatically. Only use Codex subagents when the user explicitly asks for delegation or parallel agents. |
| AskUserQuestion | Ask concise clarification questions, or use Codex structured user input when available. |
| WebSearch | Use Codex web browsing for current facts, source verification, citation checks, journal policies, and external evidence. Provide source links. |
| Bash, Write, Edit | Treat as capability descriptions. Follow Codex safety rules and the user's filesystem constraints. |
| Claude, Claude Code, model-specific wording | Interpret as "the current Codex agent" unless the text is part of a disclosure template or historical example. |
| `ARS_CROSS_MODEL`, `ARS_CROSS_MODEL_SAMPLE_INTERVAL` | Treat as no-op unless the user explicitly asks for cross-model review. Skip unconfigured cross-model report sections instead of inventing results. |
| `S2_API_KEY`, `OPENALEX_POLITE_EMAIL`, `CROSSREF_POLITE_EMAIL` | Treat as optional bibliographic lookup settings. Use only when programmatic reference verification is required. |
| `fresh Claude Code session`, `Claude Code session` | Read as "a new Codex conversation"; preserve Material Passport reset semantics where referenced. |
| `/ars-*` slash command, Claude plugin command | Treat `ars/commands/ars-*.md` as prompt recipes. Codex does not register native slash commands from this package. |
| SessionStart hook, SubagentStop hook, `hooks/hooks.json` | Treat as upstream Claude Code hook metadata only. Do not install or execute Claude hooks unless the user explicitly asks to inspect or port a hook. |

## Agent Prompt Use

When a workflow lists agents:

1. Read the workflow `WORKFLOW.md` to identify the mode and phase.
2. Read the specific `agents/<name>.md` files for the current phase.
3. Treat each agent file as a scoped role prompt with an input/output contract.
4. Produce the phase output in the current conversation unless the user requests
   files.
5. Use `ars/shared/handoff_schemas.md` when a phase hands material to another
   phase.

For multi-review phases, preserve independence by writing each reviewer section
before synthesizing. Do not let the final synthesis erase critical findings from
devil's advocate or methodology roles.

## Canonical Agent Files

Use these exact filenames. Do not invent hyphenated alternatives or rename files
from memory.

`ars/deep-research/agents/`:
`bibliography_agent.md`, `devils_advocate_agent.md`,
`editor_in_chief_agent.md`, `ethics_review_agent.md`,
`meta_analysis_agent.md`, `monitoring_agent.md`,
`report_compiler_agent.md`, `research_architect_agent.md`,
`research_question_agent.md`, `risk_of_bias_agent.md`,
`socratic_mentor_agent.md`, `source_verification_agent.md`,
`synthesis_agent.md`.

`ars/academic-paper/agents/`:
`abstract_bilingual_agent.md`, `argument_builder_agent.md`,
`citation_compliance_agent.md`, `draft_writer_agent.md`,
`formatter_agent.md`, `intake_agent.md`,
`literature_strategist_agent.md`, `peer_reviewer_agent.md`,
`revision_coach_agent.md`, `socratic_mentor_agent.md`,
`structure_architect_agent.md`, `visualization_agent.md`.

`ars/academic-paper-reviewer/agents/`:
`devils_advocate_reviewer_agent.md`, `domain_reviewer_agent.md`,
`editorial_synthesizer_agent.md`, `eic_agent.md`,
`field_analyst_agent.md`, `methodology_reviewer_agent.md`,
`perspective_reviewer_agent.md`.

`ars/academic-pipeline/agents/`:
`claim_ref_alignment_audit_agent.md`, `collaboration_depth_agent.md`,
`integrity_verification_agent.md`, `pipeline_orchestrator_agent.md`,
`state_tracker_agent.md`.

`ars/experiment-agent/agents/`:
`code_runner_agent.md`, `study_manager_agent.md`.

## Shared Resources

Use `ars/shared/` for cross-workflow contracts and quality gates:

- `ars/shared/handoff_schemas.md` defines inter-stage artifact schemas.
- `ars/shared/style_calibration_protocol.md` defines writing voice calibration.
- `ars/shared/mode_spectrum.md` defines fidelity, balanced, and originality
  modes.
- `ars/shared/agents/compliance_agent.md` defines compliance checks.
- `ars/shared/compliance_checkpoint_protocol.md`, `ars/shared/prisma_trAIce_protocol.md`,
  and `ars/shared/raise_framework.md` define integrity and reporting gates.
- `ars/scripts/` contains upstream validators and reference adapters.
- `ars/examples/` contains upstream non-PDF fixtures and templates.
- `ars/docs/design/` contains upstream design specs referenced by ARS protocols.
- `ars/commands/` contains upstream prompt recipes.
- `ars/hooks/` contains upstream Claude hook metadata preserved for traceability.
- `ars/tests/` contains upstream fixture corpora used by validator tests.

When an ARS file points to `shared/...`, resolve it as `ars/shared/...`.
When it points to another workflow, resolve it under `ars/<workflow>/...`.
When it points to root-level `scripts/...`, `examples/...`, or `docs/...`,
resolve it under `ars/scripts/...`, `ars/examples/...`, or `ars/docs/...`.

## Verification Discipline

- Verify claims, citations, references, statistics, journal policies, API
  behavior, and current facts against primary or authoritative sources.
- Never fabricate references. If verification is not possible, mark the item as
  unverified instead of inventing support.
- For HEP and ML papers, prefer arXiv, INSPIRE, journal pages, official dataset
  documentation, and paper repositories over secondary summaries.
- For claims about this repository, inspect the local files and code before
  asserting implementation status.
- Separate evidence, inference, recommendation, and speculation in research
  outputs.
- Do not present planned experiments as completed results.
- Do not overstate physics significance from benchmark deltas without
  uncertainty, repeated seeds, and comparable baselines.

## Output Defaults

- Default to the user's conversation language for explanations, but keep created
  project files in English.
- For staged workflows, show the current stage, required inputs, output artifact,
  and whether the next gate is optional or mandatory.
- For paper and research outputs, make uncertainty explicit and distinguish
  evidence from interpretation.
- For experiment plans, include dataset split assumptions, seeds, metrics,
  baselines, ablations, compute constraints, and reproducibility checks.
- For manuscript work, preserve a sober research tone suitable for physics or
  computational science audiences.
