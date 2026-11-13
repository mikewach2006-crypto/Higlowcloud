# HiglowCloud Android Builds — private beta

## Architecture

HiglowCloud is the owner-facing build control plane. The existing Codemagic app is the Android build executor. The existing Render API remains in place and does not compile APKs.

- Dashboard: `/android-builds/`
- API: `/api/v1/android-builds`
- Source: `mikewach2006-crypto/HiglowBiz`, branch `main`
- Codemagic application ID: `6af6e0a644d39155bd54ea5f`
- Codemagic workflow key: `nenva-android`
- Workflow display name: `Nenva Android production release`
- Outputs: signed unified Nenva APK and signed standalone Nenva Call APK
- Build machine: existing `mac_mini_m2` selection in `codemagic.yaml`

HiglowCloud sends a build request to Codemagic, stores the returned build ID in its database, polls build status when the dashboard is open, and streams selected APK artifacts through an authenticated HiglowCloud download endpoint. The long-lived Codemagic API token is stored only in the existing HiglowCloud API Render environment.

## Existing release signing — reuse, do not replace

The HiglowBiz repository's existing `codemagic.yaml` already references the Codemagic variable group `nenva_release` and decodes the persistent `NENVA_ANDROID_KEYSTORE_BASE64` into the build VM. It uses these secure variables:
- `NENVA_ANDROID_KEYSTORE_BASE64`
- `NENVA_ANDROID_KEYSTORE_PASSWORD`
- `NENVA_ANDROID_KEY_ALIAS`
- `NENVA_ANDROID_KEY_PASSWORD`

The existing keystore was created as `nenva-release.jks`, with alias `nenva-release`. Do not generate a replacement keystore, change the alias, or copy signing secrets into HiglowCloud, GitHub source, or the Android app. The signing operation stays entirely inside Codemagic.

The same existing Codemagic variable group also contains `GITHUB_TOKEN`, used by the current workflow to publish the Nenva release assets/checksums to the HiglowBiz GitHub repository.

A successful build with `apksigner verify` and the existing release key is the final proof that the stored signing material is valid. The dashboard must not claim signing is verified merely because the variable group is referenced.

## One-time Codemagic API connection

1. Open [Codemagic account settings](https://codemagic.io/settings).
2. Create or copy the personal API token.
3. Open the existing **HiglowCloud API** web service in the [Render dashboard](https://dashboard.render.com/).
4. In Environment, add `CODEMAGIC_API_TOKEN` with the token value. Do not place the token in a frontend variable, source file, GitHub secret, chat, or APK.
5. Save and allow the existing Render API service to restart.
6. Sign in to HiglowCloud and open **Android Builds**. The provider status should change to **Codemagic connected**.

Codemagic REST API authentication uses the `x-auth-token` header. The API token is never returned to the browser. See [Codemagic API overview](https://docs.codemagic.io/rest-api/codemagic-rest-api/).

## First signed test

1. Open HiglowCloud `/android-builds/`.
2. Click **Build both signed APKs**.
3. HiglowCloud calls `POST https://api.codemagic.io/builds` with the fixed app ID, workflow key and `main` branch.
4. Codemagic executes the existing workflow: Android SDK setup, unit tests, signed unified and call release builds, package/permission checks, signature verification, SHA-256 checksums and GitHub release publishing.
5. HiglowCloud polls Codemagic's build status and exposes two authenticated artifact downloads when the build completes.
6. Install both APKs on test devices. Verify that updating a previously installed build signed by the same key works without uninstalling it.

The existing Codemagic workflow builds both APKs in one run. The dashboard does not offer a separate debug build path for this release workflow.

## Security and launch limits

- The Codemagic API token stays in Render environment variables and is not exposed to browsers.
- APK downloads are proxied through HiglowCloud and require an authenticated workspace session. The API generates a five-minute Codemagic artifact URL server-side and fetches it without forwarding the API token to the artifact storage redirect.
- The browser never receives the raw Codemagic artifact URL or API token.
- Only workspace owners and admins can start or cancel builds.
- One active build per workspace and five build requests per rolling 24 hours in this private beta.
- No additional Render worker, Docker daemon, local Android Studio, or always-on owner PC is required.
- Build minutes and artifact retention follow the existing Codemagic account plan and limits.
- The current Codemagic workflow also publishes GitHub release assets. Repository/release visibility still governs those GitHub assets; the HiglowCloud authenticated proxy is a separate download path.

## Production readiness

Do not invite external developers until the first successful build is verified, the exact signing certificate fingerprint is recorded, install/update behavior is tested on physical devices, Codemagic usage limits are understood, and the workspace's multi-tenant abuse controls and audit trail have been reviewed.
