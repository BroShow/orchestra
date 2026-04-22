# 06 — Frontend (Next.js)

## Goal
A clean, single-page chat-style UI where the user submits a task, watches the agent's reasoning and tool calls stream in, and approves/denies tool calls when prompted.

## Location
`apps/web/`

## Stack
- Next.js 15 (app router)
- React 19
- Tailwind CSS 4
- shadcn/ui components
- `@microsoft/fetch-event-source` for SSE (handles auth headers and reconnection better than native `EventSource`)
- Zustand for client state

## Pages / Routes
- `/` — Run list + new run input (split layout)
- `/runs/[id]` — Single run detail with live event stream

## Components

### `<RunComposer />`
Textarea + submit button. POST to `/runs`, then route to `/runs/[id]`.

### `<RunTimeline />`
Vertical timeline of events. Each event type renders differently:
- **`step_start`** — divider with step number
- **`model_chunk`** — appended to a streaming text bubble
- **`tool_call_requested`** — collapsed card showing tool name + args (expandable to see full args)
- **`approval_required`** — prominent inline card with "Approve" / "Deny" buttons; blocks the rest of the timeline visually
- **`tool_result`** — collapsed by default; expandable to see full output
- **`run_complete`** — final answer in a highlighted card
- **`error`** — red card with the error message

### `<ApprovalCard />`
Renders for `approval_required` events. Shows:
- Tool name (prominent)
- Pretty-printed JSON args (syntax-highlighted)
- Approve / Deny buttons
On click, POSTs to `/runs/{id}/approve` and disables itself.

### `<RunList />`
Sidebar list of recent runs with status badges (running / awaiting approval / complete / error).

## State Management
Single Zustand store per route:
```ts
interface RunStore {
  events: RunEvent[];
  status: "idle" | "connecting" | "streaming" | "awaiting_approval" | "complete" | "error";
  pendingApproval: ApprovalPayload | null;
  appendEvent: (e: RunEvent) => void;
  approve: (decision: "approved" | "denied") => Promise<void>;
}
```

The SSE connection lives in a `useEffect` in the run detail page; it appends events to the store. The store is responsible for deriving `status` and `pendingApproval` from event history.

## Streaming Pattern
```ts
import { fetchEventSource } from '@microsoft/fetch-event-source';

await fetchEventSource(`/api/runs/${id}/events`, {
  onmessage(ev) {
    const event = JSON.parse(ev.data) as RunEvent;
    store.appendEvent(event);
  },
  onerror(err) {
    // backoff and retry; library handles this if we don't throw
  },
});
```

Use Next.js's built-in API proxy or `rewrites()` config to forward `/api/*` to the FastAPI backend in dev to avoid CORS pain.

## Type Safety
TypeScript types for all API requests/responses live in `packages/shared-types/`. Generate them from the Pydantic schemas using `datamodel-code-generator` or maintain a JSON Schema export step. The frontend imports from `@workspace/shared-types`.

## Visual Design
- Default to shadcn/ui's default theme. Don't bikeshed colors in v1.
- Monospace font for tool args and tool results.
- Streaming text uses a subtle pulsing cursor at the end while streaming.
- Approval cards have a distinct accent color (amber/yellow) to draw attention.
- Mobile is out of scope; assume desktop viewport.

## Acceptance Criteria
- [ ] User can submit a task and is routed to a live-streaming run page.
- [ ] All event types render distinctly and correctly.
- [ ] Approval flow works: card appears, user clicks approve, run continues, card stays in timeline as a record.
- [ ] Network drop: closing/reopening the tab resumes the stream from where it left off (relies on `Last-Event-ID` from spec 05).
- [ ] Accessible: keyboard-navigable, screen-reader-friendly approval buttons, `aria-live` for streaming text.
- [ ] No console errors during a normal happy-path run.

## Anti-Goals (v1)
- No dark/light mode toggle (pick one default; system pref is fine).
- No rich markdown rendering of agent output (plain text + monospace for code is enough).
- No editing/replaying past runs.
- No charts, graphs, or fancy visualizations of the agent graph itself.
