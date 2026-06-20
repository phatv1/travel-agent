Tiếng Việt | [Tiếng Anh](README.md)

# Travel Agent

> Một trợ lý tư vấn du lịch đa-agent lập lịch trình, gợi ý lưu trú & ăn uống, và ước chi phí từ một câu nói tự nhiên.

Mỗi lượt, một node supervisor điều phối ba chuyên gia — lịch trình, gợi ý, chi phí — gọi tool dữ liệu thực (Wikipedia, DuckDuckGo, Geoapify, giá vé máy bay live), rồi tổng hợp thành một câu trả lời. Supervisor biết rõ ba năng lực của mình và **từ chối trung thực** khi được yêu cầu phần nằm ngoài — đặt vé, visa, thời tiết — thay vì bịa. Câu trả lời theo ngôn ngữ user đang dùng (tiếng Việt, tiếng Anh, hoặc khác).

Xây dựng bằng LangGraph, FastAPI, Vue 3, và model Ollama chạy local.

---

<video src="docs/demo.mp4" controls width="100%" style="max-width:800px;border-radius:8px"></video>

---

---

## Chạy nhanh

**Chuẩn bị:** Python 3.13 + [uv](https://docs.astral.sh/uv/), [bun](https://bun.sh/), [Ollama](https://ollama.com/).

```bash
# 1. Backend
cd backend && uv sync && cp .env.example .env
uv run uvicorn app.main:app --app-dir src --reload      # :8000

# 2. Frontend (terminal khác)
cd frontend && bun install && bun run dev               # :5173

# 3. Model
ollama pull gemma4:12b-it-qat                           # đổi OLLAMA_MODEL trong .env nếu cần
```

Mở **http://localhost:5173**. Đầy đủ cấu hình (LLM, Geoapify key, đường dẫn DB) ở [`backend/README.md`](backend/README.md).

---

## Tìm hiểu sâu

| Tài liệu | Nội dung |
|---|---|
| 📐 [Kiến trúc](docs/architecture.md) | Thiết kế graph, năng lực, 4-action routing, honest refusal, tool-calling, multi-turn memory |
| 🔌 [API](docs/api.md) | Endpoint REST + SSE, trình tự event, schema request/response |

---

## Giấy phép

[MIT](LICENSE).
