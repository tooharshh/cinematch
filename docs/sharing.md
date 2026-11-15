# Free public demo with Cloudflare

The application stays on your Linux laptop in its existing Podman containers.
Cloudflare Quick Tunnel supplies a temporary public HTTPS URL. No account,
payment card, domain purchase or router port forwarding is needed.

## Start sharing

Install the Linux binary matching your CPU from the [official downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/).
Put the executable at `.runtime/cloudflared` (ignored by Git), install it on your
PATH, or set `CLOUDFLARED_BIN` to its absolute path.

With the existing containers stopped, start them with `podman start backend frontend`.
For a first installation, follow the README first; sharing does not build images
or create a catalog. Then run:

```bash
bash scripts/share-demo.sh
```

Share the printed `https://….trycloudflare.com` address. The URL changes whenever
you create another tunnel. Keep this terminal running; Ctrl+C stops the tunnel
without stopping the application. Anyone with the URL can access CineMatch.
Only the frontend is forwarded, not FastAPI's port or your filesystem.

## Background session configured on the development laptop

The setup uses a transient user service named `siw-share`. To inspect or stop it:

```bash
systemctl --user status siw-share
journalctl --user -u siw-share -n 40 --no-pager
systemctl --user stop siw-share
```

The foreground command above can create a new link later. This transient setup
is not configured to restart after a reboot. Keep the laptop powered, awake and
online; logout may stop user services depending on the system configuration.

## Checks and limitations

Open the public URL on a phone using mobile data. Check movie search, poster
loading and five recommendations. If the page loads but stays disconnected,
inspect tunnel/frontend logs and WebSocket connectivity. Do not disable
Streamlit's CORS or XSRF protections as a workaround.

[Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
have no uptime guarantee, allow 200 in-flight requests, and do not support SSE.
The app uses Streamlit WebSockets; a full browser check is still required.
Laptop sleep or lost internet interrupts access. Keep the local URL and an
offline demo available for your viva.
