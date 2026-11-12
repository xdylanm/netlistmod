# 0023 — The v1 beta release and a public repository

- **Status:** accepted (2026-11-11, maintainer)
- **Date:** 2026-11-11
- **Amends:** decision 0018 item 6.
- **Context:** The v1 gate passed on 2026-11-11 ([v1-review.md](../design/archive/phase-2/v1-review.md)). The plan and m19 decision 5 put the `0.9.0` beta on its own release branch after the gate, following decision 0018's procedure. The maintainer is making the repository public at this release and turning on branch protection.
- **Decision:**
  1. **`0.9.0` is the v1 beta.** The version is `0.9.0`, the classifier `Development Status :: 4 - Beta`, and `uv.lock` records the same version. The release follows decision 0018 items 2 to 4: merge, tag `v0.9.0` on `main`, and publish the GitHub Release.
  2. **The repository is public** (amends decision 0018 item 6). PyPI does not resolve relative links, so the README's links are absolute GitHub URLs on `main` (m19-tasks 5.1.1 point 6).
  3. **`main` is protected:** changes arrive by pull request, and the CI jobs must pass before a merge.
  4. **Smaller release changes:** the sdist's `README.md` and `LICENSE` patterns are anchored to the root, so the `README.md` files under `docs/` are no longer packaged (m19 A3-4); the release workflow's smoke test edits a transistor's model on ngspice and a B expression on LTspice, which reads the packaged data files (m19 A3-10).
- **Consequences:**
  - The README's links point at `main`, so on PyPI they show the current documents, not those of the release.
  - What 1.0 commits to in the public API (§18) is still reviewed after practical use of the beta.
