export type ToolCallStatus = "running" | "done" | "error"

export interface ToolCall {
  id: string
  name: string
  label: string
  icon: string
  input: unknown
  output?: unknown
  status: ToolCallStatus
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
