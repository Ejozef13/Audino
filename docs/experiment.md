# Data and model card — preliminary

## Current evidence

The desktop walkthrough verified a real Navidrome login and imported scrobble,
but personal desktop data is not in this cloud checkout. No licensed public
subset or real-data recommendation benchmark has been run here.
Executed training experiments use `music_discovery.demo.events`:
6 fictional listeners, 18 fictional tracks, 168 events, 2026-01-01–2026-01-28 UTC.
The generator contains no copied listening data, artist names, or copyrighted audio.
It is useful for plumbing tests only. **Do not cite these results as ML quality.**

| Method | Real-data Recall@10 | Real-data NDCG@10 | Status |
|---|---|---|---|
| Popularity | Pending | Pending | Implemented baseline |
| Artist affinity | Pending | Pending | Implemented metadata baseline |
| Implicit ALS | Pending | Pending | Trains and loads; fixture-tested |
| Metadata cosine | Pending | Pending | Deferred until metadata source verified |
| Hybrid | Pending | Pending | No blending before standalone comparison |

The machine-generated fixture comparison is `artifacts/fixture-validation.json`.
It includes all baselines, both ranking tasks, denominators, and failure cases.
Fixture ALS does not consistently outperform simpler baselines. That is not
evidence about real listening; it demonstrates that the report preserves losses.

## Bounded real-data acquisition plan (blocked, not executed)

Candidate: **Last.fm 1K**, creator's primary page:
https://www.upf.edu/web/mtg/lastfm1k . It is a candidate because multi-listener,
timestamped scrobbles can support chronological evaluation. Its license, archive
size, current availability, format, and redistribution rights are **unverified**.
Access currently receives a network-policy 403; do not download a mirror or assert
license terms from memory. No candidate catalog or coverage promise exists yet.

Once allowed, inspect the creator's license and README before acquisition. Reject
the source if terms do not permit this portfolio workflow. Record exact source
URL, retrieval date, license text/URL, archive checksum, byte count, and format in
an ignored manifest. If the archive is large, use a streaming parser with limits
of 32 listeners, 100,000 accepted events, and 512 MiB transferred; stop rather than
silently exceed limits. If truncation prevents complete listener histories, record
that coverage and do not interpret it as complete observation. Sort candidate
listener identifiers deterministically and fix the selected subset in the manifest.
Do not redistribute raw history or publish listener identifiers without confirmed
permission. This is a proposed recipe, not a reproducibility claim for acquired data.

Spotify primary documentation to verify before adding the adapter:
https://support.spotify.com/us/article/understanding-my-data/ . Do not confuse
standard history and Extended Streaming History. ListenBrainz export schema also
remains to be read in https://listenbrainz.readthedocs.io/ . No vendor parser is
claimed. Personal data can personalize a model; one listener is not a population
collaborative-training dataset.

## Model and protocol

Reference implicit weighted ALS: preference `p_ui = 1[count_ui > 0]`, confidence
`c_ui = 1 + 10 log(1 + count_ui)`. Minimize weighted squared error between `p_ui`
and `x_u dot y_i` plus L2 regularization 0.1 by alternating linear solves. Default:
16 factors, 10 iterations, NumPy RNG seed 42. CPU-only; bounded dense matrix limit
2 million user/item cells. This is an educational reference, not a scalable engine.
The maintained `implicit` project's current primary pyproject was inspected:
https://github.com/benfred/implicit/blob/main/pyproject.toml (version 0.7.3,
Python >=3.9). NumPy 2.3.5 is the smaller dependency for this bounded reference;
do not generalize its performance to a production sparse implementation.

Training only reads events strictly before the UTC cutoff; catalog, popularity,
artist weights, user profiles, and ALS features all derive from those rows. Source
IDs are namespaced, and metadata is not joined across sources. Plays imply evidence
of preference, not enjoyment. The absent entries have low confidence, not explicit
dislikes. Models are persisted in NPZ with pickle disabled and JSON metadata.

Before real training, freeze global training/validation/test boundaries in a
manifest after inspecting only data availability, then record the subset checksum,
timestamp coverage, seed, hardware/CPU model, OS, dependency versions, and commands.
The validation runner now freezes a config, compares bounded grids across seeds,
and leaves its final test interval unscored. The standalone evaluation CLI checks
cutoff/window consistency but does not enforce a locked experiment registry or
prevent a human from repeatedly inspecting a test window.
Do not call the final test until hyperparameters and method choices are fixed.

Fixture training cutoff: 2026-01-15T00:00:00Z. Validation: Jan 15 inclusive–Jan 22
exclusive. Jan 22–Jan 29 is reserved; no fixture final-test command was run.
Default eligibility: at least 5 training events and one eligible held-out unique
track. Candidates are the complete training catalog; no negative sampling.
Discovery excludes all training-seen items, while repeat ranking includes only
seen items. Targets outside each task's eligibility are excluded and counted.
Future tracks absent from training cannot be recommended. Unknown users receive
an explicitly labeled popularity fallback; they are reported separately and are
not mixed into the known-user metric denominators. Targets use unique track sets,
so repeated plays do not inflate recall. All methods share this protocol.

Recall@K is hits divided by eligible held-out unique tracks. NDCG@K discounts hits
by `log2(rank + 1)` and divides by the ideal ordering. Metrics are macro-averaged
across eligible listeners. Reports give eligible listener counts, standard error
across listeners (not a causal confidence interval), catalog and artist coverage,
and inference time. Diversity is the fraction of unordered recommendation pairs
with different artist strings. Novelty is mean `-log2` of add-one-smoothed training
play frequency. It measures rarity in this subset, not discovery or enjoyment.

## Outstanding analyses and limits

Real-data license verification, reproducible acquired subset, metadata cosine,
training-popularity decile exposure, cold-start history buckets, multiple seeds,
hardware-specific timings, and personal relevance/save evaluation are pending.
Current cold-start reporting counts unknown listeners and absent tracks only.
Current uncertainty ignores correlation among listeners. Genre support is absent.
User/item sampling changes the population and may distort popularity. Matching
errors, missing metadata, aliases, and exposure bias can dominate model quality.
Predicting a held-out listen does not prove that a recommendation introduced
enjoyable new music. Keep a separate consented relevance/save feedback assessment.
