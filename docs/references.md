# References

Reference documents cited by spec entries, decision records and design notes.
Cite a reference by its key and section, for example
`[ngspice-manual] §2.4.4 "End-of-line comments"`. The spec checker
(`tests/architecture/test_spec_coverage.py`) requires every `manual_ref` key to
have an entry here.

Section numbers belong to the edition recorded below. When a newer edition is
adopted, update the edition and access date and re-check every citation.

## [ngspice-manual]

- **Title:** Ngspice User's Manual
- **Publisher:** the ngspice project, ngspice.sourceforge.io
- **URL (HTML):** https://ngspice.sourceforge.io/docs/ngspice-html-manual/manual.xhtml
- **URL (PDF):** https://ngspice.sourceforge.io/docs/ngspice-manual.pdf
- **Edition:** Version 47+ (ngspice development version); preface "as of Mar 2026"
- **Accessed:** 2026-10-30 (HTML edition; section numbers verified against it)

## [iec-60062]

- **Title:** IEC 60062:2016, *Marking codes for resistors and capacitors*
- **Publisher:** International Electrotechnical Commission
- **Edition:** 2016 (later amendments not checked)
- **Used for:** RKM letter codes (decision 0004, `docs/grammars/ngspice/numbers.md`).
  Secondary source: https://en.wikipedia.org/wiki/RKM_code (accessed 2026-10-30).

## [ltspice-ref]

- **Title:** LTspice AI Reference (`analogdevicesinc/ltspice-reference`)
- **Publisher:** Analog Devices, Inc.
- **URL:** https://github.com/analogdevicesinc/ltspice-reference
- **License:** Apache-2.0 for the documentation (`LICENSE.md`; verified 2026-10-31); LTspice itself
  is proprietary
- **Commit:** `b4358f83e9d09a719ee5c08f25b7e236a896c41d` (2026-09-16), the head of `main` on the
  access date
- **Copy cited:** the copy LTspice 26.1.1 installs under `%LOCALAPPDATA%\LTspice\reference\`, marked
  version "24+"
- **Accessed:** 2026-11-01
- **Citation form:** `[ltspice-ref] <FILE>.md "<heading>"`, because the reference has no section
  numbers. Paraphrase only (architecture §11.3 rule 4). The built-in LTspice Help is proprietary and
  is not cited or copied (decision 0009).
