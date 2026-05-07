# 前端对接：Agent Playground HTTP API

- **Base URL（开发）**：`http://127.0.0.1:8011`（后端默认端口 `8011`）
- **API 前缀**：所有业务接口为 **`/api/...`**
- **内容类型**：`Content-Type: application/json`（除流式运行见下文）
- **CORS**：后端已允许 `http://127.0.0.1:5173`、`http://localhost:5173`；若前端部署在其他源，需在后端 `main.py` 的 `CORSMiddleware` 中追加。

前端 Vite 开发服务器将 `/api` 代理到 `http://127.0.0.1:8011`（见 `frontend/vite.config.js`），因此用相对路径 `/api/...` 即可。

**可选：显式基地址**（独立域名或移动端 WebView 等）：

- 环境变量：`VITE_API_BASE_URL=https://你的后端:8011`（无尾部 `/`）
- 或注入：`globalThis.__AGENT_PLAYGROUND_CONFIG__ = { apiBaseUrl: "https://..." }`

---

## 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 返回 `{"status":"ok"}` |

---

## 应用设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取模型配置、环境变量等 |
| PUT | `/api/settings` | 更新设置（会刷新 LLM 客户端） |

**`AppSettings`（响应/请求体，字段与后端一致）**

- `model_profiles`: `ModelProfile[]`
- `active_model_profile_id`: `string | null`
- `env_vars`: `{ key: string, value: string }[]`
- `env_path`: `string`（只读，来自服务端）

**`ModelProfile`**

- `id`, `provider`, `name`, `api_key`, `base_url`, `model`

---

## 工作流模板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workflow-templates` | 内置工作流类型列表 |

每项含 `type`, `label`, `description`, `required_agent_count`。`type` 取值：

`router_specialists` | `planner_executor` | `supervisor_dynamic` | `single_agent_chat` | `peer_handoff`

---

## 技能 Skills

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/skills` | 列表（含 `runtime_preflight` 等） |
| POST | `/api/skills` | 创建（body: `SkillDefinitionCreate`） |
| POST | `/api/skills/{skill_id}/install` | 安装/同步包（SkillHub 会下载文件） |
| POST | `/api/skills/sync` | 从 SkillHub 拉取并入库 |

**`SkillDefinitionCreate`**

- `name`, `description`, `instruction`（必填）

**`SkillSyncRequest`**

- `provider`: 固定 `"skillhub"`
- `query`: 可选，默认 `"search"`
- `limit`: 1–100，默认 40

**`SkillSyncResponse`**

- `provider`, `query`, `fetched`, `imported`, `updated`

---

## 智能体 Agents

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents` | 列表 |
| POST | `/api/agents` | 创建 |
| PUT | `/api/agents/{agent_id}` | 更新 |
| DELETE | `/api/agents/{agent_id}` | 删除（若仍被工作流引用则 409） |

**`AgentDefinitionCreate` / 更新体**

- `name`, `description`, `system_prompt`（必填）
- `model`: 可选
- `skill_ids`: 字符串 ID 列表
- `builtin_capabilities`: `("filesystem" \| "fs_list" \| "fs_read" \| "fs_write")[]`

---

## 工作流 Workflows

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workflows` | 列表 |
| POST | `/api/workflows` | 创建 |
| PUT | `/api/workflows/{workflow_id}` | 更新 |
| DELETE | `/api/workflows/{workflow_id}` | 删除 |
| GET | `/api/workflows/{workflow_id}/graph` | 用于画布展示的图结构（nodes/edges） |

**`WorkflowDefinitionCreate` / 更新体**

- `name`, `type`（见上表）, `specialist_agent_ids`（需满足模板 `required_agent_count`）
- `router_prompt`, `finalizer_enabled`

**`WorkflowGraph`**

- `nodes`: `{ id, label, kind, parent_id? }[]`，`kind` 为 `start` | `logic` | `agent` | `final` | `end` | `group`
- `edges`: `{ source, target, label? }[]`

---

## 运行工作流

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/runs` | 同步一次完整运行，返回终态 JSON |
| POST | `/api/runs/stream` | **Server-Sent Events (SSE)**，流式 trace + 最终结果 |

**请求体 `WorkflowRunRequest`**

- `workflow_id`: 必填
- `user_input`: 必填
- `conversation_id`: 可选；不传时服务端会**新建会话**并在响应里带上 `conversation_id`

**`WorkflowRunResponse`（同步与 stream 的 `final` 事件数据一致）**

- `workflow_id`, `user_input`, `assistant_message`
- `trace`: `TraceEvent[]`
- `graph`: `WorkflowGraph`
- `artifacts`: `route_agent_id`, `route_agent_name`, `route_reason`, `specialist_answer`, `final_answer` 等
- `conversation_id`

**`TraceEvent`**

- `type`, `title`, `detail`, `at`, `payload`

**SSE（`/api/runs/stream`）**

- `event: trace` — data 为 trace 单条
- `event: final` — data 为完整 `WorkflowRunResponse` 字典
- `event: error` — data 为 `{ "message": "..." }`
- `event: end` — 结束

示例（概念）：使用 `POST`，`Accept` 为默认即可；响应 `Content-Type: text/event-stream`，按 `\n\n` 分帧解析。

---

## 会话 Conversations

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/conversations` | 列表；可选 query `?workflow_id=...` |
| POST | `/api/conversations` | 创建，body: `{ "workflow_id": "..." }` |
| GET | `/api/conversations/{conversation_id}` | 含消息列表的详情 |
| DELETE | `/api/conversations/{conversation_id}` | 删除 |

**`ConversationDetail`**

- 在 `Conversation` 基础上增加 `messages: Message[]`

**`Message`**

- `id`, `conversation_id`, `role`, `content`, `agent_name?`, `created_at`

---

## 与仓库内前端的对应关系

`frontend/src/api.js` 已封装上述路径；联调时保证后端已启动（`uvicorn app.main:app --host 127.0.0.1 --port 8011`），前端 `npm run dev` 走代理即可。

---

## OpenAPI

后端为 FastAPI，启动服务后可访问：

- `GET http://127.0.0.1:8011/docs`（Swagger UI）
- `GET http://127.0.0.1:8011/redoc`（ReDoc）

以交互方式查看请求/响应模型与在线调试。
