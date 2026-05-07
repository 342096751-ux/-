<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { Bot, BrainCircuit, Download, Network, Upload, Zap } from "lucide-vue-next";
import { I18N_KEY } from "../i18n";

const props = defineProps({
  graph: {
    type: Object,
    default: null,
  },
  activeNodeId: {
    type: String,
    default: "",
  },
  focusNodeId: {
    type: String,
    default: "",
  },
  trace: {
    type: Array,
    default: () => [],
  },
  workflow: {
    type: Object,
    default: null,
  },
  /** 覆盖默认标题，例如 UGC 审核流程 */
  graphTitle: {
    type: String,
    default: "",
  },
  /** false 时隐藏保存/加载编排（固定管线） */
  allowLayoutIO: {
    type: Boolean,
    default: true,
  },
  agents: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["select-node", "dblclick-node", "update-chain", "update-graph"]);
const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((key) => key);

const canvasRef = ref(null);
const canvasSize = ref({ width: 0, height: 0 });
const hoveredNodeId = ref("");
const dragState = reactive({
  active: false,
  nodeId: "",
  startX: 0,
  startY: 0,
  offsetX: 0,
  offsetY: 0,
});
const nodeOffsets = ref({});
const linking = reactive({
  active: false,
  sourceId: "",
  x: 0,
  y: 0,
});
const fileInputRef = ref(null);
const chainAgentIds = computed(() =>
  Array.isArray(props.workflow?.specialist_agent_ids)
    ? [...props.workflow.specialist_agent_ids]
    : (props.graph?.nodes || []).filter((n) => n.kind === "agent").map((n) => n.id),
);

const effectiveGraph = computed(() => {
  const rawNodes = Array.isArray(props.graph?.nodes) ? props.graph.nodes : [];
  const rawEdges = Array.isArray(props.graph?.edges) ? props.graph.edges : [];
  /** 固定管线（如 UGC）：图节点 id 为 intent/audit_* 等，与 specialist_agent_ids（真实 Agent UUID）不一致，不能按串联表过滤，否则工作单元节点会被丢光。 */
  if (props.allowLayoutIO === false) {
    return { nodes: rawNodes, edges: rawEdges };
  }
  const order = chainAgentIds.value;
  if (!order.length) return { nodes: rawNodes, edges: rawEdges };

  const agentById = new Map(rawNodes.filter((n) => n.kind === "agent").map((n) => [n.id, n]));
  const orderedAgents = order.map((id) => agentById.get(id)).filter(Boolean);
  const nonAgents = rawNodes.filter((n) => n.kind !== "agent");
  const nodes = [...nonAgents, ...orderedAgents];
  const nodeIdSet = new Set(nodes.map((n) => n.id));
  const edges = rawEdges.filter((e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target));
  return { nodes, edges };
});

const availableAgentOptions = computed(() =>
  (props.agents || []).map((a) => ({ id: a.id, name: a.name || a.id })),
);

let resizeObserver = null;

function refreshCanvasSize() {
  if (!canvasRef.value) return;
  const rect = canvasRef.value.getBoundingClientRect();
  canvasSize.value = {
    width: rect.width,
    height: rect.height,
  };
}

function byId(nodes) {
  const map = new Map();
  nodes.forEach((node) => map.set(node.id, node));
  return map;
}

function placeNode(result, map, nodeId, x, y) {
  const node = map.get(nodeId);
  if (!node) return;
  result.push({ ...node, x, y });
}

function placeRow(result, nodes, y, from, to) {
  if (!nodes.length) return;
  nodes.forEach((node, index) => {
    const x = nodes.length === 1 ? (from + to) / 2 : from + ((to - from) * index) / (nodes.length - 1);
    result.push({ ...node, x, y });
  });
}

function layoutRouter(nodes, width, height) {
  const map = byId(nodes);
  const result = [];
  placeNode(result, map, "start", width * 0.5, height * 0.1);
  placeNode(result, map, "router", width * 0.5, height * 0.3);
  placeRow(
    result,
    nodes.filter((node) => node.kind === "agent"),
    height * 0.56,
    width * 0.16,
    width * 0.84,
  );
  placeNode(result, map, "finalize", width * 0.5, height * 0.8);
  placeNode(result, map, "end", width * 0.5, height * 0.92);
  return result;
}

function layoutPlanner(nodes, width, height) {
  const map = byId(nodes);
  const result = [];
  placeNode(result, map, "start", width * 0.5, height * 0.08);
  placeNode(result, map, "planner_core", width * 0.5, height * 0.24);
  placeNode(result, map, "planner_validator", width * 0.5, height * 0.4);
  placeNode(result, map, "task_dispatcher", width * 0.5, height * 0.56);
  placeRow(
    result,
    nodes.filter((node) => node.kind === "agent"),
    height * 0.74,
    width * 0.14,
    width * 0.86,
  );
  placeNode(result, map, "synthesizer", width * 0.5, height * 0.87);
  placeNode(result, map, "end", width * 0.5, height * 0.95);
  return result;
}

function layoutSupervisor(nodes, width, height) {
  const map = byId(nodes);
  const result = [];
  placeNode(result, map, "start", width * 0.5, height * 0.08);
  placeNode(result, map, "supervisor_intake", width * 0.5, height * 0.24);
  placeNode(result, map, "delegation_policy", width * 0.3, height * 0.42);
  placeNode(result, map, "supervisor_review", width * 0.7, height * 0.42);
  placeRow(
    result,
    nodes.filter((node) => node.kind === "agent"),
    height * 0.68,
    width * 0.14,
    width * 0.86,
  );
  placeNode(result, map, "finalize", width * 0.5, height * 0.86);
  placeNode(result, map, "end", width * 0.5, height * 0.95);
  return result;
}

function layoutPeerHandoff(nodes, width, height) {
  const map = byId(nodes);
  const result = [];
  const groupNode = map.get("peer_pool");
  const finalNode = map.get("finalize");
  const endNode = map.get("end");
  const agents = nodes.filter((node) => node.kind === "agent");

  placeNode(result, map, "start", width * 0.5, height * 0.08);
  placeNode(result, map, "first_owner_router", width * 0.5, height * 0.23);

  const groupWidth = Math.min(width * 0.74, Math.max(340, width * 0.68));
  const groupHeight = Math.min(height * 0.5, Math.max(210, height * 0.42));
  if (groupNode) {
    result.push({
      ...groupNode,
      x: width * 0.5,
      y: height * (finalNode ? 0.54 : 0.6),
      boxWidth: groupWidth,
      boxHeight: groupHeight,
    });
  }

  if (agents.length) {
    const columns = Math.min(3, agents.length);
    const rows = Math.ceil(agents.length / columns);
    const innerLeft = width * 0.5 - groupWidth / 2 + 82;
    const innerRight = width * 0.5 + groupWidth / 2 - 82;
    const innerTop = (groupNode ? height * (finalNode ? 0.54 : 0.6) : height * 0.58) - groupHeight / 2 + 74;
    const innerBottom = (groupNode ? height * (finalNode ? 0.54 : 0.6) : height * 0.58) + groupHeight / 2 - 58;

    agents.forEach((node, index) => {
      const column = columns === 1 ? 0 : index % columns;
      const row = Math.floor(index / columns);
      const x = columns === 1 ? width * 0.5 : innerLeft + ((innerRight - innerLeft) * column) / (columns - 1);
      const y = rows === 1 ? (innerTop + innerBottom) / 2 : innerTop + ((innerBottom - innerTop) * row) / (rows - 1);
      result.push({ ...node, x, y });
    });
  }

  if (finalNode) placeNode(result, map, "finalize", width * 0.5, height * 0.86);
  if (endNode) placeNode(result, map, "end", width * 0.5, height * 0.95);
  return result;
}

/** UGC：开始 → 意图 → N 个 audit_* 工作单元 → 验证 → 仲裁 → 结束 */
function layoutUgcDynamic(nodes, width, height) {
  const map = byId(nodes);
  const result = [];
  const w = width;
  const h = height;
  const workUnitIds = nodes
    .filter((n) => n && typeof n.id === "string" && n.id.startsWith("audit_") && n.kind === "agent")
    .map((n) => n.id);
  const nUnits = workUnitIds.length;
  placeNode(result, map, "start", w * 0.5, h * 0.06);
  placeNode(result, map, "intent_analyst", w * 0.5, h * 0.2);
  if (nUnits) {
    workUnitIds.forEach((id, index) => {
      const x = nUnits === 1 ? w * 0.5 : w * (0.08 + (0.84 * index) / (nUnits - 1));
      placeNode(result, map, id, x, h * 0.42);
    });
  }
  placeNode(result, map, "verifier", w * 0.5, h * 0.6);
  placeNode(result, map, "arbiter", w * 0.5, h * 0.78);
  placeNode(result, map, "end", w * 0.5, h * 0.93);
  return result;
}

function layoutFallback(nodes, width, height) {
  const startNode = nodes.find((node) => node.kind === "start");
  const endNode = nodes.find((node) => node.kind === "end");
  const finalNode = nodes.find((node) => node.kind === "final");
  const logicNodes = nodes.filter((node) => node.kind === "logic");
  const agentNodes = nodes.filter((node) => node.kind === "agent");
  const result = [];

  if (startNode) result.push({ ...startNode, x: width / 2, y: height * 0.1 });
  if (logicNodes.length) {
    logicNodes.forEach((node, index) => {
      const x = logicNodes.length === 1
        ? width / 2
        : width * (0.24 + (0.52 * index) / (logicNodes.length - 1));
      result.push({ ...node, x, y: height * 0.28 });
    });
  }
  if (agentNodes.length) {
    agentNodes.forEach((node, index) => {
      const x = agentNodes.length === 1
        ? width / 2
        : width * (0.14 + (0.72 * index) / (agentNodes.length - 1));
      result.push({ ...node, x, y: height * 0.56 });
    });
  }
  if (finalNode) result.push({ ...finalNode, x: width / 2, y: height * 0.79 });
  if (endNode) result.push({ ...endNode, x: width / 2, y: height * 0.92 });
  return result;
}

const baseNodes = computed(() => {
  if (!effectiveGraph.value?.nodes?.length) return [];
  const width = canvasSize.value.width || 560;
  const height = canvasSize.value.height || 420;
  const nodes = effectiveGraph.value.nodes;
  const nodeIds = new Set(nodes.map((node) => node.id));

  if (nodeIds.has("planner_core")) return layoutPlanner(nodes, width, height);
  if (nodeIds.has("supervisor_intake")) return layoutSupervisor(nodes, width, height);
  if (nodeIds.has("peer_pool")) return layoutPeerHandoff(nodes, width, height);
  if (nodeIds.has("router")) return layoutRouter(nodes, width, height);
  if (nodeIds.has("intent_analyst") && nodeIds.has("verifier") && nodeIds.has("arbiter")) {
    const wu = nodes.filter(
      (n) => n && typeof n.id === "string" && n.id.startsWith("audit_") && n.kind === "agent",
    );
    if (wu.length > 0) {
      return layoutUgcDynamic(nodes, width, height);
    }
  }
  return layoutFallback(nodes, width, height);
});

const graphNodes = computed(() =>
  baseNodes.value.map((node) => {
    const offset = nodeOffsets.value[node.id] || { x: 0, y: 0 };
    return {
      ...node,
      x: node.x + offset.x,
      y: node.y + offset.y,
    };
  }),
);

const nodeMap = computed(() => {
  const map = new Map();
  graphNodes.value.forEach((node) => map.set(node.id, node));
  return map;
});

const traversedEdgeKeys = computed(() => {
  const keys = new Set();
  let lastEnteredNode = "";
  props.trace.forEach((event) => {
    const from = event?.payload?.node_id || "";
    const to = event?.payload?.next_node_id || "";
    if (from && to) {
      keys.add(`${from}->${to}`);
    }

    if (event?.type === "node_entered" && from) {
      if (lastEnteredNode && lastEnteredNode !== from) {
        keys.add(`${lastEnteredNode}->${from}`);
      }
      lastEnteredNode = from;
    }
  });
  return keys;
});

const staticEdgeKeys = computed(() => {
  const keys = new Set();
  (effectiveGraph.value?.edges || []).forEach((edge) => {
    if (edge?.source && edge?.target) {
      keys.add(`${edge.source}->${edge.target}`);
    }
  });
  return keys;
});

function parentGroupId(nodeId) {
  const node = nodeMap.value.get(nodeId);
  return node?.parent_id || "";
}

function normalizeEdgeEndpoints(sourceId, targetId) {
  let source = sourceId;
  let target = targetId;
  const sourceGroup = parentGroupId(sourceId);
  const targetGroup = parentGroupId(targetId);

  if (sourceGroup && (!targetGroup || targetGroup !== sourceGroup)) {
    source = sourceGroup;
  }
  if (targetGroup && (!sourceGroup || sourceGroup !== targetGroup)) {
    target = targetGroup;
  }

  return { source, target };
}

function boundaryPoint(node, otherNode) {
  const dx = otherNode.x - node.x;
  const dy = otherNode.y - node.y;

  if (node.kind === "group") {
    const halfWidth = (node.boxWidth || 320) / 2;
    const halfHeight = (node.boxHeight || 220) / 2;
    if (!dx && !dy) return { x: node.x, y: node.y };
    const scaleX = dx === 0 ? Number.POSITIVE_INFINITY : halfWidth / Math.abs(dx);
    const scaleY = dy === 0 ? Number.POSITIVE_INFINITY : halfHeight / Math.abs(dy);
    const scale = Math.min(scaleX, scaleY);
    return {
      x: node.x + dx * scale,
      y: node.y + dy * scale,
    };
  }

  const hasCap = Boolean(node.caption) && node.kind !== "group";
  const radius = hasCap ? 32 : 26;
  const distance = Math.max(1, Math.hypot(dx, dy));
  return {
    x: node.x + (dx / distance) * radius,
    y: node.y + (dy / distance) * radius,
  };
}

function connectionPath(fromNode, toNode) {
  const dx = toNode.x - fromNode.x;
  const dy = toNode.y - fromNode.y;
  const startPoint = boundaryPoint(fromNode, toNode);
  const endPoint = boundaryPoint(toNode, fromNode);
  const startX = startPoint.x;
  const startY = startPoint.y;
  const endX = endPoint.x;
  const endY = endPoint.y;

  const verticalCurve = Math.abs(dy) >= Math.abs(dx)
    ? Math.max(24, Math.abs(dy) * 0.4)
    : 0;
  const horizontalCurve = Math.abs(dx) > Math.abs(dy)
    ? Math.max(24, Math.abs(dx) * 0.22)
    : 0;

  const cp1x = startX + horizontalCurve * Math.sign(dx || 1);
  const cp1y = startY + verticalCurve * Math.sign(dy || 1);
  const cp2x = endX - horizontalCurve * Math.sign(dx || 1);
  const cp2y = endY - verticalCurve * Math.sign(dy || 1);

  return `M ${startX} ${startY} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${endX} ${endY}`;
}

const graphEdges = computed(() => {
  const deduped = new Map();

  function upsertEdge(sourceId, targetId, active, dynamic) {
    const normalized = normalizeEdgeEndpoints(sourceId, targetId);
    const fromNode = nodeMap.value.get(normalized.source);
    const toNode = nodeMap.value.get(normalized.target);
    if (!fromNode || !toNode) return;
    const key = `${normalized.source}->${normalized.target}`;
    const internal = !!(
      fromNode.parent_id &&
      toNode.parent_id &&
      fromNode.parent_id === toNode.parent_id
    );
    const existing = deduped.get(key);
    deduped.set(key, {
      key,
      d: connectionPath(fromNode, toNode),
      active: active || existing?.active || false,
      dynamic: dynamic || existing?.dynamic || false,
      internal,
    });
  }

  (effectiveGraph.value?.edges || []).forEach((edge) => {
    upsertEdge(edge.source, edge.target, traversedEdgeKeys.value.has(`${edge.source}->${edge.target}`), false);
  });

  traversedEdgeKeys.value.forEach((key) => {
    if (staticEdgeKeys.value.has(key)) return;
    const [source, target] = key.split("->");
    upsertEdge(source, target, true, true);
  });

  const edges = [...deduped.values()];
  return {
    base: edges.filter((edge) => !edge.internal),
    overlay: edges.filter((edge) => edge.internal),
  };
});

function nodeIcon(kind) {
  if (kind === "logic") return BrainCircuit;
  if (kind === "agent") return Bot;
  if (kind === "final") return Zap;
  return null;
}

function nodeVisited(nodeId) {
  if (!props.trace.length) return false;
  const node = nodeMap.value.get(nodeId);
  if (node?.kind === "group") {
    return graphNodes.value.some((item) => item.parent_id === nodeId && nodeVisited(item.id));
  }
  return props.trace.some((event) => event?.payload?.node_id === nodeId || event?.payload?.next_node_id === nodeId);
}

function nodeCurrent(nodeId) {
  const node = nodeMap.value.get(nodeId);
  if (node?.kind === "group") {
    return graphNodes.value.some((item) => item.parent_id === nodeId && nodeCurrent(item.id));
  }
  return props.activeNodeId === nodeId || (!props.activeNodeId && props.focusNodeId === nodeId);
}

function nodeStyle(node) {
  const isCaption = Boolean(node.caption) && node.kind !== "group";
  const width = node.kind === "group" ? node.boxWidth || 320 : isCaption ? 80 : 42;
  const height = node.kind === "group" ? node.boxHeight || 220 : isCaption ? 56 : 42;
  return {
    left: `${node.x}px`,
    top: `${node.y}px`,
    width: `${width}px`,
    height: `${height}px`,
    marginLeft: `-${width / 2}px`,
    marginTop: `-${height / 2}px`,
  };
}

function resetOffsets() {
  nodeOffsets.value = {};
}

watch(
  () => props.graph?.nodes?.map((node) => node.id).join("|") || "",
  () => resetOffsets(),
);

function onPointerMove(event) {
  if (!dragState.active || !dragState.nodeId) return;
  const rect = canvasRef.value?.getBoundingClientRect();
  if (!rect) return;
  const localX = event.clientX - rect.left;
  const localY = event.clientY - rect.top;
  const deltaX = localX - dragState.startX;
  const deltaY = localY - dragState.startY;
  nodeOffsets.value = {
    ...nodeOffsets.value,
    [dragState.nodeId]: {
      x: dragState.offsetX + deltaX,
      y: dragState.offsetY + deltaY,
    },
  };
}

function onPointerUp() {
  dragState.active = false;
  dragState.nodeId = "";
}

function emitChain(nextIds) {
  emit("update-chain", nextIds.filter(Boolean));
}

function updateChainAgent(index, nextAgentId) {
  const next = [...chainAgentIds.value];
  next[index] = nextAgentId;
  emitChain(next);
}

function moveChain(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= chainAgentIds.value.length) return;
  const next = [...chainAgentIds.value];
  const [item] = next.splice(index, 1);
  next.splice(target, 0, item);
  emitChain(next);
}

