from pathlib import Path

from lark import Lark, Transformer, Tree, Token
from dataclasses import dataclass, field
import sys

@dataclass
class NumericValue:
    text: str
    span: tuple[int, int]

@dataclass
class Formula:
    text: str        # content, delimiters stripped
    delimiter: str    # "{}" | '"' | "'"
    span: tuple[int, int]   # whole token, delimiters included

@dataclass
class ModelReference:
    model_name: str
    span: tuple[int, int]

def make_value(token: Token) -> NumericValue | Formula:
    if token.type == "SPICE_VALUE":
        return NumericValue(text=str(token), span=(token.start_pos, token.end_pos))
    if token.type == "BRACE_EXPR":
        return Formula(text=str(token)[1:-1], delimiter="{}", span=(token.start_pos, token.end_pos))
    if token.type == "QUOTED_EXPR":
        text = str(token)
        return Formula(text=text[1:-1], delimiter=text[0], span=(token.start_pos, token.end_pos))
    raise ValueError(f"Unexpected value token type: {token.type}")

@dataclass
class Title:
    text: str
    span: tuple[int, int]

@dataclass
class Line:
    content: object | None
    span: tuple[int, int]

@dataclass
class Component:
    name: str
    span: tuple[int, int]

@dataclass
class Resistor(Component):
    net_a: str
    net_b: str
    value: NumericValue | Formula | None
    model: ModelReference | None
    params: list["ParamAssignment"] = field(default_factory=list)

@dataclass
class Capacitor(Component):
    net_a: str
    net_b: str
    value: NumericValue | Formula | None
    model: ModelReference | None
    params: list["ParamAssignment"] = field(default_factory=list)

@dataclass
class Diode(Component):
    net_a: str
    net_b: str
    model: ModelReference
    params: list["ParamAssignment"] = field(default_factory=list)

@dataclass
class Voltage(Component):
    net_a: str
    net_b: str
    value: NumericValue | Formula
    params: list["ParamAssignment"] = field(default_factory=list)

@dataclass
class ParamAssignment:
    name: str
    value: NumericValue | Formula
    span: tuple[int, int]

@dataclass
class ParamStatement:
    assignments: list[ParamAssignment]
    span: tuple[int, int]


class NetlistTransformer(Transformer):
    def title(self, children):
        token = children[0]
        return Title(text=str(token), span=(token.start_pos, token.end_pos))
    
    def value_field(self, children):
        return make_value(children[0])

    def model_name(self, children):
        token = children[0]
        return ModelReference(model_name=str(token), span=(token.start_pos, token.end_pos))

    def param_kv(self, children):
        name_token, value = children
        return ParamAssignment(name=str(name_token), value=value, span=(name_token.start_pos, value.span[1]))

    def dot_param(self, children):
        kw_token, *assignments = children
        return ParamStatement(assignments=assignments, span=(kw_token.start_pos, assignments[-1].span[1]))

    def diode(self, children):
        designator, net_a, net_b, model, *params = children
        end = params[-1].span[1] if params else model.span[1]
        return Diode(name=str(designator), net_a=str(net_a), net_b=str(net_b),
                     model=model, params=params, span=(designator.start_pos, end))

    def voltage(self, children):
        designator, net_a, net_b, value, *params = children
        end = params[-1].span[1] if params else value.span[1]
        return Voltage(name=str(designator), net_a=str(net_a), net_b=str(net_b),
                       value=value, params=params, span=(designator.start_pos, end))

    def resistor(self, children):
        return self._passive(Resistor, children)

    def capacitor(self, children):
        return self._passive(Capacitor, children)

    def _passive(self, cls, children):
        designator, net_a, net_b, *rest = children
        value, model, params = None, None, []
        for item in rest:
            if isinstance(item, (NumericValue, Formula)):
                value = item
            elif isinstance(item, ModelReference):
                model = item
            elif isinstance(item, ParamAssignment):
                params.append(item)
        end = (params[-1].span[1] if params else
               model.span[1] if model else
               value.span[1] if value else net_b.end_pos)
        return cls(name=str(designator), net_a=str(net_a), net_b=str(net_b),
                   value=value, model=model, params=params, span=(designator.start_pos, end))


