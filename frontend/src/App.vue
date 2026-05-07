<script setup>
import { computed, onMounted, provide, ref, watch } from "vue";
import {
  Activity,
  BrainCircuit,
  GitBranch,
  LayoutDashboard,
  Play,
  Settings2,
  Users,
} from "lucide-vue-next";

import {
  createAgent,
  createConversation,
  createWorkflow,
  deleteAgent,
  deleteWorkflow,
  fetchAppSettings,
  fetchAgents,
  fetchConversation,
  fetchSkills,
  fetchTemplates,
  fetchWorkflowGraph,
  fetchWorkflows,
  updateAgent,
  updateAppSettings,
  updateWorkflow,
  runWorkflowStream,
  runWorkflow,
} from "./api";
import { I18N_KEY, createUiI18n } from "./i18n";
import OverviewPage from "./pages/OverviewPage.vue";
import AuditPipelinePage from "./pages/audit/AuditPipelinePage.vue";
import AuditRunPage from "./pages/audit/AuditRunPage.vue";
import AuditUnitsPage from "./pages/audit/AuditUnitsPage.vue";
import SettingsPage from "./pages/SettingsPage.vue";

const templates = ref([]);
const skills = ref([]);
const agents = ref([]);
const workflows = ref([]);
const selectedWorkflowId = ref("");
const selectedGraph = ref(null);
const lastRun = ref(null);
const loading = ref(false);
const errorMessage = ref("");
const batchRunState = ref({ running: false, total: 0, done: 0, success: 0, failed: 0, concurrency: 1, results: [] });
const currentPage = ref("overview");
const chatMessages = ref([]);
const currentConversationId = ref("");
const displayedTrace = ref([]);
const replayNodeId = ref("");
const replayingTrace = ref(false);
const replayToken = ref(0);
const activeRunController = ref(null);
const skillSyncStatus = ref("");
const appSettings = ref(null);
const savingSettings = ref(false);
const focusNodeId = ref("");
const editReturnTarget = ref({ enabled: false, agentId: "" });
const conversationStorageKey = "agent-playground:workflow-conversations";
const selectedWorkflowStorageKey = "agent-playground:selected-workflow";
/** Drives AgentManager to open create / edit when coming from 协作编排 */
const agentsPageIntent = ref({ tick: 0, action: null, agentId: null });

const i18n = createUiI18n();
provide(I18N_KEY, i18n);
const { locale, setLocale, t } = i18n;

const navItems = computed(() => [
  { id: "overview", label: t("nav.overview"), icon: LayoutDashboard },
  { id: "agents", label: t("nav.agents"), icon: Users },
  { id: "workflows", label: t("nav.workflows"), icon: GitBranch },
  { id: "playground", label: t("nav.playground"), icon: Play },
  { id: "settings", label: t("nav.settings"), icon: Settings2 },
]);

const activeNodeId = computed(() => {
  if (replayingTrace.value) return replayNodeId.value;
  const trace = lastRun.value?.trace || [];
  for (let index = trace.length - 1; index >= 0; index -= 1) {
    if (trace[index].payload?.node_id) return trace[index].payload.node_id;
  }
  return "";
});

const traceForView = computed(() => (replayingTrace.value ? displayedTrace.value : (lastRun.value?.trace || [])));

const selectedWorkflow = computed(() =>
  workflows.value.find((workflow) => workflow.id === selectedWorkflowId.value) || null,
);

const ugcWorkflows = computed(() => workflows.value.filter((w) => w.type === "ugc_moderation"));

/** 审核相关三页只使用 UGC 工作流，自动选中第一条 */
watch(
  [currentPage, workflows, selectedWorkflowId],
  () => {
    if (!["agents", "workflows", "playground"].includes(currentPage.value)) return;
    const list = ugcWorkflows.value;
    if (!list.length) return;
    if (!list.some((w) => w.id === selectedWorkflowId.value)) {
      selectedWorkflowId.value = list[0].id;
    }
  },
  { immediate: true },
);

