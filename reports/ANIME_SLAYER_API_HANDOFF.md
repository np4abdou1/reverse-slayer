# Anime Slayer API and Stream Resolver Handoff

## Purpose

This document is the detailed continuation context for the Anime Slayer reverse-engineering work completed on 2026-06-01. It describes the Android APK, public metadata API, stream-server data model, dynamic Zipline module, encrypted first-party backup CDN, third-party providers, tested episodes, browser implementation, and remaining maintenance risks.

The retained source APK is Anime Slayer `1.5.10` (`versionCode=47`, package `com.anslayer`). The original APK and complete apktool/JADX output are stored in `artifacts/anslayer-v1.5.10-reverse-engineering.tar.xz`.

Original APK SHA-256:

```text
d0a539a994455dc402c748c34aeeac69310985d77946acdc17b899ba876d1dec
```

Compressed artifact SHA-256:

```text
4b550b7cf648b3fff50f7ba95654edc0e5b6ba99bd8048c6d474c3a0cd7c60e4
```

## 1. System Overview

Anime Slayer separates catalog metadata from playback resolution:

1. The Android client queries a public API under `https://anslayer.com/anime/public/`.
2. Episode API records contain one or more `episode_urls`.
3. A `muilt` record expands to a list of third-party providers.
4. A `cdn` record points to a first-party encrypted backup resolver.
5. A downloaded Cash App Zipline Kotlin/JS module interprets stream URLs and presents supported providers.
6. The Android app passes the selected result to its player flow. The browser implementation instead uses HTML5 video for direct files and iframe embeds for provider pages.

The deployed browser client is in `anime-next/`. Its main resolver is `anime-next/src/lib/anslayer.ts`, and its direct-stream byte-range proxy is `anime-next/src/app/api/stream/route.ts`.

## 2. Primary Metadata API

### Base URL and Headers

Base URL:

```text
https://anslayer.com/anime/public/
```

The Android client sends static application headers:

```text
Client-Id: android-app2
Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd
Accept: application/json
```

The browser client uses those headers in `anime-next/src/lib/constants.ts`.

### Catalog Endpoints Used by the Website

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `animes/get-published-animes?json=<encoded-json>` | Lists published anime, latest episodes, and filtered searches. |
| `GET` | `anime/get-anime-details?anime_id=<id>&fetch_episodes=Yes&more_info=Yes` | Loads series metadata and episode list. |
| `POST` | `episodes/get-episodes-new` | Loads current server records for a requested episode. |
| `GET` | `episodes/get-episodes?json=<encoded-json>` | Older fallback episode endpoint. |
| `GET` | `configs/get-android-config` | Loads remote Android feature flags and dynamic values. |

The complete enumerated route inventory is retained in `reports/REVERSE_ENGINEERING_REPORT.md`.

### Episode Lookup Shape

The website requests:

```text
POST episodes/get-episodes-new
Content-Type: application/x-www-form-urlencoded

json={"anime_id":485,"episode_ids":[11150],"limit":1}
```

Important: the displayed episode number is not the API `episode_id`. Always find the exact requested internal episode ID in the response rather than assuming the first returned episode is correct.

## 3. Stream Server Record Types

Episode responses include `episode_urls`. Two server record types matter:

### `muilt`

The misspelling is upstream and intentional. Its URL points to a JSON array of third-party provider URLs. Historical records can contain dead providers, stale domains, deleted files, parked domains, or redirects to unrelated pages.

Example multi URL:

```text
https://a-reslayer.com/la/public/api/f?n=death_note_2006\6
```

The implementation also attempts the canonical `anslayer.com` equivalent and merges unique links because stale and current hosts can expose different subsets.

### `cdn`

The `cdn` record is the first-party backup source. It does not directly return a playable file. It points to a PHP URL carrying anime and episode identifiers:

```text
https://anslayer.com/anime/public/vq.php?f=death_note_2006&e=6|b12
```

The working resolver endpoint is:

