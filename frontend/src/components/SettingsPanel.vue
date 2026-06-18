<script setup lang="ts">
import { ref, watch, onBeforeUnmount, nextTick } from "vue"
import { theme, setTheme } from "../lib/theme"
import { locale, setLocale, t } from "../lib/i18n"

export type ThinkingDisplay = "auto" | "manual"

const props = defineProps<{
  open: boolean
  thinkingDisplay: ThinkingDisplay
}>()

const emit = defineEmits<{
  close: []
  "set-thinking-display": [mode: ThinkingDisplay]
}>()

const panelEl = ref<HTMLElement | null>(null)

// Close on outside click. The trigger gear is tagged with
// data-settings-trigger so clicking it to toggle doesn't double-fire here
// (mousedown closes, then the gear's click toggles — that race is avoided by
// ignoring the trigger element entirely).
function onDocMousedown(e: MouseEvent) {
  const target = e.target as HTMLElement | null
  if (!target) return
  if (panelEl.value?.contains(target)) return
  if (target.closest("[data-settings-trigger]")) return
  emit("close")
}

watch(
  () => props.open,
  (v) => {
    if (v) nextTick(() => document.addEventListener("mousedown", onDocMousedown))
    else document.removeEventListener("mousedown", onDocMousedown)
  },
)
onBeforeUnmount(() => document.removeEventListener("mousedown", onDocMousedown))

function pickTheme(th: "light" | "dark") {
  if (theme.value !== th) setTheme(th)
}
function pickLocale(l: "vi" | "en") {
  if (locale.value !== l) setLocale(l)
}
function pickMode(m: ThinkingDisplay) {
  if (props.thinkingDisplay !== m) emit("set-thinking-display", m)
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="open"
        ref="panelEl"
        class="fixed right-3 top-12 z-50 w-[300px] origin-top-right rounded-2xl border shadow-2xl"
        :style="{ background: 'var(--surface)', borderColor: 'var(--border)' }"
      >
        <!-- Header -->
        <div
          class="flex items-center justify-between border-b px-4 py-3"
          :style="{ borderColor: 'var(--border)' }"
        >
          <h2 class="flex items-center gap-1.5 text-sm font-semibold" :style="{ color: 'var(--text)' }">
            ⚙️ {{ t("settings") }}
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

        <div class="flex flex-col gap-4 px-4 py-4">
          <!-- Appearance -->
          <div>
            <div class="mb-2 text-[11px] font-semibold uppercase tracking-wide" :style="{ color: 'var(--muted)' }">
              {{ t("appearance") }}
            </div>

            <!-- Theme -->
            <div class="mb-3">
              <div class="mb-1.5 text-xs font-medium" :style="{ color: 'var(--text)' }">
                {{ t("theme") }}
              </div>
              <div class="grid grid-cols-2 gap-1 rounded-xl p-1" :style="{ background: 'var(--surface-hover)' }">
                <button
                  class="flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium transition"
                  :style="
                    theme === 'light'
                      ? { background: 'var(--surface)', color: 'var(--text)', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                      : { color: 'var(--muted)' }
                  "
                  @click="pickTheme('light')"
                >
                  ☀️ {{ t("theme_light") }}
                </button>
                <button
                  class="flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium transition"
                  :style="
                    theme === 'dark'
                      ? { background: 'var(--surface)', color: 'var(--text)', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                      : { color: 'var(--muted)' }
                  "
                  @click="pickTheme('dark')"
                >
                  🌙 {{ t("theme_dark") }}
                </button>
              </div>
            </div>

            <!-- Language -->
            <div class="mb-3">
              <div class="mb-1.5 text-xs font-medium" :style="{ color: 'var(--text)' }">
                {{ t("language") }}
              </div>
              <div class="grid grid-cols-2 gap-1 rounded-xl p-1" :style="{ background: 'var(--surface-hover)' }">
                <button
                  class="rounded-lg py-1.5 text-xs font-medium transition"
                  :style="
                    locale === 'vi'
                      ? { background: 'var(--surface)', color: 'var(--text)', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                      : { color: 'var(--muted)' }
                  "
                  @click="pickLocale('vi')"
                >
                  🇻🇳 Tiếng Việt
                </button>
                <button
                  class="rounded-lg py-1.5 text-xs font-medium transition"
                  :style="
                    locale === 'en'
                      ? { background: 'var(--surface)', color: 'var(--text)', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                      : { color: 'var(--muted)' }
                  "
                  @click="pickLocale('en')"
                >
                  🇬🇧 English
                </button>
              </div>
            </div>
          </div>

          <!-- Thinking display -->
          <div>
            <div class="mb-1.5 text-xs font-medium" :style="{ color: 'var(--text)' }">
              {{ t("thinking_display") }}
            </div>
            <div class="grid grid-cols-2 gap-1 rounded-xl p-1" :style="{ background: 'var(--surface-hover)' }">
              <button
                class="flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium transition"
                :style="
                  thinkingDisplay === 'auto'
                    ? { background: 'var(--surface)', color: 'var(--text)', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                    : { color: 'var(--muted)' }
                "
                @click="pickMode('auto')"
              >
                ⚡ {{ t("mode_auto") }}
              </button>
              <button
                class="flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium transition"
                :style="
                  thinkingDisplay === 'manual'
                    ? { background: 'var(--surface)', color: 'var(--text)', boxShadow: '0 1px 3px rgba(0,0,0,0.12)' }
                    : { color: 'var(--muted)' }
                "
                @click="pickMode('manual')"
              >
                ✋ {{ t("mode_manual") }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
