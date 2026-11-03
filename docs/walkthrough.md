# Executed fixture walkthrough

This is a real execution of a **synthetic fixture demo**, not Enrique's listening
history or a real-data recommendation benchmark. Run the README commands in order.

1. Generate 168 fictional events for six fictional listeners. First import inserts
   168; identical reimport inserts zero. The dashboard's `demo` listener has 28 plays.
2. Train the CPU reference ALS artifact on events before Jan 15, 2026 UTC. Run all
   three methods on the Jan 15–22 validation window, for discovery and repeat tasks.
   The final fixture test window has not been evaluated.
3. Start the local dashboard with `--demo --model artifacts/fixture-model.npz`.
   Confirm the banner says synthetic demo. Default calendar-2026 interval shows
   28 play events, 63 reported minutes from 21 events, and 7 events lacking duration.
4. Inspect top artists and tracks. Recommendations are explicitly marked as catalog
   suggestions with unverified library availability and ALS dot-product scores.
   Save writes separate feedback. No playback or playlist creation occurs.
5. Export a recap SVG with a truthful interval and imported-data coverage. Review
   personal metadata before sharing any future nonfixture card.

Local functional requests and a Chromium browser verified dashboard rendering,
the Save action, and SVG rendering. Ignored artifacts include
`artifacts/fixture-dashboard.png`, `artifacts/fixture-recap.png`, and
`artifacts/fixture-recap.svg`. These are fixture captures only. The browser's first
attempt lacked a Playwright-managed binary; validation used installed Chromium.
No personal-history walkthrough has been recorded, and no public preview exists.
