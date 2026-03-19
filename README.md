# Figure Skating Analyzer

Web application for downloading and analyzing figure skating score cards from competition result websites.

## Stack

- **Backend**: Python + [Litestar](https://litestar.dev/) (async REST API)
- **Frontend**: React + Vite + TypeScript
- **Database**: SQLite (via SQLAlchemy async)
- **Package manager**: [uv](https://github.com/astral-sh/uv)

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Backend

```bash
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Development

```bash
# From project root
make dev-backend   # Start Litestar on http://localhost:8000
make dev-frontend  # Start Vite dev server on http://localhost:5173
make test          # Run backend tests
```

Or manually:

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev
```

## Usage

1. Open http://localhost:5173
2. Add a competition by pasting its result website URL
3. The app will download and parse the PDF score sheets
4. Browse scores, statistics, and visualizations per skater or competition

## Features

- Download PDF score sheets from competition result websites
- Parse and store structured score data (technical scores, components, elements)
- Cross-competition statistics and skater progression tracking
- Interactive charts and visualizations
