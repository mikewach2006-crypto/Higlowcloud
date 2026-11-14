# Nenva Call cloud service

Nenva Call is a separate application service inside HiglowCloud. It does not run on a customer's or operator's PC. Its API is mounted at `/api/v1/nenva-call` and uses the existing HiglowCloud PostgreSQL database connection while keeping Nenva Call identities and records in separate tables.

## Implemented API surface

- `GET /health` and `GET /config`
- `POST /auth/register` — create an account, send email and SMS verification codes, and record acceptance of the Terms and Privacy Policy.
- `POST /auth/verify` — verify email or phone using its separate six-digit code.
- `POST /auth/resend` — resend unverified-channel codes, limited to one request per minute.
- `POST /auth/login` and `GET /auth/me`
- `GET/POST /contacts` — list existing conversations and start a direct conversation by verified email or phone.
- `GET/POST /conversations/{id}/messages` — persistent text messaging with cursor-based polling.
- `POST /calls`, `GET /calls/incoming`, `POST /calls/{id}/accept`
- `POST/GET /calls/{id}/signals` — exchange WebRTC offer, answer and ICE candidate payloads.
- `POST /calls/{id}/end` and `GET /calls/history`

All app endpoints other than health/config and registration/verification/login require the Nenva Call bearer token. Nenva Call accounts are separate from HiglowCloud dashboard accounts.

## Required Render environment

Configure these on the **higlowcloud-api** service. Never put credentials in the Windows/mobile application or commit them to Git.

| Variable | Purpose |
|---|---|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Send email verification codes |
| `AT_USERNAME`, `AT_API_KEY` | Africa's Talking SMS verification |
| `AT_SENDER_ID` | Optional approved SMS sender ID |
| `TURN_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL` | TURN relay configuration for WebRTC calls |

The service defaults to Google's public STUN server only. STUN alone is not enough for reliable calls across all mobile networks, corporate firewalls and restrictive NATs. Configure a real TURN service and test it from multiple networks before public launch. TURN credentials in this initial version are static server environment values; replace them with short-lived TURN credentials before scaling.

## Realtime and scale boundary

Messages and call-signalling events are persisted in PostgreSQL and clients poll for updates. This allows API instances to share message/signalling state, but it is not a push-notification system and it is not yet a low-latency WebSocket delivery service. A production launch should add authenticated WebSocket delivery, Redis pub/sub or an equivalent broker, push notifications, abuse/rate limits, delivery receipts, message retention controls, monitoring and load testing.

Audio/video media is exchanged by WebRTC between clients; this API exchanges call setup/signalling data and does not relay media itself. A TURN service is required for reliable connectivity where direct peer-to-peer connectivity fails.

## Launch checklist

1. Configure SMTP, Africa's Talking and TURN credentials in Render.
2. Deploy the API and confirm `/api/v1/nenva-call/health`.
3. Test registration with real email and phone delivery, then verify both channels.
4. Test messages between two separate accounts.
5. Test audio and video calls across different Wi-Fi/mobile networks with TURN enabled.
6. Integrate these endpoints into the Windows and Android clients.
7. Add privacy/terms review, account recovery, block/report controls, rate limiting, push notifications, monitoring, backups and load tests.
8. Move the API and database to an always-on production plan before relying on it for public calling. Render's free web services can sleep and its free database is not a durable production database.

This API addition does not itself create a Windows installer, deploy a TURN relay, configure provider credentials, or prove calls work end-to-end. Those require the client integration and live provider/network tests above.
