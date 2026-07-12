# TrueBrief on Phones — PWA + Native Shells

*Built 2026-07-12. Architecture: ONE frontend (the existing Next.js app) delivered three
ways — browser, installable PWA, and Capacitor native shells (Android/iOS) whose webview
loads the hosted app. No second codebase, no rewrite. Native projects live in
`frontend/android/` and `frontend/ios/` (committed).*

---

## 1. Install on your phone TODAY (PWA — no store, no build)

The PWA is live the moment the frontend is deployed (or tunneled). It has the app icon,
full-screen mode, and push notifications (existing VAPID web push).

**Android (Chrome):** open the app URL → ⋮ menu → **Add to Home screen / Install app**.
**iPhone (Safari):** open the app URL → Share → **Add to Home Screen**. Push works on
iOS 16.4+ for installed PWAs (Settings → enable notifications when prompted in-app).

### Phone → your PC (before production deploy)

PWA install + push require HTTPS, so use a free Cloudflare tunnel to your local stack:

```powershell
# 1. one-time: winget install Cloudflare.cloudflared
# 2. start backend + frontend as usual (scripts/start-local.ps1 + npm run dev)
# 3. tunnel the FRONTEND:
cloudflared tunnel --url http://localhost:3000
# → prints https://<random>.trycloudflare.com — open THAT on your phone
```

Two config touches for the tunnel origin (revert not needed for prod):
- Railway/local backend env `FRONTEND_URL` must include the tunnel URL (CORS + billing origin check), e.g. `FRONTEND_URL=http://localhost:3000,https://<random>.trycloudflare.com`.
- Clerk dashboard → your dev instance → add the tunnel URL to allowed origins if sign-in complains.
- The frontend must reach the backend from the PHONE: also tunnel the API (`cloudflared tunnel --url http://localhost:8000`) and set `NEXT_PUBLIC_API_BASE_URL=https://<api-tunnel>.trycloudflare.com` in `frontend/.env.local`, then restart `npm run dev`.

**When production is deployed, none of this is needed** — the phone just uses the prod URL.

## 2. Native Android app (APK you sideload, later Play Store)

The Capacitor project is committed and icon-stamped. Building needs Android Studio
(one-time install on any machine) — **no code work remains**.

```powershell
# one-time: install Android Studio (bundles SDK + JDK): https://developer.android.com/studio
cd frontend
# point the shell at prod (default) or a tunnel:
#   $env:CAP_SERVER_URL="https://<random>.trycloudflare.com"   # optional, dev only
npm run cap:sync
npm run cap:android         # opens Android Studio
# Android Studio: Build → Build APK(s) → install on phone via USB or file share
# CLI alternative once SDK is installed:  cd android && ./gradlew assembleDebug
# → android/app/build/outputs/apk/debug/app-debug.apk
```

**Play Store (when ready to publish):** Google Play Console account ($25 one-time) →
Build → Generate Signed App Bundle (keystore wizard in Android Studio — BACK UP the
keystore file, losing it means losing the app listing) → upload AAB → listing (use
landing-page copy + screenshots) → review takes ~1-3 days.

## 3. Native iOS app

`frontend/ios/` is scaffolded and synced. Apple requires a Mac (or a cloud Mac like
MacStadium/Codemagic CI) + Apple Developer Program ($99/yr) to build, sign, and ship:

```bash
# on a Mac:
cd frontend && npm i && npx cap sync ios && npx cap open ios
# Xcode: set your Team under Signing & Capabilities → run on device / archive → TestFlight
```

Same shell, same remote URL — there is no iOS-specific code to write.

## 4. Known limits & the one future task

- **Sign-in inside the native shells:** use Clerk's **email-code** sign-in. Google OAuth
  blocks embedded webviews; if Google sign-in in-app is ever required, add
  `@capacitor/browser` and open the OAuth flow in the system browser (documented pattern,
  ~half a day).
- **Push inside the native shells:** webviews don't support Web Push (PWA push works
  fine). For store-app push, add `@capacitor/push-notifications` + Firebase FCM (Android)
  / APNs (iOS) and a backend sender alongside `src/truebrief/push/`. Defer until the
  store apps matter — the PWA covers push today.
- `capacitor.config.ts` has `PROD_URL = https://app.truebrief.app` — **update it if the
  deployed frontend lands on a different domain**, then `npm run cap:sync`.

## 5. What each piece is (for future sessions)

| Path | Purpose |
|---|---|
| `frontend/public/manifest.json` | PWA identity (icons, standalone display, shortcuts) |
| `frontend/public/sw.js` | Service worker: push handlers + offline fallback page |
| `frontend/public/offline.html` | Shown when a navigation fails offline |
| `frontend/src/components/PwaRegister.tsx` | Registers the SW for every visitor (installability) |
| `frontend/scripts/generate-icons.mjs` | Rebuilds all web/PWA icons from the inline SVG mark |
| `frontend/scripts/generate-android-icons.mjs` | Stamps launcher icons into the Android project |
| `frontend/capacitor.config.ts` | Native shell config — remote URL, app id `com.truebrief.app` |
| `frontend/mobile-shell/` | Local fallback page bundled into the native apps |
| `frontend/android/`, `frontend/ios/` | The committed native projects |
