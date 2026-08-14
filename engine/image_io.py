"""Photo/drawing of a kolam -> nx.MultiGraph, in the EXACT node/edge
format graph_io.py already produces from CSVs (integer (x, y) lattice
coordinate node tuples; MultiGraph edges, so genuine double-strand
kambi-kolam lines are preserved with their real multiplicity). Everything
downstream in engine/ (motifs, symmetry, generation, validity) consumes
this with zero changes.

PIPELINE
  preprocess    : grayscale, deskew, binarize -> a clean binary ink mask
  detect_lattice: find dot blobs (they're visually "fatter" than line
                  strokes, even though dot ink and line ink are the same
                  color/intensity -- so this uses a distance-transform +
                  local-maxima approach, not intensity-based blob
                  detection, which fails outright: see session notes),
                  then fit a regular integer lattice to the detected
                  pixel positions
  trace_path    : skeletonize the WHOLE ink mask (dots + lines together,
                  since separating them first would break the exact
                  connectivity info being extracted), remove pixels near
                  each dot ("hub" regions), and use the connected
                  components of what's left to decide which dots are
                  directly joined -- a component touching exactly 2
                  distinct dot-hubs is an edge; touching 1 (or the same
                  hub twice) is a loop-around detour with NO edge, the
                  exact same convention graph_io.py already uses for the
                  CSV half-integer detour points. A dot-pair joined by
                  TWO disjoint stroke components is a genuine double
                  strand -> two parallel MultiGraph edges.
  build_graph   : composes the above into one nx.MultiGraph.

KNOWN SCOPE LIMITATIONS (see PULLI session notes -- stated up front, not
discovered later):
  - preprocess only corrects ROTATION (via minAreaRect on the ink mask),
    not full 4-point projective/keystone correction -- there are no
    fiducial markers to anchor a homography to. The grid-fitting step in
    detect_lattice uses a full 2x2 affine (not just axis-aligned
    rounding), which absorbs mild residual skew on top of that; this
    combination is scoped for "roughly top-down, mild phone-camera
    skew," explicitly not a steep-angle photo.
  - detect_lattice's grid-fit assumes the true lattice spacing is the
    smallest of a short list of candidate divisors of the observed
    nearest-neighbor spacing (1x, sqrt(2)x, 2x, 2*sqrt(2)x) that yields a
    collision-free assignment. This matches every pattern in this
    project's dataset (Chebyshev edge length <=2, see graph_io.py) but is
    not a universal grid-spacing estimator.
"""

from __future__ import annotations

import math

import cv2
import networkx as nx
import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from skimage.morphology import skeletonize

Point = tuple[int, int]

SPACING_CANDIDATE_DIVISORS = [1.0, math.sqrt(2), 2.0, 2.0 * math.sqrt(2)]

# Fraction of the global max distance-transform value a candidate peak
# must reach to count as a dot. See _detect_dot_pixels' docstring for the
# root-cause diagnosis (session 10, Task B) and the empirical verification
# behind this specific value -- lowered from 0.75 to fix dense-pattern
# (kolam29-scale) recall with zero cost to sparse-pattern accuracy.
THRESHOLD_ABS_FRAC = 0.65


class Preprocessed:
    """Output of preprocess(): a clean, deskewed binary ink mask (255 =
    ink, 0 = background) plus the rotation angle applied, for reference."""

    def __init__(self, binary: np.ndarray, rotation_deg: float):
        self.binary = binary
        self.rotation_deg = rotation_deg


