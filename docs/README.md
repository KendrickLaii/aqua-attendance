# Documentation

| Document | Audience | Contents |
|----------|----------|----------|
| [../README.md](../README.md) | Everyone | Architecture, quick start, API/web routes, security |
| [DEPLOY.md](DEPLOY.md) | Operators | Production server: Docker, Caddy, GHCR, seed/reset |
| [CICD-EXPLAINED.md](CICD-EXPLAINED.md) | Developers | How CI, GHCR, and deploy scripts fit together |
| [KNOWN-GAPS.md](KNOWN-GAPS.md) | Maintainers | MVP limitations and planned hardening |
| [../apps/api/README.md](../apps/api/README.md) | Backend | API-only setup and tests |
| [../apps/web/README.md](../apps/web/README.md) | Frontend | Web dev server and attendance pages |
| [../apps/mobile/README.md](../apps/mobile/README.md) | Mobile | Expo scanner app setup |

**Suggested reading order**

1. Root README — understand products vs users and QR flow  
2. App README for the layer you are changing  
3. DEPLOY + CICD when shipping to a server  
4. KNOWN-GAPS before opening the system to the public internet  
