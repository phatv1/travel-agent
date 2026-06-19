<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue"
import { marked } from "marked"
import DOMPurify from "dompurify"
import type { ChatSession } from "../types"
import { t } from "../lib/i18n"
import {
  composePrompt,
  initialValues,
  isComplete,
  type TemplateKind,
  type TemplateValues,
} from "../lib/templates"
import InputExpandModal from "./InputExpandModal.vue"
import SlashMenu from "./SlashMenu.vue"
import TemplateFields from "./TemplateFields.vue"

const props = defineProps<{
  session: ChatSession | null
  loading: boolean
  statusKey: string
}>()

const emit = defineEmits<{
  send: [message: string]
  openThinking: [messageId: string]
  toggleSidebar: []
  openSettings: []
}>()

const draft = ref("")
const messagesEl = ref<HTMLDivElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const expandOpen = ref(false)

// Slash-command templates. "free" = plain textarea; "fast"/"advanced" =
// inline form whose submit composes a natural-language prompt the supervisor
// parses as if the user typed it. UI-only — no backend contract.
type ComposeMode = "free" | TemplateKind
const mode = ref<ComposeMode>("free")
const tplValues = ref<TemplateValues>({})
const slashMenuOpen = ref(false)

// Slash menu opens only when the draft is exactly "/" in free mode; any further
// typing or template entry closes it.
watch(draft, (v) => {
  slashMenuOpen.value = mode.value === "free" && v === "/"
})

const canSend = computed(() => {
  if (props.loading) return false
  if (mode.value === "free") return draft.value.trim().length > 0
  return isComplete(mode.value, tplValues.value)
})

const templateIcon = computed(() =>
  mode.value === "fast" ? "⚡" : mode.value === "advanced" ? "🎯" : "",
)
const templateTitle = computed(() =>
  mode.value === "fast" ? t("tpl_fast") : mode.value === "advanced" ? t("tpl_advanced") : "",
)

function render(md: string): string {
  return DOMPurify.sanitize(marked.parse(md, { async: false }) as string)
}

function submit() {
  let text: string
  if (mode.value === "free") {
    text = draft.value.trim()
  } else {
    if (!isComplete(mode.value, tplValues.value)) return
    text = composePrompt(mode.value, tplValues.value)
    if (!text) return
  }
  if (!text || props.loading) return
  emit("send", text)
  // Reset to free mode so the next turn starts from a plain textarea.
  mode.value = "free"
  tplValues.value = {}
  draft.value = ""
  autoGrow()
}

function onSlashSelect(kind: TemplateKind) {
  mode.value = kind
  tplValues.value = initialValues(kind)
  draft.value = "" // clear the triggering "/"
  slashMenuOpen.value = false
}

function onSlashClose() {
  slashMenuOpen.value = false
  // Don't leave a lone "/" in the textarea.
  if (draft.value === "/") draft.value = ""
}

function triggerSlash() {
  // Discoverable "/" button: drop a "/" into the empty draft so the watch
  // opens the menu (same path as typing it).
  draft.value = "/"
  nextTick(() => textareaEl.value?.focus())
}

function exitTemplate() {
  mode.value = "free"
  tplValues.value = {}
  draft.value = ""
  nextTick(() => textareaEl.value?.focus())
}

