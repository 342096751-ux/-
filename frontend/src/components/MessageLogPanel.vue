<script setup>
import { computed, ref } from "vue";
import { clusterStore } from "../store/clusterStore";
import ConversationModal from "./ConversationModal.vue";

const expandedId = ref("");
const modalVisible = ref(false);
const modalEntry = ref(null);

const logs = computed(() => (Array.isArray(clusterStore.lastRunLogs) ? clusterStore.lastRunLogs : []));

const dossier = computed(() => {
  const list = logs.value;
  const final = list.find((l) => l?.fullContext?.parsedOutput?.verdict);
  return {
    content: list.find((l) => l?.fullContext?.input?.userPrompt)?.fullContext?.input?.userPrompt || "",
    finalVerdict: final?.fullContext?.parsedOutput?.verdict || "",
    finalEvidence: final?.fullContext?.parsedOutput?.evidence || "",
  };
});

function entryId(entry, idx) {
  return String(entry?.id || `${entry?.at || ""}-${idx}`);
}

function iconByType(entry) {
  const t = String(entry?.messageType || "");
  if (t === "send") return "📤";
  if (t === "receive") return "🟢";
  if (t === "warning") return "🔴";
  return "🟡";
}

function lineSummary(entry) {
  const from = entry?.from || entry?.source || "Agent";
  const to = entry?.to ? ` → ${entry.to}` : "";
  const summary = entry?.summary || entry?.text || "";
  return `${from}${to} ${summary}`.trim();
}

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? "" : id;
}

function asText(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function openModal(entry) {
  modalEntry.value = {
    at: entry?.at || new Date(entry?.timestamp || Date.now()).toISOString(),
    payload: {
      agent_name: entry?.from || entry?.source || "",
      context: entry?.fullContext?.input?.context || entry?.fullContext?.input || {},
      thinking: entry?.fullContext?.thinking || "",
      system_prompt: entry?.fullContext?.input?.systemPrompt || "",
      raw_output: entry?.fullContext?.rawOutput || "",
    },
  };
  modalVisible.value = true;
}
</script>

<template>
  <section class="glass-panel message-log-shell">
    <header class="run-panel-header">
      <h3 class="run-panel-title">消息日志</h3>
      <span class="panel-tag">案件卷宗</span>
    </header>
    <div class="message-log-body">
      <div class="dossier-box" v-if="dossier.content || dossier.finalVerdict">
        <p><strong>📋 审核卷宗</strong></p>
        <p v-if="dossier.content" class="truncate">内容：{{ dossier.content }}</p>
        <p v-if="dossier.finalVerdict">最终结论：{{ dossier.finalVerdict }} {{ dossier.finalEvidence ? `· ${dossier.finalEvidence}` : "" }}</p>
      </div>

      <div v-if="logs.length" class="message-log-list">
        <article v-for="(entry, idx) in logs" :key="entryId(entry, idx)" class="message-log-entry">
          <button class="message-log-head" @click="toggleExpand(entryId(entry, idx))">
            <span class="message-log-time">{{ (entry.at || "").slice(11, 19) || "--:--:--" }}</span>
            <span>{{ iconByType(entry) }}</span>
            <span class="message-log-summary">{{ lineSummary(entry) }}</span>
            <span class="message-log-expand">{{ expandedId === entryId(entry, idx) ? "▼" : "▶" }}</span>
          </button>
          <div v-if="expandedId === entryId(entry, idx)" class="message-log-detail">
            <div class="ctx-block">
              <strong>输入上下文</strong>
              <pre>{{ asText(entry.fullContext?.input || {}) }}</pre>
            </div>
            <div class="ctx-block">
              <strong>思考过程</strong>
              <pre>{{ asText(entry.fullContext?.thinking || "") }}</pre>
            </div>
            <div class="ctx-block">
              <strong>原始输出</strong>
              <pre>{{ asText(entry.fullContext?.rawOutput || "") }}</pre>
            </div>
            <div class="ctx-block">
              <strong>解析结果</strong>
              <pre>{{ asText(entry.fullContext?.parsedOutput || {}) }}</pre>
            </div>
            <button class="ghost-button small-ghost" @click="openModal(entry)">弹窗查看详情</button>
          </div>
        </article>
      </div>
      <p v-else class="trace-empty">运行后会在这里显示 Agent 间完整对话上下文。</p>
    </div>
    <ConversationModal :visible="modalVisible" :entry="modalEntry" @close="modalVisible = false" />
  </section>
</template>

<style scoped>
.message-log-shell { min-height: 0; overflow: hidden; display: flex; flex-direction: column; }
.message-log-body { min-height: 0; overflow: auto; padding: 10px; display: grid; gap: 8px; }
.dossier-box { border: 1px solid #dbeafe; border-radius: 10px; background: #f8fbff; padding: 8px; font-size: 12px; color: #334155; }
.dossier-box p { margin: 0 0 4px; }
.dossier-box p:last-child { margin-bottom: 0; }
.message-log-list { display: grid; gap: 8px; }
.message-log-entry { border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; overflow: hidden; }
.message-log-head { width: 100%; border: none; background: #fff; text-align: left; padding: 8px; display: grid; grid-template-columns: auto auto 1fr auto; gap: 8px; align-items: center; }
.message-log-time { font-size: 11px; color: #64748b; }
.message-log-summary { font-size: 12px; color: #0f172a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.message-log-expand { color: #64748b; font-size: 12px; }
.message-log-detail { border-top: 1px dashed #e2e8f0; padding: 8px; display: grid; gap: 8px; }
.ctx-block strong { display: block; font-size: 12px; color: #475569; margin-bottom: 4px; }
.ctx-block pre { margin: 0; padding: 8px; border-radius: 8px; border: 1px solid #e2e8f0; background: #f8fafc; font-size: 11px; white-space: pre-wrap; word-break: break-word; max-height: 140px; overflow: auto; }
</style>
