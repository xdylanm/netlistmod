# M9 code changes — handoff to a developer

> **Status:** READY — from the M9 review (2026-11-02, `2127bb3`). The maintainer triaged it on 2026-11-02: H1–H4 must land before M9 is accepted; H5–H8 are phase 2. H1–H4 and the fixes in [section 5](#5-review-of-h1h4-fixes-to-make) are made, reviewed and committed (`88a8754`). M9 closed on 2026-11-03; this document stays here because H5–H8 are open for phase 2.
> **Part of:** [m9-tasks.md](./archive/m9-tasks.md) (R7). Governed by [architecture.md](../architecture.md). The M9 review itself changes nothing under `src/`.

## 1. Summary

The review found no violation of the round-trip or topology guarantees, and no solver disagreement beyond those already recorded. One behaviour defect is required; the other entries are about messages and documentation.

| ID | Change | Severity | Needs a decision? |
|---|---|---|---|
| [H1](#h1--a-repeated-upsert-in-a-batch-writes-duplicates) | A repeated upsert in a batch writes duplicates | **required for the gate** | Yes: decision 0010 amends decision 0007 |
| [H2](#h2--incomplete-lines-get-an-unhelpful-parse-error) | Incomplete lines get an unhelpful parse error | **required for the gate** | No |
| [H3](#h3--two-misleading-edit-messages) | Two misleading edit messages | **required for the gate** | No |
| [H4](#h4--public-docstrings-that-predate-ltspice) | Public docstrings that predate LTspice | **required for the gate** | No |
| [H5](#h5--argument-type-misuse) | Argument type misuse | phase 2 | No |
| [H6](#h6--listed-ltspice-commands-are-reported-as-unknown) | Listed LTspice commands are reported as "unknown" | phase 2 | Possibly |
| [H7](#h7--internal-references-in-user-facing-messages) | Internal references in user-facing messages | phase 2 | No |
| [H8](#h8--a-model-defined-in-an-if-block-gets-a-warning) | A model defined in an `.if` block gets a warning | phase 2 | Yes: changes architecture §17 |

Every change ends with the full check set green (`docs/testing.md`), with `--require-solver ngspice --require-solver ltspice`. Add a CHANGELOG line for each. Message changes do not move line or column: the `*_rejects` manifests pin them.

## 2. Entries

### H1 — A repeated upsert in a batch writes duplicates

**Location:** `edit/api.py` `Batch` (`:481`), `edit/operations.py` (`_assign` `:267`, `set_param_statement` `:439`, `set_directive` `:606`, `add_include` `:671`).

**Defect.** Each batch operation is computed against the netlist the batch was opened on. Two upserts of one target that does not exist yet therefore each add it. Both are zero-width insertions, so `EditPlan.ordered()` allows them, and the slot checks pass. No error is raised, and only `.param` gets a diagnostic.

```python
netlist = Netlist.from_text(TEXT, dialect=Dialect.NGSPICE)
with netlist.batch() as batch:
    batch.set_param("R1", "m", "1")
    batch.set_param("R1", "m", "2")
```

| Operation repeated in one batch | Text written | ngspice 47 | LTspice 26.1.1 |
|---|---|---|---|
| `set_param` | `R1 a 0 1k m=1 m=2` | runs, last wins | runs, last wins |
| `set_model_param` | `.model dm D n=1 n=2` | runs, last wins | runs, last wins |
| `set_instance_param` | `X1 a s k=1 k=2` | runs, last wins | runs, last wins |
| `params.set` | two `.param x=` lines | runs, last wins (`DUPLICATE_DEFINITION` info) | **stops** (`DUPLICATE_DEFINITION` warning) |
| `directives.set(".tran …")` | two `.tran` lines | **runs both analyses** | **stops** |
| `directives.set(".op")`, `add_include` of one path | two identical lines | not probed | not probed |

**Why it matters.**
- `directives.set` is documented as an upsert of a singleton, and `.param` as an upsert too, yet the file may hold two lines. One of them stops LTspice, while the library reports success.
- The next `set_param` on the result fails with "parameter `m` is repeated": the batch built a state the API then refuses.
- `set_value` and existing-parameter edits already give `EditError` when repeated (decision 0007: two edits of one span are an error, never last-wins). New targets are the gap.
- M6's review recorded only the `.param` case, as a limit for the gate. The other rows are new.

`set_ac` and `set_dc` on a source without that part fail loudly today, as a parse error of the result. The fix should give them the same clearer message.

**Proposed change.** Make the rule the same for new targets as for existing ones: in one batch, a second upsert of one target is an `EditError` naming the target, when the operation is submitted. The key is the operation family, scope and folded target (element and parameter name; model and parameter name; parameter name; directive kind, or `.step` quantity; include path). Do not merge or apply last-wins, which decision 0007 rules out. Different new parameters on one line stay valid.

**Docs.** State the rule in `edit-layer.md` §1, add it to `EditError` in `docs/usage/errors.md`, and amend architecture §7.5.

**Tests.** A parametrised negative test in `tests/edits/test_edit_lifecycle.py`, on both dialects, for every row above plus `set_ac` and `set_dc`. A positive test that two different new parameters on one line still work. Golden diffs do not change.

**Decision.** Decision 0010 (M9 T2) amends decision 0007 item 1 and §7.5 to state the rule.

### H2 — Incomplete lines get an unhelpful parse error

**Location:** `grammar/loader.py` `_map_error`, `_expected_names`. M4 §10.3 deferred this to "the M9 error reference if it reads poorly". It does.

```text
Parse error at line 2, column 10:
.tran 1ns
         ^
Expected: `,` field separator, `\\` continuation onto a line of statement text, field separator, trailing comment (`;`, `$` or `//`)
```

The same text appears for `R1 a 0`, `R1 a`, `.model dm` and `V1 a 0 AC`. The position is right, but the message does not say that a field is missing, and it offers a comment as if that would help. An element after `.end` gets only `Expected: end of line`.

**Proposed change.** Error enrichment only (P13 (c)); no grammar change.
- When the failure is at the end of a line and only separators, continuations or comments are expected, add a `reason` such as "this line is incomplete: another field is needed", and leave those punctuation terminals out of `expected`.
- An element or dot-command after `.end`: a `reason` saying the netlist ends at `.end`.

**Tests.** Message assertions for the cases above on both dialects. Line and column in the `*_rejects` manifests stay as they are. Do not try to name the missing field per construct: that would duplicate the grammar in Python.

### H3 — Two misleading edit messages

From M6's review; both still reproduce.

1. `edit/operations.py:561`: `directives.add(".model d1 D")` says "use params.set or set_model_param". `params.set` cannot do it, and adding a `.model` has no API (§7.1). Say that a `.model` line cannot be added, and that `set_model_param` edits an existing one. Keep the `params.set` hint for `.param`.
2. `edit/placement.py` `_anchor` (`:112`): `directives.add(".op", Placement.after(line))` with a line of a subcircuit body says "look the line up again in the netlist being edited", but the line is valid. Say that the line is inside a subcircuit and directives go to the top level. Keep the current text for a stale line.

**Tests.** One message assertion each in `tests/edits/test_edit_negative.py`.

### H4 — Public docstrings that predate LTspice

Architecture §14 requires docstrings on the public API. They all exist, but these are now wrong:

| Location | Says | Actually |
|---|---|---|
| `edit/api.py:96` `set_param` | "an R, C, L or D line" | also an LTspice V or I line, and an LTspice flag's value |
| `edit/api.py:338` `DirectiveEditor.set` | the singleton kinds only | also upserts LTspice `.step` by swept quantity |
| `edit/api.py:118` `set_model` | describes R, C and L models | LTspice has none (`EditError`) |
| `edit/api.py:142` `remove_value` | as above | refused on LTspice |
| `document/topology.py:40` `Net` | global means ground or `.global` | also LTspice `$G_*` |

No test change.

### H5 — Argument type misuse

- `scope="ab"` is iterated as characters, so the message names `('a', 'b')`, and on a netlist with nested definitions `a` and `b` it would address that scope instead of failing. Raise `TypeError` for a `str` in `Index.scope`.
- `parse("text", dialect)` raises `AttributeError: 'str' object has no attribute 'text'`. Raise a `TypeError` that names `SourceText`, or document it.

Both are outside the type annotations and mypy catches them, so they can wait.

### H6 — Listed LTspice commands are reported as "unknown"

Every LTspice export gets one `UNKNOWN_DIRECTIVE_PRESERVED` (info) for `.backanno`, and `.tf`, `.noise` and `.four` are called "unknown" although they are on the closed list (M8 §9.4, §16). Consider a separate wording or code for listed commands. A new code changes §17. M8 left this for phase 2.

### H7 — Internal references in user-facing messages

About 15 messages cite internal documents, such as "(decision 0007 item 8)" and "(architecture §7.3)". The wheel does not ship those documents, and `(§2.5)` in a diagnostic means the ngspice manual, while `§` elsewhere means the architecture. Say which document is meant, or drop the citation. Do this with the phase 2 message work; the error reference (M9 T6) gives the meaning for now.

### H8 — A model defined in an `.if` block gets a warning

`D1 a 0 dm` with `.model dm D` only inside `.if (1)` … `.endif` gets `UNRESOLVED_MODEL` as a warning, and the same applies to subcircuits and parameters. An `.include` in scope makes it info, because the name may be defined there; §7.8 says the same is true of an opaque block. This matches §17 as written, so changing it needs a decision. M9 T4 documents the current behaviour.

## 3. Reviewed: no change proposed

- **Token slicing in the transformer** (`model/transform.py:716`, `:1018`, `:1134`). These take a name out of one token (`STEP_MODEL_REF`, `AKO_REF`, the `v(` opener). The grammar has already matched the token, so Python decides no syntax. Read strictly, P13 says Python must not "split" syntax. Splitting the tokens was tried on a scratch copy of the grammar: without lookarounds, `.step NPN 2N2222(VAF) 1 2 1` stops parsing (`2N2222` lexes as an embedded decimal) and `ako: fast` becomes valid; with lookaheads, those are fixed, but `2N2222( VAF)` becomes valid and the terminals join the list that strict mode cannot check. The maintainer chose to keep them (2026-11-02), and decision 0010 item 6 clarifies P13.
- **Name semantics in `document/`** (`names.py` `$G_` and `X§` prefixes, `diagnostics.py:224` `<instance>:<node>`). These interpret a name the grammar accepted (`names.md`), not syntax.
- **`add_include` text** (`add_include('a" ; c')` writes a trailing comment; an empty path is accepted). The caller's text is not validated (architecture §19, decision 18).
- **Hand-built plans** may change a title or a `.model` type. Neither is topology, and the type change gets `MODEL_TYPE_MISMATCH`.
- **A missing file** raises `FileNotFoundError`, outside `SpiceNetlistError`. T6 documents it.

## 4. What the review tried that held

- Topology and injection: new elements through a value or `.param` text, comments, line breaks and repeated fields in a slot, hand-built plans that add an element, alter a node's case or rename a call, and cuts into opaque blocks. Each was refused with the expected error, and nothing was written.
- Encoding: a cp1252 CRLF file with no final newline edits and saves byte-exactly. An unencodable edit raises `EncodingError` and leaves the file unchanged.
- `Dialect`: a string, `None` or an unknown value is a `ValueError` (`build_parser` checks the type), so the code's `is` comparisons are safe.
- Repeated `.subckt`: an edit addresses the first definition, the one ngspice uses (`scoping.md` S7); LTspice stops if it is used.
- Packaging: the wheel and sdist build, and the wheel imports and edits from a clean environment.

## 5. Review of H1–H4: fixes to make

The maintainer sent these four to the developer on 2026-11-02, after the review of the uncommitted H1–H4 work. Everything else in that work is accepted, including the regenerated snapshot, the two changed assertions, the wider H2 rule and existing targets failing on submission. T10 waits for these fixes.

1. **Report `.end` before an unsupported letter** (`grammar/loader.py` `_map_error`). `structure_rejects/text_after_end.cir` holds the word `text`, and it still gets an unsupported T device error. H2 asked for the `.end` reason on any element after `.end`.
   - Move the `_after_end` check above the planned-letter check, and update the comment above them.
   - Replace `test_a_planned_letter_after_end_stays_an_unsupported_construct` with a test that `Q1 a b c m` and `hello world` after `.end` get the `.end` reason on both dialects. A planned letter before `.end` stays an `UnsupportedConstruct`.
   - Regenerate `tree_snapshot.json`, and compare it with the current version: only `structure_rejects/text_after_end.cir` should change, from `UnsupportedConstruct` to `ParseError`, in both `rkm` modes. Update the count in the `test_tree_snapshot.py` docstring and in the CHANGELOG.
   - A trial on a scratch copy failed only the snapshot entry and the replaced test, but it skipped the solver tests. Run those too, including `test_element_after_end_is_ignored_by_solver_rejected_by_parser`.
2. **Correct the incomplete-line reason** (`_INCOMPLETE_LINE` in `grammar/loader.py`). ngspice reads `R1 a 0 1k foo bar`, which has too many fields, as a parameter waiting for `=`, and says "another field is needed". A repeated `set_value` gets the same message on `R2 a 0 1 2 rm`.
   - Change the reason to "this line ends too early". Keep the rule for when it applies, and what `expected` lists.
   - Update `tests/grammar/test_parse_messages.py`, the `docs/usage/errors.md` example and the CHANGELOG.
   - Add `R1 a 0 1k foo bar` on ngspice to the tests.
3. **Bring decision 0010 item 5 into line with the code.**
   - Add element (`set_dc`, `set_ac`) to the key list, as `edit-layer.md` has it.
   - Add that the second upsert is an error whether or not the target exists yet.
4. **Update `phase-1-review.md`.**
   - In section 1, H1–H4 are no longer "not yet made".
   - Add a limit to section 6: `directives.add` is not an upsert, so `directives.add(".tran …")` over an existing `.tran`, or followed by `directives.set` in a batch, writes two `.tran` lines. ngspice runs both analyses and LTspice stops. Section 2's results stay interim until T10.

Finish with the full check set green, with `--require-solver ngspice --require-solver ltspice`. Do not commit unless the maintainer asks.
