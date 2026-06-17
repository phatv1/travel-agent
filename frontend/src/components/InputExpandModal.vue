<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue"
import { t } from "../lib/i18n"

const props = defineProps<{ open: boolean; modelValue: string }>()
const emit = defineEmits<{
  close: []
  "update:modelValue": [value: string]
}>()

const textareaEl = ref<HTMLTextAreaElement | null>(null)

function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") emit("close")
}

onMounted(() => {
  window.addEventListener("keydown", onKey)
  document.body.style.overflow = "hidden"
  nextTick(() => textareaEl.value?.focus())
})
onUnmounted(() => {
  window.removeEventListener("keydown", onKey)
  document.body.style.overflow = ""
})
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" @click="emit('close')"></div>
      <div class="relative w-full max-w-2xl">
        <button
          type="button"
          :title="t('minimize')"
          class="absolute right-2 top-2 z-10 flex h-8 w-8 items-center justify-center rounded-lg text-base leading-none transition hover:opacity-70"
          :style="{ background: 'var(--surface-hover)', color: 'var(--muted)' }"
          @click="emit('close')"
        >
          ⤡
        </button>
        <textarea
          ref="textareaEl"
          :value="modelValue"
          :placeholder="t('input_placeholder')"
          rows="16"
          class="block w-full resize-none rounded-2xl border p-5 pr-12 text-sm leading-6 shadow-2xl outline-none"
          :style="{ background: 'var(--surface)', borderColor: 'var(--border)', color: 'var(--text)' }"
          @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        ></textarea>
      </div>
    </div>
  </Teleport>
</template>
