<script setup lang="ts">
import { ref, watch, nextTick } from "vue"
import { marked } from "marked"
import DOMPurify from "dompurify"
import type { ChatSession } from "../types"
import { t, locale, setLocale } from "../lib/i18n"
import { theme, toggleTheme } from "../lib/theme"
import InputExpandModal from "./InputExpandModal.vue"

const props = defineProps<{
  session: ChatSession | null
  loading: boolean
  statusKey: string
}>()

const emit = defineEmits<{
  send: [message: string]
  openThinking: [messageId: string]
  toggleSidebar: []
}>()

const draft = ref("")
const messagesEl = ref<HTMLDivElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const expandOpen = ref(false)

function render(md: string): string {
  return DOMPurify.sanitize(marked.parse(md, { async: false }) as string)
}

function submit() {
  const text = draft.value.trim()
  if (!text || props.loading) return
  emit("send", text)
  draft.value = ""
  autoGrow()
}

function onKeydown(e: KeyboardEvent) {
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

function toggleLocale() {
  setLocale(locale.value === "vi" ? "en" : "vi")
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
          :title="t('toggle_theme_' + (theme === 'dark' ? 'light' : 'dark'))"
          class="rounded-lg px-2 py-1 transition hover:bg-[var(--surface-hover)]"
          :style="{ color: 'var(--text)' }"
          @click="toggleTheme()"
        >
          {{ theme === "dark" ? "☀️" : "🌙" }}
        </button>
        <button
          :title="locale === 'vi' ? 'Switch to English' : 'Chuyển sang Tiếng Việt'"
          class="min-w-[2rem] rounded-lg px-2 py-1 text-xs font-semibold transition hover:bg-[var(--surface-hover)]"
          :style="{ color: 'var(--text)' }"
          @click="toggleLocale"
        >
          {{ locale.toUpperCase() }}
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
              {{ t("thinking_btn") }}
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

    <form class="flex items-end gap-2 border-t px-6 py-3" :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }" @submit.prevent="submit">
      <div class="relative flex-1">
        <button
          type="button"
          :title="t('expand')"
          class="absolute bottom-3 left-3 text-base leading-none transition hover:opacity-70"
          :style="{ color: 'var(--muted)' }"
          @click="expandOpen = true"
        >
          ⤢
        </button>
        <textarea
          ref="textareaEl"
          v-model="draft"
          :disabled="loading"
          rows="1"
          :placeholder="t('input_placeholder')"
          class="block max-h-[200px] w-full resize-none rounded-xl border px-11 py-3 text-sm leading-5 outline-none transition focus:border-[var(--primary)] disabled:opacity-60"
          :style="{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' }"
          @keydown="onKeydown"
          @input="autoGrow"
        ></textarea>
      </div>
      <button
        type="submit"
        :disabled="loading || !draft.trim()"
        class="h-[44px] shrink-0 rounded-xl px-5 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        :style="{ background: 'var(--primary)' }"
      >
        {{ t("send") }}
      </button>
    </form>

    <InputExpandModal
      v-model="draft"
      :open="expandOpen"
      @close="onExpandClose"
    />
  </section>
</template>
