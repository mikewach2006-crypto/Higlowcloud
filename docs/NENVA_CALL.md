# Nenva Call — HiglowCloud integration

## What is included

Nenva Call is included as a separate web entry point in the HiglowCloud frontend and as API routes in the existing FastAPI service.

- Web app: `/nenva-call.html`
- API base: `/api/v1/nenva-call`
- Authentication: reuses HiglowCloud email/password accounts and bearer sessions.
- Contacts: search active HiglowCloud users by name/email and add contacts.
- Messaging: one-to-one messages persisted in the configured SQL database.
- Live events: WebSocket delivery for messages, presence, call offers/answers, ICE candidates and hangups.
- Calling: browser WebRTC audio/video with Google STUN by default and optional TURN configuration.
- Socket security: browser requests a single-use, two-minute socket ticket; the long-lived account bearer token is not put in the WebSocket URL.
- Connection handling: 25-second WebSocket heartbeat and exponential reconnect.

## Deploy from this repository

The frontend Vite build now has two HTML entry points: the existing HiglowCloud dashboard and `nenva-call.html`. The backend includes the `nenva_call` router at startup. Deploy the branch through the existing Render services after reviewing/merging the pull request.

After deployment, open:

`https://higlowcloud.onrender.com/nenva-call.html`

The app uses the same API origin already configured by `VITE_API_URL`. No GitHub Actions or Codemagic build is required for the web app.

## Required runtime configuration for reliable calls

Set these optional environment variables on the HiglowCloud API service when a TURN provider is available:

- `NENVA_TURN_URLS`: comma-separated TURN URLs, e.g. `turn:turn.example.com:3478?transport=udp,turns:turn.example.com:5349?transport=tcp`.
- `NENVA_TURN_USERNAME`: TURN username.
- `NENVA_TURN_CREDENTIAL`: TURN password/credential.

The API exposes these ICE servers only to authenticated users. Never place TURN credentials in frontend source code.

Without TURN, calls use STUN-only connectivity. That can work on many networks, but restrictive NATs, corporate networks and some mobile carriers can prevent media from connecting. A TURN service is required for dependable connectivity across arbitrary networks.

## Current deployment and scale boundaries

- Text messages are stored in the configured SQL database and survive API restarts when that database is persistent.
- WebSocket presence and call signalling are currently held in the API process memory. Run one API instance for this initial implementation. Multiple instances require shared Redis/pub-sub signalling before horizontal scaling.
- The current Render free web service can spin down after 15 minutes without inbound HTTP or WebSocket messages. The client sends a WebSocket heartbeat while open, which keeps an active session from being considered idle, but it does not keep an unused service permanently running. Free Render services are for testing, not production.
- Render free Postgres databases expire after 30 days. Use a persistent database plan before storing real customer conversations.
- Account registration currently uses HiglowCloud's existing email/password system. Separate Nenva Call phone verification, email verification, password reset, privacy/terms acceptance, push notifications, group chats, attachments, encryption beyond TLS/at-rest platform controls, and call history are not implemented in this first integration.
- WebRTC media travels peer-to-peer when possible; otherwise it uses the configured TURN relay. The API only coordinates call setup and does not record call audio/video.

## Test checklist

1. Register two test HiglowCloud accounts or use two existing accounts.
2. Sign in from two separate browsers/devices.
3. Search for the other account by email and add it as a contact.
4. Send messages in both directions and reload to verify persistence.
5. Start an audio call, accept it on the other device, and verify two-way audio.
6. Repeat with video and verify mute/camera toggles and hang-up.
7. Test from different networks. If direct media fails, configure TURN and repeat.
8. Verify reconnect after briefly disconnecting the network.

Do not advertise this as a production-ready large-scale calling service until the above checks pass, TURN is configured, persistent database hosting is active, and shared signalling is added for multi-instance deployments.
