# ResearchAgent

A dark-themed, AI-powered research web app that runs a multi-step pipeline to generate deep research reports on any topic — complete with web search, content scraping, report writing, and critic review.

---

## Features

- **4-step research pipeline** — Search → Read → Write → Critique
- **Live progress tracking** — Real-time SSE (Server-Sent Events) stream with step indicators and a progress bar
- **Markdown report rendering** — Final reports rendered with full heading, table, and code block support via `marked.js`
- **Raw output dropdowns** — Collapsible panels showing raw search results and scraped content
- **Critic feedback** — A second AI pass reviews and scores the generated report
- **Suggestion shortcuts** — One-click topic starters to get going fast
- **User session support** — Avatar, name, email display with a logout button

---

## Tech Stack

| Layer | Details |
|---|---|
| Frontend | Vanilla HTML/CSS/JS, `marked.js` for Markdown |
| Fonts | Syne, IBM Plex Mono, Lora (Google Fonts) |
| Backend (expected) | Python/Flask or similar — serves `/research`, `/stream`, `/api/logout` |
| Streaming | Server-Sent Events via `/stream` endpoint |

---

## Project Structure

```
.
├── templates/
│   └── index.html        # Main app UI (this file)
├── app.py                # Backend server (not included)
└── README.md
```

---

## API Endpoints

The frontend expects these backend routes:

| Method | Route | Description |
|---|---|---|
| `POST` | `/research` | Accepts `{ topic: string }`, kicks off the pipeline |
| `GET` | `/stream` | SSE stream emitting `log`, `done`, and `error` events |
| `POST` | `/api/logout` | Clears session and redirects to `/login` |

### SSE Event Shapes

**Log event** — progress updates while the pipeline runs:
```json
{ "type": "log", "message": "Step 2: Scraping content..." }
```

**Done event** — final results:
```json
{
  "type": "done",
  "result": {
    "search_result": "...",
    "scrapped_content": "...",
    "report": "# Report title\n\n...",
    "feedback": "## Critic feedback\n\n..."
  }
}
```

**Error event:**
```json
{ "type": "error", "message": "Something went wrong" }
```

---

## Pipeline Steps

| # | Agent | What it does |
|---|---|---|
| 01 | **Search Agent** | Queries the web for recent, relevant information on the topic |
| 02 | **Reader Agent** | Scrapes and extracts deep content from source URLs |
| 03 | **Writer Chain** | Synthesizes gathered content into a full research report |
| 04 | **Critic Chain** | Reviews the report and returns a quality score with feedback |

---

## Template Variables

The HTML template uses Jinja2-style variables for the user session:

| Variable | Description |
|---|---|
| `{{ user.name }}` | Displayed in the sidebar header |
| `{{ user.email }}` | Shown in monospace below the name |
| `{{ user.avatar }}` | Optional avatar image URL; falls back to first initial |

---

## Getting Started

1. Clone the repo and install backend dependencies.
2. Implement `app.py` with the three endpoints above (Flask recommended).
3. Serve `templates/index.html` via your framework's template engine.
4. Run the server and open `http://localhost:5000` in your browser.
5. Enter a topic, hit **Run Research Pipeline**, and watch it go.

---

## Customization

- **Accent color** — change `--accent: #f97316` in `:root` to any color
- **Suggestions** — edit the `.suggestion` spans in the sidebar to add your own quick-start topics
- **Pipeline steps** — add more `<div class="p-step">` blocks and extend the JS `steps` / `progressSteps` arrays to match
