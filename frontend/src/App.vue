<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

interface ChatResponse {
  final_answer: string
  itinerary?: { days?: unknown[] } | null
  recommendations?: unknown | null
  cost_report?: unknown | null
}

const message = ref('')
const answer = ref('')
const loading = ref(false)
const error = ref('')

const renderedAnswer = computed(() =>
  answer.value ? DOMPurify.sanitize(marked.parse(answer.value, { async: false })) : ''
)

async function send() {
  if (!message.value.trim() || loading.value) return
  loading.value = true
  error.value = ''
  answer.value = ''
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: message.value }),
    })
    if (!res.ok) {
      throw new Error(`Lỗi máy chủ (${res.status})`)
    }
    const data: ChatResponse = await res.json()
    answer.value = data.final_answer
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Không thể kết nối máy chủ.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 bg-slate-50 p-6">
    <header>
      <h1 class="text-3xl font-bold text-slate-900">Travel Agent</h1>
      <p class="text-slate-600">Trợ lý tư vấn du lịch — lịch trình, gợi ý & chi phí.</p>
    </header>

    <form class="flex flex-col gap-3" @submit.prevent="send">
      <textarea
        v-model="message"
        :disabled="loading"
        rows="3"
        placeholder="VD: Đi Đà Nẵng 3 ngày 2 đêm, 2 người. Lên lịch trình, gợi ý ks quán ăn và ước chi phí."
        class="w-full resize-none rounded-lg border border-slate-300 p-3 text-slate-900 outline-none focus:border-slate-500 disabled:bg-slate-100"
      />
      <button
        type="submit"
        :disabled="loading || !message.trim()"
        class="self-start rounded-lg bg-slate-900 px-5 py-2 font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {{ loading ? 'Đang xử lý...' : 'Gửi' }}
      </button>
    </form>

    <p v-if="loading" class="text-sm text-slate-500">
      Đang chạy agent (có thể mất 1-2 phút với Ollama cục bộ)...
    </p>

    <p v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-700">
      {{ error }}
    </p>

    <section
      v-if="answer"
      v-html="renderedAnswer"
      class="markdown rounded-lg bg-white p-4 text-slate-800 shadow-sm"
    ></section>
  </main>
</template>
