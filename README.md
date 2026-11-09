# Reseam YouTube Compatibility

An automatically rebuilt community bundle based on the latest **stable** release of [Reseam patches](https://git.reseam.app/reseam/patches).

It carries the upstream patch catalogue plus a small compatibility overlay for YouTube:

- AMOLED/dark and light surface resource coverage.
- Legacy runtime color lookups for older YouTube builds.
- Classic horizontal miniplayer restoration using YouTube experiment flags `45630429` and `45622882`.
- The portrait-player status-bar inset compatibility adjustment.

This is an independent community bundle, not an official Reseam release.

## Add it to Reseam Manager

Add this URL as a custom patch source:

```text
https://github.com/LisaExists/reseam-youtube-compat/releases/latest/download/patches.json
```

The URL stays the same. Reseam Manager reads the index and discovers new releases automatically. The index contains the complete release history and the permanent public signing key.

## Automatic updates

GitHub Actions checks the upstream Forgejo release feed every 15 minutes. When a new stable upstream release appears, it:

1. Downloads the exact tagged upstream source and verifies its commit against the release API.
2. Applies the overlay. Every expected source fragment must match exactly once; unknown upstream changes stop the job safely.
3. Builds the bundle using the Reseam CLI version declared by that upstream release.
4. Verifies the signature and checks that the expected YouTube patches are present.
5. Publishes a versioned GitHub release and updates its `patches.json` index while preserving previous releases.

A failed or incompatible build is **not** published. You can also start the workflow manually from **Actions → Poll upstream and publish**.

## One-time signing-key setup

The private signing key must remain stable between releases. Generate it once, back it up somewhere safe, and store its base64 representation as a repository Actions secret named:

`BUNDLE_SIGNING_KEY_B64`

You need the Reseam CLI installed locally. Generate the key:

```sh
mkdir -p ~/.reseam
reseam bundle keygen --out ~/.reseam/bundle-signing.key
```

On Linux, copy its single-line base64 representation:

```sh
base64 -w0 ~/.reseam/bundle-signing.key
```

Then open **Settings → Secrets and variables → Actions → New repository secret** in this repository. Name it `BUNDLE_SIGNING_KEY_B64` and paste the output as its value. Do not commit or share the private key file or its base64 value.

Alternatively, with GitHub CLI authenticated for this repository:

```sh
gh secret set BUNDLE_SIGNING_KEY_B64 --repo LisaExists/reseam-youtube-compat --body "$(base64 -w0 ~/.reseam/bundle-signing.key)"
```

Keep an offline backup of the key. Losing it means a new key would need to be trusted by every user again. The public key is embedded in the published index and bundle.

Without the secret, the workflow can still compile and verify the current bundle using a disposable key, but it will not publish anything. After adding the secret, run the workflow once using **Actions → Poll upstream and publish → Run workflow**. That first signed run publishes the current upstream release; later runs happen automatically.

## Upstream and compatibility policy

- Upstream source: [Reseam/patches](https://git.reseam.app/reseam/patches)
- Upstream release API: `https://git.reseam.app/api/v1/repos/reseam/patches/releases/latest`
- Upstream code is licensed under AGPL-3.0-or-later with additional terms and notices; see [upstream LICENSE](https://git.reseam.app/reseam/patches/src/branch/main/LICENSE) and [NOTICE](https://git.reseam.app/reseam/patches/src/branch/main/NOTICE).
- Our overlay is provided under AGPL-3.0-or-later.

The overlay is intentionally strict. If upstream renames a resource, changes a Kotlin implementation, removes a feature hook, or introduces a conflicting patch, automation will fail rather than guessing at a replacement. Update `overlay/apply_fixes.py` and test the new source before restoring automatic publishing.

The currently tested classic-miniplayer compatibility target is YouTube **21.23.492**. Upstream patches may support additional versions; this overlay does not promise that every upstream version behaves identically.

## License

The overlay and automation in this repository are AGPL-3.0-or-later. The resulting bundle also contains upstream Reseam code and remains subject to upstream licensing and notices.
