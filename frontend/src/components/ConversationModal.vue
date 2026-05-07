<script setup>
const props = defineProps({
  visible: { type: Boolean, default: false },
  entry: { type: Object, default: null },
});
const emit = defineEmits(["close"]);

function jsonText(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}
</script>

<template>
  <div v-if="visible && entry" class="conv-modal-mask" @click="$emit('close')">
    <section class="conv-modal-panel" @click.stop>
      <header class="conv-modal-head">
        <h3>对话详情</h3>
        <button class="ghost-button" @click="$emit('close')">关闭</button>
      </header>
      <div class="conv-modal-body">
        <div class="conv-meta">发送者：{{ entry.payload?.agent_name || entry.payload?.from || "-" }}</div>
        <div class="conv-meta">时间：{{ entry.at || "-" }}</div>
        <div class="conv-section">
          <strong>输入上下文</strong>
          <pre>{{ jsonText(entry.payload?.context || entry.payload?._input || entry.payload?.input || {}) }}</pre>
        </div>
        <div class="conv-section">
          <strong>思考过程</strong>
          <pre>{{ jsonText(entry.payload?.thinking || entry.payload?._thinking || "") }}</pre>
        </div>
        <div class="conv-section">
          <strong>系统提示词</strong>
          <pre>{{ jsonText(entry.payload?.system_prompt || entry.payload?.systemPrompt || "") }}</pre>
        </div>
        <div class="conv-section">
          <strong>原始输出</strong>
          <pre>{{ jsonText(entry.payload?.raw_output || entry.payload?._rawOutput || entry.payload?.preview || "") }}</pre>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.conv-modal-mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 200; display: grid; place-items: center; padding: 20px; }
.conv-modal-panel { width: min(860px, calc(100vw - 40px)); max-height: calc(100vh - 40px); background: #fff; border-radius: 14px; border: 1px solid #e2e8f0; display: flex; flex-direction: column; overflow: hidden; }
.conv-modal-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; }
.conv-modal-head h3 { margin: 0; font-size: 15px; }
.conv-modal-body { padding: 12px; overflow: auto; display: grid; gap: 10px; }
.conv-meta { font-size: 12px; color: #64748b; }
.conv-section strong { display: block; font-size: 12px; color: #334155; margin-bottom: 4px; }
.conv-section pre { margin: 0; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; font-size: 12px; white-space: pre-wrap; word-break: break-word; }
</style>
