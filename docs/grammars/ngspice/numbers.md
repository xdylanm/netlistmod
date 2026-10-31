# ngspice numbers and values

How the ngspice grammar reads value fields (M3; [decision 0004](../../decisions/0004-element-and-value-grammar.md)).
The library stores the text of every value with its span. It never computes a value
(architecture non-goal 6); the rules below decide only which forms are accepted. Section
numbers refer to the manual edition in [references.md](../../references.md).

## Standard notation (`NG-NUM-001`, `NG-NUM-002`, `NG-NUM-004`)

- A number is an integer or decimal mantissa (`12`, `3.14`, `.5`, `5.`) with an optional `+`
  or `-` sign and an optional exponent (`1e-14`, `2.65E3`)
  (`[ngspice-manual] §2.1.3.2 "Numbers"`).
- Letters may follow, with no blank: the scale factors `T G Meg K mil m u n p f a`
  (case-insensitive; `m`/`M` is milli and `meg` is mega), and any letters after a number or
  a scale factor, which ngspice ignores (`10V`, `1kOhm`, `1kk`;
  `[ngspice-manual] §2.1.3.3 "Letters following a number"`). The whole token is the value
  text.
- The micro sign `µ` (U+00B5) counts as a letter. The manual's table does not list it;
  ngspice 47 reads `1µ` as `1u` (spec entry status `observed`).
- An exponent may be followed by letters (`1e3k`; ngspice 47 reads 1e6).
- Digits after the letters (`1k5x`, `1meg5`) are an error unless the value is RKM, below.
- A field of the form `name` + operator (`1.1*Rx`) is not a number. Expressions must be
  braced or quoted (architecture §6.3 rule 10).

## RKM notation (`NG-NUM-003`, parser option `rkm`)

The manual accepts RKM notation (`2K7`, `100R`) for resistor and capacitor values only in LT
compatibility mode (`[ngspice-manual] §12.11.6 "LTSPICE Compatibility mode"`). The library
accepts it only with `parse(source, dialect, rkm=True)`; without the option an RKM value is a
`ParseError` that names the option. Standard notation reads the same in both modes.

RKM values follow IEC 60062: digits, a code letter in place of the decimal point, then digits.

| Element | Code letters | Also |
|---|---|---|
| R | `L` (milli), `R` (unit), `K` (kilo), `M` (mega, uppercase only), `G` (giga), `T` (tera) | a leading `R` or `L`: `R47` |
| C | `p`, `n`, `u`/`µ`, `m`/`M` (milli), `F` (unit) | |

- Codes are case-insensitive except `M` on a resistor. A lowercase `m` inside a resistor
  value (`1m5`) is a `ParseError` in both modes, with a hint to write `L`.
- `E` is not a code letter: `4E7` is an exponent in both modes.
- A letter with no digit after it (`47K`, `1M`, `470R`) is standard notation. `1M` is one
  milliohm.
- RKM does not apply to L, K, V, I or parameter values.

### Where ngspice and IEC 60062 disagree

ngspice 47 reads a resistor's `1M0` or `4M7` as milli, and a capacitor's `4F7` as femto, in
both its default and LT modes. The library follows the standard. Such a value parses (with
`rkm=True`) with `notation="rkm"` and `solver_mismatch=True`, so M5 can report
`RKM_SOLVER_MISMATCH`: the netlist will not simulate with the value it states. See
[discrepancies.md](./discrepancies.md).

Without LT mode, ngspice drops the digits after a scale letter without a warning (`2k7` is
read as `2k`). This is why the RKM option is off by default.

## Formulas and strings (`NG-VAL-001`)

- `{expr}` and `'expr'` are formulas; the text excludes the delimiters and the span includes
  them (`[ngspice-manual] §2.11.2 "Brace expressions in circuit elements"`). Contents are not
  parsed.
- Braces do not nest, may not be empty and may not span lines. As in directive text, quotes
  protect the comment markers `;`, `$` and `//`, and braces do not.
- A double-quoted string is a value only for a subcircuit parameter
  (`[ngspice-manual] §2.11.3 "Subcircuit parameters"`).
