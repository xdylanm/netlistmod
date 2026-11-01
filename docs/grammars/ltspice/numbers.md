# LTspice numbers and values

How the LTspice grammar reads value fields ([decision 0009](../../decisions/0009-ltspice-dialect.md)
item 6). The library stores the text of every value with its span and never computes one
(architecture non-goal 6). The readings below are LTspice's, recorded so that users know what a
value means; they decide only which forms are accepted.

## Standard notation (`LT-NUM-001`, `LT-NUM-002`, `LT-NUM-004`)

- A number is an integer or decimal mantissa with an optional sign and exponent
  (`[ltspice-ref] SPICE-SYNTAX-REFERENCE.md "Engineering Multipliers"`).
- The multipliers are `T G Meg K mil m u n p f`, case-insensitive. `M` is always **milli**: `1M` is
  one milliohm. `Meg` is mega.
- Other letters after a number are ignored by LTspice and are part of the value text: `10V`,
  `5Volts`, `1kOhm`, `1kΩ`. `4Farads` is 4 femto (the `F`). `a` is not a multiplier here: LTspice
  reads `1a` as 1, unlike ngspice's atto.
- `µ` (U+00B5) and `μ` (U+03BC) are micro. An LTspice export writes either one, depending on how the
  schematic was encoded.

## The embedded decimal (`LT-NUM-003`)

Digits, a multiplier in place of the decimal point, digits: `6K34` is 6.34K, `2k2` is 2.2k, `1meg5`
is 1.5Meg, `1M0` is 1 m, `1µ5` is 1.5 µ. `R` works as the unit (`2R2` is 2.2; observed, not in the
reference's table).

| | ngspice | LTspice |
|---|---|---|
| Option | `rkm=True` | none; `rkm=True` is a `ValueError` |
| `M` in `1M0` | mega for R, per IEC 60062, marked `RKM_SOLVER_MISMATCH` | milli, LTspice's own reading |
| `R47` | 0.47 with `rkm=True` | a bare name: rejected, with a hint |
| Slots | R and C values | every value slot |
| Node | `notation="rkm"` | `notation="rkm"`, `solver_mismatch=False` |
| Diagnostics | `DIALECT_GATED_SYNTAX`, `RKM_SOLVER_MISMATCH` | none |

**Slots (settled by probe per slot, T5):** R, C, L, V, I (with `DC`, `AC` and phase), K, the D area,
every instance parameter, `X` and `.subckt` parameters, `.model` parameters, `.param`, `.tran`,
`.ac`, `.dc`, `.temp`, `.ic`, `.nodeset`, `.options` and `.step` all read it.

**Not accepted:** a decimal mantissa (`2.2k2`: LTspice reads 2.4k, an undocumented sum), other
letters before the digits (`1x5`, `1a5`, `1l5`, `1kohm5`, `1V5`: LTspice drops the rest), an exponent
(`1e3k2`), and text after the digits (`1k5x`, `1k5k`, which LTspice stops at too). See
[discrepancies.md](./discrepancies.md).

## A bare name is not a value

`R1 a b R47`, `R1 a b x` and `R1 a b x*3` are rejected: LTspice reads a bare name as a model
("Undefined model"), and R, C and L take no model in LTspice. Write `{x}`.

## Formulas and strings (`LT-VAL-001`, `LT-PRM-001`)

- `{expr}` and `'expr'` are formulas; the text excludes the delimiters and the span includes them.
  Contents are not parsed, may not be empty, and may not hold `;`. Braces do not nest.
- A double-quoted string is a value only for `.param`, a subcircuit parameter, a `.model`'s `mfg` and
  `type`, and an element's `mfg`, `pn` and `type`. It may hold blanks and commas.
- A bare word (`mfg=OnSemi`) is a value only for an element's `mfg`, `pn` and `type` and a `.model`'s
  `mfg` and `type`: an `Identifier`, kept verbatim, never read as a formula or a reference. LTspice
  reads a bare word in any other `.model` parameter as a parameter reference, so `Is=x` is a
  `ParseError` that suggests `{x}`.
- A flag (`noiseless`, `load`, `off`) may take a number or a formula (`noiseless=0`). LTspice reads
  0.5 or more as on; the library keeps the text and does not interpret it.
- **Bare expressions** are accepted only in `.param`, which the reference documents
  (`.param x=2*pi*100`): `Formula` with an empty delimiter. An expression holds no blank except around
  an operator or inside parentheses (up to three levels), so `.param x=1 + 1 y=2` is two assignments.
  A plain number stays a `NumericValue`.
