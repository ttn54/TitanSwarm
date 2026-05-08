# Domain-less HTTPS via Nginx and Let's Encrypt

## Architecture and Data Flow
We are replacing the direct IP access (http://137.184.161.71:8501) with a production-grade Nginx reverse proxy.

1. **DNS (nip.io):** We will use the wildcard DNS service `nip.io`. The domain `137.184.161.71.nip.io` automatically resolves to `137.184.161.71`.
2. **Nginx Reverse Proxy:** Nginx will listen on port 80 (HTTP) and 443 (HTTPS) on the DigitalOcean droplet.
3. **Streamlit (Backend):** The Streamlit UI continues to run locally on the server on port `8501`. Nginx acts as a middleman, forwarding external HTTPS requests securely to port 8501.
4. **SSL/TLS:** We will use `certbot` to generate a free Let's Encrypt SSL certificate for `137.184.161.71.nip.io`.

## Components to Update
Because this is a server administrative task, it does not involve changes to the Python source code or Pydantic models. Instead, it involves shell commands and a new configuration file on the DigitalOcean server.

*   `nginx.conf` slice for `titanswarm`
*   `certbot` installation and execution.

## Edge Cases and Failure Modes
*   **WebSockets:** Streamlit relies heavily on WebSockets. If Nginx does not explicitly Upgrade connections to WebSockets, the app will refuse to load and say "Please wait". Our Nginx config must include the standard `Connection "Upgrade"` headers.
*   **Rate Limits:** Let's Encrypt limits how many times you can request a certificate for the same domain in a short window. We will do a dry-run test first to ensure everything works.
*   **Firewall:** Port 80 and 443 must be open on the DigitalOcean droplet (e.g., using `ufw`).

## Execution Context
These changes must be run **via SSH on your DigitalOcean droplet**, not on your local development laptop. I will provide the exact script sequence for you to run once you SSH in.