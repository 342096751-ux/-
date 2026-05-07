<script setup>
import {
  CheckCircle2,
  CirclePlus,
  Pencil,
  Plus,
  Minimize2,
  Maximize2,
  Search,
  Trash2,
  UserPlus,
  Workflow as WorkflowIcon,
} from "lucide-vue-next";
import { computed, inject, reactive, ref, watch } from "vue";
import { I18N_KEY } from "../i18n";
import { loadLayout, saveCurrentLayout } from "../store/clusterStore";

const props = defineProps({
  templates: {
    type: Array,
    required: true,
  },
  agents: {
    type: Array,
    required: true,
  },
  workflows: {
    type: Array,
    required: true,
  },
  selectedWorkflowId: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["create", "update", "delete", "select", "add-agent", "edit-agent"]);
const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((key) => key);
const workflowTypeLabel = i18n?.workflowTypeLabel || ((type) => type);
const workflowTypeDesc = i18n?.workflowTypeDesc || ((_type, fallback) => fallback || _type);
const managedWorkflowTypes = [
  "router_specialists",
  "planner_executor",
  "supervisor_dynamic",
  "peer_handoff",
  "ugc_moderation",
];

const isAdding = ref(false);
const editingWorkflowId = ref("");
const agentSearch = ref("");
const canvasRef = ref(null);
const canvasExpandedRef = ref(null);
const linkDraft = ref({ active: false, sourceId: "", x: 0, y: 0 });
const nodePicker = ref({ open: false, nodeId: "" });
const canvasExpanded = ref(false);
const graphCustomized = ref(false);
const form = reactive({
  name: "",
  type: "router_specialists",
  description: "",
  specialist_agent_ids: [],
  finalizer_enabled: true,
  router_prompt: "You are an orchestration router. Select the best specialist based on user intent.",
});
const editorGraph = reactive({
  nodes: [],
  edges: [],
});

const colorTokens = [
  "agent-theme-blue",
  "agent-theme-violet",
  "agent-theme-green",
  "agent-theme-orange",
  "agent-theme-rose",
  "agent-theme-indigo",
];

const requiredAgentCount = computed(() => {
  const found = props.templates.find((template) => template.type === form.type);
  return found?.required_agent_count ?? 2;
});

const workflowTypeOptions = computed(() =>
  props.templates.filter((template) => managedWorkflowTypes.includes(template.type)),
);

const visibleWorkflows = computed(() =>
  props.workflows.filter((workflow) => managedWorkflowTypes.includes(workflow.type)),
);

const filteredAgents = computed(() => {
  const q = String(agentSearch.value || "")
    .trim()
    .toLowerCase();
  if (!q) return props.agents;
  return props.agents.filter((a) => {
    const name = String(a.name || "").toLowerCase();
    const desc = String(a.description || "").toLowerCase();
    return name.includes(q) || desc.includes(q);
  });
});

const selectedAgentCount = computed(() => {
  const ids = new Set(
    editorGraph.nodes
      .map((node) => String(node?.agentId || "").trim())
      .filter(Boolean),
  );
  return ids.size;
});

const canSubmit = computed(() => Boolean(form.name.trim()) && selectedAgentCount.value >= requiredAgentCount.value);
const linkedPairs = computed(() =>
  editorGraph.edges.map((edge) => ({
    ...edge,
    sourceName: agentNameById(editorGraph.nodes.find((n) => n.id === edge.source)?.agentId || edge.source),
    targetName: agentNameById(editorGraph.nodes.find((n) => n.id === edge.target)?.agentId || edge.target),
  })),
);
const selectedAgents = computed(() => {
  const ids = new Set(editorGraph.nodes.map((n) => String(n.agentId || "").trim()).filter(Boolean));
  return [...ids].map((id) => ({
    id,
    name: agentNameById(id),
  }));
});

watch(
  () => form.type,
  (type, prev) => {
    if (!type || !prev || type === prev) return;
    if (graphCustomized.value) return;
    applyPresetGraphByType(type);
  },
);

function requestAddAgent() {
  emit("add-agent");
}

function requestEditAgent(agentId) {
  emit("edit-agent", agentId);
}

function resolveAgent(agentId) {
  const index = props.agents.findIndex((agent) => agent.id === agentId);
  const agent = props.agents.find((item) => item.id === agentId);
  return {
    name: agent?.name || agentId,
    theme: colorTokens[(index >= 0 ? index : 0) % colorTokens.length],
  };
}

function workflowDescription(workflow) {
  return workflowTypeDesc(workflow.type, "");
}

function workflowLinkPreview(workflow) {
  const stored = loadLayout(workflow?.id);
  const storedNodes = Array.isArray(stored?.nodes) ? stored.nodes : [];
  const storedEdges = Array.isArray(stored?.edges) ? stored.edges : [];
  if (storedNodes.length && storedEdges.length) {
    const nodeMap = new Map(storedNodes.map((n) => [n.id, n]));
    const previews = storedEdges
      .slice(0, 6)
      .map((edge) => {
        const s = nodeMap.get(edge.source);
        const t = nodeMap.get(edge.target);
        const from = agentNameById(s?.agentId || "");
        const to = agentNameById(t?.agentId || "");
        return from && to ? `${from} -> ${to}` : "";
      })
      .filter(Boolean);
    if (previews.length) return previews;
  }
  const ids = Array.isArray(workflow?.specialist_agent_ids) ? workflow.specialist_agent_ids : [];
  const linear = [];
  for (let i = 1; i < ids.length; i += 1) {
    linear.push(`${agentNameById(ids[i - 1])} -> ${agentNameById(ids[i])}`);
  }
  return linear.slice(0, 6);
}

function beginCreate() {
  editingWorkflowId.value = "";
  isAdding.value = true;
  form.name = "";
  form.type = "router_specialists";
  form.description = "";
  form.specialist_agent_ids = [];
  form.finalizer_enabled = true;
  form.router_prompt = "You are an orchestration router. Select the best specialist based on user intent.";
  graphCustomized.value = false;
  applyPresetGraphByType(form.type);
}

function beginEdit(workflow) {
  if (!managedWorkflowTypes.includes(workflow.type)) return;
  isAdding.value = false;
  editingWorkflowId.value = workflow.id;
  form.name = workflow.name || "";
  form.type = workflow.type || "router_specialists";
  form.description = workflowDescription(workflow);
  form.specialist_agent_ids = [...(workflow.specialist_agent_ids || [])];
  form.finalizer_enabled = Boolean(workflow.finalizer_enabled);
  form.router_prompt = workflow.router_prompt || "You are an orchestration router. Select the best specialist based on user intent.";
  loadEditorGraph(workflow);
}

function cancelForm() {
  isAdding.value = false;
  editingWorkflowId.value = "";
  form.name = "";
  form.type = "router_specialists";
  form.description = "";
  form.specialist_agent_ids = [];
  form.finalizer_enabled = true;
  form.router_prompt = "You are an orchestration router. Select the best specialist based on user intent.";
  graphCustomized.value = false;
  canvasExpanded.value = false;
  resetEditorGraph();
}

function removeWorkflow(workflowId) {
  emit("delete", workflowId);
  if (editingWorkflowId.value === workflowId) {
    cancelForm();
  }
}

async function submit() {
  if (!canSubmit.value) return;
  const sortedAgentIds = deriveOrderedAgentIds();
  const data = {
    name: form.name,
    type: form.type,
    specialist_agent_ids: sortedAgentIds,
    finalizer_enabled: form.finalizer_enabled,
    router_prompt: form.router_prompt,
  };
  if (editingWorkflowId.value) {
    await emit("update", {
      id: editingWorkflowId.value,
      data,
    });
    saveCurrentLayout(editingWorkflowId.value, {
      nodes: editorGraph.nodes,
      edges: editorGraph.edges,
    });
  } else {
    await emit("create", data);
  }
  cancelForm();
}

function resetEditorGraph() {
  applyPresetGraphByType(form.type);
}

function loadEditorGraph(workflow) {
  const stored = loadLayout(workflow.id);
  if (stored?.nodes?.length) {
    editorGraph.nodes = [...stored.nodes];
    editorGraph.edges = [...(stored.edges || [])];
    graphCustomized.value = true;
    return;
  }
  graphCustomized.value = false;
  applyPresetGraphByType(form.type, workflow?.specialist_agent_ids || []);
}

function addCanvasNode() {
  graphCustomized.value = true;
  const idx = editorGraph.nodes.length;
  editorGraph.nodes.push({
    id: `draft_${Date.now()}_${idx}`,
    agentId: "",
    x: 90 + (idx % 4) * 160,
    y: 100 + Math.floor(idx / 4) * 110,
  });
}

function openNodePicker(nodeId) {
  nodePicker.value = { open: true, nodeId };
}

function closeNodePicker() {
  nodePicker.value = { open: false, nodeId: "" };
}

function assignNodeAgent(agentId) {
  const node = editorGraph.nodes.find((n) => n.id === nodePicker.value.nodeId);
  if (node) {
    node.agentId = agentId;
    graphCustomized.value = true;
  }
  closeNodePicker();
}

function removeNode(nodeId) {
  graphCustomized.value = true;
  editorGraph.nodes = editorGraph.nodes.filter((n) => n.id !== nodeId);
  editorGraph.edges = editorGraph.edges.filter((e) => e.source !== nodeId && e.target !== nodeId);
}

function agentNameById(agentId) {
  return props.agents.find((a) => a.id === agentId)?.name || "双击选择模型";
}

function beginLink(event, nodeId) {
  event.preventDefault();
  event.stopPropagation();
  linkDraft.value = { active: true, sourceId: nodeId, x: 0, y: 0 };
}

function onCanvasMove(event) {
  if (!linkDraft.value.active) return;
  const activeCanvas = canvasExpanded.value ? canvasExpandedRef.value : canvasRef.value;
  const rect = activeCanvas?.getBoundingClientRect();
  if (!rect) return;
  linkDraft.value = {
    ...linkDraft.value,
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
}

function cancelLink() {
  linkDraft.value = { active: false, sourceId: "", x: 0, y: 0 };
}

function endLink(event, targetId) {
  event.preventDefault();
  event.stopPropagation();
  const sourceId = linkDraft.value.sourceId;
  if (!sourceId) return cancelLink();
  if (sourceId === targetId) {
    window.alert("不能连接自己");
    return cancelLink();
  }
  if (hasPath(targetId, sourceId)) {
    window.alert("不能形成闭环");
    return cancelLink();
  }
  const exists = editorGraph.edges.some((e) => e.source === sourceId && e.target === targetId);
  if (!exists) {
    editorGraph.edges.push({ source: sourceId, target: targetId });
    graphCustomized.value = true;
  }
  cancelLink();
}

function hasPath(fromId, toId) {
  const adj = new Map();
  editorGraph.edges.forEach((e) => {
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source).push(e.target);
  });
  const q = [fromId];
  const seen = new Set();
  while (q.length) {
    const cur = q.shift();
    if (cur === toId) return true;
    if (seen.has(cur)) continue;
    seen.add(cur);
    (adj.get(cur) || []).forEach((x) => q.push(x));
  }
  return false;
}

function removeEdge(edge) {
  graphCustomized.value = true;
  editorGraph.edges = editorGraph.edges.filter((e) => !(e.source === edge.source && e.target === edge.target));
}

function enterBigCanvas() {
  canvasExpanded.value = true;
}

function exitBigCanvas() {
  canvasExpanded.value = false;
}

function buildPresetGraph(type, sourceAgentIds = []) {
  const baseIds = sourceAgentIds.length
    ? sourceAgentIds
    : props.agents.slice(0, Math.max(2, requiredAgentCount.value)).map((a) => a.id);
  const useIds = baseIds.length ? baseIds : [""];
  const nodes = useIds.map((id, index) => ({
    id: `preset_${type}_${index}_${id || "draft"}`,
    agentId: id || "",
    x: 90 + (index % 3) * 180,
    y: 100 + Math.floor(index / 3) * 120,
  }));
  const edges = [];
  if (nodes.length <= 1) return { nodes, edges };

  if (type === "router_specialists") {
    for (let i = 1; i < nodes.length; i += 1) {
      edges.push({ source: nodes[0].id, target: nodes[i].id });
    }
  } else if (type === "supervisor_dynamic") {
    const mid = Math.floor(nodes.length / 2);
    for (let i = 0; i < nodes.length; i += 1) {
      if (i === mid) continue;
      edges.push({ source: nodes[mid].id, target: nodes[i].id });
    }
  } else if (type === "peer_handoff") {
    for (let i = 1; i < nodes.length; i += 1) {
      edges.push({ source: nodes[i - 1].id, target: nodes[i].id });
    }
  } else {
    for (let i = 1; i < nodes.length; i += 1) {
      edges.push({ source: nodes[i - 1].id, target: nodes[i].id });
    }
  }
  return { nodes, edges };
}

function applyPresetGraphByType(type, sourceAgentIds = []) {
  const preset = buildPresetGraph(type, sourceAgentIds);
  editorGraph.nodes = preset.nodes;
  editorGraph.edges = preset.edges;
}

function linePath(edge) {
  const s = editorGraph.nodes.find((n) => n.id === edge.source);
  const t = editorGraph.nodes.find((n) => n.id === edge.target);
  if (!s || !t) return "";
  const sx = s.x + 110;
  const sy = s.y + 24;
  const tx = t.x;
  const ty = t.y + 24;
  const c = Math.max(40, Math.abs(tx - sx) * 0.35);
  return `M ${sx} ${sy} C ${sx + c} ${sy}, ${tx - c} ${ty}, ${tx} ${ty}`;
}

function draftPath() {
  if (!linkDraft.value.active) return "";
  const s = editorGraph.nodes.find((n) => n.id === linkDraft.value.sourceId);
  if (!s) return "";
  const sx = s.x + 110;
  const sy = s.y + 24;
  const tx = linkDraft.value.x;
  const ty = linkDraft.value.y;
  const c = Math.max(40, Math.abs(tx - sx) * 0.35);
  return `M ${sx} ${sy} C ${sx + c} ${sy}, ${tx - c} ${ty}, ${tx} ${ty}`;
}

function deriveOrderedAgentIds() {
  const nodeIds = editorGraph.nodes.map((n) => n.id);
  const inCount = new Map(nodeIds.map((id) => [id, 0]));
  const next = new Map(nodeIds.map((id) => [id, []]));
  editorGraph.edges.forEach((e) => {
    inCount.set(e.target, Number(inCount.get(e.target) || 0) + 1);
    next.get(e.source)?.push(e.target);
  });
  const q = nodeIds.filter((id) => Number(inCount.get(id) || 0) === 0);
  const visited = [];
  while (q.length) {
    const id = q.shift();
    visited.push(id);
    (next.get(id) || []).forEach((nxt) => {
      inCount.set(nxt, Number(inCount.get(nxt) || 0) - 1);
      if (Number(inCount.get(nxt) || 0) === 0) q.push(nxt);
    });
  }
  return visited
    .map((id) => editorGraph.nodes.find((n) => n.id === id)?.agentId || "")
    .filter(Boolean);
}

function removeAgentFromCanvas(agentId) {
  const relatedNodeIds = editorGraph.nodes.filter((n) => n.agentId === agentId).map((n) => n.id);
  if (!relatedNodeIds.length) return;
  graphCustomized.value = true;
  editorGraph.nodes = editorGraph.nodes.filter((n) => n.agentId !== agentId);
  editorGraph.edges = editorGraph.edges.filter(
    (e) => !relatedNodeIds.includes(e.source) && !relatedNodeIds.includes(e.target),
  );
}
</script>

<template>
  <section class="page-stack">
    <div class="manager-topbar">
      <div>
        <h2>Workflows</h2>
        <p>{{ t("page.workflowsDesc") }}</p>
      </div>
      <button class="primary-button" @click="beginCreate">
        <Plus :size="16" />
        {{ t("workflow.new") }}
      </button>
    </div>

    <div class="workflow-list">
      <article v-if="isAdding || editingWorkflowId" class="glass-panel add-card add-card-violet workflow-form">
        <div class="workflow-form-grid">
          <div class="page-stack compact-gap">
            <h4>{{ editingWorkflowId ? "Edit Workflow" : "Basic Config" }}</h4>
            <input v-model="form.name" :placeholder="t('workflow.name')" />
            <select v-model="form.type" class="workflow-native-select">
              <option
                v-for="template in workflowTypeOptions"
                :key="template.type"
                :value="template.type"
              >
                {{ workflowTypeLabel(template.type) }}
              </option>
            </select>
            <textarea
              v-model="form.description"
              rows="4"
              placeholder="Collaboration logic description..."
            />
            <label class="check-row">
              <input v-model="form.finalizer_enabled" type="checkbox" />
              <span>{{ t("workflow.enableFinalizer") }}</span>
            </label>
            <label class="field-label" style="margin-bottom: 0;">结果输出内容/路由提示词</label>
            <textarea
              v-model="form.router_prompt"
              rows="6"
              placeholder="可在这里定义集群最终输出要求，例如：必须输出结论、风险等级、证据和建议。"
            />
            <p class="selection-footnote">
              保存后立即生效，运行时会按这个提示词组织最终输出内容。
            </p>
          </div>

          <div class="page-stack compact-gap workflow-agent-bind-column">
            <div class="workflow-bind-header">
              <h4>
                {{ t("workflow.bindAgents") }} ({{ selectedAgentCount }})
              </h4>
              <p class="selection-footnote workflow-bind-sub">
                {{ t("workflow.allAgentsSummary", { total: props.agents.length, shown: filteredAgents.length }) }}
              </p>
            </div>

            <div class="workflow-canvas-toolbar">
              <button type="button" class="workflow-add-agent-button" @click="addCanvasNode">
                <CirclePlus :size="16" />
                添加节点
              </button>
              <button type="button" class="workflow-add-agent-button" @click="enterBigCanvas">
                <Maximize2 :size="16" />
                大画布
              </button>
              <div class="workflow-search-wrap">
                <Search :size="16" class="workflow-search-icon" />
                <input
                  v-model="agentSearch"
                  type="search"
                  class="workflow-search-input"
                  :placeholder="t('workflow.searchAgents')"
                  autocomplete="off"
                />
              </div>
            </div>
            <div v-if="selectedAgents.length" class="workflow-chip-list">
              <span class="selection-footnote">已添加 Agent：</span>
              <button
                v-for="agent in selectedAgents"
                :key="`sel_${agent.id}`"
                type="button"
                class="workflow-agent-chip"
                @click="removeAgentFromCanvas(agent.id)"
              >
                {{ agent.name }}
                <Trash2 :size="11" />
              </button>
            </div>

            <div
              ref="canvasRef"
              class="workflow-editor-canvas"
              @mousemove="onCanvasMove"
              @click="cancelLink"
              @dblclick.self="enterBigCanvas"
            >
              <svg class="workflow-canvas-svg">
                <defs>
                  <marker id="wfArrow" viewBox="0 0 10 10" refX="7.8" refY="5" markerWidth="6.2" markerHeight="6.2" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
                  </marker>
                </defs>
                <path
                  v-for="edge in editorGraph.edges"
                  :key="`${edge.source}_${edge.target}`"
                  :d="linePath(edge)"
                  class="workflow-canvas-edge"
                  marker-end="url(#wfArrow)"
                  @dblclick.prevent.stop="removeEdge(edge)"
                />
                <path
                  v-if="linkDraft.active"
                  :d="draftPath()"
                  class="workflow-canvas-edge workflow-canvas-edge-draft"
                  marker-end="url(#wfArrow)"
                />
              </svg>

              <div
                v-for="node in editorGraph.nodes"
                :key="node.id"
                class="workflow-canvas-node"
                :style="{ left: `${node.x}px`, top: `${node.y}px` }"
                @dblclick.stop="openNodePicker(node.id)"
              >
                <button class="node-port node-port-in" type="button" @mouseup.stop="endLink($event, node.id)"></button>
                <div class="node-card-main">
                  <strong>{{ agentNameById(node.agentId) }}</strong>
                  <span v-if="node.agentId" class="node-agent-id">{{ node.agentId }}</span>
                  <span v-else class="node-agent-placeholder">双击选择模型</span>
                </div>
                <div class="node-card-actions">
                  <button type="button" class="workflow-agent-edit-btn" @click.stop="openNodePicker(node.id)">
                    <Pencil :size="12" />
                  </button>
                  <button type="button" class="workflow-agent-edit-btn workflow-icon-delete" @click.stop="removeNode(node.id)">
                    <Trash2 :size="12" />
                  </button>
                </div>
                <button class="node-port node-port-out" type="button" @mousedown.stop="beginLink($event, node.id)"></button>
              </div>
            </div>
            <p class="selection-footnote">
              双击节点可选择模型；从右侧端口拖到另一节点左侧端口即可连线。双击连线可删除。
            </p>
            <p class="selection-footnote">
              当前模式：{{ graphCustomized ? "自定义编排" : "跟随方案类型自动生成" }}
            </p>
            <div v-if="linkedPairs.length" class="workflow-linked-list">
              <div class="selection-footnote">已连接组件：</div>
              <button
                v-for="edge in linkedPairs"
                :key="`link_${edge.source}_${edge.target}`"
                type="button"
                class="workflow-linked-item"
                @click="removeEdge(edge)"
              >
                {{ edge.sourceName }} -> {{ edge.targetName }}
                <Trash2 :size="11" />
              </button>
            </div>
            <div class="inline-actions">
              <button class="accent-button accent-button-violet" :disabled="!canSubmit" @click="submit">
                {{ editingWorkflowId ? "Save Changes" : t("workflow.save") }}
              </button>
              <button class="ghost-button" @click="requestAddAgent">
                <UserPlus :size="14" />
                新建 Agent
              </button>
              <button class="ghost-button" @click="cancelForm">{{ t("workflow.cancel") }}</button>
            </div>
          </div>
        </div>
      </article>

      <article
        v-for="workflow in visibleWorkflows"
        :key="workflow.id"
        class="glass-panel workflow-card workflow-card-rich"
        :class="{ selected: workflow.id === props.selectedWorkflowId }"
        @click="emit('select', workflow.id)"
      >
        <div class="workflow-rich-head">
          <div class="workflow-rich-main">
            <div class="workflow-title-row">
              <h4>{{ workflow.name }}</h4>
              <span class="chip chip-dark">{{ workflowTypeLabel(workflow.type) }}</span>
            </div>
            <p class="workflow-id">workflow_{{ workflow.id }}</p>
            <p class="workflow-rich-desc">{{ workflowDescription(workflow) }}</p>

            <div class="workflow-agent-stack">
              <div class="avatar-stack">
                <div
                  v-for="(agentId, index) in workflow.specialist_agent_ids"
                  :key="agentId"
                  class="stack-avatar"
                  :class="resolveAgent(agentId).theme"
                  :style="{ zIndex: 10 - index }"
                >
                  {{ resolveAgent(agentId).name.charAt(0) }}
                </div>
              </div>
              <span class="workflow-agent-count">
                {{ workflow.specialist_agent_ids.length }} Agents involved
              </span>
            </div>
            <div v-if="workflowLinkPreview(workflow).length" class="workflow-link-preview">
              <span
                v-for="(link, idx) in workflowLinkPreview(workflow)"
                :key="`wf_link_${workflow.id}_${idx}`"
                class="workflow-link-pill"
              >
                {{ link }}
              </span>
            </div>
          </div>

          <div class="workflow-rich-mark" :class="{ selected: workflow.id === props.selectedWorkflowId }">
            <WorkflowIcon :size="24" />
          </div>
        </div>

        <div v-if="workflow.id === props.selectedWorkflowId" class="workflow-selected-foot">
          <span class="workflow-selected-note">
            <CheckCircle2 :size="12" />
            {{ t("workflow.selected") }}
          </span>
          <div class="inline-actions compact-workflow-actions">
            <button
              class="workflow-icon-action"
              type="button"
              title="Edit Workflow"
              @click.stop="beginEdit(workflow)"
            >
              <Pencil :size="14" />
            </button>
            <button
              class="workflow-icon-action workflow-icon-delete"
              type="button"
              title="Delete Workflow"
              @click.stop="removeWorkflow(workflow.id)"
            >
              <Trash2 :size="14" />
            </button>
          </div>
        </div>
      </article>
    </div>
  </section>

  <div v-if="nodePicker.open" class="agent-modal-overlay" @click="closeNodePicker">
    <section class="agent-modal-panel node-picker-panel" @click.stop>
      <header class="agent-modal-header">
        <h3>选择要加入的模型</h3>
      </header>
      <div class="agent-modal-body">
        <p v-if="!filteredAgents.length" class="workflow-agent-empty">{{ t("workflow.noSearchResults") }}</p>
        <button
          v-for="agent in filteredAgents"
          :key="`pick_${agent.id}`"
          type="button"
          class="node-picker-item"
          @click="assignNodeAgent(agent.id)"
        >
          <span class="mini-dot" :class="resolveAgent(agent.id).theme"></span>
          <span>{{ agent.name }}</span>
          <small>{{ agent.description || agent.id }}</small>
        </button>
      </div>
      <footer class="agent-modal-footer">
        <button type="button" class="agent-modal-cancel" @click="closeNodePicker">关闭</button>
      </footer>
    </section>
  </div>

  <div v-if="canvasExpanded" class="agent-modal-overlay" @click="exitBigCanvas">
    <section class="agent-modal-panel canvas-expanded-panel" @click.stop>
      <header class="agent-modal-header">
        <h3>大画布编排编辑器</h3>
        <button type="button" class="agent-modal-close" @click="exitBigCanvas">
          <Minimize2 :size="16" />
        </button>
      </header>
      <div class="canvas-expanded-body">
        <div class="workflow-canvas-toolbar">
          <button type="button" class="workflow-add-agent-button" @click="addCanvasNode">
            <CirclePlus :size="16" />
            添加节点
          </button>
          <div class="workflow-search-wrap">
            <Search :size="16" class="workflow-search-icon" />
            <input
              v-model="agentSearch"
              type="search"
              class="workflow-search-input"
              :placeholder="t('workflow.searchAgents')"
              autocomplete="off"
            />
          </div>
        </div>
        <div ref="canvasExpandedRef" class="workflow-editor-canvas workflow-editor-canvas-xl" @mousemove="onCanvasMove" @click="cancelLink">
          <svg class="workflow-canvas-svg">
            <defs>
              <marker id="wfArrowXL" viewBox="0 0 10 10" refX="7.8" refY="5" markerWidth="6.2" markerHeight="6.2" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
              </marker>
            </defs>
            <path
              v-for="edge in editorGraph.edges"
              :key="`xl_${edge.source}_${edge.target}`"
              :d="linePath(edge)"
              class="workflow-canvas-edge"
              marker-end="url(#wfArrowXL)"
              @dblclick.prevent.stop="removeEdge(edge)"
            />
            <path
              v-if="linkDraft.active"
              :d="draftPath()"
              class="workflow-canvas-edge workflow-canvas-edge-draft"
              marker-end="url(#wfArrowXL)"
            />
          </svg>
          <div
            v-for="node in editorGraph.nodes"
            :key="`xl_${node.id}`"
            class="workflow-canvas-node"
            :style="{ left: `${node.x}px`, top: `${node.y}px` }"
            @dblclick.stop="openNodePicker(node.id)"
          >
            <button class="node-port node-port-in" type="button" @mouseup.stop="endLink($event, node.id)"></button>
            <div class="node-card-main">
              <strong>{{ agentNameById(node.agentId) }}</strong>
              <span v-if="node.agentId" class="node-agent-id">{{ node.agentId }}</span>
              <span v-else class="node-agent-placeholder">双击选择模型</span>
            </div>
            <div class="node-card-actions">
              <button type="button" class="workflow-agent-edit-btn" @click.stop="openNodePicker(node.id)">
                <Pencil :size="12" />
              </button>
              <button type="button" class="workflow-agent-edit-btn workflow-icon-delete" @click.stop="removeNode(node.id)">
                <Trash2 :size="12" />
              </button>
            </div>
            <button class="node-port node-port-out" type="button" @mousedown.stop="beginLink($event, node.id)"></button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.workflow-canvas-toolbar {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: center;
}

.workflow-editor-canvas {
  position: relative;
  min-height: 420px;
  border: 1px solid #d8e0ef;
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfdff, #f6f9ff);
  overflow: hidden;
}

.workflow-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.workflow-agent-chip {
  border: 1px solid #d8e0ef;
  background: #ffffff;
  color: #334155;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.workflow-linked-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.workflow-linked-item {
  border: 1px solid #dbe3f2;
  background: #f8fafc;
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 11px;
  color: #475569;
  display: inline-flex;
  gap: 4px;
  align-items: center;
  cursor: pointer;
}

.workflow-link-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.workflow-link-pill {
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
  color: #475569;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
}

.workflow-canvas-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: auto;
}

