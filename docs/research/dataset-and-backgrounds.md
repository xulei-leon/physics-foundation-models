# Dataset and Backgrounds

## Authoritative records

The analysis uses public ATLAS Open Data records:

- [2015+2016 `exactly4lep` data](https://opendata.cern.ch/record/atlas-93924)
- [2015+2016 `exactly4lep` simulation](https://opendata.cern.ch/record/atlas-93928)
- [13 TeV variable definitions](https://opendata.atlas.cern/docs/data/for_education/13TeV25_details)

Catalog generation performs direct HTTPS GET requests. It does not use an
implicit discovery service or a remote filesystem protocol. The frozen catalog
is the complete allowed input boundary.

## Process policy

| Group | Definition | Nominal policy |
|---|---|---|
| Signal | public name includes `H125` and `ZZ4l` or `ZZ4lep` | one nominal generator per production mode |
| Irreducible background | continuum four-lepton production dominated by \(ZZ^*\) | separate template |
| Reducible background | \(Z+\)jets, \(t\bar t\), and declared reducible samples | separate template, 50% normalization nuisance |
| Unknown | no explicit rule match | rejected |

An alternative generator for an already represented production mode is a
systematic comparison. It must not be added to nominal yield.

## Input branches and units

The ingestion boundary expects lepton multiplicity, lepton kinematics, charge,
type, identification, isolation, trigger matching, event trigger bits, jets,
missing transverse momentum, generator weight, cross-section metadata, sum of
generator weights, and object/trigger scale factors.

Kinematic ROOT branches stored in MeV are converted exactly once to GeV during
ingestion. Canonical Parquet data never mix unit systems.

## Weight metadata

Every simulated file must provide cross section, \(k\)-factor, filter
efficiency, sum of generator weights, event generator weight, pileup factor,
electron factor, muon factor, and lepton-trigger factor. A missing or
non-finite value rejects the affected dataset or event. Real data receive
`w_yield=1` only for observed counts and never receive a training weight.

## Limitations

The open ntuples and simplified nuisance model do not reproduce the complete
ATLAS analysis chain. The v1 reducible-background treatment is simulated and
assigned a pedagogical 50% normalization uncertainty; a full data-driven fake
estimate is out of scope.
