import { computed, ref } from "vue";

export const I18N_KEY = Symbol("ui-i18n");

const messages = {
  "en-US": {
    nav: {
      overview: "Overview",
      agents: "Audit units",
      workflows: "Audit pipeline",
      playground: "Run audit",
      settings: "Settings",
    },
    brand: {
      title: "UGC Review",
      subtitle: "UGC moderation — audit_system orchestrator",
    },
    audit: {
      unitsTitle: "Audit system modules",
      unitsDesc:
        "These roles map to the Python package audit_system/: intent → work units → verifier → arbiter. Model and API keys come from your .env.",
      intentAnalyst: "Intent analyst",
      intentAnalystDesc: "Classifies intent and suggests which moderators to activate.",
      workUnits: "Work units",
      workUnitsDesc: "Domain experts (e.g. politics, sexual) produce structured findings with evidence.",
      promptsHint: "Prompts: prompts/work_unit_*.txt",
      verifier: "Verifier",
      verifierDesc: "Challenges findings; may trigger follow-up or escalation.",
      arbiter: "Arbiter",
      arbiterDesc: "Final decision when verifier and work unit disagree (strategy: safety-first by default).",
      coreFiles: "Core files",
      orchestratorBlurb: "streams stage updates used by the Run page",
      configBlurb: "strategy & model (OPENAI_MODEL, etc.)",
      promptsBlurb: "Chinese-key JSON prompts",
      selectPipeline: "Pipeline",
      selectAuditWorkflow: "Audit workflow",
      noUgcWorkflow: "No ugc_moderation workflow in the backend. Create one or import DB.",
      graphWait: "Select an audit pipeline to load the graph.",
      pipelineExplainTitle: "What this graph shows",
      pipelineStep1: "<strong>Intent</strong> — classifies content and picks moderators.",
      pipelineStep2: "<strong>Work units</strong> — each activated domain returns conclusion + evidence.",
      pipelineStep3: "<strong>Verifier</strong> — may raise challenges.",
      pipelineStep4: "<strong>Arbiter</strong> — final action (block / pass / pass with log).",
      goRun: "Open <strong>Run audit</strong>, enter content, and watch Trace on the right.",
    },
    status: {
      ready: "System Ready",
    },
    lang: {
      zh: "中文",
      en: "EN",
    },
    page: {
      agentsTitle: "Agents",
      agentsDesc: "Create role specialists for reuse across different orchestrations.",
      workflowsTitle: "Orchestration",
      workflowsDesc: "Define collaboration patterns and create executable setups.",
    },
    settings: {
      title: "Settings",
      desc: "Configure model access for the desktop app runtime.",
      modelProfiles: "Model Profiles",
      modelProfilesDesc: "Create multiple model configurations. Save changes inside each profile editor.",
      addProfile: "Add Profile",
      active: "Active",
      setActive: "Set Active",
      editProfile: "Edit Profile",
      closeEditor: "Close",
      profileName: "Profile Name",
      profileNamePlaceholder: "Profile name",
      providerPreset: "Provider Preset",
      apiKey: "OpenAI API Key",
      apiKeyPlaceholder: "sk-...",
      baseUrl: "Base URL",
      baseUrlPlaceholder: "https://api.openai.com/v1",
      model: "Model",
      modelPlaceholder: "gpt-4o-mini",
      envVars: "Environment Variables",
      envVarsDesc: "Add any extra env vars required by tools or providers.",
      envVarsHint: "Press Enter or click save on a row to persist environment variables.",
      addEnvVar: "Add Variable",
      envKeyPlaceholder: "TAVILY_API_KEY",
      envValuePlaceholder: "value",
      saveProfile: "Save Profile",
      saveEnvVar: "Save",
      envNoValue: "No value",
      envEmpty: "No extra environment variables configured.",
      storageLabel: "Env File",
      save: "Save Settings",
      saving: "Saving...",
    },
    overview: {
      chip: "Orchestration-first Playground",
      headline1: "Define pattern first.",
      headline2: "Observe agents in motion.",
      desc: "This UI demonstrates agents, orchestration routing, and runtime trace in one clear experience.",
      flowTitle: "Flow",
      flowDesc: "Follow this order for the clearest walkthrough.",
      step1Title: "Create Agents",
      step1Desc: "Define reusable specialists.",
      step2Title: "Define Pattern",
      step2Desc: "Select a collaboration pattern and create a setup.",
      step3Title: "Run Playground",
      step3Desc: "Send messages and inspect graph plus trace.",
      agents: "Agents",
      workflows: "Setups",
      templates: "Patterns",
    },
    agent: {
      registryTitle: "Agent Registry",
      registryDesc: "Create and reuse specialists across orchestrations.",
      new: "New Agent",
      name: "Agent name",
      role: "Role description",
      prompt: "System prompt",
      save: "Save",
      cancel: "Cancel",
      systemPrompt: "System prompt",
    },
    workflow: {
      catalogTitle: "Orchestration Catalog",
      catalogDesc: "Choose a collaboration pattern and create executable setups.",
      new: "New Setup",
      setup: "Setup Configuration",
      name: "Setup name",
      enableFinalizer: "Enable Finalizer",
      bindAgents: "Bind Agents",
      requiresAtLeast: "This pattern requires at least {count} agents.",
      save: "Save Setup",
      cancel: "Cancel",
      selected: "selected",
      current: "Current setup",
      specialists: "Agents",
      finalizer: "Finalizer",
      on: "On",
      off: "Off",
      selectWorkflow: "Select Setup",
      template_router_specialists: "Router Specialists",
      template_planner_executor: "Planner Executor",
      template_supervisor_dynamic: "Supervisor Dynamic",
      template_single_agent_chat: "Single Agent Chat",
      template_peer_handoff: "Peer Handoff",
      template_desc_router_specialists:
        "Router selects the best specialist for the user intent, then optionally passes through a finalizer.",
      template_desc_planner_executor:
        "Planner decomposes the request into sub-tasks, delegates each task to workers, then synthesizes a final answer.",
      template_desc_supervisor_dynamic:
        "Supervisor decides delegation at runtime, loops through workers as needed, and composes the final answer.",
      template_desc_single_agent_chat:
        "Direct chat with one selected agent using a minimal start -> agent -> end graph.",
      template_desc_peer_handoff:
        "Router selects the first owner, then specialists hand work to each other inside a shared collaboration zone.",
      searchAgents: "Search by name or description",
      addAgent: "New Agent",
      editAgent: "Edit",
      allAgentsSummary: "Total {total} agents · list shows {shown}",
      noSearchResults: "No matching agents. Try other keywords or create one first.",
    },
    chat: {
      title: "Run audit",
      active: "Active setup",
      noneSelected: "No setup selected",
      clear: "Clear",
      presets: "Example Scenarios",
      fill: "Fill",
      presetRouter: "Single intent routing",
      presetPlanner: "Structured multi-part task",
      presetSupervisor: "Dynamic delegation with risks",
      startRun: "Start a run",
      startRunDesc: "Send a prompt and watch routing, graph highlights and trace updates.",
      thinking: "Thinking...",
      inputPlaceholder: "Paste content to moderate...",
      send: "Send",
      assistant: "Assistant",
    },
    graph: {
      title: "Graph",
      auditTitle: "Audit pipeline",
      fixedPipeline: "Fixed",
      subtitle: "Runtime highlighted nodes",
      liveGraph: "Live Graph",
      empty: "Select a setup to display its graph.",
      activeNode: "Active node",
      waiting: "Waiting for interaction...",
      live: "Live",
    },
    trace: {
      title: "Trace",
      subtitle: "Runtime events and routing decisions",
      live: "Live",
      playing: "Playing",
      showAll: "All events",
      showKey: "Key only",
      empty: "Run a setup to view events here.",
      payload: "payload",
    },
  },
  "zh-CN": {
    nav: {
      overview: "总览",
      agents: "审核单元",
      workflows: "审核流程",
      playground: "运行审核",
      settings: "设置",
    },
    brand: {
      title: "UGC 审核",
      subtitle: "UGC 内容审核 — audit_system 编排",
    },
    audit: {
      unitsTitle: "审核系统模块",
      unitsDesc:
        "以下角色对应项目内 audit_system/ 包：意图分析 → 工作单元 → 验证器 → 仲裁。模型与密钥读取自 .env。",
      intentAnalyst: "意图分析员",
      intentAnalystDesc: "识别内容意图与风险域，并建议激活哪些审核员。",
      workUnits: "工作单元",
      workUnitsDesc: "各领域的专业审核员（如政治、色情等），输出结论文本与证据。",
      promptsHint: "提示词见 prompts/work_unit_*.txt",
      verifier: "验证器",
      verifierDesc: "对工作单元结论做质询，可触发补充或进入仲裁。",
      arbiter: "仲裁者",
      arbiterDesc: "在验证员与工作单元未达成一致时给出最终执行动作（默认安全优先）。",
      coreFiles: "核心文件",
      orchestratorBlurb: "分阶段输出，供「运行审核」与 Trace 展示",
      configBlurb: "策略与模型名（如 OPENAI_MODEL）",
      promptsBlurb: "中文键名 JSON 提示词",
      selectPipeline: "审核管线",
      selectAuditWorkflow: "审核工作流",
      noUgcWorkflow: "后端尚无 ugc_moderation 类型工作流，请先创建或恢复数据库。",
      graphWait: "请选择一条审核管线以加载流程图。",
      pipelineExplainTitle: "流程图说明",
      pipelineStep1: "<strong>意图分析</strong>：判定意图并建议激活哪些审核员。",
      pipelineStep2: "<strong>工作单元</strong>：被激活的领域依次产出结论、证据与置信度。",
      pipelineStep3: "<strong>验证器</strong>：对证据链提出质疑。",
      pipelineStep4: "<strong>仲裁者</strong>：输出最终执行动作（拦截/放行/放行但记录）。",
      goRun: "请打开左侧「<strong>运行审核</strong>」，输入待审内容，在右侧查看 Trace 与报告卡片。",
    },
    status: {
      ready: "系统就绪",
    },
    lang: {
      zh: "中文",
      en: "EN",
    },
    page: {
      agentsTitle: "智能体",
      agentsDesc: "创建可复用的角色型 Agent，用于不同编排方案。",
      workflowsTitle: "协作编排",
      workflowsDesc: "定义协作模式并创建可执行编排方案。",
    },
    settings: {
      title: "设置",
      desc: "配置桌面应用运行时使用的大模型参数。",
      modelProfiles: "模型配置组",
      modelProfilesDesc: "可以保存多组模型配置，并在每个编辑面板内单独保存。",
      addProfile: "新增配置组",
      active: "已激活",
      setActive: "设为激活",
      editProfile: "编辑配置组",
      closeEditor: "收起",
      profileName: "配置组名称",
      profileNamePlaceholder: "输入配置组名称",
      providerPreset: "预设供应商",
      apiKey: "OpenAI API Key",
      apiKeyPlaceholder: "sk-...",
      baseUrl: "Base URL",
      baseUrlPlaceholder: "https://api.openai.com/v1",
      model: "模型",
      modelPlaceholder: "gpt-4o-mini",
      envVars: "环境变量",
      envVarsDesc: "可添加工具或其他 provider 需要的任意环境变量。",
      envVarsHint: "每行可按回车或点击保存立即写入环境变量。",
      addEnvVar: "新增变量",
      envKeyPlaceholder: "TAVILY_API_KEY",
      envValuePlaceholder: "值",
      saveProfile: "保存配置组",
      saveEnvVar: "保存",
      envNoValue: "未设置值",
      envEmpty: "当前没有额外环境变量。",
      storageLabel: "配置文件位置",
      save: "保存设置",
      saving: "保存中...",
    },
    overview: {
      chip: "编排优先演示",
      headline1: "先定义模式。",
      headline2: "再观察智能体协作。",
      desc: "该界面用于演示：在一个视图中查看 Agents、编排路由和运行 Trace。",
      flowTitle: "流程",
      flowDesc: "按下面顺序体验最清晰。",
      step1Title: "创建 Agents",
      step1Desc: "定义可复用专家角色。",
      step2Title: "定义模式",
      step2Desc: "选择协作模式并创建编排方案。",
      step3Title: "运行 Playground",
      step3Desc: "发送消息并查看图与追踪。",
      agents: "Agents",
      workflows: "方案",
      templates: "模式",
    },
    agent: {
      registryTitle: "Agent 注册表",
      registryDesc: "创建并复用不同角色专家。",
      new: "新建 Agent",
      name: "Agent 名称",
      role: "角色描述",
      prompt: "系统提示词",
      save: "保存",
      cancel: "取消",
      systemPrompt: "系统提示词",
    },
    workflow: {
      catalogTitle: "编排方案目录",
      catalogDesc: "选择协作模式并创建可执行方案。",
      new: "新建方案",
      setup: "方案配置",
      name: "方案名称",
      enableFinalizer: "启用 Finalizer",
      bindAgents: "绑定 Agents",
      requiresAtLeast: "当前模式至少需要 {count} 个 Agent。",
      save: "保存方案",
      cancel: "取消",
      selected: "已选中",
      current: "当前方案",
      specialists: "Agents",
      finalizer: "Finalizer",
      on: "启用",
      off: "关闭",
      selectWorkflow: "选择方案",
      template_router_specialists: "路由专家",
      template_planner_executor: "规划执行",
      template_supervisor_dynamic: "动态监督",
      template_single_agent_chat: "单 Agent 对话",
      template_peer_handoff: "同伴交接",
      template_desc_router_specialists:
        "先由 Router 选择最匹配的专家，再按需经过 Finalizer 统一收口。",
      template_desc_planner_executor:
        "先由 Planner 拆解任务，再分配给 Worker 执行，最后统一合成答复。",
      template_desc_supervisor_dynamic:
        "由 Supervisor 在运行中动态委派，按需循环调度 Worker 并收敛结果。",
      template_desc_single_agent_chat:
        "直接与一个选定的 Agent 对话，图结构最简。",
      template_desc_peer_handoff:
        "先选出第一责任人，再由专家之间在共享协作区内相互交接，直到任务收敛。",
      searchAgents: "搜索 Agent 名称或说明",
      addAgent: "新建 Agent",
      editAgent: "编辑",
      allAgentsSummary: "共 {total} 个 Agent，当前列表显示 {shown} 个",
      noSearchResults: "没有匹配的 Agent，可调整搜索词或先点击「新建 Agent」。",
    },
    chat: {
      title: "运行审核",
      active: "当前审核方案",
      noneSelected: "未选择方案",
      clear: "清空",
      presets: "示例场景",
      fill: "填入",
      presetRouter: "单意图路由",
      presetPlanner: "结构化多段任务",
      presetSupervisor: "含风险的动态委派",
      startRun: "开始一次运行",
      startRunDesc: "发送问题并观察路由、图高亮和 Trace 变化。",
      thinking: "思考中...",
      inputPlaceholder: "粘贴待审核内容...",
      send: "发送",
      assistant: "助手",
    },
    graph: {
      title: "流程图",
      auditTitle: "审核流程图",
      fixedPipeline: "固定管线",
      subtitle: "运行节点高亮",
      liveGraph: "实时图",
      empty: "请选择一个方案查看图结构。",
      activeNode: "当前节点",
      waiting: "等待交互...",
      live: "实时",
    },
    trace: {
      title: "追踪",
      subtitle: "运行事件与路由决策",
      live: "实时",
      playing: "回放中",
      showAll: "全部事件",
      showKey: "仅关键",
      empty: "运行一次方案后会在这里显示事件。",
      payload: "载荷",
    },
  },
};