/** 进入审核三页时若图仍无节点，补拉一次（避免 Overview 下首次 load 失败或竞态后空白） */
watch(currentPage, async (page) => {
  if (!["agents", "workflows", "playground"].includes(page)) return;
  const id = selectedWorkflowId.value;
  if (!id) return;
  if (!ugcWorkflows.value.some((w) => w.id === id)) return;
  const g = selectedGraph.value;
  if (g && Array.isArray(g.nodes) && g.nodes.length > 0) return;
  await loadGraph(id);
});

function extractRawModelResponses(trace) {
  if (!Array.isArray(trace)) return [];
  return trace
    .filter((event) => event?.type === "llm_finished")
    .map((event, index) => {
      const payload = event?.payload || {};
      const rawOutput = String(payload?.raw_output || payload?._rawOutput || payload?.preview || "").trim();
      return {
        id: `${payload?.node_id || "node"}_${index}`,
        nodeId: String(payload?.node_id || ""),
        agentName: String(payload?.agent_name || payload?.node_name || ""),
        model: String(payload?.model || ""),
        rawOutput,
      };
    })
    .filter((item) => item.rawOutput);
}

function extractModelDialogueFromTrace(trace) {
  const entries = extractRawModelResponses(trace);
  if (!entries.length) return "";
  return entries
    .map((item, index) => {
      const label = item.agentName || item.nodeId || `Model ${index + 1}`;
      return `[${index + 1}] ${label}${item.model ? ` (${item.model})` : ""}\n${item.rawOutput}`;
    })
    .join("\n\n---\n\n");
}

function readConversationStorage() {
  try {
    const raw = window.localStorage.getItem(conversationStorageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function getStoredSelectedWorkflowId() {
  try {
    return String(window.localStorage.getItem(selectedWorkflowStorageKey) || "").trim();
  } catch {
    return "";
  }
}

function setStoredSelectedWorkflowId(workflowId) {
  try {
    if (workflowId) {
      window.localStorage.setItem(selectedWorkflowStorageKey, workflowId);
    } else {
      window.localStorage.removeItem(selectedWorkflowStorageKey);
    }
  } catch {
    // ignore storage failures
  }
}

function writeConversationStorage(payload) {
  try {
    window.localStorage.setItem(conversationStorageKey, JSON.stringify(payload));
  } catch {
    // ignore storage failures
  }
}

function getStoredConversationId(workflowId) {
  if (!workflowId) return "";
  const store = readConversationStorage();
  const found = store.find((item) => String(item?.workflow_id || "") === workflowId);
  return String(found?.conversation_id || "").trim();
}

function setStoredConversationId(workflowId, conversationId) {
  if (!workflowId) return;
  const store = readConversationStorage().filter(
    (item) => String(item?.workflow_id || "") !== workflowId,
  );
  if (conversationId) {
    store.push({
      workflow_id: workflowId,
      conversation_id: conversationId,
    });
  }
  writeConversationStorage(store);
}

async function restoreConversation(workflowId) {
  const conversationId = getStoredConversationId(workflowId);
  if (!conversationId) return;
  try {
    const conversation = await fetchConversation(conversationId);
    currentConversationId.value = conversation.id;
    chatMessages.value = (conversation.messages || []).map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      agentName: message.agent_name || "",
    }));
  } catch {
    currentConversationId.value = "";
    chatMessages.value = [];
    setStoredConversationId(workflowId, "");
  }
}

async function loadInitialData() {
  [templates.value, skills.value, agents.value, workflows.value, appSettings.value] = await Promise.all([
    fetchTemplates(),
    fetchSkills(),
    fetchAgents(),
    fetchWorkflows(),
    fetchAppSettings(),
  ]);

  if (!selectedWorkflowId.value && workflows.value.length) {
    const storedWorkflowId = getStoredSelectedWorkflowId();
    const restoredWorkflow = workflows.value.find((workflow) => workflow.id === storedWorkflowId);
    selectedWorkflowId.value = restoredWorkflow?.id || workflows.value[0].id;
  }
}