.workflow-canvas-edge {
  fill: none;
  stroke: #64748b;
  stroke-width: 2;
  stroke-dasharray: 4 3;
  cursor: pointer;
}

.workflow-canvas-edge-draft {
  stroke: #3b82f6;
}

.workflow-canvas-node {
  position: absolute;
  width: 110px;
  height: 48px;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px;
  box-shadow: 0 6px 14px rgba(30, 41, 59, 0.08);
}

.node-card-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.node-card-main strong {
  font-size: 11px;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-agent-id,
.node-agent-placeholder {
  font-size: 10px;
  color: #64748b;
}

.node-card-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-port {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 1px solid #93c5fd;
  background: #eff6ff;
  cursor: crosshair;
}

.node-port-in {
  left: -6px;
  top: 50%;
  transform: translateY(-50%);
}

.node-port-out {
  right: -6px;
  top: 50%;
  transform: translateY(-50%);
}

.node-picker-panel {
  width: min(560px, 92vw);
}

.canvas-expanded-panel {
  width: min(1280px, 96vw);
  max-height: 92vh;
  overflow: hidden;
}

.canvas-expanded-body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.workflow-editor-canvas-xl {
  min-height: 72vh;
}

.node-picker-item {
  width: 100%;
  border: 1px solid #dbe3f2;
  border-radius: 10px;
  background: #fff;
  text-align: left;
  padding: 10px;
  margin-bottom: 8px;
  display: grid;
  grid-template-columns: 10px 1fr;
  column-gap: 8px;
  row-gap: 4px;
  align-items: center;
}

.node-picker-item small {
  grid-column: 2;
  color: #64748b;
}
</style>