function getByPath(obj, path) {
  return path.split(".").reduce((current, key) => current?.[key], obj);
}

function interpolate(text, vars = {}) {
  return String(text).replace(/\{(\w+)\}/g, (_, key) => vars[key] ?? `{${key}}`);
}

export function createUiI18n() {
  const saved = localStorage.getItem("ui-locale");
  const locale = ref(saved === "zh-CN" || saved === "en-US" ? saved : "zh-CN");
  const dict = computed(() => messages[locale.value] || messages["zh-CN"]);

  function setLocale(nextLocale) {
    if (nextLocale !== "zh-CN" && nextLocale !== "en-US") return;
    locale.value = nextLocale;
    localStorage.setItem("ui-locale", nextLocale);
  }

  function t(path, vars = {}) {
    const found = getByPath(dict.value, path);
    if (typeof found === "string") return interpolate(found, vars);
    return path;
  }

  function workflowTypeLabel(type) {
    const path = `workflow.template_${type}`;
    const value = t(path);
    if (value !== path) return value;

    const fallbackLabels = {
      router_specialists: "Router Specialists",
      planner_executor: "Planner Executor",
      supervisor_dynamic: "Supervisor Dynamic",
      single_agent_chat: "Single Agent Chat",
      peer_handoff: "Peer Handoff",
      ugc_moderation: "UGC Moderation",
    };
    return fallbackLabels[type] || type;
  }

  function workflowTypeDesc(type, fallback = "") {
    const value = t(`workflow.template_desc_${type}`);
    if (value !== `workflow.template_desc_${type}`) return value;
    const fallbackDescriptions = {
      router_specialists:
        "Router selects the best specialist for the user intent, then optionally passes through a finalizer.",
      planner_executor:
        "Planner decomposes the request into sub-tasks, delegates each task to workers, then synthesizes a final answer.",
      supervisor_dynamic:
        "Supervisor decides delegation at runtime, loops through workers as needed, and composes the final answer.",
      single_agent_chat:
        "Direct chat with one selected agent using a minimal start -> agent -> end graph.",
      peer_handoff:
        "Router selects the first owner, then specialists hand work to each other inside a shared collaboration zone.",
    };
    return fallbackDescriptions[type] || fallback;
  }

  return {
    locale,
    setLocale,
    t,
    workflowTypeLabel,
    workflowTypeDesc,
  };
}
