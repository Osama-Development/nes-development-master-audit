# NES NEXT recovery progress

Status: 55/55 planned source references were materialized and their SHA-256 values independently matched. Eighteen candidate source trees were extracted without executing imported code. Engineering review and historical ordering remain incomplete.

## Confirmed findings

- V1–V6 packages use a standalone `dist/server.js` runtime. Later gateway packages launch `core/dist/server.js` and build from nested `core/src`.
- Archives labelled V7.1 represent at least two materially different trees. One expanded snapshot includes backup files, pre-change copies and two source roots; it must remain a mixed workspace snapshot until an authoritative runtime path is established.
- `nes-next-complete.zip` is a React/TypeScript and audio-oriented application candidate. Its relationship to the server lineage is not yet proven, so it will not be merged into that history by name alone.
- The reviewed V7.1 gateway runs `scripts/security.cjs` before proxying and its native tests expect login and origin rejection. The nested core service still has a loopback trust boundary that needs separate review; it is inaccurate to label the whole platform unauthenticated.

## Remaining decisions

Chronology, patch preconditions, WebSocket enforcement, build/source consistency and deployable configuration still require review. Reports, databases and any personal-memory content remain private. No source was executed or published, and no repository, tag or release is yet claimed for NES NEXT.
