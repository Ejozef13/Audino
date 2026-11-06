# Debian VM deployment and Obsidian handoff

Status: year-to-date calculations, managed Markdown exports, and YouTube search
links are implemented and tested locally. The included systemd units are templates;
they have not been installed or boot-tested on your Debian VM. No Navidrome collector
is connected. Running these units does not magically obtain listening events.

## Placement

Navidrome runs in Docker on Debian, hosted by Proxmox. Leave that installation,
its database, volumes, audio files, and the Proxmox host unchanged. The smallest
companion deployment is a separate Python process managed by Debian's systemd;
it can coexist with Docker without joining or changing Navidrome's container.
No public port forwarding is needed. No cloud-to-LAN route is configured here.

Prepare a dedicated `music-discovery` system account and an application checkout at
`/opt/music-discovery` on the Debian VM, owned by the administrator. Create a venv,
install `requirements-ml.txt`, and run the README test commands there. The current
changes must first be transferred or committed/pushed; do not assume the GitHub
main branch already includes uncommitted local work.

Copy `deploy/settings.example` to `/etc/music-discovery/settings` and set the exact
listener ID used by imported events, plus your calendar timezone. Keep one
canonical timezone for the annual recap. Create `/var/lib/music-discovery` owned
by `music-discovery`, mode 0700. Use a fresh private database; never copy the fixture
database as personal history.

After reviewing the templates, install `deploy/music-discovery-*.service` and
`deploy/music-discovery-notes.timer` into `/etc/systemd/system`. Run:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now music-discovery-web.service music-discovery-notes.timer
sudo systemctl status music-discovery-web.service music-discovery-notes.timer
sudo journalctl -u music-discovery-notes.service --since today
```

These administrative steps are for the VM; they have not been executed from Codex.
Stop/disable only these companion units to undo startup registration. Do not stop
Navidrome. The web service binds loopback port 8765 and restarts after failures.
The timer regenerates notes every five minutes while the VM runs. SQLite files
and generated notes persist under `/var/lib/music-discovery`; live processes do not
need to survive shutdown. Back up that application directory separately from audio.

For desktop access, use an SSH local forward to the Debian VM:

```sh
ssh -N -L 8765:127.0.0.1:8765 YOUR_VM_SSH_USER@YOUR_VM_ADDRESS
```

Open your desktop's local port 8765. This avoids exposing the unauthenticated
development dashboard. A future authenticated LAN deployment needs a proper web
server and access control; this prototype does not provide that yet.

## Obsidian is a reader, not the server

The VM writes Markdown under `/var/lib/music-discovery/notes`. Obsidian can remain
only on the desktop. Choose or create an actual Obsidian vault folder there; the
application installation path is not a vault. Later, copy/sync the generated notes
into a dedicated `Music Discovery` subfolder using a method you already trust.
Do not mount or sync the whole vault into the service. This step needs your chosen
vault folder and sync method; no sync has been configured or claimed.

Files are named `Listening-YEAR-LISTENER_HASH.md` to keep listener exports separate.
Only files with the managed marker are refreshed; unmanaged notes and symlinks are
refused. Keep personal annotations in separate notes. The hash is a filename scope,
not anonymization. Files contain private listening metadata. The exporter is not
an LLM and does not read other vault notes, run their instructions, or upload them.

Try the exporter locally with fixtures, independently of deployment:

```sh
python -m music_discovery export-year --listener demo --year 2026 --timezone America/New_York --output-directory private/notes-demo --demo
```

Default web view is the current calendar year through the time of the request;
refresh to see newly imported events. Historical years export full calendar
intervals. Future-year requests are rejected. No need to wait until December.

## Required Navidrome check before live collection

On the Debian VM, identify the actual image/version without dumping environment
variables or container configuration (which could contain credentials):

```sh
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

Also read the Navidrome About/version display. Your screenshot establishes an
address and a Recently Added view, not an installed version or full library status.
Share only the relevant container name/image tag and application version, without
tokens or passwords. A floating image tag alone does not prove the running version.

Primary source inspected: Navidrome commit
`7c1e68a1e4e68e7257affba4f25cd9cb545c7016`:

- `conf/configuration.go`: ListenBrainz BaseURL/Enabled configuration and optional scrobble history.
- `adapters/listenbrainz/client.go`: token validation, playing_now and single submissions.
- `adapters/listenbrainz/agent.go`: scrobble timestamps and metadata duration construction.
- `server/nativeapi/native_api.go`, `model/scrobble.go`: a native scrobble endpoint with IDs and timestamps.

These are current source capabilities, not proof of your installed version's API.
The ListenBrainz `additional_info.duration_ms` sent by Navidrome is **track runtime**
(`track.Duration * 1000`), not observed listening time. It must not be imported into
our reported listening-duration field. A scrobble has a threshold; it is not every
play-button press or proof of complete playback. `playing_now` must not become a
completed-play event. A reliable adapter must preserve source IDs or explicitly
report ambiguity when submissions have no unique event identifier.

Next integration choice depends on your version: a supported read-only scrobble
history endpoint, or an explicitly configured local scrobble receiver. Do not
change Navidrome's settings, redirect existing external scrobbling, or enable
history until its installed behavior and your existing setup are checked. Polling
aggregate play counts alone cannot reconstruct annual event timestamps or exact
time. No historical recovery is promised when the original data was not retained.

## YouTube and learning

New model artifacts contain training-cutoff track titles. The UI turns those into
properly encoded YouTube search links; opening a link sends that artist/title query
to YouTube. No video match, playable local file, or external catalog coverage is
claimed. Old artifacts still load; retrain them to add titles. The current real-data
training and evaluation remain pending; fictional fixtures are not personalized
recommendations for Enrique.
