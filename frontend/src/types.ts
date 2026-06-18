export type ToolCallStatus = "running" | "done" | "error"

/** "node" = a graph node (supervisor/itinerary/...); "tool" = a tool called within a node. */
export type ToolCallKind = "node" | "tool"

export interface ToolCall {
  id: string
  kind: ToolCallKind
  name: string
  label: string
  icon: string
  input: unknown
  output?: unknown
  status: ToolCallStatus
  /** Parent node name for tools (e.g. "itinerary"); undefined for nodes. */
  node?: string
  /** Node only: an LLM call is currently running inside this node. */
  thinking?: boolean
  /** Node only: how many LLM calls this node has made. */
  llmCalls?: number
  /** Node only: live raw LLM tokens (plan/JSON), shown in a collapsible preview. */
  reasoning?: string
  startedAt: number
  finishedAt?: number
}

export type MessageRole = "user" | "assistant"

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  pending?: boolean
  error?: string
  toolCalls?: ToolCall[]
  createdAt: number
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}
