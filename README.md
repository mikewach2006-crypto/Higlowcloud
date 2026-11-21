# Higlowbiz Installers

Public download distribution for the Higlowbiz desktop and Android applications.

**This repository contains installers and release information only.** The application source code remains in the private `mikewach2006-crypto/HiglowBiz` repository.

## Downloads

Visit the [Higlowbiz website](https://higlowbiz.co.ke/) or open [Releases](https://github.com/mikewach2006-crypto/Higlowcloud/releases/latest) to download the latest available installers.

- Windows: Higlowbiz Setup (.exe)
- Android: Higlowbiz (.apk)

## Automated builds

The workflow in `.github/workflows/build-installers.yml` checks out the private source repository using the `HIGLOWBIZ_SOURCE_TOKEN` repository secret, builds the installers, and publishes them as public GitHub Release assets.

### One-time setup

A repository administrator must add a GitHub Actions repository secret named `HIGLOWBIZ_SOURCE_TOKEN`. Use a fine-grained personal access token with read-only Contents access to **only** `mikewach2006-crypto/HiglowBiz`.

The Android workflow currently produces a debug-signed APK for direct testing and sideloading. Before treating APK updates as production releases, configure a protected Android release keystore and signing secrets so every version is signed with the same key.

## Privacy

Never commit application source code, API keys, signing keys, passwords, or private configuration to this public repository.
