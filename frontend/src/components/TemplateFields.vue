<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue"
import { lines, type TemplateKind, type TemplateValues } from "../lib/templates"

const props = defineProps<{
  kind: TemplateKind
  modelValue: TemplateValues
}>()
const emit = defineEmits<{
  "update:modelValue": [values: TemplateValues]
}>()

const rows = computed(() => lines(props.kind))
const rootEl = ref<HTMLElement | null>(null)

function set(key: string, value: string) {
  emit("update:modelValue", { ...props.modelValue, [key]: value })
}

// Auto-focus the first required slot when the template opens or switches kind.
watch(
  () => props.kind,
  async () => {
    await nextTick()
    const el = rootEl.value?.querySelector<HTMLElement>('[data-required="true"]')
    el?.focus()
  },
  { immediate: true },
)
</script>

<template>
  <div ref="rootEl" class="flex flex-col gap-2 px-4 pb-1 pt-3">
    <div v-for="(ln, li) in rows" :key="li" class="flex flex-wrap items-baseline gap-x-1.5">
      <template v-for="(seg, si) in ln.segments" :key="si">
        <!-- STATIC TEXT -->
        <span v-if="'text' in seg" class="text-sm" :style="{ color: 'var(--muted)' }">{{ seg.text }}</span>

        <!-- SEGMENTED SELECT (plan) -->
        <div v-else-if="seg.slot.kind === 'select'" class="inline-flex overflow-hidden rounded-lg border" :style="{ borderColor: 'var(--border)' }">
          <button
            v-for="opt in seg.slot.options"
            :key="opt.value"
            type="button"
            class="px-2.5 py-1 text-xs font-medium transition"
            :style="{
              background: modelValue[seg.slot.key] === opt.value ? 'var(--primary)' : 'transparent',
              color: modelValue[seg.slot.key] === opt.value ? 'white' : 'var(--text)',
            }"
            @click="set(seg.slot.key, opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>

        <!-- TEXT SLOT (underlined fill-in-the-blank) -->
        <input
          v-else
          :value="String(modelValue[seg.slot.key] ?? '')"
          :placeholder="seg.slot.placeholder"
          :data-required="seg.slot.required ? 'true' : undefined"
          class="min-w-[8rem] flex-1 border-b bg-transparent pb-0.5 text-sm outline-none transition placeholder:opacity-50 focus:border-[var(--primary)]"
          :style="{
            borderColor: seg.slot.required && !(modelValue[seg.slot.key] ?? '').trim() ? 'var(--primary)' : 'var(--border)',
            color: 'var(--text)',
          }"
          @input="set(seg.slot.key, ($event.target as HTMLInputElement).value)"
        />
      </template>
    </div>
  </div>
</template>
