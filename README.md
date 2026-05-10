# LithoLearn: Personalized Semiconductor Process Education

**Team SOPy Times** — Tamar Korkotashvili, Adrienne Lai, Ada Erus
`tkorkot@mit.edu` · `awlai@mit.edu` · `aerus@mit.edu`

---

## Overview

LithoLearn is a personalized, interactive semiconductor education platform built to address the growing workforce shortage in microelectronics. Learning semiconductor fabrication is hard: resources are either too surface-level or overly theoretical, workplace training is tool-specific, and process knowledge is fragmented across individual fabrication steps — making it difficult to build a complete picture of wafer fabrication.

LithoLearn transforms disconnected semiconductor documentation (SOPs, silicon docs, process recipes) into an adaptive learning experience tailored to each user's background, experience level, and technical interests. Engineers without microelectronics backgrounds get a faster, smoother knowledge transfer into the field — growing the semiconductor talent pool and accelerating onboarding.

---

## Features

### Personalized Onboarding
Users answer four questions about their background and goals. The AI agent uses these answers to calibrate content depth and relevance throughout the platform.

### Adaptive Dashboard
After onboarding, a personalized dashboard is generated showing:
- An **interactive process flow diagram** for overall context
- **Recommended SOPs** ranked by relevance to the user's role, process area, and background — each tagged with a match percentage, process flow tag, and keyword tags

### Process Deep-Dives
Clicking any process opens a five-section summary tailored to the user:
1. **Summary** — overview contextualized to the user's background with relevant examples
2. **Tools** — high-level overview of equipment encountered in this process
3. **Your Focus** — personalized recommendations based on the user's role
4. **Parameter Overview** — key process parameters and what to watch out for
5. **Related SOPs + AI Chatbox** — linked documents and a personalized Q&A assistant

### SOP Viewer
The PDF viewer provides three panels for each SOP:
- The original PDF
- AI-extracted text (editable)
- Associated images (replaceable)

### Study Guide Generation
Users can request a generated study guide with a configurable focus area for any process or SOP.

### AI-Assisted Document Editing
Users can annotate or edit documents and optionally propagate changes to related documents — keeping training materials current as processes evolve.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS |
| Backend | Python, Flask, Flask-SQLAlchemy |
| Database | SQLite + Flask-SQLAlchemy |
| AI | OpenRouter API, OpenAI API |
| PDF Processing | PyMuPDF (fitz) |
| Document Sync | Google Drive integration |

---

## Getting Started

### Prerequisites
- Python 3.14+
- [uv](https://docs.astral.sh/uv/) installed
- A `.env` file with your API keys (OpenRouter, OpenAI, Google Drive credentials)

### Backend Setup

```bash
uv sync
uv run python seed.py    # create tables and seed the database
uv run python app.py     # start the Flask server
```

### Syncing Documents from Google Drive

```bash
python scripts/sync_drive.py
```

### Ingesting New Documentation

```bash
python scripts/ingest_data.py
```

---

## Project Structure

```
sopy-times/
├── routes/          # Flask API routes (documents, search, summaries, drive)
├── services/        # Business logic (document, drive, image services)
├── database/        # SQLAlchemy models
├── scripts/         # Data ingestion and Google Drive sync
├── static/          # Frontend assets and JS
├── config.py        # App configuration
├── seed.py          # Database seeding
└── package.json     # Next.js frontend
```

---

## Motivation

Semiconductor fabrication knowledge is critical and growing in demand, but the path into the field is steep. LithoLearn exists to lower that barrier — giving engineers from adjacent fields (mechanical, electrical, chemical, materials) a structured, intelligent ramp into microelectronics, without requiring years of hands-on cleanroom time first.
