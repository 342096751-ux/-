import { reactive } from "vue";

const DEFAULT_MODELS = ["gpt-4o-mini", "claude-3-5-sonnet", "qwen-plus", "local-llama"];
const LAYOUT_STORAGE_KEY = "agent-playground:custom-layouts";

function clone(v) {
  return JSON.parse(JSON.stringify(v));
}

function defaultSchema() {
  return JSON.stringify(
    {
      type: "object",
      properties: {
        verdict: { type: "string", enum: ["违规", "不违规"] },
        confidence: { type: "number", minimum: 0, maximum: 1 },
        evidence: { type: "string" },
      },
      required: ["verdict", "confidence"],
    },
    null,
    2,
  );
}

function uid(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function newInputField() {
  return { key: "", source: "upstream", from: "", required: false };
}

function newOutputField() {
  return { key: "", type: "string", desc: "" };
}

function newRouteRule() {
  return {
    id: uid("rr"),
    when: 'output.verdict == "违规" && output.confidence >= 0.6',
    toAgentId: "",
    templateId: "",
  };
}

function newTemplate(agentId) {
  return {
    id: uid(`tmpl_${agentId}`),
    targetAgent: "",
    template:
      "主题：请复核{{dimension}}维度\\n内容：\\n原始文本：{{input.content}}\\n初审结果：{{self.output.verdict}}\\n请确认或反驳。",
  };
}

function defaultRoutingConfig() {
  return {
    enabled: false,
    validatorNodeId: "",
    successTargetNodeId: "",
    challengeAction: "retry",
    arbitratorNodeId: "",
    maxRounds: 1,
  };
}

function normalizeRoutingConfig(routing) {
  const next = { ...defaultRoutingConfig(), ...(routing && typeof routing === "object" ? routing : {}) };
  next.enabled = Boolean(next.enabled);
  next.validatorNodeId = String(next.validatorNodeId || "");
  next.successTargetNodeId = String(next.successTargetNodeId || "");
  next.challengeAction = next.challengeAction === "arbitrate" ? "arbitrate" : "retry";
  next.arbitratorNodeId = String(next.arbitratorNodeId || "");
  next.maxRounds = Math.max(1, Math.min(3, Number(next.maxRounds || 1)));
  return next;
}

function normalizeAgentConfig(cfg, fallback = {}) {
  const next = cfg || {};
  next.name = next.name || fallback.name || fallback.id || "";
  next.role = next.role || fallback.description || "";
  next.routing = normalizeRoutingConfig(next.routing);
  return next;
}

function createAgentConfig(agent) {
  const presetModel = String(agent?.model || "").trim();
  return {
    id: agent.id,
    name: agent.name || agent.id,
    role: agent.description || "",
    systemPrompt: agent.system_prompt || "你是内容审核员，请给出结构化判断。",
    outputSchema: defaultSchema(),
    temperature: 0.2,
    confidenceThreshold: 0.6,
    model: presetModel || DEFAULT_MODELS[0],
    inputFields: [
      { key: "content", source: "upstream", from: "", required: true },
      { key: "context", source: "blackboard", from: "context", required: false },
    ],
    outputFields: [
      { key: "verdict", type: "enum", desc: "违规/不违规" },
      { key: "confidence", type: "number", desc: "0-1" },
      { key: "evidence", type: "string", desc: "说明" },
    ],
    routeRules: [],
    messageTemplates: [newTemplate(agent.id)],
    routing: defaultRoutingConfig(),
    strictMode: false,
    schemaError: "",
    lastOutput: null,
  };
}

function resolveActiveModelFromSettings(settings) {
  const profiles = Array.isArray(settings?.model_profiles) ? settings.model_profiles : [];
  const activeId = String(settings?.active_model_profile_id || "").trim();
  const activeProfile = profiles.find((p) => String(p?.id || "") === activeId) || profiles[0] || null;
  return String(activeProfile?.model || "").trim();
}

export const clusterStore = reactive({
  selectedAgentId: "",
  selectedWorkflowId: "",
  pausedNodeId: "",
  running: false,
  lastRunLogs: [],
  configByAgentId: {},
  models: DEFAULT_MODELS,
  runState: {
    order: [],
    currentIndex: -1,
  },
  layoutByWorkflowId: {},
});

function readLayoutStorage() {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeLayoutStorage(payload) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // ignore
  }
}

