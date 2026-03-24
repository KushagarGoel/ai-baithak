# Agent Council - Refactored

A modern AI deliberation platform with a Next.js frontend and FastAPI backend using MCP (Model Context Protocol).

## Architecture

```
agent-council/
├── frontend/          # Next.js 15 + React 19 + TypeScript + Tailwind CSS
│   ├── app/          # Next.js App Router
│   ├── components/   # UI Components
│   ├── stores/       # Zustand state management
│   ├── types/        # TypeScript types
│   └── lib/          # Utilities
├── backend/          # FastAPI + Python 3.10+
│   ├── app/
│   │   ├── api/      # REST API & WebSocket routes
│   │   ├── core/     # Orchestrator, Agents, Personas
│   │   ├── mcp/      # MCP Tool Server
│   │   └── models/   # Pydantic schemas
│   └── run.py        # Entry point
└── design_assets/    # Screenshots from Stitch
```

## Features

### Frontend
- **Next.js 15** with App Router
- **React 19** with modern patterns
- **TypeScript** for type safety
- **Tailwind CSS** with custom design system matching Stitch designs
- **Zustand** for state management
- **WebSocket** for real-time discussion updates

### Backend
- **FastAPI** for high-performance API
- **WebSocket** support for real-time updates
- **MCP (Model Context Protocol)** for tool management
- **LiteLLM** integration for multiple model support
- **Segmented discussions** with context compression

### MCP Tools
- `read_file` - Read file contents
- `write_file` - Write file contents
- `list_directory` - List directory contents
- `web_search` - Search the web via DuckDuckGo
- `web_fetch` - Fetch web page content
- `execute_python` - Execute Python code

## Design System

Based on the Stitch "Council Dashboard" design:
- **Dark theme** with deep obsidian backgrounds (#0b0e14)
- **Neon accents** - Primary: #81e9ff (cyan), Secondary: #3fff8b (green)
- **Space Grotesk** for headlines, **Inter** for body, **JetBrains Mono** for code
- **No borders** - uses tonal layering and shadows for depth
- **Glass effects** for floating elements

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- LiteLLM proxy running (optional)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Backend will run on http://localhost:8000

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will run on http://localhost:3000

## Usage

1. Configure your LiteLLM proxy settings (default: http://localhost:4000)
2. Enter a discussion topic
3. Configure agents with different personas and models
4. Click "Start Council Discussion"
5. Watch the agents deliberate in real-time!

## Views

- **MCP Config** - Configure council settings and agents
- **Sessions** - Continue active discussions
- **Archives** - Browse completed discussions

## API Endpoints

- `GET /api/sessions` - List saved sessions
- `GET /api/sessions/{id}` - Get session details
- `GET /api/archives` - List archived discussions
- `WS /ws/discussion/{session_id}` - Real-time discussion WebSocket

## Migration from Streamlit

The old Streamlit dashboard (`simple_dashboard.py`) has been replaced with:
- Modern React-based UI
- Real-time WebSocket updates
- Better state management
- MCP-powered tool system

Original Python orchestrator logic has been preserved and moved to `backend/app/core/`.
