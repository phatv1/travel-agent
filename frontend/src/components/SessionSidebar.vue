<script setup lang="ts">
import { ref, computed } from "vue"
import type { ChatSession } from "../types"
import { t } from "../lib/i18n"

const props = defineProps<{
  sessions: ChatSession[]
  activeId: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  requestDelete: [id: string]
  requestRename: [id: string]
  newChat: []
}>()

const search = ref("")
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.sessions
  return props.sessions.filter((s) => s.title.toLowerCase().includes(q))
})
</script>

<template>
  <aside
    class="flex h-full w-[20vw] min-w-[200px] shrink-0 flex-col overflow-hidden border-r transition-[width] duration-200"
    :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
  >
    <div class="flex items-center justify-between px-4 py-3">
        <h2 class="text-sm font-semibold" :style="{ color: 'var(--text)' }">
          💬 {{ t("sessions") }}
        </h2>
        <button
          :title="t('new_session_btn')"
          class="rounded-md px-2 py-0.5 text-base transition hover:opacity-70"
          :style="{ color: 'var(--muted)' }"
          @click="emit('newChat')"
        >
          ✚
        </button>
      </div>

      <div class="px-3 pb-2">
        <input
          v-model="search"
          type="text"
          :placeholder="t('search_placeholder')"
          class="w-full rounded-lg border px-2.5 py-1.5 text-sm outline-none transition focus:ring-2"
          :style="{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
            color: 'var(--text)',
          }"
        />
      </div>

      <ul class="flex-1 overflow-y-auto px-2 pb-2">
        <li
          v-if="filtered.length === 0"
          class="px-2 py-6 text-center text-sm"
          :style="{ color: 'var(--muted)' }"
        >
          {{ t("no_sessions") }}
        </li>
        <li
          v-for="s in filtered"
          :key="s.id"
          :class="[
            'group mb-0.5 flex cursor-pointer items-center gap-1 rounded-lg px-2.5 py-2 text-sm transition hover:bg-[var(--surface-hover)]',
            s.id === activeId ? 'font-semibold text-[var(--primary)]' : 'text-[var(--text)]',
          ]"
          :style="s.id === activeId ? { background: 'var(--surface-hover)' } : {}"
          @click="emit('select', s.id)"
        >
          <span class="flex-1 truncate">{{ s.title }}</span>
          <span class="hidden gap-0.5 group-hover:flex">
            <button
              :title="t('rename')"
              class="rounded px-1 text-xs opacity-60 transition hover:opacity-100"
              @click.stop="emit('requestRename', s.id)"
            >
              ✏️
            </button>
            <button
              :title="t('delete')"
              class="rounded px-1 text-xs opacity-60 transition hover:opacity-100"
              @click.stop="emit('requestDelete', s.id)"
            >
              🗑️
            </button>
          </span>
        </li>
      </ul>

  </aside>
</template>
