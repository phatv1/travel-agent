<script setup lang="ts">
import { ref } from "vue"
import type { ToolCall } from "../types"
import { t } from "../lib/i18n"

defineProps<{
  open: boolean
  toolCalls: ToolCall[] | null
}>()

const emit = defineEmits<{ close: [] }>()

const expanded = ref<Set<string>>(new Set())

function toggle(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function formatJson(v: unknown): string {
  if (v === undefined) return t("status_running") + "..."
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}
</script>

<template>
  <aside
    class="h-full shrink-0 overflow-hidden border-l transition-[width] duration-200"
    :class="open ? 'w-[20vw] min-w-[200px]' : 'w-0'"
    :style="{ borderColor: 'var(--border)', background: 'var(--surface)' }"
  >
    <div v-if="open" class="flex h-full w-[20vw] min-w-[200px] flex-col">
      <div class="flex items-center justify-between border-b px-4 py-3" :style="{ borderColor: 'var(--border)' }">
        <h2 class="text-sm font-semibold" :style="{ color: 'var(--text)' }">
          🧠 {{ t("thinking") }}
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

      <div class="flex-1 overflow-y-auto px-3 py-3">
        <div
          v-if="!toolCalls || toolCalls.length === 0"
          class="px-2 py-8 text-center text-sm"
          :style="{ color: 'var(--muted)' }"
        >
          {{ t("no_tool_calls") }}
        </div>
        <div v-else class="flex flex-col gap-2">
          <div
            v-for="tc in toolCalls"
            :key="tc.id"
            class="rounded-xl border border-l-[3px]"
            :style="{
              borderColor: 'var(--border)',
              borderLeftColor: 'var(--primary)',
              background: 'var(--surface)',
            }"
          >
            <div class="flex items-center gap-2 px-3 py-2">
              <span class="text-base">{{ tc.icon }}</span>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium" :style="{ color: 'var(--text)' }">{{ tc.label }}</div>
                <div class="font-mono text-[11px]" :style="{ color: 'var(--muted)' }">{{ tc.name }}</div>
              </div>
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :style="
                  tc.status === 'done'
                    ? { background: 'rgba(21,128,61,0.15)', color: '#15803d' }
                    : tc.status === 'error'
                      ? { background: 'rgba(185,28,28,0.15)', color: '#b91c1c' }
                      : { background: 'rgba(180,83,9,0.15)', color: '#b45309' }
                "
              >
                {{ t("status_" + tc.status) }}
              </span>
            </div>

            <div class="border-t px-3 py-2" :style="{ borderColor: 'var(--border)' }">
              <div class="mb-1 text-[11px] font-semibold uppercase" :style="{ color: 'var(--muted)' }">Input</div>
              <pre
                class="overflow-x-auto rounded-lg p-2 text-[11px]"
                :style="{ background: 'var(--surface-hover)', color: 'var(--text)' }"
              >{{ formatJson(tc.input) }}</pre>
            </div>

            <div v-if="tc.status === 'done'" class="px-3 pb-2">
              <button
                class="text-[11px] font-medium transition hover:opacity-70"
                :style="{ color: 'var(--primary)' }"
                @click="toggle(tc.id)"
              >
                {{ expanded.has(tc.id) ? `▾ ${t("hide_output")}` : `▸ ${t("show_output")}` }}
              </button>
              <pre
                v-if="expanded.has(tc.id)"
                class="mt-1 max-h-64 overflow-auto rounded-lg p-2 text-[11px]"
                :style="{ background: 'var(--surface-hover)', color: 'var(--text)' }"
              >{{ formatJson(tc.output) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