function onNodeClick(node) {
  if (node.kind === "agent") emit("select-node", node.id);
}

function onNodeDoubleClick(node) {
  if (node.kind === "agent") emit("dblclick-node", node.id);
}

function onNodePointerDown(event, node) {
  if (node.kind === "group") return;
  event.preventDefault();
  const rect = canvasRef.value?.getBoundingClientRect();
  if (!rect) return;
  const offset = nodeOffsets.value[node.id] || { x: 0, y: 0 };
  dragState.active = true;
  dragState.nodeId = node.id;
  dragState.startX = event.clientX - rect.left;
  dragState.startY = event.clientY - rect.top;
  dragState.offsetX = offset.x;
  dragState.offsetY = offset.y;
}

function graphWithEdges(nextEdges) {
  return {
    ...(props.graph || {}),
    nodes: Array.isArray(props.graph?.nodes) ? [...props.graph.nodes] : [],
    edges: nextEdges,
  };
}

function wouldCreateCycle(sourceId, targetId) {
  const adjacency = new Map();
  (props.graph?.edges || []).forEach((edge) => {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
    adjacency.get(edge.source).push(edge.target);
  });
  if (!adjacency.has(sourceId)) adjacency.set(sourceId, []);
  adjacency.get(sourceId).push(targetId);

  const stack = [targetId];
  const seen = new Set();
  while (stack.length) {
    const id = stack.pop();
    if (id === sourceId) return true;
    if (seen.has(id)) continue;
    seen.add(id);
    const next = adjacency.get(id) || [];
    next.forEach((x) => stack.push(x));
  }
  return false;
}

