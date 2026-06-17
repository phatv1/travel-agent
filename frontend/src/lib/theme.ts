import { ref } from "vue"

export type Theme = "light" | "dark"

function initial(): Theme {
  return (localStorage.getItem("travel-agent-theme") as Theme | null) ?? "light"
}

export const theme = ref<Theme>(initial())

export function applyTheme(th: Theme): void {
  document.documentElement.classList.toggle("dark", th === "dark")
}

export function setTheme(th: Theme): void {
  theme.value = th
  localStorage.setItem("travel-agent-theme", th)
  applyTheme(th)
}

export function toggleTheme(): void {
  setTheme(theme.value === "dark" ? "light" : "dark")
}
