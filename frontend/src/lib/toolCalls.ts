import type { ToolCall } from "../types"

export interface AgentResult {
  itinerary?: unknown
  recommendations?: unknown
  cost_report?: unknown
  final_answer?: string
}

function uid(): string {
  return crypto?.randomUUID?.() ?? `tc-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

// Builds the agent step trace. Without `result` the steps are `running`
// (populated immediately so the thinking panel is alive during the wait);
// with `result` they are `done` with toggleable outputs.
// Today these are synthesized client-side; later they come from streamed
// backend events — the ToolCall shape stays the same.
export function buildToolCalls(userMessage: string, result?: AgentResult): ToolCall[] {
  const startedAt = Date.now()
  const done = result !== undefined
  const mk = (
    name: string,
    label: string,
    icon: string,
    input: unknown,
    output?: unknown,
  ): ToolCall => ({
    id: uid(),
    name,
    label,
    icon,
    input,
    output,
    status: done ? "done" : "running",
    startedAt,
    finishedAt: done ? startedAt + 1 : undefined,
  })

  return [
    mk("supervisor", "Phân tích yêu cầu", "🧭", { message: userMessage }, { trip_request: "(đã trích xuất)" }),
    mk("itinerary", "Lập lịch trình", "🗺️", { trip_request: "(TripRequest)" }, result?.itinerary),
    mk("recommendation", "Gợi ý lưu trú & ăn uống", "🏨", { trip_request: "(TripRequest)" }, result?.recommendations),
    mk("cost", "Ước lượng chi phí", "💰", { trip_request: "(TripRequest)" }, result?.cost_report),
    mk("synthesize", "Tổng hợp câu trả lời", "✨", {}, result?.final_answer?.slice(0, 200)),
  ]
}