function beginLink(event, node) {
  event.stopPropagation();
  event.preventDefault();
  if (node.kind === "group") return;
  linking.active = true;
  linking.sourceId = node.id;
}

function completeLink(event, node) {
  event.stopPropagation();
  event.preventDefault();
  if (!linking.active || !linking.sourceId) return;
  if (!node?.id) return;
  if (linking.sourceId === node.id) {
    window.alert("不能连接自己");
    linking.active = false;
    linking.sourceId = "";
    return;
  }
  if (wouldCreateCycle(linking.sourceId, node.id)) {
    window.alert("不能形成闭环");
    linking.active = false;
    linking.sourceId = "";
    return;
  }
  const exists = (props.graph?.edges || []).some((e) => e.source === linking.sourceId && e.target === node.id);
  if (!exists) {
    const nextEdges = [
      ...(props.graph?.edges || []),
      {
        source: linking.sourceId,
        target: node.id,
      },
    ];
    emit("update-graph", graphWithEdges(nextEdges));
  }
  linking.active = false;
  linking.sourceId = "";
}

function cancelLinking() {
  linking.active = false;
  linking.sourceId = "";
}

function removeEdge(edgeKey) {
  const nextEdges = (props.graph?.edges || []).filter((e) => `${e.source}->${e.target}` !== edgeKey);
  emit("update-graph", graphWithEdges(nextEdges));
}

