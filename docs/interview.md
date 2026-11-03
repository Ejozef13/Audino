# Interview guide and portfolio claims

**Why implicit feedback?** A listen is observed behavior with ambiguous intent.
Counts indicate confidence, not a star rating. We avoid deriving skips or completion
from data that does not provide them.

**What does matrix factorization learn?** Each listener and track gets a short
vector. Similar listening patterns influence these learned vectors; their dot
product ranks candidates. ALS alternately solves for listener vectors while track
vectors are fixed, then the reverse. Factors need not represent named genres.

**Why compare with popularity?** A simple baseline can win. Popularity exposes how
much a trained model adds under the same cutoff and candidate rules. Artist affinity
asks whether merely revisiting a listener's preferred artists already works well.

**Why chronological splits?** Deployment knows the past. Random splits can let
future popularity and user preferences influence predictions. Even metadata or
candidate construction can leak future observations. All current model features
come from rows before the training cutoff.

**Why separate discovery and repeat listening?** Their eligible items differ.
Recommending a familiar favorite can predict a repeat listen but cannot count as
an undiscovered-track success. Neither test proves enjoyment.

**What do Recall and NDCG miss?** Recall measures retrieved relevant targets; NDCG
rewards getting them near the top. Both depend on candidate universe, users,
exclusions, and K. They do not directly measure delight, diversity, fairness, or
causality. Report those denominators alongside metrics.

**What happens at cold start?** Unknown listeners get a labeled popularity fallback.
Unseen items have no collaborative vector and cannot enter the current artifact.
Metadata similarity could address that limitation once an external catalog exists.

**What failed?** On the synthetic smoke dataset ALS can lose to simple baselines.
Those results validate honest reporting, not real-world quality. Real benchmark
failure analysis remains pending; do not invent a story about improvements.

**What is completed for a resume?** A truthful draft bullet is:

> Built a Python/SQLite listening analytics prototype with idempotent event imports,
> timezone-aware statistics, SVG recap exports, and a CPU implicit-ALS experiment
> pipeline; validated core behavior with six automated tests and local browser checks.

Real-user evaluation, Navidrome integration, measured recommendation gains, and
public-data training are pending and must not appear as completed achievements.
Public bio, if needed: Enrique, George Mason University CS student, expected
graduation May 2028; GitHub Ejozef13. No public bio is published by this project.
