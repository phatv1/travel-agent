<script setup lang="ts">
import { ref, computed, watch } from "vue"
import type { ChatSession } from "../types"
import { t } from "../lib/i18n"

const props = defineProps<{
  width: number
  sessions: ChatSession[]
  activeId: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  requestBulkDelete: [ids: string[]]
  requestRename: [id: string]
  newChat: []
}>()

const search = ref("")
// Selection for bulk delete. A plain object Set kept reactive via ref + new
// Set reassignment on every mutation (Vue tracks ref identity changes).
const selected = ref<Set<string>>(new Set())

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.sessions
  return props.sessions.filter((s) => s.title.toLowerCase().includes(q))
})

const filteredIds = computed(() => filtered.value.map((s) => s.id))
const allFilteredSelected = computed(
  () =>
    filteredIds.value.length > 0 &&
    filteredIds.value.every((id) => selected.value.has(id)),
)
// Selection mode: at least one row picked → reveal every row's checkbox so
// the user can click more without hunting for hover targets.
const selecting = computed(() => selected.value.size > 0)

function toggleSelect(id: string) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function toggleSelectAll() {
  const next = new Set(selected.value)
  if (allFilteredSelected.value) {
    filteredIds.value.forEach((id) => next.delete(id))
  } else {
    filteredIds.value.forEach((id) => next.add(id))
  }
  selected.value = next
}

function clearSelection() {
  selected.value = new Set()
}

// Prune selection when sessions vanish (single/bulk deletes from the parent),
// so checked ids never dangle on a missing row.
watch(
  () => props.sessions,
  (list) => {
    const ids = new Set(list.map((s) => s.id))
    const pruned = new Set<string>()
    for (const id of selected.value) if (ids.has(id)) pruned.add(id)
    if (pruned.size !== selected.value.size) selected.value = pruned
  },
)
</script>

<template>
  <aside
    class="flex h-full shrink-0 flex-col overflow-hidden border-r"
    :style="{ width: props.width + 'px', borderColor: 'var(--border)', background: 'var(--surface)' }"
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

    <!-- Bulk action bar: only visible once at least one row is checked. -->
    <div
      v-if="selected.size > 0"
      class="flex items-center gap-2 border-y px-3 py-2 text-xs"
      :style="{ borderColor: 'var(--border)', background: 'var(--surface-hover)' }"
    >
      <button
        class="flex items-center gap-1.5 font-medium transition hover:opacity-70"
        :style="{ color: 'var(--text)' }"
        @click="toggleSelectAll"
      >
        <span
          class="inline-flex h-3.5 w-3.5 items-center justify-center rounded border"
          :style="{
            borderColor: 'var(--border)',
            background: allFilteredSelected ? 'var(--primary)' : 'transparent',
          }"
        >
          <span v-if="allFilteredSelected" class="text-[9px] leading-none text-white">✓</span>
        </span>
        {{ t("select_all") }}
      </button>
      <span class="flex-1" :style="{ color: 'var(--muted)' }">
        {{ selected.size }} {{ t("selected") }}
      </span>
      <button
        :title="t('clear_selection')"
        class="rounded px-1 transition hover:opacity-70"
        :style="{ color: 'var(--muted)' }"
        @click="clearSelection"
      >
        ✕
      </button>
      <button
        class="rounded-md px-2 py-0.5 font-semibold text-white transition hover:opacity-90"
        :style="{ background: '#dc2626' }"
        @click="emit('requestBulkDelete', [...selected])"
      >
        🗑️ {{ t("delete") }} ({{ selected.size }})
      </button>
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
          'group mb-0.5 flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-2 text-sm transition hover:bg-[var(--surface-hover)]',
          s.id === activeId ? 'font-semibold text-[var(--primary)]' : 'text-[var(--text)]',
        ]"
        :style="s.id === activeId ? { background: 'var(--surface-hover)' } : {}"
        @click="emit('select', s.id)"
      >
        <span class="flex-1 truncate">{{ s.title }}</span>
        <span
          :class="[
            'flex shrink-0 items-center gap-0.5 transition-opacity',
            selected.has(s.id) || selecting ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
          ]"
        >
          <button
            :title="t('rename')"
            class="rounded px-1 text-xs opacity-60 transition hover:opacity-100"
            @click.stop="emit('requestRename', s.id)"
          >
            ✏️
          </button>
          <input
            type="checkbox"
            :checked="selected.has(s.id)"
            class="h-3.5 w-3.5 cursor-pointer accent-[var(--primary)]"
            @click.stop="toggleSelect(s.id)"
          />
        </span>
      </li>
    </ul>
  </aside>
</template>