function onCanvasPointerMove(event) {
  if (!linking.active) return;
  const rect = canvasRef.value?.getBoundingClientRect();
  if (!rect) return;
  linking.x = event.clientX - rect.left;
  linking.y = event.clientY - rect.top;
}

function exportLayout() {
  const payload = JSON.stringify(props.graph || {}, null, 2);
  const blob = new Blob([payload], { type: "application/json;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "custom-layout.json";
  a.click();
  URL.revokeObjectURL(url);
}

function triggerImportLayout() {
  fileInputRef.value?.click();
}

function onImportLayout(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(String(reader.result || "{}"));
      if (!parsed || typeof parsed !== "object" || !Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
        window.alert("编排文件格式不正确");
        return;
      }
      emit("update-graph", parsed);
    } catch {
      window.alert("编排文件解析失败");
    }
  };
  reader.readAsText(file, "utf-8");
  event.target.value = "";
}

onMounted(() => {
  refreshCanvasSize();
  if (canvasRef.value) {
    resizeObserver = new ResizeObserver(() => refreshCanvasSize());
    resizeObserver.observe(canvasRef.value);
  }
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointermove", onCanvasPointerMove);
  window.addEventListener("pointerup", onPointerUp);
});

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect();
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointermove", onCanvasPointerMove);
  window.removeEventListener("pointerup", onPointerUp);
});
</script>

