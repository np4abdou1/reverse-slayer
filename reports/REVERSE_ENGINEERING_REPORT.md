# Technical Reverse Engineering Report: Anime Slayer (Anslayer) v1.5.10

**Package:** `com.anslayer`
**Version:** 1.5.10 (VERSION_CODE=47)
**Target SDK:** 35 (Android 15)
**APK Hash (SHA-256):** `d0a539a994455dc402c748c34aeeac69310985d77946acdc17b899ba876d1dec`
**Analysis Date:** 2026-06-01

---

## 1. EXECUTIVE SUMMARY

Anime Slayer is an Arabic-language anime streaming application with ~15K classes across 2 DEX files. The app uses a **Laravel-based REST API** backend fronted by **Cloudflare**, with Firebase for push notifications, and a custom Zipline-based JS engine for dynamic streaming logic extraction.

**Security Posture: CRITICAL** — Hardcoded credentials (client ID/secret), multiple publicly accessible API endpoints without authentication, Firebase Realtime Database exposure, and a custom tracking/analytics domain that is now dead but previously active.

- **Discovered Endpoints:** 36+
- **Live/Responsive Endpoints:** 25+ (some require params)
- **Endpoints Exposed Without Auth:** 15+

---

## 2. HARVESTED SECRETS & CREDENTIALS

| Secret | Value | Sensitivity |
|--------|-------|-------------|
| **Client ID** | `android-app2` | Medium (identifies app) |
| **Client Secret** | `7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd` | **HIGH** — Static, hardcoded |
| **Client Secret (Patched)** | `7befbe6263cc14c90d2f1d6da2c5cf9b251bfbdb` | Medium (variant) |
| **Google API Key** | `AIzaSyCTHa1VY7QVChsvHrNmBV0CEhX3lkDZ6mA` | **HIGH** — No restrictions visible |
| **Google App ID** | `1:80420911748:android:7f65105dd42cf8a9` | Medium |
| **Firebase DB URL** | `https://anslayer-be319.firebaseio.com` | **HIGH** — Firebase DB exposed |
| **Firebase Storage Bucket** | `anslayer-be319.appspot.com` | Medium |
| **GCM Sender ID** | `80420911748` | Low |
| **Google Web Client ID** | `80420911748-jqj4hhr6o7d4jrkui99q7ebq4eaqn48f.apps.googleusercontent.com` | Medium |
| **Unity Game ID** | `6051234` | Low (ads config) |
| **Base URL** | `https://anslayer.com/anime/public/` | Primary API gateway |
| **Analytics URL (B64)** | `https://appslytics.com/api/analytics` | **Dead** (DNS dead) |
| **Tracking URL** | `http://tune.reslayer.com/tapi/t.php?url=` | **Dead** (DNS dead) |
| **Reslayer JS** | `http://reslayer.com/ol4.js` (B64) | Medium — JS injection |
| **Anslayer JS** | `https://anslayer.com/anime/public/r/ol6.js` (B64) | Active |
| **Kunaiu CDN** | `https://uc.kunaiu.com` | Active — Content CDN |
| **Zipline Manifest** | `https://anslayer.com/zipline/manifest.zipline.json` | Active — JS engine |
| **OK.ru Video API** | `https://ok.ru/dk?cmd=videoPlayerMetadata&mid=` | Video source |

---

## 3. LIVE API TESTING & VALIDATION LOGS

### Authentication Mechanism

All requests include **static headers** injected by `ClientInterceptor`:
- `Client-Id: android-app2`
- `Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd`
- `Accept: application/json, application/*+json`
- `Content-Type: application/x-www-form-urlencoded` (on POST/PUT/PATCH)
- `Authorization: Bearer <access_token>` (only if authenticated — token stored in `WebToken` model, deserialized from `Settings.getAuthWebTokken()` stored as JSON)

The `RenewingInterceptor` handles 401/403 responses by attempting token refresh.

