<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue"
import { t } from "../lib/i18n"
import type { TemplateKind } from "../lib/templates"

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  select: [kind: TemplateKind]
  close: []
}>()

interface Option {
  kind: TemplateKind
  icon: string
  titleKey: string
  descKey: string
}

const OPTIONS: Option[] = [
  { kind: "fast", icon: "⚡", titleKey: "tpl_fast", descKey: "tpl_fast_desc" },
  { kind: "advanced", icon: "🎯", titleKey: "tpl_advanced", descKey: "tpl_advanced_desc" },
]

// Arrow-key navigation index. Resets whenever the menu (re)opens.
const activeIndex = ref(0)
const rootEl = ref<HTMLDivElement | null>(null)

function choose(i: number) {
  emit("select", OPTIONS[i].kind)
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return
  if (e.key === "ArrowDown") {
    e.preventDefault()
    activeIndex.value = (activeIndex.value + 1) % OPTIONS.length
  } else if (e.key === "ArrowUp") {
    e.preventDefault()
    activeIndex.value = (activeIndex.value - 1 + OPTIONS.length) % OPTIONS.length
  } else if (e.key === "Enter" || e.key === "Tab") {
    // Enter or Tab selects the highlighted template (Tab's default focus-move
    // is cancelled by preventDefault).
    e.preventDefault()
    choose(activeIndex.value)
  } else if (e.key === "Escape") {
    e.preventDefault()
    emit("close")
  }
}

// Click outside the popup closes it (but clicks inside the textarea that hosts
// the "/" don't reach here because they're outside rootEl too — handled by the
// draft watch in the parent, which only reopens on a draft *change*).
function onDocClick(e: MouseEvent) {
  if (!props.open) return
  if (rootEl.value && !rootEl.value.contains(e.target as Node)) emit("close")
}

watch(
  () => props.open,
  (v) => {
    if (v) activeIndex.value = 0
  },
)

onMounted(() => {
  window.addEventListener("keydown", onKey)
  document.addEventListener("click", onDocClick)
})
onUnmounted(() => {
  window.removeEventListener("keydown", onKey)
  document.removeEventListener("click", onDocClick)
})
</script>

<template>
  <div
    v-if="open"
    ref="rootEl"
    role="listbox"
    aria-label="Template"
    class="absolute bottom-full left-0 z-30 mb-2 w-72 overflow-hidden rounded-xl border shadow-xl"
    :style="{ background: 'var(--surface)', borderColor: 'var(--border)' }"
  >
    <button
      v-for="(o, i) in OPTIONS"
      :key="o.kind"
      type="button"
      role="option"
      :aria-selected="i === activeIndex"
      class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition"
      :style="{
        background: i === activeIndex ? 'var(--surface-hover)' : 'transparent',
        color: 'var(--text)',
      }"
      @click="choose(i)"
      @mouseenter="activeIndex = i"
    >
      <span class="text-lg">{{ o.icon }}</span>
      <span class="flex flex-col">
        <span class="text-sm font-medium">{{ t(o.titleKey) }}</span>
        <span class="text-xs" :style="{ color: 'var(--muted)' }">{{ t(o.descKey) }}</span>
      </span>
    </button>
  </div>
</template>