export function ensureAgentConfigs(agents, settings = null) {
  const fallbackModel = resolveActiveModelFromSettings(settings);
  const exists = new Set(agents.map((a) => a.id));
  agents.forEach((agent) => {
    if (!clusterStore.configByAgentId[agent.id]) {
      clusterStore.configByAgentId[agent.id] = createAgentConfig(agent);
      return;
    }
    const cfg = clusterStore.configByAgentId[agent.id];
    cfg.name = agent.name || agent.id;
    cfg.role = agent.description || "";
    cfg.systemPrompt = agent.system_prompt || cfg.systemPrompt;
    const presetModel = String(agent?.model || "").trim();
    if (presetModel) {
      cfg.model = presetModel;
      if (!clusterStore.models.includes(presetModel)) clusterStore.models.push(presetModel);
    } else if (fallbackModel) {
      cfg.model = fallbackModel;
      if (!clusterStore.models.includes(fallbackModel)) clusterStore.models.push(fallbackModel);
    } else if (!cfg.model) {
      cfg.model = DEFAULT_MODELS[0];
    }
    normalizeAgentConfig(cfg, agent);
  });

  Object.keys(clusterStore.configByAgentId).forEach((id) => {
    if (!exists.has(id)) delete clusterStore.configByAgentId[id];
  });

  if (clusterStore.selectedAgentId && !clusterStore.configByAgentId[clusterStore.selectedAgentId]) {
    clusterStore.selectedAgentId = "";
  }
}

export function selectedConfig() {
  return clusterStore.configByAgentId[clusterStore.selectedAgentId] || null;
}

export function updateAgentConfig(agentId, patch) {
  const cfg = clusterStore.configByAgentId[agentId];
  if (!cfg) return;
  Object.assign(cfg, patch);
}

export function addModelOption(modelName) {
  const m = String(modelName || "").trim();
  if (!m) return;
  if (!clusterStore.models.includes(m)) clusterStore.models.push(m);
}

export function addInputField(agentId) {
  const cfg = clusterStore.configByAgentId[agentId];
  if (!cfg) return;
  cfg.inputFields.push(newInputField());
}

export function addOutputField(agentId) {
  const cfg = clusterStore.configByAgentId[agentId];
  if (!cfg) return;
  cfg.outputFields.push(newOutputField());
}

export function addRouteRule(agentId) {
  const cfg = clusterStore.configByAgentId[agentId];
  if (!cfg) return;
  cfg.routeRules.push(newRouteRule());
}

export function addTemplate(agentId) {
  const cfg = clusterStore.configByAgentId[agentId];
  if (!cfg) return;
  cfg.messageTemplates.push(newTemplate(agentId));
}

export function removeRow(agentId, key, index) {
  const cfg = clusterStore.configByAgentId[agentId];
  if (!cfg || !Array.isArray(cfg[key])) return;
  cfg[key].splice(index, 1);
}

export function resetOutputsFrom(agentId) {
  const order = clusterStore.runState.order || [];
  const start = Math.max(0, order.indexOf(agentId));
  for (let i = start; i < order.length; i += 1) {
    const id = order[i];
    const cfg = clusterStore.configByAgentId[id];
    if (!cfg) continue;
    cfg.lastOutput = null;
    cfg.schemaError = "";
  }
}

export function exportClusterConfig() {
  return JSON.stringify(
    {
      selectedWorkflowId: clusterStore.selectedWorkflowId,
      selectedAgentId: clusterStore.selectedAgentId,
      models: clusterStore.models,
      configByAgentId: clone(clusterStore.configByAgentId),
    },
    null,
    2,
  );
}

export function importClusterConfig(payload) {
  const parsed = typeof payload === "string" ? JSON.parse(payload) : payload;
  if (!parsed || typeof parsed !== "object") return;
  if (parsed.selectedWorkflowId) clusterStore.selectedWorkflowId = String(parsed.selectedWorkflowId);
  if (parsed.selectedAgentId) clusterStore.selectedAgentId = String(parsed.selectedAgentId);
  if (Array.isArray(parsed.models)) clusterStore.models = [...parsed.models];
  if (parsed.configByAgentId && typeof parsed.configByAgentId === "object") {
    const copied = clone(parsed.configByAgentId);
    Object.keys(copied).forEach((agentId) => {
      copied[agentId] = normalizeAgentConfig(copied[agentId], { id: agentId });
    });
    clusterStore.configByAgentId = copied;
  }
}

export function ensureLayoutsLoaded() {
  if (Object.keys(clusterStore.layoutByWorkflowId).length) return;
  clusterStore.layoutByWorkflowId = readLayoutStorage();
}

export function loadLayout(workflowId) {
  ensureLayoutsLoaded();
  if (!workflowId) return null;
  return clusterStore.layoutByWorkflowId[String(workflowId)] || null;
}

export function saveCurrentLayout(workflowId, layout) {
  if (!workflowId || !layout || typeof layout !== "object") return;
  ensureLayoutsLoaded();
  const next = {
    ...clusterStore.layoutByWorkflowId,
    [String(workflowId)]: clone(layout),
  };
  clusterStore.layoutByWorkflowId = next;
  writeLayoutStorage(next);
}

export function exportLayout(workflowId) {
  const layout = loadLayout(workflowId);
  return JSON.stringify(
    {
      workflowId: String(workflowId || ""),
      layout: layout || null,
    },
    null,
    2,
  );
}

export function importLayout(payload) {
  const parsed = typeof payload === "string" ? JSON.parse(payload) : payload;
  if (!parsed || typeof parsed !== "object") return;
  const workflowId = String(parsed.workflowId || "").trim();
  if (!workflowId) return;
  if (!parsed.layout || typeof parsed.layout !== "object") return;
  saveCurrentLayout(workflowId, parsed.layout);
}
