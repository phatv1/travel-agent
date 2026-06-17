import { ref } from "vue"

export type Locale = "vi" | "en"

const stored = (localStorage.getItem("travel-agent-locale") as Locale | null) ?? "vi"
export const locale = ref<Locale>(stored)

const dict: Record<Locale, Record<string, string>> = {
  vi: {
    sessions: "Phiên chat",
    new_session_title: "Cuộc trò chuyện mới",
    search_placeholder: "Tìm phiên...",
    no_sessions: "Chưa có phiên nào.",
    rename: "Đổi tên",
    delete: "Xoá",
    thinking: "Quá trình suy nghĩ",
    close: "Đóng",
    no_tool_calls: "Chưa có tool call nào.",
    show_output: "Xem output",
    hide_output: "Ẩn output",
    status_running: "đang chạy",
    status_done: "xong",
    status_error: "lỗi",
    thinking_btn: "💭 Quá trình suy nghĩ",
    empty_prompt: "Hãy mô tả chuyến đi bạn muốn lên kế hoạch ✈️",
    new_chat_prompt: "Bắt đầu cuộc trò chuyện mới 👇",
    ready: "Sẵn sàng.",
    loading: "🧭 Đang chạy agent (có thể mất 1-2 phút)...",
    done: "Hoàn tất.",
    error_state: "Lỗi.",
    connecting: "Đang tải...",
    no_backend: "Không kết nối được máy chủ.",
    send: "Gửi",
    input_placeholder: "VD: Đi Đà Nẵng 3 ngày 2 đêm, 2 người...",
    expand: "Mở rộng ô nhập",
    minimize: "Thu nhỏ",
    compose_title: "Soạn tin nhắn",
    cancel: "Huỷ",
    save: "Lưu",
    confirm_delete_title: "Xoá phiên",
    confirm_delete_msg: "Bạn có chắc muốn xoá phiên này? Không thể hoàn tác.",
    rename_title: "Đổi tên phiên",
    rename_label: "Tên phiên",
    new_session_btn: "Cuộc trò chuyện mới",
    toggle_sidebar: "Hiện/ẩn lịch sử",
    toggle_theme_light: "Chế độ sáng",
    toggle_theme_dark: "Chế độ tối",
  },
  en: {
    sessions: "Sessions",
    new_session_title: "New conversation",
    search_placeholder: "Search sessions...",
    no_sessions: "No sessions yet.",
    rename: "Rename",
    delete: "Delete",
    thinking: "Thinking process",
    close: "Close",
    no_tool_calls: "No tool calls yet.",
    show_output: "Show output",
    hide_output: "Hide output",
    status_running: "running",
    status_done: "done",
    status_error: "error",
    thinking_btn: "💭 Thinking process",
    empty_prompt: "Describe the trip you'd like to plan ✈️",
    new_chat_prompt: "Start a new conversation 👇",
    ready: "Ready.",
    loading: "🧭 Running agent (may take 1-2 min)...",
    done: "Done.",
    error_state: "Error.",
    connecting: "Loading...",
    no_backend: "Cannot reach server.",
    send: "Send",
    input_placeholder: "e.g. 3-day trip to Da Nang, 2 people...",
    expand: "Expand input",
    minimize: "Minimize",
    compose_title: "Compose message",
    cancel: "Cancel",
    save: "Save",
    confirm_delete_title: "Delete session",
    confirm_delete_msg: "Are you sure you want to delete this session? This cannot be undone.",
    rename_title: "Rename session",
    rename_label: "Session name",
    new_session_btn: "New chat",
    toggle_sidebar: "Toggle history",
    toggle_theme_light: "Light mode",
    toggle_theme_dark: "Dark mode",
  },
}

export function setLocale(l: Locale): void {
  locale.value = l
  localStorage.setItem("travel-agent-locale", l)
}

export function t(key: string): string {
  return dict[locale.value][key] ?? dict.en[key] ?? key
}
