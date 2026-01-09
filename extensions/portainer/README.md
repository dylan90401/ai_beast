# portainer

Adds Portainer CE for managing Docker services.

Usage:
- Enable/install: `./bin/beast extensions install portainer --apply`
- Generate/restart: `./bin/beast compose gen --apply && ./bin/beast up --apply`
- UI: http://127.0.0.1:${PORT_PORTAINER:-9000}
