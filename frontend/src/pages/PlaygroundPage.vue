<script setup>
import { inject, ref, watch } from "vue";
import ChatRunner from "../components/ChatRunner.vue";
import BatchRunnerPanel from "../components/BatchRunnerPanel.vue";
import GraphViewer from "../components/GraphViewer.vue";
import MessageLogPanel from "../components/MessageLogPanel.vue";
import TraceViewer from "../components/TraceViewer.vue";
import { I18N_KEY } from "../i18n";
import { clusterStore, ensureAgentConfigs } from "../store/clusterStore";

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

const emit = defineEmits(["run", "clear", "stop", "batch-run", "select-workflow", "update-workflow", "edit-agent"]);
const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((key) => key);
const workflowTypeLabel = i18n?.workflowTypeLabel || ((type) => type);
const leftVisible = ref(true);
const rightVisible = ref(true);

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
      router_prompt: props.selectedWorkflow.router_prompt || "You are an orchestration router. Select the best specialist based on user intent.",
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
          <label class="field-label">{{ t("workflow.selectWorkflow") }}</label>
          <select
            class="workflow-native-select"
            :value="props.selectedWorkflowId"
            @change="$emit('select-workflow', $event.target.value)"
          >
            <option v-for="workflow in props.workflows" :key="workflow.id" :value="workflow.id">
              {{ workflow.name }} - {{ workflowTypeLabel(workflow.type) }}
            </option>
          </select>
        </section>

        <GraphViewer
          :graph="props.selectedGraph"
          :active-node-id="props.activeNodeId"
          :focus-node-id="props.focusNodeId"
          :trace="props.trace"
          :workflow="props.selectedWorkflow"
          :agents="props.agents"
          @select-node="handleNodeSelect"
          @dblclick-node="handleNodeDoubleClick"
          @update-chain="handleUpdateChain"
        />
      </aside>

      <section class="playground-col-center">
        <ChatRunner
          :selected-workflow-id="props.selectedWorkflowId"
          :selected-workflow="props.selectedWorkflow"
          :loading="props.loading"
          :left-visible="leftVisible"
          :right-visible="rightVisible"
          :messages="props.chatMessages"
          @run="$emit('run', $event)"
          @clear="$emit('clear')"
          @stop="$emit('stop')"
          @toggle-left="leftVisible = !leftVisible"
          @toggle-right="rightVisible = !rightVisible"
        />
      </section>

      <aside v-if="rightVisible" class="playground-col-right orchestration-right-col">
        <BatchRunnerPanel
          :selected-workflow-id="props.selectedWorkflowId"
          :batch-run-state="props.batchRunState"
          @batch-run="$emit('batch-run', $event)"
        />

        <MessageLogPanel />

        <TraceViewer :trace="props.trace" :playing="props.tracePlaying" />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.orchestration-right-col {
  display: grid;
  grid-template-rows: minmax(140px, 20%) minmax(200px, 36%) minmax(220px, 1fr);
  gap: 10px;
  min-height: 0;
}
</style>
