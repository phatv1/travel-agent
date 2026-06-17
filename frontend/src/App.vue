<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import SessionSidebar from "./components/SessionSidebar.vue"
import ChatColumn from "./components/ChatColumn.vue"
import ThinkingSidebar from "./components/ThinkingSidebar.vue"
import Modal from "./components/Modal.vue"
import * as api from "./lib/api"
import { buildToolCalls } from "./lib/toolCalls"
import { t } from "./lib/i18n"
import { applyTheme, theme } from "./lib/theme"
import type { ChatMessage, ChatSession } from "./types"

function uid(): string {
  return crypto?.randomUUID?.() ?? `id-${Date.now()}-${Math.random().toString(36).slice(2)}`
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
  const assistantMsg: ChatMessage = {
    id: uid(),
    role: "assistant",
    content: "",
    pending: true,
    toolCalls: buildToolCalls(text),
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

  activeTraceId.value = assistantMsg.id
  thinkingOpen.value = true

  const realSessionId =
    activeId.value && !activeId.value.startsWith("temp-") ? activeId.value : null

  try {
    const result = await api.chat(text, realSessionId)
    if (!realSessionId) {
      const full = await api.getSession(result.sessionId)
      const idx = sessions.value.findIndex((s) => s.id === `temp-${now}`)
      if (full && idx >= 0) {
        sessions.value[idx] = full
        activeId.value = result.sessionId
      }
    } else {
      assistantMsg.content = result.assistant.content
      assistantMsg.toolCalls = result.assistant.toolCalls
      assistantMsg.pending = false
    }
    statusKey.value = "done"
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
