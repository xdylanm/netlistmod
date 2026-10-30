# Parsing structural ngspice source

The M2 structural parser uses a strict Lark grammar. Select the dialect
explicitly and pass a `SourceText` so spans refer to the decoded input:

```python
from netlistmod import Dialect, SourceText, parse

source = SourceText("Amplifier\n.title Small signal\n.op\n.end\n")
result = parse(source, Dialect.NGSPICE)

for item in result.items:
    original_text = source.text[item.span.start : item.span.end]
```

The result is an immutable sequence of typed nodes: `Title`, `TitleDirective`,
`BlankLine`, `CommentLine`, `UnknownDirective`, `OpaqueStatement`
(`.include`/`.lib`), `OpaqueBlock` (`.control` or nested `.if`), and `End`.
Every node has a character-offset `Span`; together, the spans tile the source.
The first physical line is always a title. Later `.title` lines are represented
as `TitleDirective`.

The netlist must be non-empty and end with `.end`. A final newline after
`.end` is optional; only blank lines may follow it. `parse("")` and a missing
`.end` raise `ParseError`. A comment or directive after `.end` is rejected.
Continuations must immediately follow their statement: a comment or blank line
between them is an error, as is a `+` line after a title, comment, blank line,
or `.end`.

Unknown dot-commands are preserved without interpretation. `.control`,
conditional blocks, `.include`, and `.lib` are opaque; the parser does not
read referenced files. A `.lib name` … `.endl` definition block is not
recognized in M2. Element lines are not parsed in M2. A device letter known
to ngspice but not implemented in this milestone raises
`UnsupportedConstruct`; malformed structural input raises `ParseError` with a
source position and excerpt. LTspice grammar support is a later milestone.

The parser intentionally follows the manual's strict structure rather than
ngspice's lenient behavior. For example, it rejects missing `.end`, content
after `.end`, standalone `//` lines, and continuations separated by comments or
blank lines. Solver observations are documented in
[`discrepancies.md`](../grammars/ngspice/discrepancies.md).

End-of-line comments start at `;`, `$` or `//` after a command, with or without
a space before the marker, and run to the end of the line. Every line of a
continued statement may end in one. Statement nodes list the comment spans in
`trailing_comments`; `raw` ends at the last non-comment text. Quote a path
that contains `//`: `.include a//b` includes `a`, while `.include "a//b"` keeps
the whole path.