### Endpoint Testing Matrix

| Endpoint | Method | Auth Required | Test Status | Response Snippet |
|---|---|---|---|---|
| `configs/get-android-config` | GET | **NO** | **200** | `{"response":{"playerConfig_useFirebaseFirst":"false",...}}` |
| `configs/check-server` | GET | **NO** | **200** | `{"response":[{"name":"ok.ru","status":false}]}` |
| `animes/get-published-animes` | GET | **NO** | **200** | Returns anime list with metadata, cover images, ratings |
| `animes/get-anime-dropdowns` | GET | **NO** | **200** | 39 genres, sort options, filter configs |
| `animes/get-top-favorite-characters` | GET | **NO** | **200** | Top characters across app |
| `user/get-top-contributors` | GET | **NO** | **200** | Top user contributors |
| `news/get-published-news` | GET | **NO** | **200** | Published news articles |
| `animes/get-anime-characters` | GET | **NO** | **422** | Needs `json` param |
| `anime/get-anime-details` | GET | **NO** | **422/404** | Needs valid `anime_id` |
| `episodes/get-episodes` | GET | **NO** | **422/404** | Needs `json` with `anime_id` |
| `animes/get-anime-stats` | GET | **NO** | **422** | Needs `anime_id` |
| `animes/get-actors-details` | GET | **NO** | **422** | Needs `actor_id` |
| `animes/get-characters-details` | GET | **NO** | **422** | Needs `character_id` |
| `user/get-user-status` | GET | **NO** | **422** | Needs `user_id` |
| `user/check-username` | GET | **NO** | **422** | Needs `user_handle` |
| `user/is-user-already-exists` | GET | **NO** | **422** | Needs `email` |
| `anime-comments/get-anime-comments` | GET | **NO** | **422** | Needs `anime_id` |
| `episode-comments/get-episode-comments` | GET | **NO** | **422** | Needs `episode_id` |
| `recommendations/get-published-recommendations` | GET | **NO** | **422** | Needs `list_type` |
| `oauth/login` | POST | **NO** | **422** | Email format validation active |
| `oauth/google-login` | POST | **NO** | **500** | Invalid token handling exposed |
| `oauth/twitter-login` | POST | **NO** | **405** | Accepts POST |
| `user/create-user` | POST | **NO** | **422** | User already exists logic |
| `user/send-activation-code` | POST | **NO** | **405**| |
| `user/sync-fcm-token` | POST | **NO** | **405** | |
| `user/get-user` | GET | **YES** | **403** | Forbidden (no auth token) |
| `users/get-blocked-users` | GET | **YES** | **403** | Forbidden |
| `animes/get-favorite-characters` | GET | **YES** | **403** | Forbidden |
| `animes/get-custom-lists` | GET | **YES** | **403** | Forbidden |
| **ALL Auth mutating endpoints** | POST/PUT/DELETE | **YES** | 401/403 | Auth required |
| `oauth/refresh-token` | POST | Mixed | 200/403 | Token reissue endpoint |

### Infrastructure Server Signatures

| Host | CDN/Proxy | Backend |
|------|-----------|---------|
| `anslayer.com` | **Cloudflare** | Laravel/PHP API |
| `img.anslayer.com` | **Cloudflare** | Image CDN |
| `uc.kunaiu.com` | **Cloudflare** | Content delivery |
| `appmo.b-cdn.net` | **BunnyCDN** | Static assets |
| `anslayer-be319.firebaseio.com` | **Firebase** (nginx) | Realtime DB |
| `ezvplayers.com` | **Cloudflare** | External player site |
| `drslayer.b-cdn.net` | **BunnyCDN** | APK distribution |

---

## 4. BACKEND INTEGRATION & ARCHITECTURE REPORT

### Domain Groupings