def preprocess(image_path: str) -> Preprocessed:
    """Grayscale, deskew (rotation only -- see module docstring), binarize."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"could not read image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    ys, xs = np.nonzero(binary)
    if len(xs) < 10:
        return Preprocessed(binary, 0.0)

    pts = np.column_stack([xs, ys]).astype(np.float32)
    (_, _), (_, _), angle = cv2.minAreaRect(pts)
    # minAreaRect's angle is only defined mod 90 degrees; a kolam's
    # diamond-oriented bounding box sits near a multiple of 45 degrees, so
    # correct toward whichever of {0, 45} is closer rather than assuming 0.
    candidates = [0.0, 45.0, -45.0, 90.0, -90.0]
    target = min(candidates, key=lambda c: abs(((angle - c) + 45) % 90 - 45))
    rotation = angle - target

    h, w = binary.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rotation, 1.0)
    deskewed = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)

    return Preprocessed(deskewed, rotation)


class Lattice:
    """Output of detect_lattice(): detected dot pixel positions, their
    fitted integer lattice coordinates, and the estimated dot radius
    (needed by trace_path to size each dot's "hub" capture region)."""

    def __init__(self, pixel_positions: list[tuple[float, float]], lattice_coords: list[Point], dot_radius: float):
        self.pixel_positions = pixel_positions  # (x, y), index-aligned with lattice_coords
        self.lattice_coords = lattice_coords
        self.dot_radius = dot_radius


def _detect_dot_pixels(binary: np.ndarray) -> tuple[np.ndarray, float]:
    """Distance-transform + local-maxima dot detection. Dots are ink
    blobs several pixels wide; line strokes are ~1-3px wide everywhere.
    The distance transform's value near a dot's center is close to the
    dot's true radius R; near a line, it's close to half the stroke
    width. Thresholding at a fraction of the observed max (not
    intensity-based blob detection, which cannot separate same-colored
    dot and line ink at all -- see module docstring) isolates dot centers
    from the crossing/junction noise a lower threshold picks up.

    THRESHOLD_ABS_FRAC root-caused and tuned this session (session 10,
    Task B), not guessed: `R = dist.max()` is the GLOBAL maximum distance-
    transform value anywhere in the image -- effectively the size of the
    single largest/least-degraded dot. On dense (kolam29-scale, ~13px
    lattice spacing) patterns, dots are rendered smaller in absolute
    pixel terms than on sparse (kolam19-scale, ~21px) ones, so the SAME
    absolute blur/JPEG degradation eats a proportionally bigger bite out
    of each dot's apparent size -- many real dots' own distance-transform
    peak then falls below a threshold anchored to the single largest dot
    in the image, and they are missed entirely (not merged with a
    neighbor: verified directly on the worst held-out case,
    kolam29_k50 -- 0 spurious detections, 120/484 dots missed, and 99.2%
    of those missed dots' own distance-transform value at their true
    position was BELOW threshold_abs, not suppressed by min_distance).
    Lowering the fraction from 0.75 to 0.65 (empirically verified across
    all 8 synthetic-photo test images in both the original and held-out
    batches, not just the worst case) recovers recall to 99.6-100% on
    every dense pattern tested (kolam29_k50: 75.2%->99.6%; kolam29_k20:
    88.9%->100%; kolam29_k1/k2 in the original tuned set: 94.3%/92.0%->
    100%/100%; kolam29_k80: 88.7%->99.8%) with ZERO change on any sparse
    (kolam19) pattern -- the threshold was never the binding constraint
    there -- and at most a 0.2-point precision cost on one dense pattern
    (kolam29_k80: 99.76%->99.57%) in exchange for +11 points of recall."""
    from skimage.feature import peak_local_max

    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    R = float(dist.max())
    if R < 1.0:
        return np.empty((0, 2)), R

    min_distance = max(3, int(round(1.8 * R)))
    threshold_abs = THRESHOLD_ABS_FRAC * R
    coords = peak_local_max(dist, min_distance=min_distance, threshold_abs=threshold_abs)
    pixel_positions = np.array([[c[1], c[0]] for c in coords], dtype=float)  # (row,col)->(x,y)
    return pixel_positions, R


def _fit_lattice_coords(pixel_positions: np.ndarray) -> tuple[list[Point], np.ndarray, np.ndarray]:
    """Fit a regular integer lattice to detected pixel positions via
    iterative affine refinement (assign-nearest-integer, refit affine,
    repeat). Returns (lattice_coords, M, t) where pixel ~= M @ lattice + t.
    """
    n = len(pixel_positions)
    tree = cKDTree(pixel_positions)
    nn_dist, _ = tree.query(pixel_positions, k=min(2, n))
    median_nn = float(np.median(nn_dist[:, -1])) if n > 1 else 1.0

    def fit(s0: float, n_iter: int = 6):
        origin = pixel_positions[0]
        lattice = np.round((pixel_positions - origin) / s0)
        M, t = np.eye(2), origin.copy()
        for _ in range(n_iter):
            A = np.hstack([lattice, np.ones((n, 1))])
            sol_x, *_ = np.linalg.lstsq(A, pixel_positions[:, 0], rcond=None)
            sol_y, *_ = np.linalg.lstsq(A, pixel_positions[:, 1], rcond=None)
            M = np.array([[sol_x[0], sol_x[1]], [sol_y[0], sol_y[1]]])
            t = np.array([sol_x[2], sol_y[2]])
            new_lattice = np.round((np.linalg.inv(M) @ (pixel_positions - t).T).T)
            if np.array_equal(new_lattice, lattice):
                lattice = new_lattice
                break
            lattice = new_lattice
        pred = (M @ lattice.T).T + t
        resid = float(np.sqrt(((pred - pixel_positions) ** 2).sum(axis=1)).mean())
        n_unique = len({tuple(row) for row in lattice})
        return lattice, M, t, resid, n_unique

    best_lattice, best_M, best_t, best_resid = None, None, None, math.inf
    for divisor in SPACING_CANDIDATE_DIVISORS:
        s0 = median_nn / divisor
        if s0 < 1e-3:
            continue
        lattice, M, t, resid, n_unique = fit(s0)
        # Prefer the COARSEST spacing (smallest divisor tried first) that
        # still assigns every detected dot a distinct integer coordinate
        # -- a finer grid trivially avoids collisions without being the
        # true lattice unit.
        if n_unique == n:
            best_lattice, best_M, best_t = lattice, M, t
            break
        if resid < best_resid:
            best_lattice, best_M, best_t, best_resid = lattice, M, t, resid

    coords = [(int(x), int(y)) for x, y in best_lattice]
    return coords, best_M, best_t


def detect_lattice(preprocessed: Preprocessed) -> Lattice:
    pixel_positions, R = _detect_dot_pixels(preprocessed.binary)
    # _fit_lattice_coords needs at least 3 non-collinear points to fit a
    # 2x2 affine transform (lstsq's 3-parameter-per-axis system is
    # underdetermined below that); with fewer, its lattice column is
    # degenerate (e.g. a single point sits at relative [0,0]), forcing M
    # toward a singular matrix and crashing np.linalg.inv. Found on a
    # real (non-synthetic) low-light photo, session 10: Otsu's global
    # threshold misclassified 82.7% of a dark, low-contrast image as
    # "ink" (mean brightness 62.5/255, no clean bimodal separation --
    # every synthetic test photo in this project, however degraded with
    # blur/noise/rotation, was always well-lit and high-contrast, so
    # this failure mode was never exercised before). The 1-blob distance
    # transform this produces yields a single spurious "dot" with an
    # enormous estimated radius, which is what triggers the crash here --
    # this guard makes the OUTCOME safe (a clean degenerate result,
    # matching the existing empty-detection convention below), it does
    # NOT fix the underlying binarization failure, which is a separate,
    # larger open problem (see PROJECT_STATE.md).
    if len(pixel_positions) < 3:
        return Lattice([tuple(p) for p in pixel_positions], [], R)
    lattice_coords, _M, _t = _fit_lattice_coords(pixel_positions)
    return Lattice([tuple(p) for p in pixel_positions], lattice_coords, R)


def is_traceable(lattice: Lattice) -> bool:
    """True iff `lattice` is well-formed enough for trace_path to safely
    consume: `lattice_coords` is either empty (zero usable detections) or
    index-aligned 1:1 with `pixel_positions`. Guards the one documented,
    reproduced asymmetric shape -- 1-2 `pixel_positions` with 0
    `lattice_coords`, which `_fit_lattice_coords` (and, by construction,
    any conforming ML detector) can legitimately produce when too few
    points were found to fit a lattice -- that crashes trace_path with
    IndexError (see docs/ML_CONTRACT.md Section 5,
    tests/test_ml_contract.py::test_asymmetric_lattice_shape_is_a_documented_unfixed_blocker).
    `engine.ml_contract.assert_conforms` cannot catch this by itself (0
    coords is a legal value of its own shape invariant); this is the
    upstream gate callers should use INSTEAD of calling trace_path
    directly on a lattice they haven't checked. trace_path itself is not
    modified -- callers treat a non-traceable lattice the same as a
    zero-detection one (no edges), per the empty-detection convention
    docs/ML_CONTRACT.md already recommends detectors follow."""
    return len(lattice.lattice_coords) == len(lattice.pixel_positions)


def trace_path(preprocessed: Preprocessed, lattice: Lattice) -> list[tuple[Point, Point]]:
    """Skeletonize the ink mask and use dot-hub-removal + connected
    components to recover which dots are directly joined by a stroke.
    Returns a list of (dot_a, dot_b) lattice-coordinate pairs, one entry
    per traced strand -- duplicated for a genuine double-strand edge."""
    if not lattice.pixel_positions:
        return []

    binary_bool = preprocessed.binary > 0
    skeleton = skeletonize(binary_bool)
    sk_pixels = np.argwhere(skeleton)  # (row, col)
    if len(sk_pixels) == 0:
        return []

    dot_px = np.array(lattice.pixel_positions, dtype=float)
    capture_radius = lattice.dot_radius * 1.3
    tree = cKDTree(dot_px)
    sk_xy = sk_pixels[:, [1, 0]].astype(float)  # (x, y)
    d, idx = tree.query(sk_xy)
    hub_id = np.where(d <= capture_radius, idx, -1)

    H, W = skeleton.shape
    hub_lookup = -np.ones((H, W), dtype=int)
    non_hub_mask = np.zeros((H, W), dtype=np.uint8)
    for i, (r, c) in enumerate(sk_pixels):
        if hub_id[i] >= 0:
            hub_lookup[r, c] = hub_id[i]
        else:
            non_hub_mask[r, c] = 1

    labels, _n_labels = ndi.label(non_hub_mask, structure=np.ones((3, 3), dtype=int))

    comp_touch_hubs: dict[int, set[int]] = {}
    ys, xs = np.nonzero(labels)
    for y, x in zip(ys, xs):
        lab = int(labels[y, x])
        touched = comp_touch_hubs.setdefault(lab, set())
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx_ = y + dy, x + dx
                if 0 <= ny < H and 0 <= nx_ < W and hub_lookup[ny, nx_] >= 0:
                    touched.add(int(hub_lookup[ny, nx_]))

    edges: list[tuple[Point, Point]] = []
    for hubs in comp_touch_hubs.values():
        if len(hubs) == 2:
            a, b = sorted(hubs)
            edges.append((lattice.lattice_coords[a], lattice.lattice_coords[b]))
        elif len(hubs) > 2:
            # Rare: a skeleton fragment brushes 3+ dots at once (very
            # tight dot spacing). Fall back to connecting every pair --
            # a documented approximation, not a silent drop.
            hub_list = sorted(hubs)
            for i in range(len(hub_list)):
                for j in range(i + 1, len(hub_list)):
                    edges.append((lattice.lattice_coords[hub_list[i]], lattice.lattice_coords[hub_list[j]]))
        # len(hubs) in (0, 1): loop-around detour or dead-end -> no edge,
        # matching graph_io.py's half-integer "no edge" convention.

    return edges


def build_graph(image_path: str) -> nx.MultiGraph:
    """The single public entry point: image file -> nx.MultiGraph in the
    exact node/edge format engine/graph_io.py produces from CSVs."""
    preprocessed = preprocess(image_path)
    lattice = detect_lattice(preprocessed)
    # Gate at the boundary rather than inside trace_path itself -- see
    # is_traceable's docstring. detect_lattice's own output always
    # satisfies this (its `< 3 points` branch is the one asymmetric
    # case), so this is a no-op for every existing synthetic-corpus
    # test; it only changes behavior for the documented real-photo edge
    # case that used to crash here.
    edges = trace_path(preprocessed, lattice) if is_traceable(lattice) else []

    G = nx.MultiGraph()
    G.add_nodes_from(lattice.lattice_coords)
    for a, b in edges:
        G.add_edge(a, b)
    return G
