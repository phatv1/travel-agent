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
  icon: string
  status: string
  input: unknown
  output?: unknown
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
  return items.map((t, i) => ({
    id: `srv-${base}-${toolCounter++}`,
    name: t.name,
    label: t.label,
    icon: t.icon,
    input: t.input,
    output: t.output,
    status: mapStatus(t.status),
    startedAt: base - (items.length - i),
    finishedAt: mapStatus(t.status) === "done" ? base : undefined,
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

export async function chat(message: string, sessionId: string | null): Promise<ChatResult> {
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
