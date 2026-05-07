<script setup>
import { computed, inject, ref, watch } from "vue";
import ChatRunner from "../../components/ChatRunner.vue";
import MessageLogPanel from "../../components/MessageLogPanel.vue";
import GraphViewer from "../../components/GraphViewer.vue";
import TraceViewer from "../../components/TraceViewer.vue";
import { I18N_KEY } from "../../i18n";
import { clusterStore, ensureAgentConfigs } from "../../store/clusterStore";

const props = defineProps({
  workflows: { type: Array, required: true },
  agents: { type: Array, required: true },
  appSettings: { type: Object, default: null },
  selectedWorkflowId: { type: String, default: "" },
  selectedWorkflow: { type: Object, default: null },
  selectedGraph: { type: Object, default: null },
  activeNodeId: { type: String, default: "" },
  focusNodeId: { type: String, default: "" },
  loading: { type: Boolean, default: false },
  trace: { type: Array, default: () => [] },
  tracePlaying: { type: Boolean, default: false },
  chatMessages: { type: Array, default: () => [] },
  batchRunState: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  "run",
  "clear",
  "stop",
  "batch-run",
  "select-workflow",
  "update-workflow",
  "edit-agent",
]);
const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((key) => key);
const workflowTypeLabel = i18n?.workflowTypeLabel || ((type) => type);

const leftVisible = ref(true);
const rightVisible = ref(true);

const auditWorkflows = computed(() =>
  (props.workflows || []).filter((w) => w && w.type === "ugc_moderation"),
);

const graphReady = computed(() => {
  const g = props.selectedGraph;
  return Boolean(g && Array.isArray(g.nodes) && g.nodes.length > 0);
});

watch(
  () => [props.agents, props.appSettings],
  ([agents, settings]) => ensureAgentConfigs(agents || [], settings || null),
  { immediate: true, deep: true },
);

watch(
  () => props.selectedWorkflowId,
  (id) => {
    clusterStore.selectedWorkflowId = id || "";
  },
  { immediate: true },
);

/** 进入运行页时确保选中 UGC 审核工作流 */
watch(
  [auditWorkflows, () => props.selectedWorkflowId],
  () => {
    const list = auditWorkflows.value;
    if (!list.length) return;
    const ok = list.some((w) => w.id === props.selectedWorkflowId);
    if (!ok) emit("select-workflow", list[0].id);
  },
  { immediate: true },
);

function handleNodeSelect(nodeId) {
  clusterStore.selectedAgentId = nodeId;
}

function handleNodeDoubleClick(agentId) {
  clusterStore.selectedAgentId = agentId;
  emit("edit-agent", agentId);
}

function handleUpdateChain(agentIds) {
  if (!props.selectedWorkflow) return;
  emit("update-workflow", {
    id: props.selectedWorkflow.id,
    data: {
      name: props.selectedWorkflow.name,
      type: props.selectedWorkflow.type,
      specialist_agent_ids: agentIds,
      finalizer_enabled: Boolean(props.selectedWorkflow.finalizer_enabled),
      router_prompt:
        props.selectedWorkflow.router_prompt ||
        "UGC moderation pipeline (intent -> work unit -> verifier -> arbiter).",
    },
  });
}
</script>

<template>
  <div class="playground-shell">
    <div
      class="playground-grid"
      :class="{
        'left-collapsed': !leftVisible,
        'right-collapsed': !rightVisible,
      }"
    >
      <aside v-if="leftVisible" class="playground-col-left">
        <section class="glass-panel workflow-select-card">
          <label class="field-label">{{ t("audit.selectAuditWorkflow") }}</label>
          <select
            v-if="auditWorkflows.length"
            class="workflow-native-select"
            :value="selectedWorkflowId"
            @change="emit('select-workflow', $event.target.value)"
          >
            <option v-for="wf in auditWorkflows" :key="wf.id" :value="wf.id">
              {{ wf.name }} — {{ workflowTypeLabel(wf.type) }}
            </option>
          </select>
          <p v-else class="empty-wf">{{ t("audit.noUgcWorkflow") }}</p>
        </section>

        <GraphViewer
          v-if="graphReady"
          :graph="props.selectedGraph"
          :graph-title="t('graph.auditTitle')"
          :allow-layout-i-o="false"
          :active-node-id="activeNodeId"
          :focus-node-id="focusNodeId"
          :trace="trace"
          :workflow="selectedWorkflow"
          :agents="agents"
          @select-node="handleNodeSelect"
          @dblclick-node="handleNodeDoubleClick"
          @update-chain="handleUpdateChain"
        />
        <div v-else class="glass-panel graph-placeholder">
          {{ t("audit.graphWait") }}
        </div>
      </aside>

      <section class="playground-col-center">
        <ChatRunner
          :selected-workflow-id="selectedWorkflowId"
          :selected-workflow="selectedWorkflow"
          :loading="loading"
          :left-visible="leftVisible"
          :right-visible="rightVisible"
          :messages="chatMessages"
          @run="emit('run', $event)"
          @clear="emit('clear')"
          @stop="emit('stop')"
          @toggle-left="leftVisible = !leftVisible"
          @toggle-right="rightVisible = !rightVisible"
        />
      </section>

      <aside v-if="rightVisible" class="playground-col-right orchestration-right-col audit-run-right">
        <MessageLogPanel />
        <TraceViewer :trace="trace" :playing="tracePlaying" />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.orchestration-right-col.audit-run-right {
  grid-template-rows: minmax(200px, 38%) minmax(240px, 1fr);
  gap: 10px;
  min-height: 0;
}

.empty-wf,
.graph-placeholder {
  padding: 10px;
  font-size: 0.85rem;
  color: #94a3b8;
}
</style>
