# AI Presentation Generator

A FastAPI backend that generates presentations from documents, prompts, or outlines using a multi-stage LLM pipeline with parallel slide generation.

## How It Works

All three input methods follow the same pattern: **Analyse → Generate slides in parallel → JSON response**.

| Input | Endpoint | Stages |
|---|---|---|
| **Document** (PDF/TXT/MD) | `POST /api/v1/presentations/document` | Extract text → LLM breaks into sections → parallel slide generation |
| **Prompt** (one-liner) | `POST /api/v1/presentations/prompt` | LLM analyses intent → generates outline + TOC → parallel slide generation |
| **Outline** (structured JSON) | `POST /api/v1/presentations/outline` | LLM analyses outline → enriches each slide in parallel |

Each slide is returned as structured JSON with `title`, `content` (bullet points), `notes` (speaker notes), and `layout`.

## Project Structure

```
app/
├── main.py                          # FastAPI app, CORS, router mounting
├── core/config.py                   # Settings via pydantic-settings (.env)
├── api/endpoints/
│   ├── presentations.py             # Document, prompt, outline endpoints
│   └── health.py                    # Health check
├── models/request_schemas.py        # All Pydantic models (request, response, pipeline)
├── services/
│   ├── presentation_generator.py    # 3 generators (Document, Prompt, Outline)
│   ├── document_processor.py        # PDF extraction via marker-pdf, txt/md parsing
│   ├── llm_client.py                # Async OpenAI wrapper with JSON mode + retry
│   └── prompts.py                   # All prompt templates for every pipeline stage
└── utils/
    ├── validators.py                # Input validation utilities
    └── file_handler.py              # File I/O helpers
```

## Quick Start

```bash
# 1. Install
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
copy .env.example .env
# Edit .env → set OPENAI_API_KEY

# 3. Run
python run.py
```

API docs at http://localhost:8000/docs

## API Usage

### Document Upload
```bash
curl -X POST "http://localhost:8000/api/v1/presentations/document" \
  -F "file=@report.pdf" \
  -F "title=Quarterly Report" \
  -F "max_slides=10"
```

### Prompt
```bash
curl -X POST "http://localhost:8000/api/v1/presentations/prompt" \
  -F "prompt=Benefits of renewable energy" \
  -F "max_slides=8" \
  -F "target_audience=investors"
```

### Outline
```bash
curl -X POST "http://localhost:8000/api/v1/presentations/outline" \
  -H "Content-Type: application/json" \
  -d '{
    "outline": [
      {"title": "Introduction", "content": ["Point 1", "Point 2"]},
      {"title": "Main Topic", "content": ["Detail 1", "Detail 2"]}
    ],
    "title": "My Presentation"
  }'
```

### Response Format
```json
{
  "presentation_id": "pres_a1b2c3d4",
  "title": "Quarterly Report",
  "slides": [
    {
      "slide_number": 1,
      "title": "Introduction",
      "content": ["Key point 1", "Key point 2"],
      "notes": "Speaker notes here",
      "layout": "title"
    }
  ],
  "total_slides": 8,
  "generation_method": "document",
  "table_of_contents": ["Introduction", "Overview", "..."],
  "created_at": "2026-03-01T10:00:00"
}
```

## Configuration

Set in `.env`:

```env
OPENAI_API_KEY=sk-...          # Required for LLM pipeline
LLM_MODEL=gpt-4o-mini          # Default model
LLM_TEMPERATURE=0.7            # Default temperature
LLM_MAX_TOKENS=2000            # Default max tokens
DEBUG=false                     # Debug mode
```

## Pipeline Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Endpoint   │────▶│  Stage 1     │────▶│  Stage 2/3          │
│  (FastAPI)  │     │  LLM Analyse │     │  Parallel Slides    │
└─────────────┘     └──────────────┘     │  (asyncio.gather)   │
                                          └─────────────────────┘
                                                    │
                                          ┌─────────┼─────────┐
                                          ▼         ▼         ▼
                                       Slide 1   Slide 2   Slide N
                                       (LLM)     (LLM)     (LLM)
```

- **Fallback**: If `OPENAI_API_KEY` is not set, all generators degrade gracefully to stub/direct-mapping output.
- **JSON mode**: All LLM calls use `response_format={"type": "json_object"}` with Pydantic validation.
- **Retry**: Single automatic retry on LLM failure.

## Testing

```bash
pytest tests/
```

## Key Dependencies

| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | Web framework + ASGI server |
| `openai` | LLM API client |
| `pydantic` + `pydantic-settings` | Data validation + config |
| `marker-pdf` | PDF → Markdown extraction |
| `python-pptx` | PPTX generation (future) |

## License

MIT