```text
https://anslayer.com/anime/public/v-qs.php
```

The browser implementation rewrites the pathname from `vq.php` to `v-qs.php`, preserves the query-derived `f` and `e` values, and submits a generated `inf` field.

## 4. Backup CDN Reverse Engineering

### Why Direct Requests Initially Failed

Fetching `vq.php` directly returns a generic `404`. Posting to `v-qs.php` without the correct APK-native `inf` token also fails. The functional Android path binds requests to official APK metadata and its signing-certificate SHA-1.

The native implementation is in:

```text
lib/x86_64/libnative-lib.so
```

The Java/Kotlin bridge is `DriveUtil`. apktool smali retains the click flow and resolver calls under:

```text
com/anslayer/ui/servers/
com/anslayer/ui/servers/resolver/Cdn.smali
```

### Official APK Identity

```text
Package:      com.anslayer
Version code: 47
Version name: 1.5.10
Certificate SHA-1:
44D8B79265DDBB9C887320F64521A76D72F6D7D4
```

### `google.php` Seed

The token generator first fetches:

```text
https://anslayer.com/anime/public/google.php
```

During testing on 2026-06-01, its raw body was:

```text
84.8.219.65
```

This value must be fetched dynamically. It is an upstream-controlled seed and may change.

### Native `inf` Payload

The native code constructs compact JSON:

```json
{"uhy":"com.anslayer","dma":47,"mvd":"1.5.10","vko":"44D8B79265DDBB9C887320F64521A76D72F6D7D4"}
```

The current TypeScript implementation uses `JSON.stringify`, which emits the same compact field order.

### AES Key Derivation and Encryption

Native `DriveUtil.a(context, googleValue)` derives:

```text
googleValue[0:10] + certificateSha1[0:22]
```

The native AES routine consumes only the first 16 bytes of that derived string. The effective cipher is:

```text
AES-128-ECB with PKCS#7 padding
```

For the observed seed, the effective key is:

```text
84.8.219.644D8B7
```

The encrypted payload is Base64 encoded and wrapped as:

```json
{"a":"<base64 AES ciphertext>","b":"84.8.219.65"}
```

That JSON string is submitted as the `inf` form value.

### Backup Request

The working form post is:

```text
POST https://anslayer.com/anime/public/v-qs.php
Content-Type: application/x-www-form-urlencoded

f=death_note_2006
e=6|b12
inf=<native JSON token>
```

The endpoint returns a Base64 RNCryptor payload.

### RNCryptor Decryption

The backup response uses the standard password-mode RNCryptor v3 binary envelope:

| Bytes | Meaning |
| --- | --- |
| `0` | Version: `3` |
| `1` | Options: `1` |
| `2..9` | Encryption salt |
| `10..17` | HMAC salt |
| `18..33` | AES-CBC IV |
| `34..-33` | Ciphertext |
| Last `32` | HMAC-SHA256 |

The static APK password is:

```text
android-app9>E>VBa=X%;[5BX~=Q~K
```

Derivation and verification:

```text
encryptionKey = PBKDF2-SHA1(password, encryptionSalt, 10000 iterations, 32 bytes)
hmacKey       = PBKDF2-SHA1(password, hmacSalt,       10000 iterations, 32 bytes)
hmac          = HMAC-SHA256(hmacKey, envelope without final HMAC)
plaintext     = AES-256-CBC decrypt(ciphertext, encryptionKey, IV)
```

The plaintext is JSON containing signed media URLs.

### Decrypted Death Note Episode 6 Shape

The decrypted JSON returned three signed first-party URLs:

```text
https://b3.ab-hunter.com:8443/death_note_2006/6/m.mp4?token=...&expires=...&?
https://b3.ab-hunter.com:8443/death_note_2006/6/s.mp4?token=...&expires=...&?
https://b3.ab-hunter.com:8443/death_note_2006/6/h.mp4?token=...&expires=...&?
```

Tokens are temporary. Never hardcode complete signed URLs.

