<script setup lang="ts">
import { computed, h, defineComponent, ref, watch, nextTick } from "vue"
import type { ToolCall } from "../types"
import { t } from "../lib/i18n"

const props = defineProps<{
  open: boolean
  width: number
  toolCalls: ToolCall[] | null
}>()

const emit = defineEmits<{ close: [] }>()

const expanded = ref<Set<string>>(new Set())
const reasonExpanded = ref<Set<string>>(new Set())
const scrollEl = ref<HTMLDivElement | null>(null)

function toggle(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function toggleReason(id: string) {
  const next = new Set(reasonExpanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  reasonExpanded.value = next
}

function formatJson(v: unknown): string {
  if (v === undefined || v === null) return ""
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

// Compact "key=value" rendering of a tool's input for the collapsed tool header.
function formatToolArgs(input: unknown): string {
  if (!input || typeof input !== "object") return ""
  return Object.entries(input as Record<string, unknown>)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ")
}

function elapsed(s: ToolCall): string {
  if (!s.finishedAt) return ""
  const ms = s.finishedAt - s.startedAt
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// Local icon/label maps so the pipeline renders before any event arrives and
// covers the synthesize terminal step. Kept in sync with backend NODE_META.
const NODE_ICON: Record<string, string> = {
  supervisor: "🧭",
  itinerary: "🗺️",
  recommendation: "🏨",
  cost: "💰",
  synthesize: "✨",
}
const NODE_LABEL: Record<string, string> = {
  supervisor: "Phân tích",
  itinerary: "Lịch trình",
  recommendation: "Lưu trú",
  cost: "Chi phí",
  synthesize: "Tổng hợp",
}

// Inline status badge (tiny, kept local to the showcase).
const StatusBadge = defineComponent({
  props: { status: { type: String, required: true } },
  setup(p) {
    return () =>
      h(
        "span",
        {
          class: "rounded-full px-2 py-0.5 text-[10px] font-semibold",
          style:
            p.status === "done"
              ? { background: "rgba(21,128,61,0.15)", color: "#15803d" }
              : p.status === "error"
                ? { background: "rgba(185,28,28,0.15)", color: "#b91c1c" }
                : { background: "rgba(180,83,9,0.15)", color: "#b45309" },
        },
        t(`status_${p.status}`),
      )
  },
})

// Nodes only — drive the pipeline and the parsed-request card.
const nodes = computed(() => (props.toolCalls ?? []).filter((s) => s.kind === "node"))

// Pipeline route from the supervisor's output plan; steps light up as they run.
const pipeline = computed(() => {
  const sup = nodes.value.find((n) => n.name === "supervisor")
  const out = (sup?.output ?? {}) as { plan?: string[] }
  const order = ["supervisor", ...(out.plan ?? []), "synthesize"]
  return order
    .filter((n, i, arr) => n in NODE_ICON && arr.indexOf(n) === i)
    .map((name) => {
      const step = nodes.value.find((n) => n.name === name)
      return {
        name,
        icon: NODE_ICON[name] ?? "·",
        label: NODE_LABEL[name] ?? name,
        status: step?.status ?? "pending",
      }
    })
})

// Parsed request fields the LLM extracted (from the supervisor's trip_request).
const parsedRequest = computed<[string, unknown][] | null>(() => {
  const sup = nodes.value.find((n) => n.name === "supervisor")
  const tr = ((sup?.output ?? {}) as { trip_request?: Record<string, unknown> }).trip_request
  if (!tr) return null
  const rows: [string, string][] = [
    ["destination", "📍 Điểm đến"],
    ["time_preference", "📅 Thời gian"],
    ["origin", "🛫 Đi từ"],
    ["budget_preference", "💰 Ngân sách"],
    ["companions", "👥 Số người"],
    ["preferences", "🎯 Sở thích"],
  ]
  return rows
    .map(([k, lbl]) => [lbl, tr[k]] as [string, unknown])
    .filter(([, v]) => v !== null && v !== "" && v !== undefined)
})

// Timeline grouping: nest a node's tool calls inside its card so the reading
// order matches execution order (tools first, then the node's synthesized
// output) instead of the tools dangling below the output they produced.
interface NodeGroup {
  type: "node"
  node: ToolCall
  tools: ToolCall[]
}
interface OrphanTool {
  type: "tool"
  tool: ToolCall
}
type TimelineItem = NodeGroup | OrphanTool

const grouped = computed<TimelineItem[]>(() => {
  const items: TimelineItem[] = []
  for (const tc of props.toolCalls ?? []) {
    if (tc.kind === "node") {
      items.push({ type: "node", node: tc, tools: [] })
      continue
    }
    // Attach to the most recent node matching this tool's parent name; tools
    // fire during a node's run so the match is always the latest of that name.
    const parentName = tc.node
    const parent = [...items]
      .reverse()
      .find((it): it is NodeGroup => it.type === "node" && it.node.name === parentName)
    if (parent) parent.tools.push(tc)
    else items.push({ type: "tool", tool: tc })
  }
  return items
})

const anyRunning = computed(
  () => (props.toolCalls ?? []).some((s) => s.status === "running"),
)

// Auto-scroll the live reasoning preview to its latest line as tokens stream.
// Sum of all reasoning lengths is a cheap signal that fires on every token.
const reasoningSig = computed(() =>
  (props.toolCalls ?? []).reduce((a, s) => a + (s.reasoning?.length ?? 0), 0),
)
watch(reasoningSig, async () => {
  await nextTick()
  const els = document.querySelectorAll("[data-reasoning-pre]")
  if (els.length) {
    const el = els[els.length - 1] as HTMLElement
    el.scrollTop = el.scrollHeight
  }
})

// Auto-scroll to the latest step as the trace grows.
watch(
  () => props.toolCalls?.length,
  async () => {
    await nextTick()
    if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
  },
)
</script>

<template>
  <aside
    class="h-full shrink-0 overflow-hidden border-l transition-[width] duration-200"
    :style="{ width: props.open ? props.width + 'px' : '0px', borderColor: 'var(--border)', background: 'var(--surface)' }"
  >
    <div v-if="open" class="flex h-full flex-col" :style="{ width: props.width + 'px' }">
      <div
        class="flex items-center justify-between border-b px-4 py-3"
        :style="{ borderColor: 'var(--border)' }"
      >
        <h2 class="flex items-center gap-1.5 text-sm font-semibold" :style="{ color: 'var(--text)' }">
          🧠 {{ t("thinking") }}
          <span
            v-if="anyRunning"
            class="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full"
            :style="{ background: 'var(--primary)' }"
          ></span>
        </h2>
        <button
          :title="t('close')"
          class="rounded p-1 transition hover:opacity-70"
          :style="{ color: 'var(--muted)' }"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>

      <div ref="scrollEl" class="flex-1 overflow-y-auto px-3 py-3">
        <div
          v-if="!toolCalls || toolCalls.length === 0"
          class="px-2 py-8 text-center text-sm"
          :style="{ color: 'var(--muted)' }"
        >
          {{ t("no_tool_calls") }}
        </div>

        <template v-else>
          <!-- Pipeline: the LLM's planned route, lighting up as steps run -->
          <div v-if="pipeline.length > 0" class="mb-3">
            <div class="mb-1.5 text-[11px] font-semibold uppercase" :style="{ color: 'var(--muted)' }">
              {{ t("plan_label") }}
            </div>
            <div class="flex flex-wrap items-center gap-1">
              <template v-for="(p, i) in pipeline" :key="p.name">
                <div
                  class="flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium transition"
                  :style="
                    p.status === 'done'
                      ? { background: 'rgba(21,128,61,0.15)', color: '#15803d' }
                      : p.status === 'running'
                        ? { background: 'rgba(180,83,9,0.15)', color: '#b45309' }
                        : { background: 'var(--surface-hover)', color: 'var(--muted)' }
                  "
                >
                  <span>{{ p.icon }}</span>
                  <span>{{ p.label }}</span>
                </div>
                <span v-if="i < pipeline.length - 1" :style="{ color: 'var(--muted)' }">→</span>
              </template>
            </div>
          </div>

          <!-- Parsed request: what the LLM understood -->
          <div v-if="parsedRequest && parsedRequest.length > 0" class="mb-3">
            <div class="mb-1.5 text-[11px] font-semibold uppercase" :style="{ color: 'var(--muted)' }">
              {{ t("parsed_request") }}
            </div>
            <div class="rounded-lg border p-2 text-xs" :style="{ borderColor: 'var(--border)' }">
              <div v-for="[lbl, val] in parsedRequest" :key="lbl" class="flex gap-1.5 py-0.5">
                <span :style="{ color: 'var(--muted)' }">{{ lbl }}:</span>
                <span class="font-medium" :style="{ color: 'var(--text)' }">{{ val }}</span>
              </div>
            </div>
          </div>

          <!-- Timeline: nodes + nested tools, in execution order -->
          <div class="mb-1.5 text-[11px] font-semibold uppercase" :style="{ color: 'var(--muted)' }">
            {{ t("timeline") }}
          </div>
          <div class="flex flex-col gap-1.5">
            <template v-for="item in grouped" :key="item.type === 'node' ? item.node.id : item.tool.id">
              <!-- Node card with its tool calls nested inside -->
              <div
                v-if="item.type === 'node'"
                class="rounded-xl border border-l-[3px]"
                :style="{
                  borderColor: 'var(--border)',
                  borderLeftColor: 'var(--primary)',
                  background: 'var(--surface)',
                }"
              >
                <div class="flex items-center gap-2 px-3 py-2">
                  <span class="text-base">{{ item.node.icon }}</span>
                  <div class="min-w-0 flex-1">
                    <div class="text-sm font-medium" :style="{ color: 'var(--text)' }">{{ item.node.label }}</div>
                    <div class="font-mono text-[11px]" :style="{ color: 'var(--muted)' }">
                      {{ item.node.name }}<span v-if="elapsed(item.node)"> · {{ elapsed(item.node) }}</span>
                      <span v-if="item.node.llmCalls"> · {{ item.node.llmCalls }} LLM</span>
                    </div>
                  </div>
                  <StatusBadge :status="item.node.status" />
                </div>

                <!-- Live thinking indicator: an LLM call is running in this node -->
                <div
                  v-if="item.node.thinking"
                  class="flex items-center gap-1.5 border-t px-3 py-1.5 text-[11px] font-medium"
                  :style="{ borderColor: 'var(--border)', color: '#b45309', background: 'rgba(180,83,9,0.06)' }"
                >
                  <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full" :style="{ background: '#b45309' }"></span>
                  {{ t("thinking_indicator") }}
                </div>

                <!-- Raw reasoning preview: live LLM tokens (plan/JSON).
                     Auto-expanded while the node is thinking, auto-collapsed when done. -->
                <div
                  v-if="item.node.reasoning && (item.node.thinking || reasonExpanded.has(item.node.id))"
                  class="border-t px-3 py-2"
                  :style="{ borderColor: 'var(--border)' }"
                >
                  <button
                    class="mb-1 text-[11px] font-medium transition hover:opacity-70"
                    :style="{ color: 'var(--muted)' }"
                    @click="toggleReason(item.node.id)"
                  >
                    🤖 {{ t("reasoning") }}
                  </button>
                  <pre
                    data-reasoning-pre
                    class="max-h-40 overflow-y-auto rounded-lg p-2 font-mono text-[10px] leading-relaxed"
                    :style="{ background: 'var(--surface-hover)', color: 'var(--muted)' }"
                  >{{ item.node.reasoning }}</pre>
                </div>

                <!-- Nested tool calls: the steps that produced this node's output -->
                <div v-if="item.tools.length" class="flex flex-col gap-1 border-t px-3 py-2" :style="{ borderColor: 'var(--border)' }">
                  <div
                    v-for="tool in item.tools"
                    :key="tool.id"
                    class="rounded-lg border border-dashed"
                    :style="{ borderColor: 'var(--border)', background: 'var(--surface-hover)' }"
                  >
                    <button
                      class="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left"
                      @click="toggle(tool.id)"
                    >
                      <span class="text-xs">🔧</span>
                      <span class="flex-1 truncate font-mono text-[11px] font-medium" :style="{ color: 'var(--text)' }">
                        {{ tool.name }}<span v-if="formatToolArgs(tool.input)">({{ formatToolArgs(tool.input) }})</span>
                      </span>
                      <StatusBadge :status="tool.status" />
                    </button>
                    <div v-if="tool.output !== undefined && expanded.has(tool.id)" class="px-2.5 pb-2">
                      <pre
                        class="max-h-48 overflow-auto rounded-lg p-2 text-[10px]"
                        :style="{ background: 'var(--surface)', color: 'var(--text)' }"
                      >{{ formatJson(tool.output) }}</pre>
                    </div>
                  </div>
                </div>

                <div v-if="item.node.output !== undefined" class="px-3 pb-2">
                  <button
                    class="text-[11px] font-medium transition hover:opacity-70"
                    :style="{ color: 'var(--primary)' }"
                    @click="toggle(item.node.id)"
                  >
                    {{ expanded.has(item.node.id) ? `▾ ${t("hide_output")}` : `▸ ${t("show_output")}` }}
                  </button>
                  <pre
                    v-if="expanded.has(item.node.id)"
                    class="mt-1 max-h-64 overflow-auto rounded-lg p-2 text-[11px]"
                    :style="{ background: 'var(--surface-hover)', color: 'var(--text)' }"
                  >{{ formatJson(item.node.output) }}</pre>
                </div>
              </div>

              <!-- Orphan tool: a tool whose parent node never appeared in the
                   trace (edge case); render flat so it is still visible. -->
              <div
                v-else
                class="rounded-lg border border-dashed"
                :style="{ borderColor: 'var(--border)', background: 'var(--surface-hover)' }"
              >
                <button
                  class="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left"
                  @click="toggle(item.tool.id)"
                >
                  <span class="text-xs">🔧</span>
                  <span class="flex-1 truncate font-mono text-[11px] font-medium" :style="{ color: 'var(--text)' }">
                    {{ item.tool.name }}<span v-if="formatToolArgs(item.tool.input)">({{ formatToolArgs(item.tool.input) }})</span>
                  </span>
                  <StatusBadge :status="item.tool.status" />
                </button>
                <div v-if="item.tool.output !== undefined && expanded.has(item.tool.id)" class="px-2.5 pb-2">
                  <pre
                    class="max-h-48 overflow-auto rounded-lg p-2 text-[10px]"
                    :style="{ background: 'var(--surface)', color: 'var(--text)' }"
                  >{{ formatJson(item.tool.output) }}</pre>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>
  </aside>
</template>
