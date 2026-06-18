import type { ChatMessage, ChatSession, ToolCall, ToolCallStatus } from "../types"

interface SessionSummaryDTO {
  id: string
  title: string
  created_at: number
  updated_at: number
}

interface ToolCallDTO {
  name: string
  label: string
  icon?: string
  status: string
  input: unknown
  output?: unknown
  kind?: string
  node?: string | null
}

interface MessageDTO {
  id: string
  role: string
  content: string
  tool_calls?: ToolCallDTO[] | null
  error?: string | null
  created_at: number
}

interface SessionDetailDTO extends SessionSummaryDTO {
  messages: MessageDTO[]
}

interface ChatResponseDTO {
  session_id: string
  message_id: string
  final_answer: string
  itinerary?: unknown
  recommendations?: unknown
  cost_report?: unknown
  tool_calls?: ToolCallDTO[] | null
}

let toolCounter = 0

function mapStatus(s: string): ToolCallStatus {
  if (s === "done") return "done"
  if (s === "error") return "error"
  return "running"
}

function toToolCalls(items?: ToolCallDTO[] | null): ToolCall[] | undefined {
  if (!items) return undefined
  const base = Date.now()
  return items.map((it, i) => ({
    id: `srv-${base}-${toolCounter++}`,
    kind: (it.kind === "tool" ? "tool" : "node") as ToolCall["kind"],
    name: it.name,
    label: it.label,
    icon: it.icon ?? (it.kind === "tool" ? "🔧" : "·"),
    node: it.node ?? undefined,
    input: it.input,
    output: it.output,
    status: mapStatus(it.status),
    startedAt: base - (items.length - i),
    finishedAt: mapStatus(it.status) === "done" ? base : undefined,
  }))
}

function toMessage(m: MessageDTO): ChatMessage {
  return {
    id: m.id,
    role: m.role === "user" ? "user" : "assistant",
    content: m.content,
    error: m.error ?? undefined,
    toolCalls: toToolCalls(m.tool_calls),
    createdAt: m.created_at * 1000,
  }
}

function toSession(s: SessionSummaryDTO, messages?: MessageDTO[]): ChatSession {
  return {
    id: s.id,
    title: s.title,
    messages: messages ? messages.map(toMessage) : [],
    createdAt: s.created_at * 1000,
    updatedAt: s.updated_at * 1000,
  }
}

async function req(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, init)
  if (!res.ok) throw new Error(`Lỗi máy chủ (${res.status})`)
  return res
}

export async function listSessions(): Promise<ChatSession[]> {
  const data = (await (await req("/sessions")).json()) as SessionSummaryDTO[]
  return data.map((s) => toSession(s))
}

export async function createSession(): Promise<ChatSession> {
  const data = (await (await req("/sessions", { method: "POST" })).json()) as SessionSummaryDTO
  return toSession(data)
}

export async function getSession(id: string): Promise<ChatSession | null> {
  const res = await fetch(`/sessions/${id}`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`Lỗi máy chủ (${res.status})`)
  const data = (await res.json()) as SessionDetailDTO
  return toSession(data, data.messages)
}

export async function renameSession(id: string, title: string): Promise<void> {
  await req(`/sessions/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  })
}

export async function deleteSession(id: string): Promise<void> {
  await fetch(`/sessions/${id}`, { method: "DELETE" })
}

export interface ChatResult {
  sessionId: string
  assistant: ChatMessage
}

async function chat(message: string, sessionId: string | null): Promise<ChatResult> {
  const data = (await (
    await req("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    })
  ).json()) as ChatResponseDTO
  return {
    sessionId: data.session_id,
    assistant: {
      id: data.message_id,
      role: "assistant",
      content: data.final_answer,
      toolCalls: toToolCalls(data.tool_calls),
      createdAt: Date.now(),
    },
  }
}

/** SSE event → callback. Empty string event name = comment/heartbeat. */
export interface StreamHandlers {
  onSession?: (sessionId: string) => void
  onPlan?: (route: { name: string; label: string; icon: string }[]) => void
  onNodeStart?: (name: string, label: string, icon: string) => void
  onNodeEnd?: (name: string, output: unknown) => void
  onLlmStart?: (node: string | undefined) => void
  onLlmEnd?: (node: string | undefined) => void
  onReasoning?: (node: string | undefined, text: string) => void
  onToolStart?: (node: string | undefined, name: string, input: unknown) => void
  onToolEnd?: (node: string | undefined, name: string, output: unknown) => void
  onToken?: (text: string) => void
  onError?: (message: string) => void
  onDone?: (result: {
    sessionId: string
    messageId: string
    finalAnswer: string
    errors: string[] | null
  }) => void
}

// Backend base for SSE — the Vite proxy buffers text/event-stream, so the
// frontend reads the stream directly from FastAPI (CORS-enabled in dev).
const STREAM_BASE =
  (import.meta.env.VITE_STREAM_BASE as string | undefined) ?? "http://127.0.0.1:8000"

let streamCounter = 0
function uid(): string {
  return `ev-${Date.now()}-${streamCounter++}`
}

/** Stream /chat/stream, dispatching each SSE event to the matching handler.
 *
 * Uses fetch + a ReadableStream reader (EventSource is GET-only and can't POST
 * the message body). Parses the SSE wire format manually: `event:` / `data:`
 * lines delimited by blank lines.
 */
export async function streamChat(
  message: string,
  sessionId: string | null,
  h: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${STREAM_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`Lỗi máy chủ (${res.status})`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let eventType = ""
  let dataLines: string[] = []

  const dispatch = () => {
    if (dataLines.length === 0) return
    const raw = dataLines.join("\n")
    dataLines = []
    const et = eventType
    eventType = ""
    if (!et) return // comment/heartbeat
    let payload: Record<string, unknown> = {}
    try {
      payload = raw ? JSON.parse(raw) : {}
    } catch {
      return
    }
    switch (et) {
      case "session":
        h.onSession?.(payload.session_id as string)
        break
      case "plan":
        h.onPlan?.(payload.route as { name: string; label: string; icon: string }[])
        break
      case "node_start":
        h.onNodeStart?.(
          payload.name as string,
          payload.label as string,
          payload.icon as string,
        )
        break
      case "node_end":
        h.onNodeEnd?.(payload.name as string, payload.output)
        break
      case "llm_start":
        h.onLlmStart?.(payload.node as string | undefined)
        break
      case "llm_end":
        h.onLlmEnd?.(payload.node as string | undefined)
        break
      case "reasoning":
        h.onReasoning?.(payload.node as string | undefined, payload.text as string)
        break
      case "tool_start":
        h.onToolStart?.(payload.node as string | undefined, payload.name as string, payload.input)
        break
      case "tool_end":
        h.onToolEnd?.(payload.node as string | undefined, payload.name as string, payload.output)
        break
      case "token":
        h.onToken?.(payload.text as string)
        break
      case "error":
        h.onError?.(payload.message as string)
        break
      case "done":
        h.onDone?.({
          sessionId: payload.session_id as string,
          messageId: payload.message_id as string,
          finalAnswer: (payload.final_answer as string) ?? "",
          errors: (payload.errors as string[] | null) ?? null,
        })
        break
    }
  }

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx: number
    // SSE frames are separated by a blank line.
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).replace(/^ /, ""))
        }
      }
      dispatch()
    }
  }
  dispatch() // flush any trailing partial frame
}

export { chat, uid }