### Quality Mapping

The retained Zipline module includes:

```text
hh.mp4
h.mb4
s.mp4
m.mp4
```

The literal `h.mb4` appears to be an upstream Zipline typo. Actual tested API output uses `h.mp4`.

Based on Zipline constants, Android presentation, and tested file sizes:

| Filename | Browser label | Meaning |
| --- | --- | --- |
| `m.mp4` | `back_up_server - low` | Mobile / lowest bandwidth |
| `s.mp4` | `back_up_server - medium` | Standard quality |
| `h.mp4` | `back_up_server - high` | High quality |
| `hh.mp4` | `back_up_server - very high` | Optional very-high quality when returned |

The resolver accepts optional `hh.mp4` even though tested Death Note and One Piece responses returned only three qualities.

## 5. Dynamic Zipline Module

Anime Slayer downloads and executes Cash App Zipline Kotlin/JS modules. Retained files:

```text
stream-server-backend-presenters.zipline
JsUnpacker-js-ir.zipline
```

The stream presenter module includes extractors such as:

```text
BackupCdn
Goodstream
Lulustream
Mediafire
Okru
Pixeldrain
StreamWish
Streamtape
Telegram
VidMoly
Vidoza
Vinovo
Voe
Zxhulu
```

It also includes:

```text
backupServer
backupUrl
sortServers
getBackupServerQualities
com.sly.bms
```

`com.sly.bms` has no public DNS record and behaves like an internal synthetic marker used to identify the backup server presenter. It is not the actual CDN. The real signed direct media hosts observed during live testing were `b2.ab-hunter.com:8443` and `b3.ab-hunter.com:8443`.

## 6. Third-Party Provider Handling

### Supported Browser Presentation

| Provider | Website label | Browser behavior |
| --- | --- | --- |
| Goodstream | `GDS` | iframe embed |
| MediaFire | `MF - 1080p`, `MF - 720p`, etc. | Scrape temporary direct MP4, then proxy |
| Streamtape | `ST` | Scrape direct file URL, then proxy |
| Vinovo | `VNO` | iframe embed |
| OK.ru | `OK.ru` | Convert to video embed only if availability HTML is valid |
| First-party backup | `back_up_server - low/medium/high/very high` | Generate signed CDN URLs, then proxy |

### Retired or Unusable Legacy Providers

Historical arrays still contain unusable links. The browser resolver filters known failures:

```text
drive.google.com
tune.pk
vidlox.me
uptostream.com
jawcloud.co
streamvid.net
streamhub.ink
highstream.tv
fembed.com/api/source
```

Mixdrop is hidden when its current page does not resolve a valid media target.

### MediaFire

MediaFire episode URLs are page links, not playable media. The website fetches the page and scrapes a temporary URL shaped like:

```text
https://download<digits>.mediafire.com/.../<file>.mp4...
```

Those temporary URLs are routed through `/api/stream`.

### Streamtape

The resolver scrapes Streamtape HTML and builds its temporary direct link. It is also proxied through `/api/stream`.

### OK.ru

Legacy OK.ru links can return HTTP `200` while representing missing content. The resolver rejects HTML containing:

```text
data-movie-id="null"
vp_video_stub __na
```

## 7. Browser Stream Proxy

Direct MP4 URLs are exposed to the player through:

```text
GET /api/stream?url=<encoded-upstream-url>
```

The proxy forwards:

```text
Range
User-Agent
```

It preserves media response headers:

```text
accept-ranges
cache-control
content-length
content-range
content-type
```

Allowed upstream host families:

```text
mediafire.com
*.mediafire.com
streamtape.to
*.streamtape.to
tapecontent.net
*.tapecontent.net
ab-hunter.com
*.ab-hunter.com
```

Redirects are followed manually with the allowlist rechecked at every hop. This prevents the stream endpoint from becoming an unrestricted server-side request proxy.

## 8. Validated Episodes

### Death Note Episode 6

