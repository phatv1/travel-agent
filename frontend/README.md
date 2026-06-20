# Frontend

Vue 3 + TypeScript + Vite + Tailwind v4. Three-pane streaming UI: sessions sidebar · chat column · thinking sidebar.

> See the [root README](../README.md) for the elevator pitch and [api.md](../docs/api.md) for the SSE contract.

---

## Component map

```
src/
├── App.vue                # 3-pane shell, resizable sidebars, settings popover
├── components/
│   ├── SessionSidebar.vue   # new / search / rename / bulk-delete sessions
│   ├── ChatColumn.vue       # message list + input (auto-grow + expand-to-modal)
│   ├── ThinkingSidebar.vue  # live agent trace: pipeline, tools, reasoning
│   ├── SlashMenu.vue        # "/" → trip templates (Fast / Advanced)
│   ├── TemplateFields.vue   # inline fill-in-the-blank for a template
│   ├── SettingsPanel.vue    # theme / locale / thinking-display mode
│   ├── InputExpandModal.vue # expanded message editor
│   └── Modal.vue            # generic modal primitive
├── lib/
│   ├── api.ts               # SSE reader (fetch + ReadableStream), state machine
│   ├── i18n.ts              # EN / VI strings
│   ├── theme.ts             # dark / light, semantic CSS tokens
│   └── templates.ts         # slash-template definitions
├── types.ts                # SSE event + ToolCallData + domain types
└── style.css               # Tailwind v4 + semantic tokens
```

---

## Dev commands

```bash
bun install        # install deps
bun run dev        # dev server → http://localhost:5173
bun run build      # type-check (vue-tsc) + production build
bun run preview    # preview the built app
```

---

## Notes

- **Vite proxy**: `/health` (and JSON endpoints) proxy to `:8000`. See `vite.config.ts`.
- **SSE goes direct**: `/chat/stream` is fetched **cross-origin from the backend** (`http://localhost:8000`), not through the proxy — the proxy buffers `text/event-stream` and would kill the live token stream. `VITE_ORIGIN` on the backend allows this in dev; same-origin in production.
- **Streaming reader**: `lib/api.ts` uses `fetch` + `ReadableStream` (not `EventSource`, which is GET-only) and decodes `event:`/`data:` lines manually, accumulating `final_answer` token-by-token for the typewriter effect.
