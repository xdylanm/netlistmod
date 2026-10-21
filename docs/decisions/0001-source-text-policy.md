# 0001 — Source-text encoding and line policy

- **Status:** accepted
- **Date:** 2026-10-21
- **Context:** Source text must round-trip byte-for-byte while supporting files
  produced by LTspice and retaining exact line endings.
- **Decision:**
  - Decode a recognized BOM first (UTF-8, UTF-16 LE, or UTF-16 BE), then strict
    UTF-8, then the configurable fallback sequence `cp1252`, `latin-1`.
    UTF-32 BOMs are unsupported. If data after a recognized BOM is malformed,
    report an encoding error instead of trying another codec.
  - Keep the fallback sequence configurable. `latin-1` follows `cp1252` because
    the latter rejects five byte values; `latin-1` maps every byte and makes
    fallback decoding total.
  - Treat LF and CRLF as line terminators in the source layer. A lone CR is
    ordinary source text. Do not use APIs such as `str.splitlines()` that
    recognize additional Unicode and control-character separators.
- **Consequences:** The selected codec and BOM are retained for writes, and
  byte-oriented file I/O avoids newline translation. UTF-16 without a BOM is
  not detected; LTspice-produced fixtures validate the policy before it is
  expanded.
