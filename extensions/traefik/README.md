# Traefik Extension

Reverse proxy and load balancer for production-like deployments.

## Enable

```bash
./bin/beast extensions enable traefik --apply
./bin/beast compose gen --apply
./bin/beast up
```

## Access

- Dashboard: `http://127.0.0.1:${PORT_TRAEFIK_DASHBOARD:-8080}`
- HTTP: `http://127.0.0.1:${PORT_TRAEFIK_HTTP:-80}`
- HTTPS: `https://127.0.0.1:${PORT_TRAEFIK_HTTPS:-443}`

## Features

- Automatic service discovery via Docker labels
- Let's Encrypt TLS certificates (when configured)
- Load balancing
- Path-based routing
- Middleware support (auth, rate limiting, etc.)

## Adding Services to Traefik

Add labels to your service in compose:

```yaml
services:
  my-service:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myservice.rule=Host(`myservice.localhost`)"
      - "traefik.http.services.myservice.loadbalancer.server.port=8080"
```

## Profile

Traefik is only enabled for the `prodish` profile by default.
For local development, direct port mapping is typically simpler.
