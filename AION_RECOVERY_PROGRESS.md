# AION recovery progress

Status: 35 planned references were materialized through a deduplicated acquisition map. The baseline contains 15 candidate states across 10 distinct trees. Static source review is in progress; no imported service was executed and no AION source was published.

## Confirmed engineering evidence

- The CommonJS family uses Express, WebSocket, `sql.js` and Google GenAI. Several reviewed history/memory APIs lack endpoint authentication and require a network-deployment hold.
- The SECOND-TEST patch has 17 members that exactly match FULL(2). Its overlay applicability to FIRST-TEST-FIXED was validated at file level; the `.env` source remains private.
- One production-unified archive requires `src/robot/memoryEngine.js` from several modules but does not contain it. It is therefore not a complete buildable release.
- The r7 family is a substantial redesign around session management, memory ledgers and identity evidence. Its own report does not establish full database-backed test completion.
- The voice application is a separate ESM/HTTP browser system. Its provider-spending and ephemeral-token routes have no visible endpoint authentication; it binds to loopback by default. Local key material is excluded from publication.
- The Python/browser/firmware OMNI and Physical-AI packages, and the React/Prisma robotics package, are separate architectural candidates pending boundary review.

## Publication decision

Raw `.env`, key files, persisted robot databases and any hard-coded credential values remain private. Sanitized histories and repository boundaries are pending a second review. No chronology is inferred from FINAL, FULL or copy suffixes.