<template>
  <section class="glass-panel graph-shell">
    <header class="run-panel-header">
      <h3 class="run-panel-title">
        <Network :size="18" class="text-blue-500" />
        {{ graphTitle || t("graph.title") }}
      </h3>
      <div v-if="allowLayoutIO" class="graph-actions">
        <button class="graph-action-btn" type="button" title="保存编排" @click="exportLayout">
          <Download :size="12" />
          保存编排
        </button>
        <button class="graph-action-btn" type="button" title="加载编排" @click="triggerImportLayout">
          <Upload :size="12" />
          加载编排
        </button>
        <input ref="fileInputRef" type="file" accept=".json" class="graph-file-input" @change="onImportLayout" />
        <span class="panel-tag">Visual</span>
      </div>
      <span v-else class="panel-tag graph-fixed-tag">{{ t("graph.fixedPipeline") }}</span>
    </header>

    <section v-if="allowLayoutIO && chainAgentIds.length" class="chain-editor">
      <div class="chain-title">串联顺序（可调整）</div>
      <div class="chain-list">
        <div v-for="(agentId, index) in chainAgentIds" :key="`${agentId}_${index}`" class="chain-item">
          <span class="chain-index">{{ index + 1 }}</span>
          <select class="chain-select" :value="agentId" @change="updateChainAgent(index, $event.target.value)">
            <option v-for="opt in availableAgentOptions" :key="opt.id" :value="opt.id">{{ opt.name }}</option>
          </select>
          <button class="chain-btn" type="button" @click="moveChain(index, -1)">↑</button>
          <button class="chain-btn" type="button" @click="moveChain(index, 1)">↓</button>
        </div>
      </div>
      <p class="chain-hint">双击画布里的 Agent 节点可直接进入编辑页。</p>
    </section>

    <div ref="canvasRef" class="graph-canvas-wrap" @dblclick.self="cancelLinking">
      <div v-if="!graph" class="trace-empty">{{ t("graph.empty") }}</div>
      <template v-else>
        <svg
          class="graph-svg graph-svg-base"
          :viewBox="`0 0 ${canvasSize.width || 560} ${canvasSize.height || 420}`"
          preserveAspectRatio="none"
        >
          <defs>
            <marker id="graphArrowBase" viewBox="0 0 10 10" refX="7.8" refY="5" markerWidth="6.2" markerHeight="6.2" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#cbd5e1" />
            </marker>
            <marker id="graphArrowActive" viewBox="0 0 10 10" refX="7.8" refY="5" markerWidth="6.2" markerHeight="6.2" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
            </marker>
          </defs>

          <path
            v-for="edge in graphEdges.base"
            :key="`base_${edge.key}`"
            :d="edge.d"
            fill="none"
            stroke="#cbd5e1"
            stroke-width="2"
            stroke-dasharray="4 4"
            marker-end="url(#graphArrowBase)"
            @dblclick.prevent.stop="removeEdge(edge.key)"
          />
          <path
            v-for="edge in graphEdges.base.filter((item) => item.active)"
            :key="`active_${edge.key}`"
            :d="edge.d"
            fill="none"
            stroke="#3b82f6"
            stroke-width="2.8"
            marker-end="url(#graphArrowActive)"
            @dblclick.prevent.stop="removeEdge(edge.key)"
          />
          <path
            v-if="linking.active && nodeMap.get(linking.sourceId)"
            :d="connectionPath(nodeMap.get(linking.sourceId), { x: linking.x, y: linking.y, kind: 'temp' })"
            fill="none"
            stroke="#60a5fa"
            stroke-width="2"
            stroke-dasharray="5 4"
          />
        </svg>

        <div
          v-for="node in graphNodes"
          :key="node.id"
          class="graph-node"
          :class="[
            `kind-${node.kind}`,
            {
              visited: nodeVisited(node.id),
              active: nodeCurrent(node.id),
              'with-caption': Boolean(node.caption) && node.kind !== 'group',
            },
          ]"
          :style="nodeStyle(node)"
          @pointerdown="onNodePointerDown($event, node)"
          @mouseenter="hoveredNodeId = node.id"
          @mouseleave="hoveredNodeId = ''"
          @click="onNodeClick(node)"
          @dblclick="onNodeDoubleClick(node)"
        >
          <template v-if="node.kind === 'group'">
            <div class="graph-group-head">
              <strong>{{ node.label }}</strong>
              <span class="panel-tag">Peer Mesh</span>
            </div>
            <div class="graph-group-copy">Specialists coordinate here. Actual handoff edges appear during runtime.</div>
          </template>
          <template v-else>
            <div
              v-if="hoveredNodeId === node.id"
              class="graph-node-tooltip"
            >
              {{ node.label }}
            </div>

            <div class="graph-node-icon-wrap">
              <component v-if="nodeIcon(node.kind)" :is="nodeIcon(node.kind)" :size="15" />
              <span v-else class="terminal-dot"></span>
            </div>
            <span v-if="node.caption" class="graph-node-caption">{{ node.caption }}</span>
            <span v-if="nodeCurrent(node.id)" class="graph-node-ring"></span>
            <button
              v-if="allowLayoutIO"
              class="graph-port graph-port-in"
              type="button"
              @mouseup="completeLink($event, node)"
              title="输入端口"
            ></button>
            <button
              v-if="allowLayoutIO"
              class="graph-port graph-port-out"
              type="button"
              @mousedown="beginLink($event, node)"
              title="输出端口"
            ></button>
          </template>
        </div>

        <svg
          class="graph-svg graph-svg-overlay"
          :viewBox="`0 0 ${canvasSize.width || 560} ${canvasSize.height || 420}`"
          preserveAspectRatio="none"
        >
          <path
            v-for="edge in graphEdges.overlay"
            :key="`overlay_base_${edge.key}`"
            :d="edge.d"
            fill="none"
            stroke="#cbd5e1"
            stroke-width="2"
            stroke-dasharray="4 4"
            marker-end="url(#graphArrowBase)"
            @dblclick.prevent.stop="removeEdge(edge.key)"
          />
          <path
            v-for="edge in graphEdges.overlay.filter((item) => item.active)"
            :key="`overlay_active_${edge.key}`"
            :d="edge.d"
            fill="none"
            stroke="#3b82f6"
            stroke-width="2.8"
            marker-end="url(#graphArrowActive)"
            @dblclick.prevent.stop="removeEdge(edge.key)"
          />
        </svg>
      </template>
    </div>

    <footer class="graph-terminal">
      <span v-if="linking.active">&gt; 连线中：{{ linking.sourceId }} → ...（点击目标节点左侧端口）</span>
      <span v-else-if="activeNodeId">
        &gt; {{ t("graph.activeNode") }}:
        {{ nodeMap.get(activeNodeId)?.label || activeNodeId }}
      </span>
      <span v-else>&gt; {{ t("graph.waiting") }}</span>
    </footer>
  </section>