```text
anime_id:   485
episode_id: 11150
slug:       death-note-6
```

The phone APK presented three server records: two dead third-party providers and one working backup server with three qualities.

Public website validation after implementation:

| Quality | CDN file | Result |
| --- | --- | --- |
| Low | `m.mp4` | `206 video/mp4`, valid `ftypmp42` MP4 header |
| Medium | `s.mp4` | `206 video/mp4`, valid `ftypmp42` MP4 header |
| High | `h.mp4` | `206 video/mp4`, valid `ftypmp42` MP4 header |

### One Piece Episode 1164

```text
anime_id:   2025
episode_id: 86555
slug:       one-piece-1164
```

Visible provider set after implementation:

```text
GDS
MF - 1080p
MF - 720p
ST
VNO
back_up_server - low
back_up_server - medium
back_up_server - high
```

All three backup files returned `206 video/mp4` with valid MP4 headers through the public proxy. MF and ST direct proxy behavior was also validated earlier with ranged responses.

## 9. Current Android Remote Configuration Observations

Observed values on 2026-06-01:

```text
android_app_anime_add_baseUrl: https://uc.kunaiu.com
android_app_allow_bserver: disable
android_app_key: Z25zcmZhZy1naGgyPkU8Vg==
```

Decoded `android_app_key`:

```text
gnsrfag-ghh2>E<V
```

Native `DriveUtil.b` appends:

```text
Ba=L%;]3BJ~+N~K
```

This transformed config key is relevant to the newer multi-server `/fw` decrypt flow. It is distinct from the older hardcoded RNCryptor backup-CDN password used by `Cdn.getQualityLinks`.

The remote flag spelling and value do not fully explain phone behavior: a phone APK still exposed a working backup resolver while the observed config said `disable`. Treat the backup endpoint itself as authoritative and degrade gracefully if it fails.

## 10. Multi-Server `/fw` Flow

Decompiler analysis of `ServerViewModel` found a separate encrypted expansion path:

1. Extract `n` from a source URL.
2. Generate `inf` using `ServerUtil`.
3. Rewrite `/f2` to `/fw`.
4. POST form fields including `n` and `inf`.
5. Decrypt the result with `RNCryptorNative.decrypt(response, DriveUtil.b(android_app_key))`.
6. Parse the resulting provider URL list.
7. Pass URLs to Zipline for presenter selection and sorting.

The website currently merges JSON arrays from the supplied multi URL and the canonical `anslayer.com` equivalent. The `/fw` flow is documented for future maintenance if upstream removes the JSON-compatible route or requires its encrypted replacement.

## 11. Deployment and Verification

Production service:

```text
/etc/systemd/system/anime-next.service
```

Public website:

```text
https://anime.joy-boy.tech
```

Build:

```bash
cd anime-next
npm ci
npm run build
```

Service restart:

```bash
sudo systemctl restart anime-next.service
systemctl is-active anime-next.service
systemctl is-enabled anime-next.service
```

The project builds successfully. `npm run lint` still reports older project-wide lint debt, including existing loose `any` typing and React lint findings not introduced by the backup resolver.

## 12. Maintenance Guidance

When playback breaks:

1. Test the exact phone APK episode and compare displayed server names.
2. Query `episodes/get-episodes-new` for that internal episode ID.
3. Check whether the response includes `cdn`, `muilt`, or both.
4. Fetch `google.php` dynamically and regenerate `inf`.
5. POST to `v-qs.php`, verify RNCryptor HMAC, and inspect the decrypted JSON.
6. Test each signed URL with `Range: bytes=0-127`.
7. Require `206`, a video content type, and an MP4 header before claiming success.
8. Recheck proxy allowlists before adding any new direct CDN family.
9. Preserve dead-provider filtering so stale links do not appear as functional buttons.
10. Reinspect the latest Zipline manifest if provider naming or quality suffixes change.

Do not hardcode signed backup links or `google.php` output. Both are upstream-controlled and can rotate.
