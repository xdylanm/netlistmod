# 0018 — Publishing to PyPI

- **Status:** accepted (2026-11-07, maintainer)
- **Date:** 2026-11-07
- **Context:** Decision 0011 item 3 said v1 is tagged `0.9.0`, is not published to PyPI, and has no release workflow. The maintainer wants to use the library in an application before v1 is complete, and installing from PyPI is the simplest way to do that. M15 is merged; M15b is not started. The number 0017 is reserved for M15b ([m15b-tasks.md](../design/archive/phase-2/m15b-tasks.md)), so this record is 0018.
- **Decision:**
  1. **Publish `0.5.0` to PyPI as an alpha.** The version is below the planned `0.9.0` feature-complete beta, which stays the v1 tag. Versions only go up, so `0.9.0` follows later releases; any release between them is `0.5.x` or `0.6.0` and later. The classifier is `Development Status :: 3 - Alpha`, and the version is an ordinary one, so `pip install netlistmod` finds it without `--pre`.
  2. **The release is a tag and a GitHub Release.** The tag is `v<version>`, for example `v0.5.0`, made on `main` after the release pull request is merged. Publishing the GitHub Release starts `.github/workflows/release.yml`; nothing else publishes.
  3. **Trusted Publishing, no stored token.** The workflow builds in one job and publishes in a second, which holds the only `id-token: write` permission and runs in the GitHub environment `pypi`. PyPI trusts that repository, workflow and environment. The workflow refuses a tag that does not match the version in `pyproject.toml`, and installs the built wheel in a clean environment and runs a parse and edit before it publishes.
  4. **No TestPyPI step.** The wheel smoke test in the build job stands in for it. A published version cannot be replaced, so a faulty release is yanked and fixed in the next version.
  5. **Scope of support is unchanged.** Linux and Windows, Python 3.13 and 3.14, no macOS (decision 0011 item 1). CI still installs no solver.
  6. **The repository stays private for now.** The README links to `docs/` are relative and are dead on the PyPI page until the repository is public; the project's `Homepage` and `Repository` URLs point at it regardless.
  7. **Amendments:** decision 0011 item 3 (superseded by this record), architecture §13 ("Not in v1"), and the release lines in the [phase 2 plan](../design/phase-2-plan.md) (the beta overview, the close-out steps, and section 8 point 7).
- **Consequences:**
  - Every release is a manual act by the maintainer: bump the version and the changelog, merge, tag, publish the GitHub Release. A mistaken release is not automatically reversible, only yankable.
  - The alpha classifier tells users the public API may still change; what 1.0 commits to (§18) is still reviewed after practical use.
  - Dependabot already covers the actions the release workflow uses.