async function loadGraph(workflowId) {
  if (!workflowId) {
    selectedGraph.value = null;
    return;
  }
  selectedGraph.value = await fetchWorkflowGraph(workflowId);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function replayTrace(traceEvents) {
  const token = replayToken.value + 1;
  replayToken.value = token;
  displayedTrace.value = [];
  replayNodeId.value = "start";
  replayingTrace.value = true;

  if (!traceEvents?.length) {
    replayingTrace.value = false;
    return true;
  }

  const stepDelay = traceEvents.length > 24 ? 85 : traceEvents.length > 14 ? 120 : 160;
  for (const event of traceEvents) {
    if (token !== replayToken.value) return false;
    displayedTrace.value = [...displayedTrace.value, event];
    const nextNode =
      event?.payload?.node_id ||
      event?.payload?.next_node_id ||
      "";
    if (nextNode) replayNodeId.value = nextNode;
    await sleep(stepDelay);
  }

  if (token === replayToken.value) {
    replayingTrace.value = false;
    return true;
  }
  return false;
}

async function handleCreateAgent(payload) {
  errorMessage.value = "";
  try {
    const createdAgent = await createAgent(payload);
    const latestAgents = await fetchAgents();
    agents.value = [
      createdAgent,
      ...latestAgents.filter((agent) => agent.id !== createdAgent.id),
    ];
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleUpdateAgent(payload) {
  errorMessage.value = "";
  try {
    await updateAgent(payload.id, payload.data);
    agents.value = await fetchAgents();
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleDeleteAgent(agentId) {
  errorMessage.value = "";
  try {
    const impacted = workflows.value.filter((workflow) =>
      Array.isArray(workflow?.specialist_agent_ids) && workflow.specialist_agent_ids.includes(agentId),
    );
    for (const workflow of impacted) {
      const nextSpecialists = workflow.specialist_agent_ids.filter((id) => id !== agentId);
      if (nextSpecialists.length === 0) {
        await deleteWorkflow(workflow.id);
      } else {
        await updateWorkflow(workflow.id, {
          name: workflow.name,
          type: workflow.type,
          specialist_agent_ids: nextSpecialists,
          finalizer_enabled: Boolean(workflow.finalizer_enabled),
          router_prompt: workflow.router_prompt || "You are an orchestration router. Select the best specialist based on user intent.",
        });
      }
    }
    await deleteAgent(agentId);
    agents.value = await fetchAgents();
    workflows.value = await fetchWorkflows();
    if (selectedWorkflowId.value && !workflows.value.some((workflow) => workflow.id === selectedWorkflowId.value)) {
      selectedWorkflowId.value = workflows.value[0]?.id || "";
    }
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

function handleWorkflowAddAgent() {
  currentPage.value = "agents";
  agentsPageIntent.value = {
    tick: Date.now(),
    action: "create",
    agentId: null,
  };
}

function handleWorkflowEditAgent(agentId) {
  currentPage.value = "agents";
  editReturnTarget.value = { enabled: true, agentId: agentId || "" };
  agentsPageIntent.value = {
    tick: Date.now(),
    action: "edit",
    agentId,
  };
}

function handleAgentEdited(agentId) {
  if (!editReturnTarget.value.enabled) return;
  if (editReturnTarget.value.agentId && editReturnTarget.value.agentId !== agentId) return;
  currentPage.value = "playground";
  focusNodeId.value = agentId || "";
  editReturnTarget.value = { enabled: false, agentId: "" };
}

function findSingleAgentChatWorkflow(agentId) {
  return (
    workflows.value.find(
      (workflow) =>
        workflow.type === "single_agent_chat" &&
        Array.isArray(workflow.specialist_agent_ids) &&
        workflow.specialist_agent_ids.length === 1 &&
        workflow.specialist_agent_ids[0] === agentId,
    ) || null
  );
}

async function handleQuickChatAgent(agent) {
  if (!agent?.id) return;
  errorMessage.value = "";
  try {
    let targetWorkflow = findSingleAgentChatWorkflow(agent.id);
    if (!targetWorkflow) {
      targetWorkflow = await createWorkflow({
        name: `${agent.name || "Agent"} Chat`,
        type: "single_agent_chat",
        specialist_agent_ids: [agent.id],
        finalizer_enabled: false,
        router_prompt: "Direct single-agent chat workflow.",
      });
      workflows.value = await fetchWorkflows();
      targetWorkflow =
        workflows.value.find((workflow) => workflow.id === targetWorkflow.id) ||
        findSingleAgentChatWorkflow(agent.id) ||
        targetWorkflow;
    }

    currentPage.value = "playground";
    selectedWorkflowId.value = targetWorkflow.id;
    await loadGraph(targetWorkflow.id);
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleCreateWorkflow(payload) {
  errorMessage.value = "";
  try {
    const workflow = await createWorkflow(payload);
    workflows.value = await fetchWorkflows();
    selectedWorkflowId.value = workflow.id;
    currentPage.value = "playground";
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleUpdateWorkflow(payload) {
  errorMessage.value = "";
  try {
    const updated = await updateWorkflow(payload.id, payload.data);
    workflows.value = await fetchWorkflows();
    if (selectedWorkflowId.value === updated.id) {
      await loadGraph(updated.id);
    }
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleDeleteWorkflow(workflowId) {
  errorMessage.value = "";
  try {
    await deleteWorkflow(workflowId);
    workflows.value = await fetchWorkflows();
    if (selectedWorkflowId.value === workflowId) {
      selectedWorkflowId.value = workflows.value[0]?.id || "";
      if (selectedWorkflowId.value) {
        await loadGraph(selectedWorkflowId.value);
      } else {
        selectedGraph.value = null;
      }
    }
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleSaveSettings(payload) {
  errorMessage.value = "";
  if (savingSettings.value) return;
  savingSettings.value = true;
  try {
    appSettings.value = await updateAppSettings(payload);
    skills.value = await fetchSkills();
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    savingSettings.value = false;
  }
}

async function handleRun(payload) {
  errorMessage.value = "";
  loading.value = true;
  if (activeRunController.value) {
    activeRunController.value.abort();
    activeRunController.value = null;
  }
  const token = replayToken.value + 1;
  replayToken.value = token;
  displayedTrace.value = [];
  replayNodeId.value = "start";
  replayingTrace.value = true;
  const controller = new AbortController();
  activeRunController.value = controller;

  const userMessage = {
    id: `user_${Date.now()}`,
    role: "user",
    content: payload.user_input,
  };
  chatMessages.value = [...chatMessages.value, userMessage];

  const runPayload = {
    ...payload,
    conversation_id: currentConversationId.value || undefined,
  };

  try {
    let streamResult = null;
    let streamError = "";
    let streamTransportFailed = false;

    try {
      await runWorkflowStream(runPayload, {
        signal: controller.signal,
        onTrace: (event) => {
          if (token !== replayToken.value) return;
          displayedTrace.value = [...displayedTrace.value, event];
          const nextNode =
            event?.payload?.node_id ||
            event?.payload?.next_node_id ||
            "";
          if (nextNode) replayNodeId.value = nextNode;
        },
        onFinal: (result) => {
          if (token !== replayToken.value) return;
          streamResult = result;
        },
        onError: (error) => {
          if (token !== replayToken.value) return;
          streamError = error?.message || String(error || "");
        },
      });
    } catch (error) {
      if (error?.name === "AbortError") return;
      streamResult = null;
      streamTransportFailed = true;
    }

    if (token !== replayToken.value) return;

    if (!streamResult) {
      if (streamError && !streamTransportFailed) {
        errorMessage.value = streamError;
        return;
      }
      const runResult = await runWorkflow(runPayload);
      if (token !== replayToken.value) return;
      lastRun.value = runResult;
      selectedGraph.value = runResult.graph;
      if (runResult.conversation_id) {
        currentConversationId.value = runResult.conversation_id;
        setStoredConversationId(payload.workflow_id, runResult.conversation_id);
      }
      const finished = await replayTrace(runResult.trace || []);
      if (finished && token === replayToken.value) {
        const assistantMessage = {
          id: `assistant_${Date.now()}`,
          role: "assistant",
          agentName: runResult.artifacts?.route_agent_name || t("chat.assistant"),
          content: runResult.assistant_message,
          debugRawResponses: extractRawModelResponses(runResult.trace || []),
        };
        chatMessages.value = [...chatMessages.value, assistantMessage];
      }
      return;
    }

    if (streamError) {
      errorMessage.value = streamError;
    }

    lastRun.value = streamResult;
    selectedGraph.value = streamResult.graph;
    displayedTrace.value = streamResult.trace || displayedTrace.value;
    if (streamResult.conversation_id) {
      currentConversationId.value = streamResult.conversation_id;
      setStoredConversationId(payload.workflow_id, streamResult.conversation_id);
    }
    const assistantMessage = {
      id: `assistant_${Date.now()}`,
      role: "assistant",
      agentName: streamResult.artifacts?.route_agent_name || t("chat.assistant"),
      content: streamResult.assistant_message,
      debugRawResponses: extractRawModelResponses(streamResult.trace || []),
    };
    chatMessages.value = [...chatMessages.value, assistantMessage];
  } catch (error) {
    if (token === replayToken.value) {
      errorMessage.value = String(error.message || error);
    }
  } finally {
    if (activeRunController.value === controller) {
      activeRunController.value = null;
    }
    if (token === replayToken.value) {
      replayingTrace.value = false;
    }
    loading.value = false;
  }
}


async function handleBatchRun(payload) {
  errorMessage.value = "";
  const workflowId = String(payload?.workflow_id || selectedWorkflowId.value || "").trim();
  const inputs = Array.isArray(payload?.inputs)
    ? payload.inputs.map((x) => String(x || "").trim()).filter(Boolean)
    : [];
  const concurrency = Math.max(1, Math.min(8, Number(payload?.concurrency || 1)));
  if (!workflowId || !inputs.length) return;

  batchRunState.value = {
    running: true,
    total: inputs.length,
    done: 0,
    success: 0,
    failed: 0,
    concurrency,
    results: [],
  };

  let cursor = 0;
  const workers = new Array(concurrency).fill(0).map(async () => {
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= inputs.length) break;
      const userInput = inputs[index];
      const startedAt = Date.now();
      try {
        const res = await runWorkflow({ workflow_id: workflowId, user_input: userInput });
        const trace = Array.isArray(res?.trace) ? res.trace : [];
        const modelDialogue = extractModelDialogueFromTrace(trace);
        const finalizerOutput =
          String(res?.artifacts?.final_answer || "").trim() ||
          String(res?.assistant_message || "").trim();
        batchRunState.value.results.push({
          index,
          input: userInput,
          ok: true,
          latencyMs: Date.now() - startedAt,
          output: res?.assistant_message || "",
          finalizerOutput,
          modelDialogue,
          routeAgent: res?.artifacts?.route_agent_name || "",
          traceCount: trace.length,
        });
        batchRunState.value.success += 1;
      } catch (err) {
        batchRunState.value.results.push({
          index,
          input: userInput,
          ok: false,
          latencyMs: Date.now() - startedAt,
          error: String(err?.message || err),
          finalizerOutput: "",
          modelDialogue: "",
          routeAgent: "",
          traceCount: 0,
        });
        batchRunState.value.failed += 1;
      } finally {
        batchRunState.value.done += 1;
      }
    }
  });

  await Promise.all(workers);
  batchRunState.value.running = false;
  batchRunState.value.results.sort((a, b) => a.index - b.index);
}

function handleClearRun() {
  if (activeRunController.value) {
    activeRunController.value.abort();
    activeRunController.value = null;
  }
  lastRun.value = null;
  chatMessages.value = [];
  if (selectedWorkflowId.value) {
    setStoredConversationId(selectedWorkflowId.value, "");
  }
  currentConversationId.value = "";
  displayedTrace.value = [];
  replayNodeId.value = "";
  replayingTrace.value = false;
  replayToken.value += 1;
}

function handleStopRun() {
  if (activeRunController.value) {
    activeRunController.value.abort();
    activeRunController.value = null;
  }
  replayingTrace.value = false;
  loading.value = false;
}

watch(selectedWorkflowId, async (workflowId) => {
  focusNodeId.value = "";
  setStoredSelectedWorkflowId(workflowId);
  if (activeRunController.value) {
    activeRunController.value.abort();
    activeRunController.value = null;
  }
  chatMessages.value = [];
  currentConversationId.value = "";
  lastRun.value = null;
  displayedTrace.value = [];
  replayNodeId.value = "";
  replayingTrace.value = false;
  replayToken.value += 1;
  await loadGraph(workflowId);
  await restoreConversation(workflowId);
});

onMounted(async () => {
  try {
    await loadInitialData();
    await loadGraph(selectedWorkflowId.value);
    await restoreConversation(selectedWorkflowId.value);
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
});
</script>

<template>
  <div class="app-frame" :class="{ 'playground-mode': currentPage === 'playground' }">
    <div class="app-with-sidebar">
      <aside class="left-sidebar">
        <div class="brand">
          <div class="brand-mark">
            <BrainCircuit :size="22" />
          </div>
          <div>
            <h1>{{ t("brand.title") }}</h1>
            <p>{{ t("brand.subtitle") }}</p>
          </div>
        </div>

        <nav class="topnav">
          <button
            v-for="item in navItems"
            :key="item.id"
            class="topnav-item"
            :class="{ active: currentPage === item.id }"
            @click="currentPage = item.id"
          >
            <component :is="item.icon" :size="16" />
            <span>{{ item.label }}</span>
          </button>
        </nav>
      </aside>

      <main class="shell page-shell">
        <div class="topbar-right topbar-right-inline">
          <div class="lang-switch">
            <button
              class="lang-button"
              :class="{ active: locale === 'zh-CN' }"
              @click="setLocale('zh-CN')"
            >
              {{ t("lang.zh") }}
            </button>
            <button
              class="lang-button"
              :class="{ active: locale === 'en-US' }"
              @click="setLocale('en-US')"
            >
              {{ t("lang.en") }}
            </button>
          </div>
          <div class="topbar-status">
            <span class="chip chip-dark">MVP</span>
            <Activity :size="14" class="status-icon" />
            <span>{{ t("status.ready") }}</span>
          </div>
        </div>
        <div v-if="errorMessage" class="error-banner">
          {{ errorMessage }}
        </div>

        <Transition name="page-fade" mode="out-in">
          <div :key="currentPage" class="page-stage" :class="{ 'playground-stage': currentPage === 'playground' }">
            <OverviewPage
              v-if="currentPage === 'overview'"
              :agents="agents"
              :workflows="workflows"
              :templates="templates"
              @navigate="currentPage = $event"
            />

            <AuditUnitsPage v-else-if="currentPage === 'agents'" />

            <AuditPipelinePage
              v-else-if="currentPage === 'workflows'"
              :workflows="workflows"
              :agents="agents"
              :app-settings="appSettings"
              :selected-workflow-id="selectedWorkflowId"
              :selected-workflow="selectedWorkflow"
              :selected-graph="selectedGraph"
              :active-node-id="activeNodeId"
              :focus-node-id="focusNodeId"
              :trace="traceForView"
              @select-workflow="selectedWorkflowId = $event"
              @update-workflow="handleUpdateWorkflow"
              @edit-agent="handleWorkflowEditAgent"
            />

            <AuditRunPage
              v-else-if="currentPage === 'playground'"
              :workflows="workflows"
              :agents="agents"
              :app-settings="appSettings"
              :selected-workflow-id="selectedWorkflowId"
              :selected-workflow="selectedWorkflow"
              :selected-graph="selectedGraph"
              :active-node-id="activeNodeId"
              :focus-node-id="focusNodeId"
              :loading="loading"
              :trace="traceForView"
              :trace-playing="replayingTrace"
              :chat-messages="chatMessages"
              :batch-run-state="batchRunState"
              @run="handleRun"
              @clear="handleClearRun"
              @stop="handleStopRun"
              @batch-run="handleBatchRun"
              @select-workflow="selectedWorkflowId = $event"
              @update-workflow="handleUpdateWorkflow"
              @edit-agent="handleWorkflowEditAgent"
            />

            <SettingsPage
              v-else
              :settings="appSettings"
              :saving="savingSettings"
              @save="handleSaveSettings"
            />
          </div>
        </Transition>
      </main>
    </div>
  </div>
</template>