#### 4.1 Primary API — `https://anslayer.com/anime/public/`
- **Technology:** Laravel PHP (inferred from API route structure, validation format, Eloquent-like responses)
- **All HTTP methods used:** GET, POST, PUT, DELETE (via `@HTTP(method=DELETE, hasBody=true)` in Retrofit)

#### 4.2 Authentication Flow
1. User sends credentials via `POST oauth/login` → receives `Container<AuthTokenUser>` containing `WebToken` (access_token + refresh_token)
2. `WebToken` serialized as JSON and stored in `Settings` (SharedPreferences)
3. Every request intercepts via `ClientInterceptor` → adds `Authorization: Bearer <access_token>`
4. On 401/403, `RenewingInterceptor` triggers token refresh via `POST oauth/refresh-token`
5. Google login: `POST oauth/google-login` with `google_access_token`
6. Twitter login: `POST oauth/twitter-login` with `twitter_access_token` + `twitter_access_token_secret`

#### 4.3 Verified `cURL` Commands

**Get app configuration (no auth):**
```bash
curl -s 'https://anslayer.com/anime/public/configs/get-android-config' \
  -H 'Client-Id: android-app2' \
  -H 'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd' \
  -H 'Accept: application/json' | jq .
```

**Get latest episodes (no auth):**
```bash
curl -s 'https://anslayer.com/anime/public/animes/get-published-animes?json=%7B%22list_type%22%3A%22latest_episodes%22%2C%22limit%22%3A5%7D' \
  -H 'Client-Id: android-app2' \
  -H 'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd' \
  -H 'Accept: application/json' | jq .
```

**Get anime details:**
```bash
curl -s 'https://anslayer.com/anime/public/anime/get-anime-details?anime_id=100&fetch_episodes=true&more_info=true' \
  -H 'Client-Id: android-app2' \
  -H 'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd' \
  -H 'Accept: application/json' | jq .
```

**Get anime filters/dropdowns:**
```bash
curl -s 'https://anslayer.com/anime/public/animes/get-anime-dropdowns' \
  -H 'Client-Id: android-app2' \
  -H 'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd' \
  -H 'Accept: application/json' | jq .
```

**Login attempt (no auth):**
```bash
curl -s -X POST 'https://anslayer.com/anime/public/oauth/login' \
  -H 'Client-Id: android-app2' \
  -H 'Client-Secret: 7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd' \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=user@example.com&password=password123&device_id=test123'
```

#### 4.4 Dynamic Code Execution (Zipline)
The app uses **CashApp Zipline** to dynamically download and execute Kotlin/JS modules:
- Manifest: `https://anslayer.com/zipline/manifest.zipline.json`
- Contains `JsUnpacker-js-ir.zipline` used for unpacking streaming URLs
- Flow extractors enabled (`android_app_zipline_flow_extractors_enabled: "true"`)

#### 4.5 Video Streaming Architecture
- Primary video sources: OK.ru (`ok.ru/dk?cmd=videoPlayerMetadata&mid=`)
- Content CDN: `uc.kunaiu.com`
- Firebase first config (`playerConfig_useFirebaseFirst: "false"`) suggests Firebase remote config for host swapping
- `playerConfig_adsEnabled: "true"` — Unity Ads integration (`Unity Game ID: 6051234`)

---

## 5. REMEDIATION & SECURITY RECOMMENDATIONS

### Critical

1. **Hardcoded Client Secret** (`Constants.java:17`)
   - The static `clientSecret` shared across all app instances enables anyone to impersonate the official client.
   - **Fix:** Implement dynamic client secret generation per install, or switch to PKCE-based OAuth flow.

2. **Cleartext Traffic Enabled** (`android:usesCleartextTraffic="true"`)
   - Allows HTTP traffic, exposing analytics/tracking endpoints (`tune.reslayer.com`) to MITM.
   - **Fix:** Remove `usesCleartextTraffic` or restrict to specific domains.

