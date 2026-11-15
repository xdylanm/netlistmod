# Xyce numbers and values

How the Xyce grammar reads value fields ([decision 0026](../../decisions/0026-the-xyce-dialect.md)).
X-M0 reads no value: every line that holds one is refused, so nothing in this document is
implemented yet. Page numbers refer to the manual editions in [references.md](../../references.md).

## What X-M0 knows

- **RKM.** The Xyce manuals define no RKM notation, so `rkm=True` is a `ValueError` on Xyce, as
  on LTspice. X-M1 confirms how Xyce reads a value such as `2k7`.

## Planned (X-M1)

- **Numbers and scale factors.** An integer or floating-point number, followed by one of the
  scale factors of `[xyce-ug] §4.1.3 p41–42` (Table 4-1), which includes `mil` and `X` for mega.
  Letters after a factor, and the factors that differ from ngspice's, need probes.
- **Expressions.** Braces, and single quotes for compatibility; bare expressions in some places
  (`[xyce-ref] §2.2 p164`; decision X-D5). The formula grammar and reserved words have no Xyce
  entry yet, and a lookup fails loudly (`src/netlistmod/grammar/formula.py`).
