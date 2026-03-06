# UE Capability Parser – Frontend

## Overview

A dark-mode React + Vite + TypeScript UI for parsing and comparing decoded 4G LTE / 5G NR UE Capability logs.

No fake charts. No performance metrics. No ML. Focus on correctness and interpretability.

---

## Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173

> The Vite dev server proxies `/parse` and `/compare` to `http://localhost:8000` automatically.
> Make sure the backend is running first.

---

## Pages

| Route       | Description |
|-------------|-------------|
| `/`         | Upload DUT and REF log files |
| `/parse`    | Expandable JSON tree of the parsed capability |
| `/compare`  | Colored diff table + explanation accordion |

---

## Design Decisions

- **Dark-mode first** — GitHub-inspired dark palette with `#0d1117` background
- **No charts** — Tabular diff view is more precise and interpretable than visualizations for spec compliance
- **No accuracy metrics** — There is no ground truth or labeled dataset; correctness is spec-driven
- **JetBrains Mono** for all technical values (field paths, JSON keys, file names)
- **Color coding**: 🔴 missing in DUT, 🟡 extra in DUT, 🟠 value mismatch
- **Accordion explanations** anchored to 3GPP spec clauses

---

## Folder Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── FileUploader.tsx        # Drag-and-drop file picker
│   │   ├── JsonTree.tsx            # Recursive collapsible JSON viewer
│   │   ├── DiffTable.tsx           # Color-coded diff table
│   │   └── ExplanationPanel.tsx    # Accordion with spec-referenced explanations
│   ├── pages/
│   │   ├── Upload.tsx              # / – file upload entry point
│   │   ├── ParseView.tsx           # /parse – single log view
│   │   └── CompareView.tsx         # /compare – DUT vs REF diff view
│   ├── services/
│   │   └── api.ts                  # Axios API calls to FastAPI backend
│   ├── types/
│   │   └── capability.ts           # TypeScript interface definitions
│   ├── App.tsx                     # React Router + global state
│   ├── main.tsx                    # Entry point
│   └── index.css                   # Global dark theme CSS variables
├── index.html
├── package.json
├── vite.config.ts
└── README.md
```

---

## Tech Stack

| Tool | Version | Purpose |
|------|---------|---------|
| React | 18 | UI framework |
| Vite | 5 | Build tool + dev server |
| TypeScript | 5 | Type safety |
| React Router | 6 | Client-side routing |
| Axios | 1.6 | HTTP client |
| CSS Modules | (native) | Scoped, collision-free styles |