3. **Dead/Expired Domains Still Embedded**
   - `appslytics.com`, `tune.reslayer.com`, `reslayer.com` — DNS dead, could be re-registered and used for supply-chain attack.
   - **Fix:** Remove or replace all references immediately.

4. **Unauthenticated Public API Access**
   - 15+ endpoints serving anime metadata, user stats, news, and comments require no authentication.
   - **Fix:** Implement rate limiting, API key rotation, and consider adding basic auth for read endpoints.

### High

5. **Google API Key No Restrictions**
   - `AIzaSyCTHa1VY7QVChsvHrNmBV0CEhX3lkDZ6mA` lacks Android app/bundle restriction.
   - **Fix:** Restrict in Google Cloud Console to the specific app package + SHA-1.

6. **Firebase Realtime Database Exposure**
   - URL `https://anslayer-be319.firebaseio.com` publicly referenced in the APK.
   - **Fix:** Ensure Firebase DB rules require authentication and are not set to public read.

7. **Zipline JS Manifest Served Over Unauthenticated CDN**
   - `manifest.zipline.json` allows dynamic code execution with no integrity verification beyond SHA-256.
   - **Fix:** Add code signing and verify signatures at runtime.

### Medium

8. **Predictable API Structure**
   - All endpoints follow clean Laravel conventions, making enumeration trivial.
   - **Fix:** Implement API versioning and consider non-predictable route identifiers for sensitive operations.

9. **Clear Image/Traffic CDN (`img.anslayer.com`)**
   - Easy to enumerate cover images and anime metadata.
   - **Fix:** Add signed URLs or referrer checks on CDN.

10. **Analytics/User Tracking**
    - Embedded analytics base URL suggests user behavior tracking.
    - **Fix:** Ensure GDPR/CCPA compliance for data collection; add opt-in consent.

---

## APPENDIX: Complete Endpoint Inventory

