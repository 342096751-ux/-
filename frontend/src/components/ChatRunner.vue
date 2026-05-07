<script setup>
import { Bug, MessageSquare, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Send, Square, X } from "lucide-vue-next";
import { inject, nextTick, onMounted, reactive, ref, watch } from "vue";
import { marked } from "marked";
import { I18N_KEY } from "../i18n";
import MermaidBlock from "./MermaidBlock.vue";

const props = defineProps({
  selectedWorkflowId: { type: String, default: "" },
  selectedWorkflow: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  leftVisible: { type: Boolean, default: true },
  rightVisible: { type: Boolean, default: true },
  messages: { type: Array, default: () => [] },
});

const emit = defineEmits(["run", "clear", "stop", "toggle-left", "toggle-right"]);
const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((key) => key);

const form = reactive({ user_input: "" });
const inputRef = ref(null);
const scrollRef = ref(null);
const debugDialog = ref(null);

marked.setOptions({ breaks: true, gfm: true });

function resizeInput() {
  const el = inputRef.value;
  if (!el) return;
  el.style.height = "auto";
  const maxHeight = 180;
  const nextHeight = Math.min(el.scrollHeight, maxHeight);
  el.style.height = `${nextHeight}px`;
  el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
}

function handleInput() { nextTick(resizeInput); }
function renderMarkdown(content) { return marked.parse(String(content || "")); }
function scrollToBottom() { const el = scrollRef.value; if (el) el.scrollTop = el.scrollHeight; }
function parseAuditReport(content) {
  const text = String(content || "").trim();
  if (!text || (!text.startsWith("{") && !text.startsWith("["))) return null;
  try {
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object") return null;
    if (!Object.prototype.hasOwnProperty.call(parsed, "意图标签")) return null;
    return parsed;
  } catch {
    return null;
  }
}

function handleKeydown(event) {
  if (event.isComposing) return;
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    submit();
  }
}

function openDebugDialog(message) {
  const rawItems = Array.isArray(message?.debugRawResponses) ? message.debugRawResponses : [];
  if (!rawItems.length) return;
  debugDialog.value = {
    agentName: message?.agentName || "",
    items: rawItems,
  };
}

function closeDebugDialog() {
  debugDialog.value = null;
}

async function submit() {
  if (props.loading || !props.selectedWorkflowId || !form.user_input.trim()) return;
  const nextInput = form.user_input;
  form.user_input = "";
  await nextTick();
  resizeInput();
  await emit("run", { workflow_id: props.selectedWorkflowId, user_input: nextInput });
}

onMounted(() => { resizeInput(); nextTick(scrollToBottom); });
watch(() => [props.messages.length, props.loading], () => nextTick(scrollToBottom));
</script>

