# Interactive Tools + UI/UX Enhancements

## Overview
Add five client-side interactive tools and a suite of UX refinements to the Databricks Cross-Cloud Migration Runbook.

## Tools

### 1. Cloud Instance Type Mapper
Searchable/filterable table mapping AWS EC2, Azure VM, and GCP compute instance families to Databricks-equivalent SKUs. Side-by-side comparison mode.

- `src/components/InstanceTypeMapper.tsx`
- `src/data/instanceTypes.json` (~150 curated entries)
- Page: `/tools/instance-mapper`

### 2. Cost Comparison Calculator
Form-based tool estimating per-cloud monthly costs for compute clusters, storage, and data transfer. Output as visual bar chart.

- `src/components/CostCalculator.tsx`
- Page: `/tools/cost-calculator`

### 3. Migration Timeline Estimator
Input workspace profile → generates phase-based Gantt timeline with draggable sliders.

- `src/components/TimelineEstimator.tsx`
- Page: `/tools/timeline-estimator`

### 4. Dependency Graph Viewer
D3.js force-directed graph showing workspace → asset → pipeline relationships. Interactive zoom/pan/hover.

- `src/components/DependencyGraph.tsx`
- `src/data/sampleDependencies.json`
- Page: `/tools/dependency-graph`

### 5. RACI Matrix Builder
Select phases + define roles → auto-generate customizable RACI table with CSV export.

- `src/components/RaciBuilder.tsx`
- Page: `/tools/raci-builder`

## UI/UX Improvements
- Breadcrumb navigation on content pages
- Reading progress bar (fixed top)
- Back-to-top button
- Keyboard shortcut `⌘K` for search
- Print CSS styles
- Smooth page transitions
- Improved dark mode polish table borders/accents

## Architecture
All tools are pure client-side React components (no API/data-fetch). Data embedded as JSON imports. Each tool gets its own Astro page under `/pages/tools/*`.

## Navigation
New "Tools" section in sidebar with sub-items for each tool. Updated `navigation.json`.

## Implementation Order
1. Instance Type Mapper (highest practical value, self-contained)
2. RACI Matrix Builder (form → table pattern, reusable)
3. Migration Timeline Estimator (sliders → Gantt bars)
4. Cost Comparison Calculator (form → chart)
5. Dependency Graph Viewer (D3.js, most complex)
6. UI/UX improvements (breadcrumb, progress bar, back-to-top, print styles, etc.)
7. Navigation & sidebar updates