class Lines:
    def __init__(self, tree: Tree):
        self._lines: list[Line] = []
        for child in tree.children:
            if isinstance(child, Tree) and child.data in ("line", "end_line"):
                self._lines.append(Line(
                    content=self._extract_content(child),
                    span=(child.meta.start_pos, child.meta.end_pos),
                ))

    def index_of(self, line: Line) -> int:
        return next(i for i, l in enumerate(self._lines) if l is line)

    def first(self) -> Line | None:
        return self._lines[0] if self._lines else None

    def last(self) -> Line | None:
        return self._lines[-1] if self._lines else None
    
    def find(self, predicate) -> Line | None:
        return next((l for l in self._lines if predicate(l)), None)

    def find_all(self, predicate) -> list[Line]:
        return [l for l in self._lines if predicate(l)]

    def insert_before(self, anchor: Line, text: str) -> tuple[tuple[int, int], str]:
        pos = anchor.span[0]
        return (pos, pos), text

    def insert_after(self, anchor: Line, text: str) -> tuple[tuple[int, int], str]:
        pos = anchor.span[1]
        return (pos, pos), text

    def _extract_content(self, node):
        """Unwrap structural wrapper Trees (element, instruction, ...)
        down to the single typed dataclass inside, or None for blank/comment-only lines."""
        if isinstance(node, Tree):
            for child in node.children:
                result = self._extract_content(child)
                if result is not None:
                    return result
            return None
        if isinstance(node, Token):
            return None
        return node  # a dataclass: Title, Resistor, ParamStatement, ...
    

def check_roundtrip(source: str, tree) -> str:
    """Reconstruct from top-level statement spans; fail if
    anything non-whitespace falls between recognized nodes."""
    def span(node):
        if hasattr(node, "span"):       # Node with a span attribute (e.g., Resistor)
            return node.span
        if hasattr(node, "meta"):       # Tree
            return node.meta.start_pos, node.meta.end_pos
        return node.start_pos, node.end_pos  # Token

    children = sorted(tree.children, key=lambda c: span(c)[0])
    out = []
    pos = 0
    for child in children:
        start, end = span(child)
        assert start >= pos, f"Child node starts before the current position: start={start}, pos={pos}"
        gap = source[pos:start]
        assert gap.strip() == "", f"Non-whitespace content missing from tree: {gap!r}"
        out.append(gap)
        out.append(source[start:end])
        pos = end
    tail = source[pos:]
    assert tail.strip() == "", f"Non-whitespace trailing content missing from tree: {tail!r}"
    out.append(tail)
    return "".join(out)

def parse_netlist(netlist_content: str):
    with open(Path(__file__).parent.absolute() / "ngspice.lark") as grammar:
        parser = Lark(grammar, parser="lalr", propagate_positions=True, strict=True)
        c = parser.parse(netlist_content)
        return c

def apply_edit(source: str, span: tuple[int, int], new_text: str) -> str:
    start, end = span
    return source[:start] + new_text + source[end:]

def apply_edits(source: str, edits: list[tuple[tuple[int, int], str]]) -> str:
    edits = sorted(edits, key=lambda e: e[0][0])
    out = []
    pos = 0
    for (start, end), new_text in edits:
        assert start >= pos, f"Overlapping or out-of-order edit at {start}"
        out.append(source[pos:start])
        out.append(new_text)
        pos = end
    out.append(source[pos:])
    return "".join(out)

def find_components(node):
    if isinstance(node, Tree):
        for child in node.children:
            yield from find_components(child)
    elif isinstance(node, Component):
        yield node

def find_lines(node):
    if isinstance(node, Tree):
        for child in node.children:
            yield from find_lines(child)
    elif isinstance(node, Line):
        yield node

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python nsgpice.py <input_netlist> <output_netlist>")
        sys.exit(1)
    input_netlist_file = Path(sys.argv[1])
    output_netlist_file = Path(sys.argv[2])
    with open(input_netlist_file, "r", encoding="utf-8") as f:
        netlist_content = f.read()
        parsed_netlist = parse_netlist(netlist_content)
        result = NetlistTransformer().transform(parsed_netlist)
        #print(result.children)
        
        lines = Lines(result)
        
        param_lines = lines.find_all(lambda l: isinstance(l.content, ParamStatement))
        title_line  = lines.find_all(lambda l: isinstance(l.content, Title))
        
        param_defn = ".param Ry = 22k\n"
        if param_lines:
            insert_edit = lines.insert_after(param_lines[-1], param_defn)
        elif title_line:
            insert_edit = lines.insert_after(title_line[0], param_defn)
        else:
            insert_edit = lines.insert_before(lines.first(), param_defn)

        components = list(find_components(result))
        r1 = next(c for c in components if isinstance(c, Resistor) and c.name=="R1")
        value_edit = (r1.value.span, "{Ry}")
        modified = apply_edits(netlist_content, [insert_edit, value_edit])

        Path(output_netlist_file).write_text(modified, encoding="utf-8")

        #print(parsed_netlist)
        # roundtrip = check_roundtrip(netlist_content, parsed_netlist)
        # if roundtrip != netlist_content:
        #     raise RuntimeError("Roundtrip reconstruction failed")
        # else: 
        #     print("Roundtrip reconstruction succeeded")
    # with open(output_netlist_file, "w") as f:
    #     f.write(roundtrip)

        