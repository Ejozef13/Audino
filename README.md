# Music Discovery

An offline-first listening analytics and recommendation workbench for Enrique's
Navidrome companion. **First runnable slice, not a finished release.** Current
offline integration format is internal JSON. A version-specific read-only
Navidrome 0.64.2 history adapter is implemented and fixture-tested; its real-server
connection check is pending. Spotify and ListenBrainz adapters remain pending.

To check your server from its local network (password is prompted, not saved):

```sh
.venv/bin/python -m music_discovery navidrome-check --url http://YOUR_NAVIDROME_ADDRESS:4533
```

Follow [the connection and import guide](docs/debian.md) before importing personal
history. This does not enable automatic background collection or exact duration.

The dashboard now defaults to the current year through the time of each request,
with top-five artists/tracks and reported-duration coverage. New trained artifacts
support labeled YouTube search links. Obsidian-compatible year summaries can be
exported without running Obsidian on the server:

```sh
python -m music_discovery export-year --listener demo --timezone America/New_York --output-directory private/notes-demo --demo
```

See [Debian deployment and desktop Obsidian handoff](docs/debian.md) for startup
templates, sync boundaries, and the remaining Navidrome version/collection checks.
These changes do not yet connect to a running Navidrome instance or collect plays.

Python 3.12+. Analytics, web UI, SQLite, and SVG exports use the standard library.
Training/evaluation additionally require `pip install -r requirements-ml.txt`.
The cloud instance already has NumPy 2.3.5; this is not Enrique's desktop or NAS.

```sh
cd /workspace/Audino
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-ml.txt
python -m unittest discover -s tests -v
python -m music_discovery.demo
python -m music_discovery import-events private/demo-events.json
python -m music_discovery serve --demo
```

The development server binds loopback port 8765. It is not a public deployment.
The synthetic dashboard is marked prominently. Import again safely; source event
IDs make identical reimports idempotent. The generator refuses to overwrite files.
To inspect private imports, use a separate database and omit `--demo`.

```sh
mkdir -p artifacts
python -m music_discovery train --cutoff 2026-01-15T00:00:00Z --output artifacts/fixture-model.npz
python -m music_discovery evaluate --model artifacts/fixture-model.npz --start 2026-01-15T00:00:00Z --end 2026-01-22T00:00:00Z --output artifacts/fixture-validation.json
python -m music_discovery serve --demo --model artifacts/fixture-model.npz
python -m music_discovery recap --listener demo --start 2026-01-01T00:00:00Z --end 2026-02-01T00:00:00Z --demo --output artifacts/fixture-recap.svg
```

Stop the previous server before starting another on the same port. Models and
reports refuse overwrite through the CLI. Fixture evaluation is a plumbing check,
not evidence of recommendation quality. No real-data benchmark has run.

## Internal event contract

JSON array of objects with nonempty string fields `source`, `event_id`, `listener`,
`timestamp` (ISO 8601 with offset), `track_id`, `artist`, `title`; optional `album`
and `duration_ms` (reported listening milliseconds, **not track runtime**).
Do not populate duration from runtime when only a play event is known.
IDs must be stable upstream event IDs or source-adapter occurrence IDs. Never
deduplicate by track and timestamp alone: legitimate repeated plays can share them.
Conflicting event IDs reject the entire batch. The internal format deliberately
does not claim compatibility with a vendor export.

Track identity is `(source, track_id)`; cross-source joins are not automatic.
Unicode-normalized artist/title hints are retained for future match review only.
Metadata aliases are currently not reconciled, so top-artist counts may split
spelling variants. Source IDs remain intact. Privacy: raw files, databases, model
artifacts, reports, and credentials belong in ignored `private/` or `artifacts/`.
Exports include listening metadata; inspect before sharing. No audio is downloaded
and no server/database outside this application is accessed.

## Plan for this week's release

1. Runnable offline core and fixture validation (implemented).
2. Verify source documentation/license; acquire a bounded real multi-listener
   subset; freeze a manifest and split boundaries before experiments.
3. Compare popularity, artist affinity, and trained implicit ALS on identical
   chronological protocols. Add metadata cosine similarity as a standalone method
   before any hybrid. Tune only validation; run final test once after decisions.
4. Personal import, feedback review, recap polish, real walkthrough/screenshots.
5. Read-only Navidrome capability probe after a reachable URL is supplied.

See [data and evaluation](docs/experiment.md), [architecture](docs/architecture.md),
and [interview guide](docs/interview.md). No push, deployment, resume claim, or
personal-history publication has occurred.