<template>
  <section class="glass-panel chat-shell">
    <header class="run-panel-header">
      <div class="chat-head-main">
        <button class="chat-panel-button" type="button" @click="$emit('toggle-left')">
          <component :is="props.leftVisible ? PanelLeftClose : PanelLeftOpen" :size="15" />
        </button>
        <div class="chat-icon">
          <MessageSquare :size="16" />
        </div>
        <div>
          <h3 class="run-panel-title">{{ t("chat.title") }}</h3>
          <p class="chat-active-text">{{ t("chat.active") }}: {{ selectedWorkflow?.name || t("chat.noneSelected") }}</p>
        </div>
      </div>
      <div class="chat-header-actions">
        <button class="text-button text-xs" @click="$emit('clear')">{{ t("chat.clear") }}</button>
        <div class="chat-header-divider"></div>
        <button class="chat-panel-button" type="button" @click="$emit('toggle-right')">
          <component :is="props.rightVisible ? PanelRightClose : PanelRightOpen" :size="15" />
        </button>
      </div>
    </header>

    <div ref="scrollRef" class="chat-scroll">
      <div v-if="!messages.length && !loading" class="chat-empty-state">
        <div class="chat-empty-icon"><Send :size="26" /></div>
        <div>
          <h4>{{ t("chat.startRun") }}</h4>
          <p>{{ t("chat.startRunDesc") }}</p>
        </div>
      </div>

      <template v-else>
        <div v-for="message in messages" :key="message.id" class="chat-row" :class="{ user: message.role === 'user' }">
          <div class="chat-row-inner">
            <span v-if="message.agentName" class="chat-agent-name">{{ message.agentName }}</span>
            <div class="chat-bubble markdown-body" :class="{ user: message.role === 'user' }">
              <div v-if="message.role === 'user'">{{ message.content }}</div>
              <template v-else>
                <template v-if="parseAuditReport(message.content)">
                  <div class="audit-report-card">
                    <h4>审核报告</h4>
                    <div class="audit-report-row">
                      <strong>意图标签：</strong>
                      <span>{{ (parseAuditReport(message.content)?.意图标签 || []).join("、") || "无" }}</span>
                    </div>
                    <div class="audit-report-row">
                      <strong>最终执行动作：</strong>
                      <span>{{ parseAuditReport(message.content)?.最终执行动作 || "放行" }}</span>
                    </div>
                    <div class="audit-report-row">
                      <strong>最终判定：</strong>
                      <span>{{ parseAuditReport(message.content)?.最终判定 || "安全" }}</span>
                    </div>
                    <div
                      v-for="(item, domain) in (parseAuditReport(message.content)?.工作单元结果 || {})"
                      :key="domain"
                      class="audit-findings"
                    >
                      <div class="audit-findings-title">{{ domain }}</div>
                      <div>结论：{{ item?.结论 || "-" }}</div>
                      <div>置信度：{{ item?.置信度 || "-" }}</div>
                      <div>证据：{{ Array.isArray(item?.证据) ? item.证据.map((x) => x?.内容片段).filter(Boolean).join("；") || "-" : "-" }}</div>
                    </div>
                    <template v-if="parseAuditReport(message.content)?.['流程图Mermaid_管线']">
                      <h5 class="audit-subh">管线图（并行的各工作单元）</h5>
                      <MermaidBlock :code="parseAuditReport(message.content)['流程图Mermaid_管线']" />
                    </template>
                    <template v-if="parseAuditReport(message.content)?.['流程图Mermaid_顺序']">
                      <h5 class="audit-subh">本运行步骤链</h5>
                      <MermaidBlock :code="parseAuditReport(message.content)['流程图Mermaid_顺序']" />
                    </template>
                    <div v-if="(parseAuditReport(message.content)?.['执行轨迹'] || []).length" class="audit-trace-block">
                      <h5 class="audit-subh">执行轨迹</h5>
                      <table class="audit-trace-table">
                        <thead>
                          <tr>
                            <th>时间</th>
                            <th>阶段</th>
                            <th>详情</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="(tr, trIdx) in parseAuditReport(message.content)['执行轨迹']" :key="`tr-${trIdx}`">
                            <td class="trace-time">{{ tr?.时间 || "—" }}</td>
                            <td>{{ tr?.阶段 || "—" }}</td>
                            <td>{{ tr?.详情 || "—" }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </template>
                <div v-else v-html="renderMarkdown(message.content)"></div>
              </template>
            </div>
            <button
              v-if="message.role !== 'user' && Array.isArray(message.debugRawResponses) && message.debugRawResponses.length"
              class="chat-debug-button"
              type="button"
              @click="openDebugDialog(message)"
            >
              <Bug :size="12" />
              调试原始返回
            </button>
          </div>
        </div>

        <div v-if="loading" class="chat-row">
          <div class="typing-indicator"><span></span><span></span><span></span><strong>{{ t("chat.thinking") }}</strong></div>
        </div>
      </template>
    </div>

    <footer class="chat-input-wrap">
      <div class="chat-input-shell">
        <textarea ref="inputRef" v-model="form.user_input" rows="1" :placeholder="t('chat.inputPlaceholder')" @input="handleInput" @keydown="handleKeydown" />
        <button v-if="loading" class="stop-mini-button" type="button" @click="$emit('stop')"><Square :size="12" /></button>
        <button class="send-mini-button" :disabled="!selectedWorkflowId || loading" @click="submit"><Send :size="14" /></button>
      </div>
    </footer>
  </section>

  <div v-if="debugDialog" class="debug-dialog-overlay" @click="closeDebugDialog">
    <section class="debug-dialog" @click.stop>
      <header class="debug-dialog-header">
        <strong>原始模型返回</strong>
        <button class="debug-dialog-close" type="button" @click="closeDebugDialog">
          <X :size="14" />
        </button>
      </header>
      <p v-if="debugDialog.agentName" class="debug-dialog-agent">来源: {{ debugDialog.agentName }}</p>
      <div class="debug-dialog-body">
        <article v-for="(item, index) in debugDialog.items" :key="item.id || index" class="debug-item">
          <div class="debug-item-meta">
            <span>#{{ index + 1 }}</span>
            <span v-if="item.agentName">{{ item.agentName }}</span>
            <span v-if="item.model">{{ item.model }}</span>
          </div>
          <pre>{{ item.rawOutput }}</pre>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.audit-report-card {
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  padding: 10px;
  display: grid;
  gap: 6px;
}

.audit-report-card h4 {
  margin: 0 0 4px;
  font-size: 13px;
}

.audit-report-row {
  font-size: 12px;
  color: #0f172a;
}

.audit-findings {
  border-top: 1px dashed #cbd5e1;
  padding-top: 6px;
  margin-top: 4px;
  font-size: 12px;
}

.audit-findings-title {
  font-weight: 600;
  margin-bottom: 2px;
}

.audit-subh {
  margin: 8px 0 4px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.audit-trace-block {
  border-top: 1px dashed #cbd5e1;
  margin-top: 6px;
  padding-top: 6px;
}

.audit-trace-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  color: #0f172a;
}

.audit-trace-table th,
.audit-trace-table td {
  border: 1px solid #e2e8f0;
  padding: 4px 6px;
  text-align: left;
  vertical-align: top;
}

.audit-trace-table th {
  background: #f1f5f9;
  font-weight: 600;
}

.trace-time {
  white-space: nowrap;
  color: #64748b;
  max-width: 160px;
}

.chat-debug-button {
  margin-top: 6px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 11px;
  display: inline-flex;
  gap: 4px;
  align-items: center;
  background: #f8fafc;
  color: #334155;
  cursor: pointer;
}

.debug-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1600;
}

.debug-dialog {
  width: min(820px, 92vw);
  max-height: 78vh;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  display: flex;
  flex-direction: column;
}

.debug-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
}

.debug-dialog-close {
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  border-radius: 8px;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.debug-dialog-agent {
  margin: 0;
  padding: 8px 12px 0;
  font-size: 12px;
  color: #475569;
}

.debug-dialog-body {
  padding: 10px 12px 12px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.debug-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}

.debug-item-meta {
  padding: 6px 8px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 11px;
  color: #475569;
  display: flex;
  gap: 8px;
}

.debug-item pre {
  margin: 0;
  padding: 8px;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
