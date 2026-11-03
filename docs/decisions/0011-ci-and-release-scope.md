# 0011 — CI and release scope

- **Status:** proposed
- **Date:** 2026-11-03
- **Context:** Decision 0010 deferred CI to the start of phase 2. Architecture §13 and §10.3 describe a wider setup than the project needs: a macOS test job, an optional ngspice job, and a release workflow that publishes to PyPI. The maintainer has no macOS system, LTspice is only available on Windows, and v1 is a beta that is not published ([phase 2 plan](../design/phase-2-plan.md) section 8; [m10-tasks.md](../design/m10-tasks.md) section 2).
- **Decision:**
  1. **Platforms are Linux and Windows,** on Python 3.13 and 3.14. macOS is neither required nor claimed; the library may work there, but nothing is validated.
  2. **CI installs no solver, and the optional ngspice job is dropped.** The solver tests skip through their fixture, which also proves that they skip cleanly. The local run with both solvers stays required for each milestone. Solver tests and spec entries are validated on ngspice 47, a distribution package may be another version, and differences would be noise.
  3. **No release workflow in v1.** v1 is a feature-complete beta, tagged `0.9.0` and not published to PyPI. A later release decides its own publishing.
  4. **One pull request per milestone,** merged with "Rebase and merge" after the maintainer's review, and only when CI is green. Branch protection enforces this if the repository's plan and visibility allow; otherwise it is a convention.
  5. **CI runs Hypothesis derandomized,** through the `ci` profile, so a pull request cannot fail on an example unrelated to its change. Local runs stay random. The 90% coverage gate applies to every test job.
  6. **Amendments to the architecture:** §4 (the layout regains `.github/`); §10.3 ("Environment"); §13 ("GitHub Actions", "Branch protection", and the "Phase 1" line); §19 decision 14.
- **Consequences:**
  - Decision 0010 item 2 is fulfilled: phase 2 began by adding CI.
  - CI does not validate solver behaviour. A change can be green in CI and still fail the local solver run, so CI does not replace it.
  - A macOS problem would go unnoticed until someone reports it.
  - This record stays `proposed` until the maintainer accepts it when M10 closes.
