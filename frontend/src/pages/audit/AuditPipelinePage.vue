<script setup>
import { computed, inject, ref, watch } from "vue";
import { GitBranch } from "lucide-vue-next";
import GraphViewer from "../../components/GraphViewer.vue";
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
  trace: { type: Array, default: () => [] },
});

const emit = defineEmits(["select-workflow", "update-workflow", "edit-agent"]);
const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((k) => k);
const workflowTypeLabel = i18n?.workflowTypeLabel || ((type) => type);

const leftVisible = ref(true);

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
  <div class="playground-shell audit-pipeline">
    <div
      class="playground-grid"
      :class="{
        'left-collapsed': !leftVisible,
        'right-collapsed': true,
      }"
    >
      <aside v-if="leftVisible" class="playground-col-left">
        <section class="glass-panel workflow-select-card">
          <label class="field-label">
            <GitBranch :size="14" class="label-icon" />
            {{ t("audit.selectPipeline") }}
          </label>
          <select
            v-if="auditWorkflows.length"
            class="workflow-native-select"
            :value="props.selectedWorkflowId"
            @change="emit('select-workflow', $event.target.value)"
          >
            <option v-for="wf in auditWorkflows" :key="wf.id" :value="wf.id">
              {{ wf.name }} — {{ workflowTypeLabel(wf.type) }}
            </option>
          </select>
          <p v-else class="empty-hint">{{ t("audit.noUgcWorkflow") }}</p>
        </section>

        <GraphViewer
          v-if="graphReady"
          :graph="props.selectedGraph"
          :graph-title="t('graph.auditTitle')"
          :allow-layout-i-o="false"
          :active-node-id="props.activeNodeId"
          :focus-node-id="props.focusNodeId"
          :trace="props.trace"
          :workflow="props.selectedWorkflow"
          :agents="props.agents"
          @select-node="handleNodeSelect"
          @dblclick-node="handleNodeDoubleClick"
          @update-chain="handleUpdateChain"
        />
        <div v-else class="glass-panel graph-placeholder">
          {{ t("audit.graphWait") }}
        </div>
      </aside>

      <section class="playground-col-center explain-col">
        <div class="glass-panel explain-panel">
          <h3>{{ t("audit.pipelineExplainTitle") }}</h3>
          <ol>
            <li v-html="t('audit.pipelineStep1')"></li>
            <li v-html="t('audit.pipelineStep2')"></li>
            <li v-html="t('audit.pipelineStep3')"></li>
            <li v-html="t('audit.pipelineStep4')"></li>
          </ol>
          <p class="tip">{{ t("audit.goRun") }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.audit-pipeline .playground-grid {
  grid-template-columns: minmax(280px, 0.9fr) minmax(300px, 1.1fr);
}

.label-icon {
  display: inline;
  vertical-align: text-bottom;
  margin-right: 4px;
}

.explain-col {
  min-width: 0;
}

.explain-panel {
  padding: 16px 18px;
}

.explain-panel h3 {
  margin: 0 0 10px;
  font-size: 1rem;
}

.explain-panel ol {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.88rem;
  color: #334155;
  line-height: 1.7;
}

.tip {
  margin: 12px 0 0;
  font-size: 0.85rem;
  color: #64748b;
}

.empty-hint,
.graph-placeholder {
  padding: 12px;
  font-size: 0.85rem;
  color: #94a3b8;
}
</style>
