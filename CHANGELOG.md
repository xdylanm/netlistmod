# Changelog

## Unreleased

- Implemented byte-preserving source text and spans, including BOM-aware
  decoding, configurable fallbacks, atomic file writes, and line/column
  diagnostics.
- Added the public error hierarchy, `Dialect` enum, and package exports.
- Added a strict, cached ngspice LALR parser for source structure, including
  grammar-defined syntax, typed title/comment/directive/opaque nodes,
  immediate continuation spans, required final `.end`, and positioned errors
  for unsupported element lines. The M2 rework is awaiting review.
- Added ngspice 47 discrepancy probes, grammar/spec traceability, positive and
  negative structural corpora, property/performance tests, and wheel resource
  checks.
- Spec entries now cite the ngspice manual as `[ngspice-manual] §<section>
  "<title>"` against the edition recorded in `docs/references.md`; the spec
  checker enforces the form and rejects the previous, incorrect section numbers.
- Made `SourceText.write()` preserve existing permission bits and write through
  symlinks; new files use normal umask-derived permissions.
