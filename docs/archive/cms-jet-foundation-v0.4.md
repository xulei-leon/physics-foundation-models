# Legacy Project Archive

**State:** archived, not completed  
**Final commit:** `facaa72c3ad095c2f8aaca7e8dbba6ae164a774c`  
**Git tree:** `e2b546c6016249b58a92d1cbb9fc639a48559bff`  
**Annotated tag:** `cms-jet-foundation-v0.4-final`  
**Archive branch:** `codex/archive-cms-jet-foundation-v0.4`  
**Storage:** local Git refs, by explicit user decision; not pushed remotely

## Archived scope

The archive preserves the complete CMS jet foundation-model project tree,
including the CMSSW extractor, A--D feature views, OmniLearned/PET and Deep
Sets/PFN integration, JetClass learning material, configurations, schemas,
tests, notebooks, documentation, reviews, and sprint history.

Its research question studied feature representations for top-tagging against
QCD under a fixed model boundary. The production corpus was intended to be
public CMS 2015 simulation.

## Final evidence state

The pre-migration baseline was:

```text
157 passed, 1 skipped in 9.49s
```

The skip was an optional PyTorch-dependent baseline test. Formal E0 extraction
had not passed, and the project produced no formal training result or physics
conclusion. The correct status is therefore **archived, not completed**.

## Reproduction

```powershell
git switch --detach cms-jet-foundation-v0.4-final
python -m pip install --requirement requirements-ci.lock
python -m pip install --no-deps --editable .
python -m pytest -q
```

The archive branch provides a named mutable checkout, while the annotated tag
is the immutable reference. Do not force-update or delete either local ref.
