# 0015 — Linear dependent sources and switches

- **Status:** proposed (M14; accepted when M14 closes)
- **Date:** 2026-11-06
- **Context:** M14 adds the linear dependent sources E, F, G and H and the switches S and W on both dialects. Their controls are topology (phase 2 plan, section 3, point 2): an edit that rewired a control path would otherwise pass verification. Probes on ngspice 47 and LTspice 26.1.1 are in [m14-tasks.md](../design/m14-tasks.md) section 3. The maintainer accepted these on 2026-11-06.
- **Decision:**
  1. **Node classes.** `Vcvs` (E), `Vccs` (G), `Cccs` (F), `Ccvs` (H), `VoltageSwitch` (S) and `CurrentSwitch` (W), with the public bases `ControlledSource` (E, F, G, H) and `Switch` (S, W).
  2. **Control nodes are nodes.** E, G and S have four `nodes`, the output pair then the control pair, with a `control_nodes` property for the last two. So the signature and every net query include them.
  3. **Controlling sources are element references.** F, H and W have two `nodes` and `control: ElementReference`. The signature gains a `("control", scope, designator, name)` entry for each, beside the element's own entry, as K has `("coupling", …)`. No existing entry changes.
  4. **A controlling source resolves in its own scope only,** in any case and anywhere in that scope, as both solvers do: a top-level source is not found from inside a subcircuit. Not found: `UNRESOLVED_ELEMENT`, a warning, or info where the scope has an `.include`, `.lib` or opaque block. LTspice's `X1:Vq`, a source inside an instance, runs there; the library keeps it as text and reports `UNRESOLVED_ELEMENT` as info (a known limit, §7.8).
  5. **A controlling source that is not a V gets `CONTROL_SOURCE_MISMATCH`,** a warning whose message says what each solver does: both also read an E or an H, LTspice also an L, and both stop on anything else.
  6. **The gain is one positional value,** a number or a formula. Refused: a missing gain, a second value (ngspice 47 runs it with an output that matches neither), a word in the gain's place (LTspice's export of an unset gain), and `gain=`, which both solvers run but neither reference writes; manual chapter 27 lists `gain` as a device parameter, not a line form (decision 0002).
  7. **Instance parameters.** ngspice takes `m=` on F and G (manual §4.2.1, §4.2.3) and nothing on E and H. LTspice takes none on E, F, G or H. S and W take none on either.
  8. **Switches.** The model is mandatory, and the state is an optional `on` or `off`, in any case, kept as a `Flag`. Both together are refused, although both solvers run them and the last wins. LTspice's `off=1` is accepted, as LTspice flags may take a value. The model is a fixed field, so a model named `off` is a model. S takes an SW model and W a CSW model.
  9. **The nonlinear forms stay `UnsupportedConstruct` until M15:** ngspice's `vol=`, `cur=`, `VALUE`, `TABLE` and `POLY` after the output nodes; LTspice's `value=` and `POLY` there, and `table=` and `Laplace=` after E's and G's control nodes. ngspice stops on `Laplace=`, so there it is a `ParseError`.
  10. **Edits.** `set_value` and `set_formula` on the gain; `set_param` with `m=` on an ngspice F or G; `set_model` on S and W with the type check; and the new `set_switch_state(designator, "on" | "off" | None)`. Nodes and controlling sources have no operation (§7.3).
  11. **Corpus.** The maintainer's examples and the variants written from them are the `controlled_sources` families; the intentional failures are in each dialect's `elements_rejects`.
  12. **`lt_test_esource.asc`** never set E1's gain; the maintainer fixed it, and the earlier export is the LTspice reject `unset_gain.net`.
  13. This record amends §5.2 and §5.3 (the new nodes), §7.2 (the switch model types and the new operation), §7.7 (the `control` entry), §7.8 (sources inside an instance) and decision 0006 (the new diagnostic).
  14. The element rules and operations live in the family modules `model/_rules_controlled.py` and `edit/_ops_controlled.py` (P12).
- **Consequences:**
  - The device matrices show E, F, G, H, S and W as `supported`; their nonlinear forms are listed in `NG-UNS-001` and `LT-UNS-001`.
  - Any change to a control node or a controlling source is a `TopologyViolation`.
  - The signature snapshot is unchanged. The tree snapshot adds the new files, and the same 17 rejected files that M13 changed list the six letters among their expected terminals.
  - LTspice runs a comma between E's output nodes (`E1 out,0 vx 0 2`), and the library refuses it, as it refuses commas between nodes on every LTspice letter (decision 0009).
