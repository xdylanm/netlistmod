# Xyce numbers and values

How the Xyce grammar reads numbers ([decision 0027](../../decisions/0027-xyce-structure-names-and-values.md)
item 8; xm1-tasks 5.1 point 19). Page numbers refer to the manual editions in
[references.md](../../references.md). The library stores a number's text and never evaluates it
(non-goal 6).

## Two readers

Xyce reads a number in a device field differently from a number in an expression, and the grammar
has a terminal for each. Both read, in any case:

1. an integer or a decimal number, with an optional sign (`+1`, `-1.5`, `.5`, `2.`) and an optional
   exponent (`1e3`, `1E-3`);
2. an optional **scale factor**: `T` (1e12), `G` (1e9), `Meg` (1e6), `X` (1e6), `K` (1e3), `mil`
   (25.4e-6), `m` (1e-3), `u` (1e-6), `n` (1e-9), `p` (1e-12) or `f` (1e-15) (`[xyce-ug] §4.1.3
   p41–42`, Table 4-1). `M` is milli, never mega. A letter that begins a scale factor is read as
   one, as Xyce reads it: `1farad` is femto followed by `arad`, which is refused, and `1fa` is a
   femto with the unit `a`;
3. an optional **unit**, from a closed list that depends on where the number stands:

| Reader | Terminal | Where | Units | Then |
|---|---|---|---|---|
| device field | `NUMBER` (`XY-NUM-001`) | the value fields of element lines (X-M1 B5) | `a`, `amp`, `c`, `f`, `farad`, `h`, `henry`, `hertz`, `hy`, `hz`, `m`, `ohm`, `s`, `v`, `vdc`, `volt` | the end of the field |
| expression | `EXPR_NUMBER` (`XY-NUM-002`) | `.PARAM` and `.GLOBAL_PARAM` values (X-M1 B3), and the numbers of the formula grammar | `a`, `f`, `h`, `hz`, `m`, `s`, `v` | an optional `j`, the imaginary part (`[xyce-ref] §2.2.1 p172`), then the end of the field |

So `R1 a 0 1kohm` reads (in B5), and `.param r=1kohm` is refused, as Xyce refuses it. `1kj` and
`2j` are numbers only in an expression. A unit is not a scale factor: `1a` is one ampere, not atto
(Xyce has no atto). The unit lists are not in the manual, which gives only the scale factors; they
rest on the binary, so both entries are `observed`.

## Refused

Both readers end a number where its word ends: any letter, digit or `.` that the closed lists do
not take is refused, at the start of the number.

- **Other letters:** `1kk`, `1z`, `1kq`, `1fz`. Xyce refuses them too.
- **RKM notation** (`2k7`, `4n7`, `1R5`): the manuals define none, and Xyce refuses it. `rkm=True` is
  a `ValueError` on Xyce, as on LTspice.
- **The micro sign** `µ`: Table 4-1 lists it beside `u`, but Xyce 7.10 refuses it, so the library
  does too (discrepancies.md).
- **The binary's lexer artefacts:** Xyce runs `1keg`, `1kmeg`, `1kmhz` and `1e`, which no table
  lists and which read as an accident of its lexer; the library refuses them (discrepancies.md).

## Expressions

A value in braces (`{...}`) or single quotes (`'...'`), or, on `.PARAM` and `.GLOBAL_PARAM` only, a
bare expression without blanks (decision X-D5), is a `Formula`; the formula grammar
(`formula_xyce.lark`) reads it only to find the names it refers to. X-M1 B3 reads them; see
[scoping.md](./scoping.md).
