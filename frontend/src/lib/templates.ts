import { locale } from "./i18n"

/** UI-only feature: a fill-in-the-blank prompt laid out as one field per line.
 * Each line is a lead-in phrase + an editable slot; on submit the slots are
 * composed into a natural-language prompt the supervisor parses as if typed by
 * hand. No backend contract — slot keys mirror TripRequest 1:1 so compose maps
 * straight onto it. */

export type TemplateKind = "fast" | "advanced"

export interface SelectOption {
  value: string
  label: string
}

/** One editable blank within a line. */
export interface Slot {
  key: string
  /** "text" (default) or "select" (segmented control). */
  kind?: "text" | "select"
  required?: boolean
  placeholder?: string
  options?: SelectOption[]
  defaultValue?: string
}

/** A line = interleaved text + slots. Rendered as one flex row. */
export interface Line {
  segments: Array<{ text: string } | { slot: Slot }>
}

// Selector options for the "Hãy giúp mình lên kế hoạch ___" line (advanced only).
// Maps to backend needs_*: cost is never offered — it always runs.
const PLAN_OPTIONS_VI: SelectOption[] = [
  { value: "itinerary", label: "đi tham quan" },
  { value: "recommendations", label: "nghỉ ngơi & ăn uống" },
  { value: "both", label: "hoàn chỉnh" },
]
const PLAN_OPTIONS_EN: SelectOption[] = [
  { value: "itinerary", label: "sightseeing" },
  { value: "recommendations", label: "stays & dining" },
  { value: "both", label: "complete" },
]

// Full closing sentence per option (UI labels are short; compose uses these for
// correct grammar — "lên kế hoạch nghỉ ngơi" / "plan complete" read oddly).
const PLAN_CLAUSE_VI: Record<string, string> = {
  itinerary: "Hãy giúp mình lên kế hoạch đi tham quan, kèm ước tính chi phí.",
  recommendations: "Hãy giúp mình gợi ý chỗ nghỉ và ăn uống, kèm ước tính chi phí.",
  both: "Hãy giúp mình lên kế hoạch hoàn chỉnh, kèm ước tính chi phí.",
}
const PLAN_CLAUSE_EN: Record<string, string> = {
  itinerary: "Help me plan the itinerary, with a cost estimate.",
  recommendations: "Help me plan stays and dining, with a cost estimate.",
  both: "Help me plan a complete trip, with a cost estimate.",
}

// Placeholders for the 2 broad required fields. Multi-example (city /
// country / spot for dest; days / month / weekend for time) signals the field
// accepts many forms rather than one narrow format.
const DEST_PH = { vi: "Đà Nẵng, Nhật Bản, Bà Nà...", en: "Da Nang, Japan, Ba Na..." }
const TIME_PH = {
  vi: "3 ngày, tháng 8, cuối tuần...",
  en: "3 days, August, weekend...",
}

/** Lines for a template. Locale-reactive (call inside a computed). */
export function lines(kind: TemplateKind): Line[] {
  const vi = locale.value === "vi"
  const destPh = DEST_PH[vi ? "vi" : "en"]
  const timePh = TIME_PH[vi ? "vi" : "en"]
  if (kind === "fast") {
    return [
      {
        segments: [
          { text: vi ? "Tôi muốn đi " : "I want to visit " },
          { slot: { key: "destination", required: true, placeholder: destPh } },
          { text: vi ? " trong " : " for " },
          { slot: { key: "time", required: true, placeholder: timePh } },
        ],
      },
    ]
  }
  const plan = vi ? PLAN_OPTIONS_VI : PLAN_OPTIONS_EN
  return [
    {
      segments: [
        { text: vi ? "Tôi muốn đi " : "I want to visit " },
        { slot: { key: "destination", required: true, placeholder: destPh } },
        { text: vi ? " trong khoảng " : " for around " },
        { slot: { key: "time", required: true, placeholder: timePh } },
      ],
    },
    line(vi ? "khởi hành từ " : "departing from ", "origin", vi ? "TP.HCM" : "Ho Chi Minh"),
    line(vi ? "cùng " : "with ", "companions", vi ? "2 người" : "2 people"),
    line(vi ? "ngân sách khoảng " : "budget around ", "budget", vi ? "25 triệu" : "25M VND"),
    line(vi ? "ưu tiên " : "prioritize ", "prefs_like", vi ? "biển, gần biển..." : "beach, seafront..."),
    line(vi ? "tránh " : "avoid ", "prefs_avoid", vi ? "đông người, đi bộ nhiều..." : "crowds, long walks..."),
    {
      segments: [
        { text: vi ? "Hãy giúp mình lên kế hoạch " : "Help me plan " },
        { slot: { key: "plan", kind: "select", options: plan, defaultValue: "both" } },
      ],
    },
  ]
}

function line(phrase: string, key: string, placeholder: string): Line {
  return { segments: [{ text: phrase }, { slot: { key, placeholder } }] }
}

export type TemplateValues = Record<string, string>

/** Initial values — every text slot empty, select at its default. */
export function initialValues(kind: TemplateKind): TemplateValues {
  const v: TemplateValues = {}
  for (const ln of lines(kind)) {
    for (const seg of ln.segments) {
      if ("slot" in seg) v[seg.slot.key] = seg.slot.defaultValue ?? ""
    }
  }
  return v
}

/** Every required slot filled? Drives the submit button state. */
export function isComplete(kind: TemplateKind, values: TemplateValues): boolean {
  return lines(kind).every((ln) =>
    ln.segments.every((seg) => {
      if (!("slot" in seg) || !seg.slot.required) return true
      return String(values[seg.slot.key] ?? "").trim() !== ""
    }),
  )
}

export function composePrompt(kind: TemplateKind, values: TemplateValues): string {
  const dest = String(values.destination ?? "").trim()
  const time = String(values.time ?? "").trim()
  if (!dest || !time) return ""
  const vi = locale.value === "vi"

  const head = kind === "fast"
    ? (vi ? `Tôi muốn đi ${dest} trong ${time}` : `I want to visit ${dest} for ${time}`)
    : (vi ? `Tôi muốn đi ${dest} trong khoảng ${time}` : `I want to visit ${dest} for around ${time}`)
  if (kind === "fast") return head + "."

  const extra: string[] = []
  const o = String(values.origin ?? "").trim()
  if (o) extra.push(vi ? `khởi hành từ ${o}` : `departing from ${o}`)
  const c = String(values.companions ?? "").trim()
  if (c) extra.push(vi ? `cùng ${c}` : `with ${c}`)
  const b = String(values.budget ?? "").trim()
  if (b) extra.push(vi ? `ngân sách khoảng ${b}` : `budget around ${b}`)
  const lk = String(values.prefs_like ?? "").trim()
  if (lk) extra.push(vi ? `ưu tiên ${lk}` : `prioritize ${lk}`)
  const av = String(values.prefs_avoid ?? "").trim()
  if (av) extra.push(vi ? `tránh ${av}` : `avoid ${av}`)

  let s = head
  if (extra.length) s += ", " + extra.join(", ")
  s += "."

  // Plan selector → which agents run. Cost is always included (never chosen).
  const plan = String(values.plan ?? "both")
  const clauses = vi ? PLAN_CLAUSE_VI : PLAN_CLAUSE_EN
  s += " " + (clauses[plan] ?? clauses.both)
  return s
}
