# XSportsX QR Device Sync

Phone-to-TV pairing uses a short-lived pairing code rather than placing Xtream/M3U credentials in the QR code.

1. TV requests `GET /pair/start` and displays `qrPayload` as a QR code.
2. Authenticated phone scans the QR and sends `POST /pair/approve` with the pairing code and its authenticated account token.
3. TV sends `POST /pair/complete` with the session ID and one-time device token.
4. The pairing service returns a device ID. The app then obtains the encrypted account configuration through the authenticated account/session layer.

Pairing codes expire after five minutes and are consumed after completion. Credentials are never encoded into the QR payload.
