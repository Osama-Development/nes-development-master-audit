# NES Robotics / Xterasys recovery progress

Status: 46 source candidates are tracked; 35 directly reviewed source objects were independently SHA-256 matched. The remaining candidates include omnibus or supporting hardware references and are not counted as semantically complete. No firmware, browser application or physical hardware was executed.

## Confirmed architectural candidates

- Xterasys UI Methods 1–4 are browser/ES-module interfaces. In one reviewed implementation, `websocket-client.js` simulates connection state and latency instead of opening a WebSocket; it must not be described as a live robot transport.
- Engineering Build R2 is a distinct integrated candidate: Node HTTP/WebSocket server, SQLite storage, browser workspace, shared profile/map/runtime modules and ESP32 FreeRTOS firmware.
- R2 defaults live operation off and loopback binding, and includes command gates. Its stored compile report explicitly says compilation was blocked and contains no firmware binary; successful firmware compilation is not claimed.
- R2 also has security and functional risks: an empty admin token authorizes API/WebSocket users; firmware transport is cleartext WebSocket; provisioning exposes an open access point and an unauthenticated save endpoint; backup restores objects but not event history.
- NEXTERASYS FINAL is another server/application family with store, map, robot, simulation, mission and WebSocket modules plus unified firmware.
- NES-Robotics-Source is a TypeScript/React studio family with API, database and provider integration.
- AION NES Robotics is a React/Prisma/realtime candidate shared with the AION boundary review.
- ESP32-CAM and motor-control documents are retained as related evidence until their exact release relationship is proven.

## Publication decision

No canonical single repository or linear release sequence has been selected. Original configuration, tokens, device/network material and persisted databases remain private. Source inventories and merge matrices guide comparison but do not prove behavior. Filename labels such as FINAL, R2 and copy suffixes are not chronology. Public history construction awaits a second security pass, exact tree reconstruction and interface comparison.
