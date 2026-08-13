# Kolam CSV Data Format

Every fact in this document was established by directly inspecting
`kolam_data/Kolam CSV files/Kolam CSV files/{kolam19,kolam29,kolam109}.csv`
with pandas/numpy (commands and output are reproduced inline below where
useful) - not assumed from row/column counts or from memory of prior
work. Anything not directly verifiable from the CSVs themselves is
labeled **UNRESOLVED**.

## Dataset files

Three CSV files, one per "collection":

| file | rows | columns | patterns | trace length per pattern |
|---|---|---|---|---|
| `kolam19.csv` | 725 | 800 | 400 | 725 |
| `kolam29.csv` | 1685 | 200 | 100 | 1685 |
| `kolam109.csv` | 23765 | 200 | 100 | 23765 |

Verified: `df.isna().sum().sum() == 0` for all three files - **there are
zero missing values anywhere**. Verified: for every pattern column-pair
in every file, `x.notna().sum() == df.shape[0]` - **every pattern in a
file has exactly the same trace length as that file's row count.** This
means the CSV is not ragged/padded; row `i` is trace step `i` for every
pattern in the file simultaneously.

The "19"/"29"/"109" in the collection name does not have a confirmed
exact geometric meaning (e.g. it is not literally "coordinates range
0..19") - pattern 1 of kolam19 spans x,y in `[-18.5, 18.5]`, kolam29
spans `[-28.5, 28.5]`, kolam109 spans `[-108.5, 108.5]`. The names
correlate with pattern scale but the precise definition (grid width?
some other convention?) is **UNRESOLVED** - not needed for this task,
noted so it isn't asserted elsewhere as fact.

## CSV structure

- **One row** = one time-step of the single continuous drawn stroke, for
  every pattern in the file at once (row `i` is the `i`-th point of
  every pattern's trace).
- **Columns** are named `x-kolam {n}` / `y-kolam {n}`, `n` from 1 to the
  pattern count, 1-based. Each pair is one pattern's independent trace;
  the shared row index does NOT imply the patterns are spatially related
  to each other, only that they happen to be stored in lockstep columns.
- **No missing values** in any file (verified above) - no NaN-handling
  logic is actually load-bearing for this dataset, though a defensive
  `.dropna()` is harmless and kept in the loader.
- **Coordinate encoding**: every value in every file is an exact multiple
  of 0.5 (verified: `(values * 2) % 1` is exactly `0.0` everywhere, for
  every file). Precisely one of two cases holds for every point, never
  both or neither (verified on kolam19 pattern 1: 369 both-integer
  points, 356 one-integer/one-half-integer points, **zero** both-half
  points):
  - **both x and y are integers** - a dot-lattice position, or
  - **exactly one of x, y is a half-integer** (`n + 0.5`) - an
    intermediate point on the small loop the stroke draws around a dot
    it does not connect to (see "Loop-around points" below).
- **Pattern indexing**: 1-based (`x-kolam 1` .. `x-kolam 400` for
  kolam19). The bundled *rendered image* files
  (`kolam_data/Kolam19 Images/.../kolam19-N.jpg`) are separately
  0-based, and a prior session's inline code comment claimed
  `kolam19-26.jpg` corresponds to CSV pattern 27 (i.e. image index N ↔
  CSV pattern N+1) - this specific offset has **not been independently
  re-verified in this session** and should be treated as an unconfirmed
  carried-over claim, not a fact re-established here.
- Every sampled pattern (checked: first, middle, last pattern in each of
  the 3 files) has `first_point == last_point` - **every trace is a
  closed loop.**

## Trace representation

The ordered trace for pattern `n` in a collection is recovered simply by
reading `x-kolam {n}` / `y-kolam {n}` top-to-bottom and zipping them -
row order IS stroke order, with no reordering, resampling, or filtering
needed. This raw, unfiltered sequence is `KolamPattern.raw_trace` /
`trace_points` (see `docs/DATA_FORMAT.md` → `engine/kolam_pattern.py`).

No two consecutive rows are ever numerically identical (verified: 0
consecutive-duplicate `(x, y)` rows in all three files' pattern-1 trace)
- the raw trace contains no redundant repeated points to deduplicate.

## Dot representation

A **dot visit** is a trace point where both coordinates are exact
integers. Concretely (verified on kolam19 pattern 1): 369 of 725 raw
trace points (50.9%) are integer-coordinate points. Collapsing
*immediately consecutive* repeated dot-visits (the stroke dips out via a
loop-around and returns to the exact same dot - see below) yields a
reduced sequence of 313 points, spanning 184 distinct dot locations. This
same 50-59%-integer / reduce-consecutive-repeats pattern holds
consistently across all three files (kolam29 pattern 1: 56.1% integer,
472 distinct dots; kolam109 pattern 1: 59.0% integer, 7016 distinct
dots).

## Loop-around points

When the stroke passes near a dot without connecting to it, it does not
touch that dot's exact integer coordinate - it dips out to one
intermediate mixed-integer/half-integer point and back, forming a small
loop. Concrete verified example (kolam19 pattern 1, row indices 0-5):

```
row 0: (1.0, 0.0)   <- dot visit: (1, 0)
row 1: (2.0, 1.0)   <- dot visit: (2, 1)
row 2: (2.5, 2.0)   <- loop-around point (mixed: x half-integer)
row 3: (2.0, 2.5)   <- loop-around point (mixed: y half-integer)
row 4: (1.5, 2.0)   <- loop-around point (mixed: x half-integer)
row 5: (2.0, 1.0)   <- dot visit: (2, 1) again -- SAME dot as row 1
```

The stroke leaves dot `(2, 1)`, loops around dot `(2, 2)` on three sides
without ever landing on `(2, 2)`'s exact coordinate, and returns to
`(2, 1)`. Because the sequence of *dot visits* (integer-coordinate rows
only) goes `(2,1) -> (2,1)` here, this is collapsed to a single visit
with **no edge recorded** - `(2, 2)` is not connected to `(2, 1)` by this
detour. This is the load-bearing rule that distinguishes "the stroke
connects these two dots" from "the stroke merely passes near this dot."

## Edge representation

1. Filter the raw trace to integer-coordinate (dot-visit) points only.
2. Collapse immediately-consecutive repeated visits to the same dot
   (loop-around detours, per above) - this is NOT a self-loop edge, it
   is the absence of an edge.
3. Every consecutive pair of *distinct* dots remaining in this reduced
   sequence is one traversed edge instance, in stroke order.

Verified edge-length distribution (Chebyshev distance between the two
dots of a distinct edge pair), consistent across all three files:
**only distances 1 (orthogonal/diagonal adjacent) and 2 (skip-one-dot)
occur** - kolam19 pattern 1: 180 distance-1, 48 distance-2 edges (of 228
distinct pairs); kolam29 pattern 1: 528/152; kolam109 pattern 1:
7832/2796. No edge ever connects dots more than 2 lattice-steps apart.
A distance-2 edge is a real, deliberate stroke convention (the line
passes closely around, but does not stop at, the skipped dot) - not a
data artifact.

## Edge multiplicity

The same unordered dot-pair is sometimes traversed by the stroke more
than once - verified fraction of distinct pairs with multiplicity > 1:
kolam19 pattern 1: 84/228 (36.8%); kolam29 pattern 1: 156/680 (22.9%);
kolam109 pattern 1: 2364/10628 (22.2%). Concrete verified example
(kolam19 pattern 1, dots `(3,0)` and `(5,0)`):

```
rows 6-8:   (3,0) -> (4,-0.5) -> (5,0)   [passes BELOW skipped dot (4,0)]
rows 68-70: (5,0) -> (4, 0.5) -> (3,0)   [passes ABOVE skipped dot (4,0)]
```

The same two dots are connected twice by two genuinely different curve
paths (one arcing below the skipped middle dot, one arcing above it) -
the classic kambi/sikku kolam "double line" / "twin strand" visual
motif, not a duplicate-row data error (recall: zero literal duplicate
rows were found anywhere). An `nx.Graph` would silently collapse these
two distinct strands into one edge and corrupt vertex degree parity,
which breaks the Eulerian single-stroke validity check - this is why
`nx.MultiGraph` is required, not a stylistic preference.

## Known limitations

- The exact meaning of the "19"/"29"/"109" collection names is not
  confirmed beyond correlating with pattern scale - **UNRESOLVED**.
- The claimed 0-based-image-to-1-based-CSV index offset
  (`kolam19-26.jpg` ↔ CSV pattern 27) is carried over from a prior
  session's inline comment and was **not re-verified** in this pass -
  **UNRESOLVED**, do not rely on it without independent confirmation.
- All quantitative claims above about per-pattern statistics (integer
  fraction, edge-length distribution, multiplicity fraction) were
  checked on pattern 1 of each file (plus first/middle/last pattern for
  the closed-loop and 0.5-resolution checks) - not exhaustively on every
  one of the 600 total patterns across the three files. The qualitative
  rules (dot = integer coords, loop-around = no edge, edge length ∈
  {1, 2}, double strands are real) are structural/encoding-level claims
  expected to hold dataset-wide, but this has not been exhaustively
  verified pattern-by-pattern.
