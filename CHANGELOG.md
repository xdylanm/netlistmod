# Changelog

## Unreleased

- Implemented byte-preserving source text and spans, including BOM-aware
  decoding, configurable fallbacks, atomic file writes, and line/column
  diagnostics.
- Added the public error hierarchy, `Dialect` enum, and package exports.
- Added a strict, cached ngspice LALR parser for source structure, including
  grammar-defined syntax, typed title/comment/directive/opaque nodes,
  immediate continuation spans, required final `.end`, and positioned errors
  for unsupported element lines.
- Added ngspice 47 discrepancy probes, grammar/spec traceability, positive and
  negative structural corpora, property/performance tests, and wheel resource
  checks.
- Spec entries now cite the ngspice manual as `[ngspice-manual] §<section>
  "<title>"` against the edition recorded in `docs/references.md`; the spec
  checker enforces the form and rejects the previous, incorrect section numbers.
- `//` is an end-of-line comment delimiter alongside `;` and `$` (manual
  §2.4.4); a standalone `//` line is still rejected, and a path containing
  `//` must be quoted.
- Each line of a continued statement may end in an end-of-line comment
  (manual §2.4.5). Statement nodes now have `trailing_comments` (a tuple of
  spans) instead of `trailing_comment`.
- `.include` and `.lib` can no longer be continued (manual §2.4.5); a `+`
  line after them is a positioned syntax error.
- A line ending in `\\` continues a statement (manual §2.4.5); the next line
  must start with statement text.
- Made `SourceText.write()` preserve existing permission bits and write through
  symlinks; new files use normal umask-derived permissions.
