<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import SessionSidebar from "./components/SessionSidebar.vue"
import ChatColumn from "./components/ChatColumn.vue"
import ThinkingSidebar from "./components/ThinkingSidebar.vue"
import Modal from "./components/Modal.vue"
import * as api from "./lib/api"
import { uid } from "./lib/api"
import { t } from "./lib/i18n"
import { applyTheme, theme } from "./lib/theme"
import type { ChatMessage, ChatSession, ToolCall } from "./types"

function makeNode(
  name: string,
  label: string,
  icon: string,
): ToolCall {
  return {
    id: uid(),
    kind: "node",
    name,
    label,
    icon,
    input: {},
    status: "running",
    startedAt: Date.now(),
  }
}

function makeTool(node: string | undefined, name: string, input: unknown): ToolCall {
  return {
    id: uid(),
    kind: "tool",
    node,
    name,
    label: name,
    icon: "🔧",
    input,
    status: "running",
    startedAt: Date.now(),
  }
}

const sessions = ref<ChatSession[]>([])
const activeId = ref<string | null>(null)
const sidebarVisible = ref(true)
const thinkingOpen = ref(false)
const activeTraceId = ref<string | null>(null)
const loading = ref(false)
const statusKey = ref("connecting")

type DialogState =
  | { kind: "none" }
  | { kind: "delete"; id: string; title: string }
  | { kind: "rename"; id: string; title: string }
const dialog = ref<DialogState>({ kind: "none" })
const renameValue = ref("")

const activeSession = computed(
  () => sessions.value.find((s) => s.id === activeId.value) ?? null,
)
const activeToolCalls = computed(() => {
  if (!activeTraceId.value || !activeSession.value) return null
  return activeSession.value.messages.find((m) => m.id === activeTraceId.value)?.toolCalls ?? null
})

onMounted(async () => {
  applyTheme(theme.value)
  try {
    sessions.value = await api.listSessions()
    statusKey.value = "ready"
  } catch {
    statusKey.value = "no_backend"
  }
})

function newChat() {
  activeId.value = null
  activeTraceId.value = null
  thinkingOpen.value = false
}

async function selectSession(id: string) {
  activeId.value = id
  const s = sessions.value.find((x) => x.id === id)
  if (s && s.messages.length === 0) {
    try {
      const full = await api.getSession(id)
      if (full) {
        const idx = sessions.value.findIndex((x) => x.id === id)
        sessions.value[idx] = full
      }
    } catch {
      /* keep summary */
    }
  }
}

function requestDelete(id: string) {
  const s = sessions.value.find((x) => x.id === id)
  dialog.value = { kind: "delete", id, title: s?.title ?? "" }
}

async function confirmDelete() {
  const d = dialog.value
  if (d.kind !== "delete") return
  await api.deleteSession(d.id)
  const idx = sessions.value.findIndex((s) => s.id === d.id)
  if (idx >= 0) sessions.value.splice(idx, 1)
  if (activeId.value === d.id) activeId.value = sessions.value[0]?.id ?? null
  dialog.value = { kind: "none" }
}

function requestRename(id: string) {
  const s = sessions.value.find((x) => x.id === id)
  dialog.value = { kind: "rename", id, title: s?.title ?? "" }
  renameValue.value = s?.title ?? ""
}

async function confirmRename() {
  const d = dialog.value
  if (d.kind !== "rename") return
  const title = renameValue.value.trim() || d.title
  await api.renameSession(d.id, title)
  const s = sessions.value.find((x) => x.id === d.id)
  if (s) s.title = title
  dialog.value = { kind: "none" }
}

function openThinking(messageId: string) {
  if (activeTraceId.value === messageId && thinkingOpen.value) {
    thinkingOpen.value = false
    return
  }
  activeTraceId.value = messageId
  thinkingOpen.value = true
}

