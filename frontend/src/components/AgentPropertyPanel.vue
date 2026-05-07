<script setup>
import { computed, ref } from "vue";
import {
  clusterStore,
  exportClusterConfig,
  importClusterConfig,
  selectedConfig,
  updateAgentConfig,
} from "../store/clusterStore";
import { runMockEngine } from "../utils/mockEngine";
import PromptEditor from "./editors/PromptEditor.vue";
import SchemaEditor from "./editors/SchemaEditor.vue";

const props = defineProps({ graph: { type: Object, default: null }, inputText: { type: String, default: "" } });
const emits = defineEmits(["append-local-log"]);

const cfg = computed(() => selectedConfig());
const allGraphNodes = computed(() => (Array.isArray(props.graph?.nodes) ? props.graph.nodes : []));
const validatorOptions = computed(() =>
  allGraphNodes.value.filter((n) => {
    const type = String(n?.type || n?.kind || "").toLowerCase();
    const label = String(n?.data?.label || n?.data?.name || n?.id || "");
    return type === "validator" || label.includes("验证");
  }),
);
const arbitratorOptions = computed(() =>
  allGraphNodes.value.filter((n) => {
    const type = String(n?.type || n?.kind || "").toLowerCase();
    const label = String(n?.data?.label || n?.data?.name || n?.id || "");
    return type === "arbitrator" || label.includes("仲裁");
  }),
);
const targetOptions = computed(() =>
  allGraphNodes.value.filter((n) => {
    const type = String(n?.type || n?.kind || "").toLowerCase();
    return type !== "content_input";
  }),
);
const defaultSuccessTargetId = computed(() => {
  const brain = targetOptions.value.find((n) => {
    const type = String(n?.type || n?.kind || "").toLowerCase();
    const label = String(n?.data?.label || n?.data?.name || "").toLowerCase();
    return type === "brain" || label.includes("brain") || label.includes("大脑");
  });
  return brain?.id || targetOptions.value[0]?.id || "";
});
const routingCfg = computed(() => {
  const routing = cfg.value?.routing || {};
  return {
    enabled: Boolean(routing.enabled),
    validatorNodeId: routing.validatorNodeId || "",
    successTargetNodeId: routing.successTargetNodeId || defaultSuccessTargetId.value,
    challengeAction: routing.challengeAction === "arbitrate" ? "arbitrate" : "retry",
    arbitratorNodeId: routing.arbitratorNodeId || "",
    maxRounds: Math.max(1, Math.min(3, Number(routing.maxRounds || 1))),
  };
});

function patch(patchObj) {
  if (!cfg.value) return;
  updateAgentConfig(cfg.value.id, patchObj);
}

function patchRouting(nextPatch) {
  patch({ routing: { ...routingCfg.value, ...nextPatch } });
}

async function runFromCurrent() {
  if (!props.graph || !cfg.value) return;
  await runMockEngine({
    graph: props.graph,
    inputText: props.inputText,
    startAtAgentId: cfg.value.id,
    onLog: (log) => emits("append-local-log", log),
  });
}

function onImportFile(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result || "{}"));
      importClusterConfig(parsed);
    } catch (e) {
      alert(`导入失败: ${String(e?.message || e)}`);
    }
  };
  reader.readAsText(file, "utf-8");
}

function downloadConfig() {
  const payload = exportClusterConfig();
  const blob = new Blob([payload], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `agent-cluster-config-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <section class="glass-panel property-shell">
    <header class="run-panel-header">
      <h3 class="run-panel-title">Agent 属性面板</h3>
      <span class="chip chip-dark" v-if="cfg">{{ cfg.name }}</span>
    </header>

    <div v-if="!cfg" class="empty-tip">请在画布中点击一个 Agent 节点。</div>

    <div v-else class="panel-body">
      <h4 class="section-title">基础配置</h4>
      <label class="field">
        <span>Agent 名称</span>
        <input :value="cfg.name" @input="patch({ name: $event.target.value })" />
      </label>
      <label class="field">
        <span>角色描述</span>
        <textarea rows="2" :value="cfg.role" @input="patch({ role: $event.target.value })" />
      </label>
      <label class="field">
        <span>系统提示词</span>
        <PromptEditor :model-value="cfg.systemPrompt" @update:model-value="patch({ systemPrompt: $event })" />
      </label>
      <label class="field">
        <span>输出格式定义 (JSON Schema)</span>
        <SchemaEditor :model-value="cfg.outputSchema" @update:model-value="patch({ outputSchema: $event })" />
      </label>
      <label class="field">
        <span>温度: {{ Number(cfg.temperature).toFixed(2) }}</span>
        <input type="range" min="0" max="1" step="0.01" :value="cfg.temperature" @input="patch({ temperature: Number($event.target.value) })" />
      </label>
      <label class="field">
        <span>置信阈值: {{ Number(cfg.confidenceThreshold).toFixed(2) }}</span>
        <input type="range" min="0" max="1" step="0.01" :value="cfg.confidenceThreshold" @input="patch({ confidenceThreshold: Number($event.target.value) })" />
      </label>
      <label class="field">
        <span>模型</span>
        <select :value="cfg.model" @change="patch({ model: $event.target.value })">
          <option v-for="m in clusterStore.models" :key="m" :value="m">{{ m }}</option>
        </select>
      </label>
      <div class="runtime-actions">
        <label class="strict-check"><input type="checkbox" :checked="cfg.strictMode" @change="patch({ strictMode: $event.target.checked })" /> 严格模式(schema错误终止)</label>
        <button class="accent-button accent-button-violet" @click="runFromCurrent">重新执行此节点</button>
        <button class="ghost-button" @click="downloadConfig">导出编排配置</button>
        <label class="ghost-button import-btn">导入配置 <input type="file" accept="application/json" @change="onImportFile" /></label>
      </div>

      <p v-if="cfg.schemaError" class="schema-error">输出格式不匹配，请检查 Prompt：{{ cfg.schemaError }}</p>
    </div>
  </section>
</template>

<style scoped>
.property-shell { height: 100%; overflow: hidden; display: flex; flex-direction: column; }
.panel-body { padding: 10px; overflow: auto; display: flex; flex-direction: column; gap: 10px; }
.section-title { margin: 0; font-size: 12px; color: #a5b4fc; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 12px; }
.field input, .field select, .field textarea { width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; background: #ffffff; color: #0f172a; padding: 8px; }
.table-wrap { border: 1px solid #dbeafe; border-radius: 8px; padding: 8px; display: flex; flex-direction: column; gap: 8px; background: #f8fbff; }
.table-wrap table { width: 100%; border-collapse: collapse; font-size: 12px; }
.table-wrap th, .table-wrap td { border-bottom: 1px solid #e2e8f0; padding: 4px; text-align: left; }
.table-wrap td input, .table-wrap td select { width: 100%; }
.field-inline { display: grid; grid-template-columns: 72px 1fr; align-items: center; gap: 8px; font-size: 12px; }
.runtime-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.strict-check { font-size: 12px; }
.import-btn { position: relative; overflow: hidden; }
.import-btn input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.schema-error { margin: 0; color: #fca5a5; font-size: 12px; }
.empty-tip { padding: 12px; color: #94a3b8; font-size: 12px; }
</style>
