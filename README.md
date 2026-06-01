# Reverse Slayer

Reverse-engineering notes, retained artifacts, and a working Next.js browser client for the Anime Slayer Android API.

## Repository Layout

- `anime-next/`: deployed Next.js website and stream proxy.
- `anime-site/`: earlier PHP prototype retained for reference.
- `reports/ANIME_SLAYER_API_HANDOFF.md`: detailed technical handoff.
- `reports/REVERSE_ENGINEERING_REPORT.md`: initial APK and API inventory.
- `reports/api_validator.py`: endpoint validation helper.
- `artifacts/anslayer-v1.5.10-reverse-engineering.tar.xz`: maximum-compression archive containing the APK, apktool output, JADX output, and downloaded Zipline modules.

## Artifact Extraction

```bash
tar -xJf artifacts/anslayer-v1.5.10-reverse-engineering.tar.xz
```

## Website

```bash
cd anime-next
npm ci
npm run build
npm run start
```

The browser client resolves the current Anime Slayer metadata API, expands multi-server records, reproduces the Android backup-CDN token flow, decrypts signed quality links, and proxies direct media through an allowlisted byte-range endpoint.

## Important Note

The upstream service is outside this repository. Hosts, tokens, and provider behavior can change without notice. Read the handoff before modifying the resolver.
