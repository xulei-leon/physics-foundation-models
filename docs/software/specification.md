# Software Specification 2.0.0

## Canonical event table

Required identity columns:

```text
dataset_id, file_checksum, entry_index, event_id,
is_data, process_group, channel, split
```

The table also contains selection kinematics, feature source values,
`w_yield`, and simulation-only target. Data target and training weight are
null. Kinematic values use GeV and radians.

## Event identity and split

```text
event_id = sha256(dataset_id + "\0" + file_checksum + "\0" + entry_index)
bucket = uint64(first 16 hex digits of event_id) mod 100
```

Buckets 0--69 are train, 70--79 calibration, 80--89 validation, and 90--99
test. Data are assigned `split=data`; they are not hashed into training
partitions.

## Pairing

Enumerate all disjoint partitions of four lepton indices into two
same-flavour opposite-sign pairs. Orient each pair by ascending indices.
Choose \(Z_1\) by `(abs(mll - 91.1876), pair_indices)`, then choose the full
candidate by `(z1_distance, z1_indices, z2_indices)`. This is deterministic
under equal masses.

## Weight semantics

`w_yield` is signed and used only for cutflows, yields, and templates.
`w_train` is non-negative and used only in learned-model fitting. Signal and
all background processes are rescaled so each class has total absolute
training weight 0.5 while retaining within-class process composition.

## Prediction payload

```text
event_id, target, w_yield, raw_score, ddt_score,
channel, m4l, model_name, seed_or_ensemble
```

Prediction rows must align one-to-one by `event_id`. Duplicate, missing, or
reordered rows are rejected before ensembling.

## DDT

Within each final state, start from half-open 5 GeV mass bins over
`[105,160)`. Effective count is
\((\sum w)^2/\sum w^2\) using non-negative calibration weights. Merge a failing
bin with its right neighbor, or with its left neighbor at the upper boundary,
and repeat from low mass until every retained bin reaches 200.

The empirical conditional CDF uses deterministic mid-ranks for tied raw scores.
Application clips values outside a fitted bin's score support to `[0,1]`.

## CLI

```text
particleml catalog validate
particleml dataset build
particleml audit data
particleml run train
particleml decorrelate
particleml evaluate
particleml analysis freeze
particleml fit expected
particleml fit observed --freeze PATH --unblind
particleml report build
particleml contracts validate
```

Each command returns 0 on success, 2 for user/config/contract errors, and 1 for
unexpected execution failures. Observed-fit policy refusal is a contract error.