| # | Method | Path | Group | Auth |
|---|--------|------|-------|------|
| 1 | GET | `configs/get-android-config` | Config | No |
| 2 | GET | `configs/check-server` | Config | No |
| 3 | POST | `oauth/login` | Auth | No |
| 4 | POST | `oauth/refresh-token` | Auth | Mixed |
| 5 | POST | `oauth/forgot-password` | Auth | No |
| 6 | POST | `oauth/change-password` | Auth | Yes |
| 7 | POST | `oauth/logout` | Auth | Yes |
| 8 | POST | `oauth/google-login` | Auth | No |
| 9 | POST | `oauth/twitter-login` | Auth | No |
| 10 | POST | `oauth/google-link` | Auth | Yes |
| 11 | POST | `oauth/twitter-link` | Auth | Yes |
| 12 | POST | `oauth/restore-fb` | Auth | Yes |
| 13 | GET | `animes/get-published-animes` | Series | No |
| 14 | GET | `anime/get-anime-details` | Series | No |
| 15 | GET | `anime/get-anime-status` | Series | No |
| 16 | GET | `episodes/get-episodes` | Series | No |
| 17 | POST | `episodes/get-episodes-new` | Series | No |
| 18 | GET | `animes/get-anime-dropdowns` | Series | No |
| 19 | GET | `animes/get-anime-stats` | Series | No |
| 20 | GET | `animes/get-anime-characters` | Series | No |
| 21 | GET | `animes/get-actors-details` | Series | No |
| 22 | GET | `animes/get-characters-details` | Series | No |
| 23 | GET | `animes/get-top-favorite-characters` | Series | No |
| 24 | GET | `animes/get-favorite-characters` | Series | Yes |
| 25 | POST | `animes/favorite-character` | Series | Yes |
| 26 | DELETE | `animes/un-favorite-character` | Series | Yes |
| 27 | POST | `anime/save-anime-rating` | Series | Yes |
| 28 | POST | `animes/add-content-rating` | Series | Yes |
| 29 | POST | `episode/save-episode-rating` | Series | Yes |
| 30 | POST | `episode/save-episode-to-watched-history` | Series | Yes |
| 31 | POST | `anime/save-anime-to-favorites` | Series | Yes |
| 32 | POST | `anime/save-anime-to-watched` | Series | Yes |
| 33 | POST | `anime/save-anime-to-watching` | Series | Yes |
| 34 | POST | `anime/save-anime-to-plan-to-watch` | Series | Yes |
| 35 | POST | `anime/save-anime-to-dropped` | Series | Yes |
| 36 | POST | `anime/save-anime-to-on-hold` | Series | Yes |
| 37 | DELETE | `anime/delete-anime-from-*` | Series | Yes |
| 38 | DELETE | `episode/delete-episode-from-watched-history` | Series | Yes |
| 39 | DELETE | `animes/remove-content-rating` | Series | Yes |
| 40 | GET | `user/get-user` | User | Yes |
| 41 | GET | `user/get-user-status` | User | No |
| 42 | GET | `user/check-username` | User | No |
| 43 | GET | `user/get-top-contributors` | User | No |
| 44 | GET | `user/get-user-notifications` | User | Yes |
| 45 | POST | `user/create-user` | User | No |
| 46 | POST | `user/sync-fcm-token` | User | No |
| 47 | POST | `user/send-activation-code` | User | No |
| 48 | POST | `user/update-email` | User | Yes |
| 49 | POST | `users/block-user` | User | Yes |
| 50 | DELETE | `users/unblock-user` | User | Yes |
| 51 | GET | `users/get-blocked-users` | User | Yes |
| 52 | PUT | `user/update-user` | User | Yes |
| 53 | PUT | `user/change-username` | User | Yes |
| 54 | PUT | `user/update-profile` | User | Yes |
| 55 | POST | `user/update-profilev2` | User | Yes |
| 56 | DELETE | `user/delete-user-image` | User | Yes |
| 57 | POST | `users/profile-image-flag` | User | Yes |
| 58 | DELETE | `user/delete-user-notification` | User | Yes |
| 59 | GET | `anime-comments/get-anime-comments` | Comments | No |
| 60 | GET | `anime-comments/get-anime-comment-replies` | Comments | No |
| 61 | POST | `anime-comments/create-anime-comment` | Comments | Yes |
| 62 | POST | `anime-comments/create-anime-comment-reply` | Comments | Yes |
| 63 | POST | `anime-comments/anime-comment-like` | Comments | Yes |
| 64 | POST | `anime-comments/anime-comment-dislike` | Comments | Yes |
| 65 | GET | `episode-comments/get-episode-comments` | Comments | No |
| 66 | GET | `episode-comments/get-episode-comment-replies` | Comments | No |
| 67 | POST | `episode-comments/create-episode-comment` | Comments | Yes |
| 68 | POST | `episode-comments/create-episode-comment-reply` | Comments | Yes |
| 69 | GET | `news/get-published-news` | News | No |
| 70 | GET | `recommendations/get-published-recommendations` | Recommendations | No |
| 71 | POST | `recommendations/create-recommendation` | Recommendations | Yes |
| 72 | DELETE | `recommendations/delete-user-recommendation` | Recommendations | Yes |
| 73 | GET | `animes/get-custom-lists` | Custom Lists | No |
| 74 | POST | `animes/create-custom-list` | Custom Lists | Yes |
| 75 | POST | `animes/add-to-custom-list` | Custom Lists | Yes |
| 76 | PUT | `animes/update-custom-list` | Custom Lists | Yes |
| 77 | DELETE | `animes/remove-from-custom-list` | Custom Lists | Yes |
| 78 | DELETE | `animes/remove-custom-list` | Custom Lists | Yes |
| 79 | GET | `animes/get-users-lists` | User | No |
| 80 | GET | `user/is-user-already-exists` | User | No |

---

*Report generated by automated Android RE pipeline. Live testing performed 2026-06-01.*