</template>


<style scoped>
.chain-editor {
  margin: 8px 12px 0;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  padding: 8px;
  background: linear-gradient(180deg, #f8fbff, #f1f7ff);
}
.chain-title {
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 6px;
}
.chain-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chain-item {
  display: grid;
  grid-template-columns: 20px 1fr 24px 24px;
  gap: 6px;
  align-items: center;
}
.chain-index {
  font-size: 11px;
  color: #64748b;
  text-align: center;
}
.chain-select {
  min-width: 0;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #0f172a;
  font-size: 12px;
  padding: 5px 6px;
}
.chain-btn {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #ffffff;
  color: #475569;
  font-size: 11px;
  cursor: pointer;
  height: 24px;
}
.chain-hint {
  margin: 6px 0 0;
  font-size: 10px;
  color: #64748b;
}
.graph-actions {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
.graph-action-btn {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  font-size: 11px;
  color: #334155;
  padding: 4px 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.graph-fixed-tag {
  margin-left: auto;
}

.graph-node.with-caption {
  display: flex !important;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 1px;
  border-radius: 12px;
  padding: 3px 3px 4px;
  line-height: 1.1;
  box-shadow: 0 8px 16px rgba(15, 23, 42, 0.1);
}

.graph-node-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.graph-node-caption {
  font-size: 8px;
  font-weight: 700;
  color: #64748b;
  text-align: center;
  max-width: 84px;
  line-height: 1.2;
  pointer-events: none;
}

.graph-file-input {
  display: none;
}
.graph-port {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  border: 1px solid #93c5fd;
  background: #eff6ff;
  cursor: crosshair;
}
.graph-port-in {
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
}
.graph-port-out {
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
}
</style>