function onKeydown(e: KeyboardEvent) {
  // While the slash menu is open, SlashMenu owns Enter + Tab (select) — don't
  // fall through to submit (which would send "/" as a message) and stop the
  // textarea defaults (Enter newline, Tab focus-move).
  if (slashMenuOpen.value && (e.key === "Enter" || e.key === "Tab")) {
    e.preventDefault()
    return
  }
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

function autoGrow() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = "auto"
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`
}

function onExpandClose() {
  expandOpen.value = false
  autoGrow()
}

watch(
  () => props.session?.messages.length,
  async () => {
    await nextTick()
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  },
)
</script>

<template>
  <section class="flex min-w-0 flex-1 flex-col">
    <header class="flex items-center justify-between border-b px-4 py-2.5" :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }">
      <div class="flex items-center gap-2">
        <button
          :title="t('toggle_sidebar')"
          class="rounded-lg px-2 py-1 transition hover:bg-[var(--surface-hover)]"
          :style="{ color: 'var(--text)' }"
          @click="emit('toggleSidebar')"
        >
          ☰
        </button>
        <h1 class="flex items-center gap-1.5 text-base font-bold" :style="{ color: 'var(--text)' }">
          <span>✈️</span> Travel Agent
        </h1>
      </div>
      <div class="flex items-center gap-1">
        <button
          :title="t('settings')"
          data-settings-trigger
          class="rounded-lg px-2 py-1 transition hover:bg-[var(--surface-hover)]"
          :style="{ color: 'var(--text)' }"
          @click="emit('openSettings')"
        >
          ⚙️
        </button>
      </div>
    </header>

    <div ref="messagesEl" class="flex-1 overflow-y-auto px-6 py-6" :style="{ background: 'var(--bg)' }">
      <div
        v-if="!session || session.messages.length === 0"
        class="flex h-full flex-col items-center justify-center gap-1"
        :style="{ color: 'var(--muted)' }"
      >
        <p v-if="!session" class="text-sm">{{ t("new_chat_prompt") }}</p>
        <p v-else class="text-sm">{{ t("empty_prompt") }}</p>
      </div>

      <div v-else class="mx-auto flex max-w-3xl flex-col gap-4">
        <template v-for="m in session.messages" :key="m.id">
          <div v-if="m.role === 'user'" class="flex justify-end">
            <div class="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm px-4 py-2 text-white" :style="{ background: 'var(--primary)' }">
              {{ m.content }}
            </div>
          </div>

          <div v-else class="flex flex-col items-start gap-2">
            <button
              v-if="m.toolCalls?.length"
              class="rounded-lg border px-2.5 py-1 text-xs transition hover:opacity-80"
              :style="{ borderColor: 'var(--border)', color: 'var(--muted)', background: 'var(--surface)' }"
              @click="emit('openThinking', m.id)"
            >
              {{ m.pending ? t("thinking_btn_active") : t("thinking_btn_done") }}
            </button>

            <div
              v-if="m.pending && !m.content"
              class="flex w-fit items-center gap-1 rounded-2xl px-4 py-3 shadow-sm"
              :style="{ background: 'var(--surface)' }"
            >
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
            </div>

            <div
              v-else-if="m.content"
              v-html="render(m.content)"
              class="markdown rounded-2xl px-4 py-3 shadow-sm"
              :style="{ background: 'var(--surface)' }"
            ></div>

            <div
              v-if="m.error"
              class="rounded-2xl px-4 py-2 text-sm"
              :style="{ background: 'rgba(185,28,28,0.1)', color: '#b91c1c' }"
            >
              {{ m.error }}
            </div>
          </div>
        </template>
      </div>
    </div>

    <div class="border-t px-6 py-1.5 text-xs" :style="{ borderColor: 'var(--border)', color: 'var(--muted)', background: 'var(--surface)' }">
      {{ t(statusKey) }}
    </div>

    <form class="relative border-t px-6 py-3" :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }" @submit.prevent="submit">
      <SlashMenu :open="slashMenuOpen" @select="onSlashSelect" @close="onSlashClose" />
      <div
        class="flex flex-col rounded-xl border transition focus-within:border-[var(--primary)]"
        :style="{ background: 'var(--bg)', borderColor: 'var(--border)' }"
      >
        <!-- TEMPLATE MODE: inline form instead of free-text textarea -->
        <div v-if="mode !== 'free'" class="flex items-center gap-1.5 px-4 pt-2.5 text-xs font-semibold" :style="{ color: 'var(--muted)' }">
          <span>{{ templateIcon }}</span>
          <span>{{ templateTitle }}</span>
        </div>
        <TemplateFields
          v-if="mode !== 'free'"
          v-model="tplValues"
          :kind="mode"
        />

        <!-- FREE MODE: plain textarea -->
        <textarea
          v-else
          ref="textareaEl"
          v-model="draft"
          :disabled="loading"
          rows="1"
          :placeholder="t('input_placeholder')"
          class="block max-h-[200px] w-full resize-none bg-transparent px-4 pt-3 pb-1 text-sm leading-5 outline-none disabled:opacity-60"
          :style="{ color: 'var(--text)' }"
          @keydown="onKeydown"
          @input="autoGrow"
        ></textarea>
        <div class="flex items-center justify-between px-2 pb-2">
          <div class="flex items-center gap-0.5">
            <button
              v-if="mode === 'free'"
              type="button"
              :title="t('slash_hint')"
              class="flex h-7 w-7 items-center justify-center rounded-lg text-sm transition hover:bg-[var(--surface-hover)]"
              :style="{ color: 'var(--muted)' }"
              @click="triggerSlash"
            >
              /
            </button>
            <button
              v-if="mode === 'free'"
              type="button"
              :title="t('expand')"
              class="flex h-7 w-7 items-center justify-center rounded-lg text-sm transition hover:bg-[var(--surface-hover)]"
              :style="{ color: 'var(--muted)' }"
              @click="expandOpen = true"
            >
              ⤢
            </button>
            <button
              v-else
              type="button"
              :title="t('tpl_clear')"
              class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs transition hover:bg-[var(--surface-hover)]"
              :style="{ color: 'var(--muted)' }"
              @click="exitTemplate"
            >
              ✕ {{ t('tpl_clear') }}
            </button>
          </div>
          <button
            type="submit"
            :disabled="!canSend"
            class="rounded-lg px-4 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            :style="{ background: 'var(--primary)' }"
          >
            {{ t("send") }}
          </button>
        </div>
      </div>
    </form>

    <InputExpandModal
      v-model="draft"
      :open="expandOpen"
      @close="onExpandClose"
    />
  </section>
</template>
