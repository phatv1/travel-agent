<script setup lang="ts">
import { onMounted, ref } from 'vue'

const status = ref('checking...')

onMounted(async () => {
  try {
    const res = await fetch('/health')
    const data: { status: string } = await res.json()
    status.value = data.status
  } catch {
    status.value = 'unreachable'
  }
})
</script>

<template>
  <main class="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50">
    <h1 class="text-3xl font-bold text-slate-900">Travel Agent</h1>
    <p class="text-slate-600">
      Backend health:
      <span class="font-mono font-semibold text-emerald-600">{{ status }}</span>
    </p>
  </main>
</template>
