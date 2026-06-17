<script setup lang="ts">
import { onMounted, onUnmounted } from "vue"

const props = withDefaults(
  defineProps<{
    title: string
    closeOnBackdrop?: boolean
    width?: string
  }>(),
  { closeOnBackdrop: true, width: "max-w-md" },
)

const emit = defineEmits<{ close: [] }>()

function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") emit("close")
}

onMounted(() => {
  window.addEventListener("keydown", onKey)
  document.body.style.overflow = "hidden"
})
onUnmounted(() => {
  window.removeEventListener("keydown", onKey)
  document.body.style.overflow = ""
})
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
    >
      <div
        class="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        @click="props.closeOnBackdrop ? emit('close') : undefined"
      ></div>
      <div
        :class="[
          'relative w-full rounded-2xl border shadow-2xl',
          props.width,
        ]"
        :style="{ background: 'var(--surface)', borderColor: 'var(--border)' }"
      >
        <header class="flex items-center justify-between border-b px-5 py-3.5" :style="{ borderColor: 'var(--border)' }">
          <h3 class="text-sm font-semibold" :style="{ color: 'var(--text)' }">{{ title }}</h3>
          <button
            class="rounded-md p-1 transition hover:opacity-70"
            :style="{ color: 'var(--muted)' }"
            @click="emit('close')"
          >
            ✕
          </button>
        </header>
        <div class="px-5 py-4">
          <slot />
        </div>
        <footer v-if="$slots.footer" class="flex justify-end gap-2 border-t px-5 py-3" :style="{ borderColor: 'var(--border)' }">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>
