/**
 * PULLI Educational Data Layer: Learning & Education Modules
 * 
 * Sourced from:
 *   - Research-Docs/KOLAM_DESIGN_PRINCIPLES.md
 *   - Research-Docs/PROBLEM_STATEMENT_ANALYSIS.md
 *   - Research-Docs/ACADEMIC_REFERENCES.md
 *   - Research-Docs/SAMPLE_DATASET_AND_CORPUS.md
 */

export const learnModules = [
  {
    id: 1,
    slug: 'history',
    numberStr: '01',
    title: 'HISTORY & CULTURAL HERITAGE',
    subtitle: 'Cultural Context, Ethnomathematics & Traditional Typologies',
    difficulty: 'Beginner',
    estimatedMinutes: 10,
    sections: [
      {
        id: 'cultural-context',
        title: '1. Cultural & Spiritual Foundations',
        content: `Kolam (also known as Pulli Kolam, Sikku Kolam, Muggu in Andhra Pradesh/Telangana, or Hase in Karnataka) is an ancient South Indian floor art tradition. Drawn daily at dawn by women on threshold entryways using rice flour or limestone powder, Kolams embody two core purposes:`,
        bullets: [
          'Ethical & Ecological (Bhuta Yajna): Coarse rice powder serves as sustenance for ants, birds, and small insects, expressing harmony with non-human life.',
          'Mathematical & Symbolic: Sacred geometry representing cosmic order, symmetry, continuous life cycles, and ritual invitation.'
        ],
        concepts: [
          {
            term: 'Bhuta Yajna',
            definition: 'The traditional duty of offering food to non-human living creatures. In Kolam, this is practiced by using raw rice flour so the daily threshold drawings serve as a charitable meal that feeds ants, birds, and insects, honoring our shared ecosystem.'
          },
          {
            term: 'Ethnomathematics',
            definition: 'The study of mathematical ideas practiced implicitly within cultural traditions. Kolam is a premier example, where practitioners intuitively construct complex topological designs, Eulerian circuits, and symmetrical group operations without formal mathematical notation.'
          }
        ]
      },
      {
        id: 'four-typologies',
        title: '2. The Four Primary Kolam Typologies',
        content: `Academic literature classifies traditional Kolam floor drawings into four structural categories based on loop closure, grid reliance, and stroke topology:`,
        typologies: [
          {
            name: 'Pulli / Sikku Kolam',
            tamil: 'புள்ளி / சிக்கு கோலம்',
            desc: 'Continuous loop strokes winding around a regular matrix of dots (pullis) without intersecting dot centers. Requires Eulerian circuit closure.',
            visualId: 'sikku'
          },
          {
            name: 'Kodu / Kambi Kolam',
            tamil: 'கோடு / கம்பி கோலம்',
            desc: 'Straight or diagonal line segments directly connecting dot to dot to form geometric polygons, stars, and lattices.',
            visualId: 'kambi'
          },
          {
            name: 'Freehand / Rangoli',
            tamil: 'ரங்கோலி',
            desc: 'Decorative organic or floral designs drawn without strict adherence to underlying dot lattices.',
            visualId: 'freehand'
          },
          {
            name: 'Bramha Mudi',
            tamil: 'பிரம்ம முடி',
            desc: 'Single endless knot loop with no beginning or end, symbolizing eternity and non-duality.',
            visualId: 'bramhamudi'
          }
        ]
      },
      {
        id: 'regional-variations',
        title: '3. Regional Nomenclature Across India',
        content: `While PULLI focuses on Tamil Nadu Pulli Kolam geometry, closely related dot-grid ethnomathematical traditions span across South and Central India:`,
        table: [
          { region: 'Tamil Nadu', name: 'Pulli / Sikku Kolam', gridType: 'Square & Interlocking Triangular' },
          { region: 'Andhra Pradesh & Telangana', name: 'Muggu', gridType: 'Square Matrix (Chukkala Muggu)' },
          { region: 'Karnataka', name: 'Hase / Rangoli', gridType: 'Lattice & Linear Geometry' },
          { region: 'Kerala', name: 'Pookkalam (Floral)', gridType: 'Concentric Circular Rings' },
          { region: 'Maharashtra & North India', name: 'Rangoli / Alpana', gridType: 'Freehand & Radial Powder Art' }
        ]
      }
    ],

  },
  {
    id: 2,
    slug: 'mathematics',
    numberStr: '02',
    title: 'MATHEMATICS & GRAPH THEORY',
    subtitle: 'Lattice Coordinates, MultiGraph Representation & Eulerian Constraints',
    difficulty: 'Intermediate',
    estimatedMinutes: 15,
    sections: [
      {
        id: 'lattice-coordinates',
        title: '1. Coordinate Space & Lattice Normalization',
        content: `In PULLI, a Kolam is digitized into a normalized coordinate grid where integer coordinates denote dot anchor centers and half-integer coordinates denote loop-around intermediate points.`,
        simpleTerms: 'Computers cannot naturally understand hand-drawn loops. We create a digital grid where dots sit on whole numbers (1, 2, 3) and loop lines sit on half-numbers (1.5, 2.5). This allows the algorithm to track exactly how the line moves around the dots without colliding with them.',
        bullets: [
          'Integer Coordinates (x, y) ∈ ℤ²: Represent Pulli dot anchor positions visited or looped around.',
          'Half-Integer Coordinates (x+0.5, y+0.5): Loop curve points where strokes pass between adjacent dots.',
          'Polyline Trace: Sampled at ~0.5u spatial resolution, storing exact stroke trajectory order.'
        ],
        concepts: [
          {
            term: 'Half-Integer Grid (0.5u)',
            definition: 'A dual coordinate space allowing continuous curves to loop precisely around dots without touching their center coordinate.'
          }
        ]
      },
      {
        id: 'multigraph-formulation',
        title: '2. MultiGraph Formulation (NetworkX)',
        content: `Why is an ordinary simple graph G = (V, E) insufficient for Kolams? Traditional Kolam lines frequently run twice in parallel along the exact same dot boundary segment. PULLI models patterns as a NetworkX MultiGraph G = (V, E, k) where edge multiplicity k(u, v) ≥ 1 explicitly preserves double-strand strokes.`,
        simpleTerms: 'In a normal computer graph, point A and point B are connected by only one single line. But in Kolam, lines often run parallel side-by-side between the same dots. PULLI uses a "MultiGraph" structure which allows multiple parallel connections, representing these dual-line strokes accurately.',
        concepts: [
          {
            term: 'Edge Multiplicity k(u, v)',
            definition: 'The number of parallel stroke segments traversing between nodes u and v. Accounted for during single-stroke verification.'
          }
        ]
      },
      {
        id: 'eulerian-theorem',
        title: '3. Eulerian Circuit Theorem & Even Degree Gate',
        content: `A central mathematical property of authentic single-stroke (Sikku) Kolams is Eulerian continuity. According to Euler's Theorem for connected graphs:`,
        formula: 'Connected Graph G is Eulerian  ⟺  ∀ v ∈ V, 2 | deg(v)',
        contentPost: `PULLI's analyzer verifies that every lattice intersection node has an even total degree (sum of incoming and outgoing strand multiplicities). If all vertices have even degrees and the graph forms a single connected component, the stroke can be drawn in one continuous movement without retracing.`,
        simpleTerms: 'This is the core "single-stroke validity check." To draw a loop continuously without lifting the pen or repeating a line, each dot must have an even number of lines meeting at it. If all dots have an even degree, Euler\'s law mathematically guarantees that the Kolam is solvable in a single loop.',
        concepts: [
          {
            term: 'Even Degree Condition',
            definition: 'Every node must have an even number of connecting strand edges so that every entry into a node has a corresponding exit.'
          }
        ]
      },
      {
        id: 'mdl-motif-induction',
        title: '4. Minimum Description Length (MDL) Principle',
        content: `To find the minimal repeating motif vocabulary without overfitting, PULLI applies the Minimum Description Length (MDL) principle:`,
        formula: 'L(G, M) = L(M) + L(G | M)',
        contentPost: `A candidate motif is accepted into the pattern vocabulary if and only if the code length to describe the pattern WITH the motif is strictly shorter than describing the raw uncompressed graph: L(G, M) < L(G, ∅).`,
        simpleTerms: 'Giant Kolams look incredibly complex, but they are built of smaller repeating designs (motifs). PULLI uses this data-compression rule to automatically identify those repeating motifs. By learning the "design DNA" of a Kolam, our AI can generate new, mathematically valid variations. (Here, G represents the Graph and M represents the Motif).'
      }
    ],

  },
  {
    id: 3,
    slug: 'symmetry',
    numberStr: '03',
    title: 'SYMMETRY IN PATTERNS (D₄ GROUP)',
    subtitle: 'The 8 Dihedral Operations, Rotations, Reflections & Canonical Induction',
    difficulty: 'Intermediate',
    estimatedMinutes: 12,
    sections: [
      {
        id: 'd4-overview',
        title: '1. The Dihedral D₄ Group of Order 8',
        content: `The spatial structure of traditional Kolams is overwhelmingly governed by the Dihedral Group D₄, consisting of 4 rotational symmetries and 4 reflectional symmetries:`,
        formula: 'D₄ = { I, R₉₀, R₁₈₀, R₂₇₀, Mₕ, Mᵥ, Mₔ₁, Mₔ₂ }',
        simpleTerms: 'Imagine a square sheet of paper. There are exactly 8 ways you can rotate or flip it over so that it still fits perfectly in the same square footprint. This set of 8 operations is called the D₄ symmetry group. In Kolam, this math ensures that if you draw one corner, it mirrors perfectly to all other sides.',
        bullets: [
          'Identity (I): Original orientation (0°).',
          'Rotations (R₉₀, R₁₈₀, R₂₇₀): Quarter, half, and three-quarter turns around the pattern centroid.',
          'Horizontal & Vertical Reflections (Mₕ, Mᵥ): Mirror flips across principal axes.',
          'Diagonal Reflections (Mₔ₁, Mₔ₂): Mirror flips across 45° main and anti-diagonals.'
        ]
      },
      {
        id: 'motif-canonicalization',
        title: '2. D₄ Motif Canonicalization',
        content: `When PULLI scans a Kolam trace for local motifs, the same physical motif may appear in different orientations across four quadrants. The engine transforms each candidate subgraph through all 8 D₄ operations to compute its canonical isomorphism signature:`,
        simpleTerms: "A single design shape can be rotated or mirrored in 8 different directions, which might look like 8 different paths to a computer. PULLI automatically standardizes (canonicalizes) them so it recognizes they are all the exact same 'motif' regardless of which way they are turned.",
        concepts: [
          {
            term: 'Canonical Signature',
            definition: 'A unique topological hash assigned to a motif shape regardless of its rotation or mirror orientation on the grid.'
          }
        ]
      },
      {
        id: 'symmetric-generation',
        title: '3. Rule-Based Symmetric Generation',
        content: `By storing a single canonical motif and its D₄ symmetry operations, the PULLI generator can stamp the motif onto a target dot grid and rotate/reflect it across all quadrants, producing a complete 4-fold symmetric Kolam pattern automatically.`,
        simpleTerms: 'Instead of programming all four corners of a massive Kolam, our system only needs to remember a single quadrant\'s design. The algorithm automatically rotates and mirrors it to generate a perfectly balanced, 4-fold symmetric pattern.'
      }
    ],

  },
  {
    id: 4,
    slug: 'tutorials',
    numberStr: '04',
    title: 'HANDS-ON TUTORIALS (THE 5 RULES)',
    subtitle: 'Interactive Visual Walkthroughs of the Core Kolam Design Principles',
    difficulty: 'Interactive',
    estimatedMinutes: 15,
    sections: [
      {
        id: 'rule-1-dot-grid',
        title: 'Rule 1: The Dot Grid (Pulli Lattice)',
        content: `Every traditional Kolam begins by laying down a regular grid of dots called Pullis. The grid establishes the mathematical anchor geometry for the entire pattern. In our digital model, the coordinate space is normalized such that dots reside on integer coordinates (x, y) ∈ ℤ², while the curves pass through intermediate half-integer coordinates (x + 0.5, y + 0.5) to loop cleanly around dots.`,
        simpleTerms: 'Every traditional Kolam starts with a regular grid of dots (Pullis). These dots act as visual guides for the hand, showing exactly where lines should bend or loop without colliding with the dot centers.',
        bullets: [
          'Square Grid (N × N): Straight rows and columns (e.g., 5×5, 7×7)',
          'Triangular / Rhombus Grid: Interlocking rows with offset columns (e.g., 1-3-5-3-1)'
        ]
      },
      {
        id: 'rule-2-continuous-loop',
        title: 'Rule 2: Continuous Loop (Sikku Continuity)',
        content: `Authentic Sikku (knot) Kolams are drawn in a single unbroken stroke. The line must travel continuously around the dot grid, winding between anchor points, and return precisely to its origin. In graph theory, this is modeled as an Eulerian Circuit: the stroke represents an endless loop (like the sacred Bramha Mudi symbol) representing infinity.`,
        formula: 'Connected Graph G is Eulerian  ⟺  ∀ v ∈ V, 2 | deg(v)',
        simpleTerms: 'To draw a loop continuously without lifting the pen or repeating a line, every single dot must have an even number of lines meeting at it (like 2 or 4). In graph theory, this is the rule for an Eulerian Circuit.'
      },
      {
        id: 'rule-3-dot-enclosure',
        title: 'Rule 3: Complete Dot Enclosure',
        content: `A core topological rule of traditional Kolam design is enclosure completeness. No guide dot (pulli) may be left stranded or un-encircled outside the drawn loop structure. When the drawing is finished, every dot in the grid must lie within the boundaries of at least one closed loop, serving as a visual anchor and symbol of universal containment.`,
        simpleTerms: 'No dot can be left sitting alone outside the drawing. Every dot must be encircled by at least one loop. This acts as a topological boundary, keeping the design complete.'
      },
      {
        id: 'rule-4-smoothness',
        title: 'Rule 4: Smooth 45° Diagonal Arcs',
        content: `Kolam lines traverse the grid at exact 45° diagonal angles relative to the principal axes. Traditional designs never make sharp 90° right-angled corners. Instead, when changing direction around a dot, the line curves gracefully using Bezier arcs. Furthermore, parallel line segments frequently pass alongside each other, creating double-strand edges.`,
        simpleTerms: 'Kolam lines travel diagonally at 45-degree angles and loop smoothly around the dots instead of making sharp, boxy 90-degree corners. This gives the drawing its signature organic, wave-like flow.'
      },
      {
        id: 'rule-5-symmetry',
        title: 'Rule 5: D₄ Dihedral Symmetry',
        content: `Traditional Kolams display high geometric symmetry. The patterns are governed by the Dihedral Group D₄ of order 8, containing 4 rotational operations (0°, 90°, 180°, 270°) and 4 reflectional operations (Horizontal, Vertical, and two Diagonals). A practitioner draws a single seed motif in one quadrant, and mirrors it across all axes to complete the entire design.`,
        formula: 'D₄ = { I, R₉₀, R₁₈₀, R₂₇₀, Mₕ, Mᵥ, Mₔ₁, Mₔ₂ }',
        simpleTerms: 'D₄ is a group of 8 actions you can perform on a square: 4 rotations (turning it by 90°, 180°, or 270°) and 4 mirrors (flipping it horizontally, vertically, or diagonally). Every symmetric Kolam is generated by applying these 8 operations to a single corner design.'
      }
    ]
  }
]
