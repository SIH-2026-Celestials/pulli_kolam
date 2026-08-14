# PROJECT STATUS — PULLI Kolam Design-Principle Engine

**Last Updated:** 2026-08-13 (merged changes)  
**Branch:** `master`

---

## Overview

PULLI is a computational platform that uses ML, computer vision, and graph theory to understand the structural grammar of traditional Indian kolam patterns and generate valid new ones.

---

## ✅ Completed Milestones

### Backend / Engine

| Milestone | Status | Notes |
|---|---|---|
| Kolam dataset ingestion (`kolam19`) | ✅ Complete | 400 geometric traces loaded |
| Dot detection pipeline | ✅ Complete | Grid-based pulli detection |
| ML Dot Lattice Detector (`experiments/m4_2`) | ✅ Complete | PyTorch lattice detection model with 99.9% recall and 99.9% precision |
| Stroke tracing algorithm | ✅ Complete | Sub-pixel resolution polyline traces |
| Graph representation (NetworkX MultiGraph) | ✅ Complete | Nodes + edges with repeated strands |
| D4 dihedral symmetry analysis | ✅ Complete | 8-fold symmetry group detection |
| Motif induction (fixed radius) | ✅ Complete | 82.8% structural edge recall |
| Motif induction (adaptive radius) | ✅ Complete | 99.5% structural edge recall |
| Eulerian trail validation | ✅ Complete | Single-stroke constraint verified |
| Automated test suite | ✅ Complete | All tests passing |

### Frontend

| Milestone | Status | Notes |
|---|---|---|
| Project scaffold (React + Vite) | ✅ Complete | Vite v8, React 19 |
| Design system (tokens, global styles) | ✅ Complete | Playfair Display + Inter, maroon/gold palette. Aligned color variables to the heritage editorial palette (deep maroon `#5A0615`, antique gold `#A97824`, warm ivory `#FBF8F1`, cream `#F5F0E6`, borders warm beige `#E6DCCB`). |
| Navbar component | ✅ Complete | Deep maroon, gold active underline, Login button |
| Theme toggle button | ✅ Complete | Default theme light, persists theme state via localStorage, toggles '.dark-theme' class on the documentElement and changes icon dynamically between Sun/Moon. |
| Reusable Decorative System | ✅ Complete | Created `KolamCornerDecoration`, `KolamDecoration` (divider/border), `KolamGridPattern` (subtle repeating dot lattices), and `KolamMotif` for inline decorations. |
| Hero section (3-column layout) | ✅ Complete | Heading, center Kolam SVG, AI meets tradition card with subtle grid overlays. |
| Center Kolam SVG illustration | ✅ Complete | Authentic 4-fold symmetric continuous loop art with automated SVG line-draw load animation and slow opacity pulse. |
| Drag-and-drop file upload modal | ✅ Complete | Interactive dropzone overlay showing 'Upload your Kolam / Drag & drop your image here / or / Browse files', including 10MB size limit check and drag states. |
| Feature strip (5 items) | ✅ Complete | Horizontal layout with vertical dividers |
| Live Analysis Pipeline card | ✅ Complete | 8-step stepper, 5 visual panels, progress bar |
| Generated Kolam Variations card | ✅ Complete | 4 thumbnails, Generate More button |
| Design Rule Summary | ✅ Complete | Grid, Symmetry, Stroke, Motif Families, Complexity |
| Footer component | ✅ Complete | Maroon, copyright, AICTE initiative credit, corner patterns and running borders |
| File upload functionality | ✅ Complete | Triggers analysis pipeline simulation |
| Generate More interactivity | ✅ Complete | Cycles between two variation sets |
| About page | ✅ Complete | Routed at `/about` |
| How it Works page | ✅ Complete | Routed at `/how-it-works` |
| Generate page | ✅ Complete | Routed at `/generate`; fixes navbar link that previously 404'd blank (no matching route) |
| 404 / catch-all route | ✅ Complete | Prevents blank page on unmatched routes |
| Gallery page (kolam archive browser) | ✅ Complete | Search/filter by number, 400-pattern grid, Load More pagination — moved up from "In Progress" below, it was already functionally complete |
| `npm run build` | ✅ Passing | Zero errors, clean production bundle |

---

## 🔄 In Progress

| Milestone | Status | Notes |
|---|---|---|
| Generative reconstruction (pattern generation) | 🔄 In Progress | Foundation laid via motif grammar |
| Backend API integration with frontend | 🔄 In Progress | REST endpoints planned |
| Kolam detail view | 🔄 In Progress | Route exists, content pending |

---

## 📋 Planned (Next Steps)

| Milestone | Status | Notes |
|---|---|---|
| Live ML inference pipeline (image → rules) | 📋 Planned | Model training in progress |
| REST API (FastAPI) for analysis endpoint | 📋 Planned | |
| Real-time websocket progress for analysis steps | 📋 Planned | |
| Kolam gallery with search and filters | 📋 Planned | |
| Mobile responsive layouts (tablet + mobile) | 📋 Planned | Desktop-first currently |
| PWA / offline capability | 📋 Planned | |

---

## Key Technical Metrics

| Metric | Value |
|---|---|
| Dataset | `kolam19` — 400 patterns |
| Dot Lattice | 37 × 37 |
| Evaluation Sample | 15 patterns |
| Fixed Radius Edge Recall | 82.8% |
| Adaptive Radius Edge Recall | 99.5% |
| ML Dot Recall | 99.78% (test set) |
| ML Dot Precision | 99.85% (test set) |
| ML Dot F1 Score | 99.81% (test set) |
| Automated Tests Passing | All |
| Frontend Build | ✅ Clean (Vite 8) |
| ESLint | ✅ 0 errors, 0 warnings |

---

## UI Reference

The Home page frontend has been implemented as a **pixel-accurate clone** of the reference design:

- **Navbar**: Deep maroon (`#500914`), PULLI brand, nav links with gold active underline, Login
- **Hero**: 3-column layout — typography + actions | center Kolam SVG | AI meets tradition card
- **Feature Strip**: 5 feature items with vertical dividers
- **Analysis Panel**: 8-step live pipeline, 5 visualization stages, 56% building graph progress
- **Variations Panel**: 4 generated Kolam thumbnails, Design Rule Summary
- **Footer**: Dark maroon, AICTE credit

---

*This document is auto-updated as milestones are reached.*
