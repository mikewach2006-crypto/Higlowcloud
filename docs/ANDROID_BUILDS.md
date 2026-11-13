# HiglowCloud Android Builds (private beta)

## Architecture

The HiglowCloud dashboard and API remain on the existing Render deployment. Android build execution is performed by short-lived GitHub-hosted Linux runners started only when a user requests a build. No always-on worker, local PC, Android Studio installation, Docker socket, or additional Render service is required.

- Dashboard: `/android-builds/`
- API: `/api/v1/android-builds`
- Build workflow: `.github/workflows/android-build.yml`
- Source repository: selected through the connected GitHub App installation.
- Initial supported source: private GitHub repositories accessible to that installation.
- Initial targets: `callDebug` and `unifiedDebug`.
- Artifacts: private GitHub Actions artifacts, retained for 7 days and downloaded through an authenticated HiglowCloud API endpoint.

The build runner checks out source using a short-lived GitHub App installation token scoped to the selected source repository and Contents: read. The checkout step removes Git metadata before Gradle runs. The source build does not receive the GitHub App token or a production signing key. The build runner is destroyed by GitHub after the job.

## Required GitHub App configuration

The existing HiglowCloud GitHub App must be installed for both:
- `mikewach2006-crypto/Higlowcloud`
- `mikewach2006-crypto/HiglowBiz` (or another selected source repository)

Required repository permissions:
- Contents: Read-only
- Actions: Read and write

The app's existing Render API configuration must be present:
- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY`
- `GITHUB_APP_SLUG`

The HiglowCloud API creates installation tokens on demand. Long-lived private keys remain in Render environment variables and are never returned to the browser or placed in the APK.

After changing GitHub App permissions, approve the permission update for the installation and ensure both repositories are selected.

## First Nenva Call test

1. Sign in to HiglowCloud.
2. Open **Android Builds** from the workspace navigation or visit `/android-builds/`.
3. Connect the HiglowCloud GitHub App if it is not connected.
4. Select `mikewach2006-crypto/HiglowBiz`, branch `main`, and target **Nenva Call — debug APK**.
5. Start the build and follow its status. Open the linked GitHub Actions run for full step logs.
6. Download the private artifact ZIP and extract the APK. Install it on the test Android phone.

A debug APK is suitable for internal testing. A debug build may need to be uninstalled before installing a later build if the runner creates a different debug signing key.

## Free-tier and safety limits

- One active platform build at a time.
- Five builds per rolling 24 hours per workspace.
- 45-minute workflow timeout.
- 7-day artifact retention.
- No public source-code mirrors or public APK releases.
- No production release signing in this first version.
- No customer code executes in the HiglowCloud API or Render service.
- The workflow is restricted to two known Gradle targets; arbitrary shell commands are not accepted.

GitHub Free currently includes up to 2,000 Actions minutes per month and 500 MB of artifact storage for private repositories. The included quota is not unlimited. Usage above the included allowance may be billed if paid usage is enabled. Set the GitHub Actions spending budget to zero / stop usage at the included limit if the account has a payment method and must not incur charges.

## Important launch boundary

This is an owner-only private beta foundation, not yet a public multi-tenant build service. Before inviting other developers, add verified account onboarding, per-user abuse controls, stronger audit events, artifact integrity verification, a durable release-signing workflow, and an independent security review.

The existing Render deployment and its hosting/deployment routes are not replaced or modified by this build workflow.
