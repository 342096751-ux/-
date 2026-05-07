<script setup>
import {
  Bot,
  CheckCircle2,
  Code,
  Database,
  FolderOpen,
  Globe,
  Image as ImageIcon,
  Library,
  Mail,
  MessageCircle,
  PencilLine,
  Plus,
  Settings2,
  ShoppingBag,
  Trash2,
  X,
  Zap,
} from "lucide-vue-next";
import { computed, inject, reactive, ref, watch } from "vue";
import { installSkill as installSkillPackage } from "../api";
import { I18N_KEY } from "../i18n";

const props = defineProps({
  agents: {
    type: Array,
    required: true,
  },
  skills: {
    type: Array,
    required: true,
  },
  skillSyncStatus: {
    type: String,
    default: "",
  },
  pageIntent: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(["create", "update", "delete", "quick-chat", "edited"]);
const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((key) => key);

const isAdding = ref(false);
const isSavingEdit = ref(false);
const isSavingStore = ref(false);

const addForm = reactive({
  name: "",
  role: "",
  details: "",
});

const editingAgent = ref(null);
const isStoreOpen = ref(false);
const storeAgentId = ref("");

const themeTokens = [
  "agent-theme-blue",
  "agent-theme-violet",
  "agent-theme-green",
  "agent-theme-orange",
  "agent-theme-rose",
  "agent-theme-indigo",
];
const maxVisibleMetaItems = 3;

const skillLibrary = computed(() =>
  props.skills.map((skill) => ({
    ...skill,
    icon: resolveSkillIcon(skill),
  })),
);

const skillMap = computed(() => {
  const map = new Map();
  skillLibrary.value.forEach((skill) => map.set(skill.id, skill));
  return map;
});

const decoratedAgents = computed(() =>
  props.agents.map((agent, index) => {
    const roleLabel = resolveRoleLabel(agent.name, agent.description);
    const boundSkills = (agent.skill_ids || [])
      .map((skillId) => {
        const skill = skillMap.value.get(skillId);
        return {
          id: skillId,
          name: skill?.name || "Unknown Skill",
          icon: skill?.icon || Zap,
        };
      })
      .filter((item) => item.name);
    const builtinCapabilities = builtinCapabilityOptions.filter((option) =>
      (agent.builtin_capabilities || []).includes(option.id),
    );
    const visibleSkills =
      boundSkills.length > maxVisibleMetaItems
        ? boundSkills.slice(0, maxVisibleMetaItems - 1)
        : boundSkills.slice(0, maxVisibleMetaItems);
    const visibleCapabilities =
      builtinCapabilities.length > maxVisibleMetaItems
        ? builtinCapabilities.slice(0, maxVisibleMetaItems - 1)
        : builtinCapabilities.slice(0, maxVisibleMetaItems);
    return {
      ...agent,
      roleLabel,
      allBoundSkills: boundSkills,
      boundSkills: visibleSkills,
      hiddenSkillCount: Math.max(0, boundSkills.length - visibleSkills.length),
      allBuiltinCapabilities: builtinCapabilities,
      builtinCapabilities: visibleCapabilities,
      hiddenCapabilityCount: Math.max(0, builtinCapabilities.length - visibleCapabilities.length),
      theme: themeTokens[index % themeTokens.length],
    };
  }),
);

const categoryOrder = ["审核类", "专家类", "验证类", "裁决类", "决策类", "其他"];

function detectAgentCategory(agent) {
  const text = `${agent?.name || ""} ${agent?.description || ""}`.toLowerCase();
  if (/主审|副审|初审|终审|review|审核/.test(text)) return "审核类";
  if (/政治|色情|广告|暴恐|辱骂|spam|expert|专家/.test(text)) return "专家类";
  if (/验证|复核|validator|strict|宽松/.test(text)) return "验证类";
  if (/仲裁|裁决|arbitrat/.test(text)) return "裁决类";
  if (/大脑|brain|decision|final/.test(text)) return "决策类";
  return "其他";
}

function shortName(name) {
  const text = String(name || "").trim();
  if (!text) return "AG";
  const noSpace = text.replace(/\s+/g, "");
  return noSpace.slice(0, 2);
}

const groupedAgents = computed(() => {
  const grouped = new Map(categoryOrder.map((label) => [label, []]));
  decoratedAgents.value.forEach((agent) => {
    const label = detectAgentCategory(agent);
    if (!grouped.has(label)) grouped.set(label, []);
    grouped.get(label).push(agent);
  });
  return [...grouped.entries()]
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
});

const storeAgent = computed(
  () => props.agents.find((agent) => agent.id === storeAgentId.value) || null,
);

const builtinCapabilityOptions = [
  {
    id: "filesystem",
    label: "File Operations",
    description: "Allow searching, listing, reading, writing, creating directories, moving, and deleting local paths.",
    icon: PencilLine,
  },
];

function resolveRoleLabel(name, description) {
  const normalized = String(name || "").trim().toLowerCase();
  const nameMap = {
    "architecture coach": "System Architect",
    "documentation writer": "Technical Writer",
    "learning coach": "Education Specialist",
  };
  if (nameMap[normalized]) return nameMap[normalized];

  const shorten = (text) => {
    const rawText = String(text || "").trim();
    if (!rawText) return "";
    const maxLength = 18;
    if (rawText.length <= maxLength) return rawText;
    return `${rawText.slice(0, maxLength - 3).trim()}...`;
  };

  const raw = String(description || "").trim();
  if (!raw) return "Specialist";
  if (raw.length <= 18) return raw;
  const head = raw.split(/[,.，。；;]/)[0].trim();
  if (head) return shorten(head);
  return shorten(raw);
}

function previewPrompt(text) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  return raw.replace(/\s+/g, " ");
}

function resolveSkillIcon(skill) {
  const text = `${skill.name || ""} ${skill.description || ""} ${skill.instruction || ""}`.toLowerCase();
  if (text.includes("search") || text.includes("web") || text.includes("internet")) return Globe;
  if (text.includes("code") || text.includes("python")) return Code;
  if (text.includes("image") || text.includes("vision")) return ImageIcon;
  if (text.includes("file") || text.includes("document")) return FileText;
  if (text.includes("database") || text.includes("sql")) return Database;
  if (text.includes("mail") || text.includes("email")) return Mail;
  return Zap;
}

function getSkillPreflight(skill) {
  const runtime = skill?.runtime_preflight;
  if (!runtime || typeof runtime !== "object") return null;
  return runtime;
}

function getSkillRuntimeLabel(skill) {
  const runtime = getSkillPreflight(skill);
  if (!runtime) return "Runtime Unknown";
  const status = String(runtime.status || "");
  if (status === "ready") return "Runtime Ready";
  if (status === "prompt_only") return "Prompt Only";
  if (status === "missing_environment") return "Missing Env";
  if (status === "missing_shell_dependencies") return "Missing Deps";
  if (status === "missing_launcher") return "Missing Launcher";
  if (status === "missing_command_target") return "Missing Script";
  if (status === "invalid_local_path") return "Invalid Path";
  if (status === "invalid_tool") return "Invalid Tool";
  return "Runtime Blocked";
}

function getSkillRuntimeClass(skill) {
  const runtime = getSkillPreflight(skill);
  if (!runtime) return "unknown";
  if (runtime.ready) return "ready";
  return "blocked";
}

function getSkillRuntimeDetail(skill) {
  const runtime = getSkillPreflight(skill);
  if (!runtime) return "";
  const missingLaunchers = Array.isArray(runtime.missing_launchers) ? runtime.missing_launchers : [];
  if (missingLaunchers.length) {
    return `Launchers: ${missingLaunchers.join(", ")}`;
  }
  const missingDeps = Array.isArray(runtime.missing_shell_dependencies)
    ? runtime.missing_shell_dependencies
    : [];
  if (missingDeps.length) {
    return `Dependencies: ${missingDeps.join(", ")}`;
  }
  const missingEnv = Array.isArray(runtime.missing_env_vars) ? runtime.missing_env_vars : [];
  if (missingEnv.length) {
    return `Env: ${missingEnv.join(", ")}`;
  }
  if (runtime.node_prepare_required) {
    return "First run may install node dependencies";
  }
  if (runtime.python_prepare_required) {
    return "First run may install python dependencies";
  }
  return String(runtime.message || "");
}

function canCreate() {
  return Boolean(addForm.name.trim() && addForm.role.trim() && addForm.details.trim());
}

function resetCreateForm() {
  isAdding.value = false;
  addForm.name = "";
  addForm.role = "";
  addForm.details = "";
}

function beginCreate() {
  resetCreateForm();
  isAdding.value = true;
}

watch(
  () => [props.pageIntent?.tick, props.pageIntent?.action, props.pageIntent?.agentId],
  () => {
    const intent = props.pageIntent;
    if (!intent || typeof intent.tick !== "number") return;
    if (intent.action === "create") {
      beginCreate();
    } else if (intent.action === "edit" && intent.agentId) {
      const ag = props.agents.find((a) => a.id === intent.agentId);
      if (ag) beginEdit(ag);
    }
  },
);

function beginEdit(agent) {
  isAdding.value = false;
  editingAgent.value = {
    id: agent.id,
    name: agent.name || "",
    role: agent.description || "",
    details: agent.system_prompt || "",
    model: agent.model ?? null,
    skill_ids: [...(agent.skill_ids || [])],
    builtin_capabilities: [...(agent.builtin_capabilities || [])],
  };
}

function closeEdit() {
  editingAgent.value = null;
}

function removeAgent(agentId) {
  emit("delete", agentId);
  if (editingAgent.value?.id === agentId) {
    closeEdit();
  }
}

function removeEditingSkill(skillId) {
  if (!editingAgent.value) return;
  editingAgent.value.skill_ids = editingAgent.value.skill_ids.filter((id) => id !== skillId);
}

function toggleBuiltinCapability(capabilityId) {
  if (!editingAgent.value) return;
  const current = new Set(editingAgent.value.builtin_capabilities || []);
  if (current.has(capabilityId)) {
    current.delete(capabilityId);
  } else {
    current.add(capabilityId);
  }
  editingAgent.value.builtin_capabilities = [...current];
}

function openSkillStore(agentId) {
  storeAgentId.value = agentId;
  isStoreOpen.value = true;
}

function startQuickChat(agent) {
  emit("quick-chat", agent);
}

function closeSkillStore() {
  isStoreOpen.value = false;
  storeAgentId.value = "";
}

async function submitCreate() {
  if (!canCreate()) return;
  await emit("create", {
    name: addForm.name,
    description: addForm.role,
    system_prompt: addForm.details,
    skill_ids: [],
    builtin_capabilities: [],
  });
  resetCreateForm();
}

async function submitEdit() {
  if (!editingAgent.value) return;
  if (!editingAgent.value.name.trim() || !editingAgent.value.role.trim() || !editingAgent.value.details.trim()) return;
  if (isSavingEdit.value) return;
  isSavingEdit.value = true;
  try {
    await emit("update", {
      id: editingAgent.value.id,
      data: {
        name: editingAgent.value.name,
        description: editingAgent.value.role,
        system_prompt: editingAgent.value.details,
        model: editingAgent.value.model,
        skill_ids: [...editingAgent.value.skill_ids],
        builtin_capabilities: [...editingAgent.value.builtin_capabilities],
      },
    });
    emit("edited", editingAgent.value.id);
    closeEdit();
  } finally {
    isSavingEdit.value = false;
  }
}

async function toggleStoreSkill(skillId) {
  if (!storeAgent.value || isSavingStore.value) return;
  const currentSkills = [...(storeAgent.value.skill_ids || [])];
  const installing = !currentSkills.includes(skillId);
  const nextSkills = currentSkills.includes(skillId)
    ? currentSkills.filter((id) => id !== skillId)
    : [...currentSkills, skillId];

  isSavingStore.value = true;
  try {
    if (installing) {
      await installSkillPackage(skillId);
    }
    await emit("update", {
      id: storeAgent.value.id,
      data: {
        name: storeAgent.value.name,
        description: storeAgent.value.description,
        system_prompt: storeAgent.value.system_prompt,
        model: storeAgent.value.model ?? null,
        skill_ids: nextSkills,
        builtin_capabilities: [...(storeAgent.value.builtin_capabilities || [])],
      },
    });
    if (editingAgent.value?.id === storeAgent.value.id) {
      editingAgent.value.skill_ids = [...nextSkills];
    }
  } finally {
    isSavingStore.value = false;
  }
}

function isSkillInstalled(skillId) {
  return Boolean(storeAgent.value?.skill_ids?.includes(skillId));
}

function getSkillDisplay(skillId) {
  const skill = skillMap.value.get(skillId);
  return {
    name: skill?.name || "Unknown Skill",
    icon: skill?.icon || Zap,
  };
}

</script>

<template>
  <section class="page-stack agents-page">
    <div class="manager-topbar">
      <div>
        <h2>Agents</h2>
        <p>{{ t("page.agentsDesc") }}</p>
      </div>
      <button class="primary-button" @click="beginCreate">
        <Plus :size="16" />
        {{ t("agent.new") }}
      </button>
    </div>

    <div class="agent-grid">
      <article class="glass-panel agent-card grouped-agent-board">
        <section v-if="isAdding" class="agent-type-group grouped-create-wrap">
          <h4 class="agent-type-title">Create Agent</h4>
          <div class="grouped-create-card">
            <input v-model="addForm.name" :placeholder="t('agent.name')" />
            <input v-model="addForm.role" :placeholder="t('agent.role')" />
            <textarea v-model="addForm.details" rows="5" :placeholder="t('agent.prompt')" />
            <div class="inline-actions">
              <button class="accent-button accent-button-blue" :disabled="!canCreate()" @click="submitCreate">
                {{ t("agent.save") }}
              </button>
              <button class="ghost-button" @click="resetCreateForm">
                {{ t("agent.cancel") }}
              </button>
            </div>
          </div>
        </section>

        <section v-for="group in groupedAgents" :key="group.label" class="agent-type-group">
          <h4 class="agent-type-title">{{ group.label }}</h4>
          <div class="agent-type-grid">
            <button
              v-for="agent in group.items"
              :key="agent.id"
              class="agent-type-cell"
              type="button"
              :title="`${agent.name} · ${agent.roleLabel}`"
              @click="beginEdit(agent)"
            >
              <div class="agent-type-cell-actions" @click.stop>
                <button class="icon-button tiny" type="button" title="技能" @click="openSkillStore(agent.id)">
                  <ShoppingBag :size="12" />
                </button>
                <button class="icon-button tiny" type="button" title="对话" @click="startQuickChat(agent)">
                  <MessageCircle :size="12" />
                </button>
                <button class="icon-button tiny danger" type="button" title="删除" @click="removeAgent(agent.id)">
                  <Trash2 :size="12" />
                </button>
              </div>
              <div class="agent-type-avatar" :class="agent.theme">{{ shortName(agent.name) }}</div>
              <span class="agent-type-name">{{ agent.name }}</span>
            </button>
          </div>
        </section>
      </article>
    </div>

    <div v-if="editingAgent" class="agent-modal-overlay" @click="closeEdit">
      <section class="agent-modal-panel" @click.stop>
        <header class="agent-modal-header">
          <h3>Edit Agent</h3>
          <button type="button" class="agent-modal-close" @click="closeEdit">
            <X :size="20" />
          </button>
        </header>
        <div class="agent-modal-body">
          <div class="agent-modal-field">
            <label>Name</label>
            <input v-model="editingAgent.name" />
          </div>
          <div class="agent-modal-field">
            <label>Role</label>
            <input v-model="editingAgent.role" />
          </div>
          <div class="agent-modal-field">
            <label>System Prompt</label>
            <textarea v-model="editingAgent.details" rows="4"></textarea>
          </div>
          <div class="agent-modal-field">
            <label>Skills</label>
            <div v-if="editingAgent.skill_ids.length === 0" class="agent-modal-empty-skill">
              No skills installed.
            </div>
            <div v-else class="agent-modal-installed-list">
              <div
                v-for="skillId in editingAgent.skill_ids"
                :key="`edit_${skillId}`"
                class="agent-modal-installed-item"
              >
                <div class="agent-modal-installed-main">
                  <component :is="getSkillDisplay(skillId).icon" :size="16" />
                  <span>{{ getSkillDisplay(skillId).name }}</span>
                </div>
                <button type="button" class="agent-modal-remove-skill" @click="removeEditingSkill(skillId)">
                  <Trash2 :size="14" />
                </button>
              </div>
            </div>
          </div>
          <div class="agent-modal-field">
            <label>Built-in Capabilities</label>
            <div class="agent-modal-capability-list">
              <button
                v-for="capability in builtinCapabilityOptions"
                :key="capability.id"
                type="button"
                class="agent-modal-capability-item"
                :class="{ active: editingAgent.builtin_capabilities.includes(capability.id) }"
                @click="toggleBuiltinCapability(capability.id)"
              >
                <div class="agent-modal-capability-main">
                  <component :is="capability.icon" :size="16" />
                  <div>
                    <strong>{{ capability.label }}</strong>
                    <p>{{ capability.description }}</p>
                  </div>
                </div>
              </button>
            </div>
          </div>
        </div>
        <footer class="agent-modal-footer">
          <button type="button" class="agent-modal-cancel" @click="closeEdit">
            Cancel
          </button>
          <button type="button" class="agent-modal-save" :disabled="isSavingEdit" @click="submitEdit">
            {{ isSavingEdit ? "Saving..." : "Save" }}
          </button>
        </footer>
      </section>
    </div>

    <div v-if="isStoreOpen" class="skill-store-overlay" @click="closeSkillStore">
      <section class="skill-store-panel" @click.stop>
        <header class="skill-store-header">
          <div class="skill-store-brand">
            <div class="skill-store-brand-icon">
              <Library :size="20" />
            </div>
            <div>
              <h3>Local Skills</h3>
              <p>Workspace Skill Repository</p>
            </div>
          </div>
          <div class="skill-store-header-actions">
            <button type="button" class="skill-store-close" @click="closeSkillStore">
              <X :size="22" />
            </button>
          </div>
        </header>
        <div v-if="skillSyncStatus" class="skill-store-sync-note">
          {{ skillSyncStatus }}
        </div>

        <div class="skill-store-grid">
          <article
            v-for="skill in skillLibrary"
            :key="`store_${skill.id}`"
            class="skill-store-card"
            :class="{ installed: isSkillInstalled(skill.id) }"
          >
            <div class="skill-store-card-top">
              <div class="skill-store-icon" :class="{ installed: isSkillInstalled(skill.id) }">
                <component :is="skill.icon" :size="18" />
              </div>
              <span v-if="isSkillInstalled(skill.id)" class="skill-store-installed-badge">
                <CheckCircle2 :size="12" />
                Installed
              </span>
            </div>
            <h4>{{ skill.name }}</h4>
            <p>{{ skill.description }}</p>
            <div
              class="skill-runtime-chip"
              :class="getSkillRuntimeClass(skill)"
            >
              <strong>{{ getSkillRuntimeLabel(skill) }}</strong>
              <span>{{ getSkillRuntimeDetail(skill) }}</span>
            </div>
            <button
              type="button"
              class="skill-store-action"
              :class="{ uninstall: isSkillInstalled(skill.id) }"
              :disabled="isSavingStore"
              @click="toggleStoreSkill(skill.id)"
            >
              {{ isSkillInstalled(skill.id) ? "Uninstall" : "Install Skill" }}
            </button>
          </article>
        </div>

        <footer class="skill-store-footer">
          <button type="button" class="skill-store-done" @click="closeSkillStore">
            Done
          </button>
        </footer>
      </section>
    </div>
  </section>
</template>