async function send(text: string) {
  if (loading.value) return
  loading.value = true
  statusKey.value = "loading"

  const now = Date.now()
  const userMsg: ChatMessage = { id: uid(), role: "user", content: text, createdAt: now }
  // Declared `let`: reassigned below to the reactive proxy after insertion.
  let assistantMsg: ChatMessage = {
    id: uid(),
    role: "assistant",
    content: "",
    pending: true,
    toolCalls: [],
    createdAt: now,
  }

  const existing = activeSession.value
  if (existing) {
    existing.messages.push(userMsg, assistantMsg)
  } else {
    const tempId = `temp-${now}`
    sessions.value.unshift({
      id: tempId,
      title: text.slice(0, 40),
      messages: [userMsg, assistantMsg],
      createdAt: now,
      updatedAt: now,
    })
    activeId.value = tempId
  }

  // Re-acquire the assistant message THROUGH the reactive store. The plain
  // `assistantMsg` above is stored raw by Vue's reactive proxy and wrapped
  // lazily on read — so the local var is the non-reactive original, and
  // mutating it directly (content, toolCalls) bypasses the proxy and triggers
  // no updates (hence "must close/reopen to see changes"). Reading it back
  // via the reactive computed yields the proxy, whose mutations track.
  const session = activeSession.value
  const reactiveMsg = session?.messages[session.messages.length - 1]
  if (reactiveMsg) assistantMsg = reactiveMsg
  if (!assistantMsg.toolCalls) assistantMsg.toolCalls = []

  activeTraceId.value = assistantMsg.id
  thinkingOpen.value = true

  const realSessionId =
    activeId.value && !activeId.value.startsWith("temp-") ? activeId.value : null
  const trace = assistantMsg.toolCalls as ToolCall[]

  // Mark the most recent running node/tool of a given name as done. Events
  // arrive in order, so reverse-search finds the matching open step.
  const complete = (predicate: (s: ToolCall) => boolean, output: unknown) => {
    for (let i = trace.length - 1; i >= 0; i--) {
      if (predicate(trace[i]) && trace[i].status === "running") {
        trace[i].status = "done"
        trace[i].output = output
        trace[i].finishedAt = Date.now()
        trace[i].thinking = false // clear even if an llm_end was missed
        return
      }
    }
  }

  try {
    await api.streamChat(text, realSessionId, {
      onSession: () => {
        statusKey.value = "streaming"
      },
      onNodeStart: (name, label, icon) => {
        trace.push(makeNode(name, label, icon))
      },
      onNodeEnd: (name, output) => {
        complete((s) => s.kind === "node" && s.name === name, output)
        // Supervisor's output carries the parsed trip_request — surface it.
        if (name === "supervisor") {
          const out = output as { trip_request?: unknown } | null
          const sup = trace.find((s) => s.kind === "node" && s.name === "supervisor")
          if (sup) sup.output = out
        }
      },
      onLlmStart: (node) => {
        const n = trace.find(
          (s) => s.kind === "node" && s.name === node && s.status === "running",
        )
        if (n) {
          n.thinking = true
          n.llmCalls = (n.llmCalls ?? 0) + 1
        }
      },
      onLlmEnd: (node) => {
        const n = trace.find(
          (s) => s.kind === "node" && s.name === node && s.status === "running",
        )
        if (n) n.thinking = false
      },
      onReasoning: (node, text) => {
        const n = trace.find(
          (s) => s.kind === "node" && s.name === node && s.status === "running",
        )
        if (n) n.reasoning = (n.reasoning ?? "") + text
      },
      onToolStart: (node, name, input) => {
        trace.push(makeTool(node, name, input))
      },
      onToolEnd: (node, name, output) => {
        complete((s) => s.kind === "tool" && s.name === name && s.node === node, output)
      },
      onToken: (tok) => {
        assistantMsg.content += tok
      },
      onError: (message) => {
        assistantMsg.error = message
      },
      onDone: (result) => {
        // Authoritative answer (covers clarify/no-token paths where tokens
        // didn't stream).
        assistantMsg.content = result.finalAnswer || assistantMsg.content
        assistantMsg.id = result.messageId
        // Keep the sidebar target in sync: the id just changed from the
        // client uuid to the backend message id, so activeTraceId (set at
        // send() start to the old id) must follow or the thinking panel loses
        // its target and shows "no tool calls" until the user clicks again.
        activeTraceId.value = result.messageId
        assistantMsg.pending = false
        // Promote any still-running steps to done (defensive; should be none).
        for (const s of trace) {
          if (s.status === "running") {
            s.status = "done"
            s.thinking = false
            s.finishedAt = Date.now()
          }
        }
        // Bind the temp session to the real id. The temp session was already
        // unshifted into the sidebar list at send() start, so mutating its id
        // in place is enough — no list refresh (summaries carry no messages,
        // which would wipe the in-memory chat we just streamed).
        const idx = sessions.value.findIndex((s) => s.id === `temp-${now}`)
        if (idx >= 0) {
          sessions.value[idx].id = result.sessionId
          sessions.value[idx].updatedAt = Date.now()
          activeId.value = result.sessionId
        }
        statusKey.value = "done"
      },
    })
  } catch (e) {
    assistantMsg.pending = false
    assistantMsg.error = e instanceof Error ? e.message : t("error_state")
    statusKey.value = "error_state"
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex h-screen overflow-hidden" :style="{ background: 'var(--bg)' }">
    <SessionSidebar
      v-show="sidebarVisible"
      :sessions="sessions"
      :active-id="activeId"
      @select="selectSession"
      @request-delete="requestDelete"
      @request-rename="requestRename"
      @new-chat="newChat"
    />
    <ChatColumn
      :session="activeSession"
      :loading="loading"
      :status-key="statusKey"
      @send="send"
      @open-thinking="openThinking"
      @toggle-sidebar="sidebarVisible = !sidebarVisible"
    />
    <ThinkingSidebar
      :open="thinkingOpen"
      :tool-calls="activeToolCalls"
      @close="thinkingOpen = false"
    />

    <Modal
      v-if="dialog.kind === 'delete'"
      :title="t('confirm_delete_title')"
      @close="dialog = { kind: 'none' }"
    >
      <p class="text-sm" :style="{ color: 'var(--text)' }">
        {{ t("confirm_delete_msg") }}
      </p>
      <p class="mt-2 truncate text-sm font-medium" :style="{ color: 'var(--muted)' }">
        {{ dialog.title }}
      </p>
      <template #footer>
        <button
          class="rounded-lg border px-4 py-2 text-sm font-medium transition hover:opacity-80"
          :style="{ borderColor: 'var(--border)', color: 'var(--muted)' }"
          @click="dialog = { kind: 'none' }"
        >
          {{ t("cancel") }}
        </button>
        <button
          class="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700"
          @click="confirmDelete"
        >
          {{ t("delete") }}
        </button>
      </template>
    </Modal>

    <Modal
      v-if="dialog.kind === 'rename'"
      :title="t('rename_title')"
      @close="dialog = { kind: 'none' }"
    >
      <label class="mb-1 block text-xs font-semibold uppercase" :style="{ color: 'var(--muted)' }">
        {{ t("rename_label") }}
      </label>
      <input
        v-model="renameValue"
        autofocus
        class="w-full rounded-lg border px-3 py-2 text-sm outline-none transition focus:ring-2"
        :style="{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' }"
        @keydown.enter="confirmRename"
      />
      <template #footer>
        <button
          class="rounded-lg border px-4 py-2 text-sm font-medium transition hover:opacity-80"
          :style="{ borderColor: 'var(--border)', color: 'var(--muted)' }"
          @click="dialog = { kind: 'none' }"
        >
          {{ t("cancel") }}
        </button>
        <button
          class="rounded-lg px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          :style="{ background: 'var(--primary)' }"
          @click="confirmRename"
        >
          {{ t("save") }}
        </button>
      </template>
    </Modal>
  </div>
</template>
