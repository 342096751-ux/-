<script setup>
import { inject } from "vue";
import { Bot, Gavel, Scale, Search } from "lucide-vue-next";
import { I18N_KEY } from "../../i18n";

const i18n = inject(I18N_KEY, null);
const t = i18n?.t || ((k) => k);
</script>

<template>
  <div class="audit-page">
    <header class="page-head">
      <h2>{{ t("audit.unitsTitle") }}</h2>
      <p class="page-desc">{{ t("audit.unitsDesc") }}</p>
    </header>

    <div class="unit-grid">
      <article class="glass-panel unit-card">
        <div class="unit-icon"><Search :size="20" /></div>
        <h3>{{ t("audit.intentAnalyst") }}</h3>
        <p>{{ t("audit.intentAnalystDesc") }}</p>
        <code>audit_system/agents/intent_analyst.py</code>
      </article>

      <article class="glass-panel unit-card">
        <div class="unit-icon"><Bot :size="20" /></div>
        <h3>{{ t("audit.workUnits") }}</h3>
        <p>{{ t("audit.workUnitsDesc") }}</p>
        <code>audit_system/agents/work_unit.py</code>
        <p class="hint">{{ t("audit.promptsHint") }}</p>
      </article>

      <article class="glass-panel unit-card">
        <div class="unit-icon"><Scale :size="20" /></div>
        <h3>{{ t("audit.verifier") }}</h3>
        <p>{{ t("audit.verifierDesc") }}</p>
        <code>audit_system/agents/verifier.py</code>
      </article>

      <article class="glass-panel unit-card">
        <div class="unit-icon"><Gavel :size="20" /></div>
        <h3>{{ t("audit.arbiter") }}</h3>
        <p>{{ t("audit.arbiterDesc") }}</p>
        <code>audit_system/arbiter.py</code>
      </article>
    </div>

    <section class="glass-panel meta-block">
      <h4>{{ t("audit.coreFiles") }}</h4>
      <ul>
        <li><code>audit_system/orchestrator.py</code> — {{ t("audit.orchestratorBlurb") }}</li>
        <li><code>audit_system/llm_utils.py</code> — LLM + JSON</li>
        <li><code>audit_system/config.py</code> — {{ t("audit.configBlurb") }}</li>
        <li><code>audit_system/prompts/*.txt</code> — {{ t("audit.promptsBlurb") }}</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.audit-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 4px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-head h2 {
  margin: 0 0 6px;
  font-size: 1.25rem;
}

.page-desc {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
  line-height: 1.5;
}

.unit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.unit-card {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.unit-card h3 {
  margin: 0;
  font-size: 0.95rem;
}

.unit-card p {
  margin: 0;
  font-size: 0.8rem;
  color: #475569;
  line-height: 1.45;
}

.unit-icon {
  color: #2563eb;
  margin-bottom: 4px;
}

.unit-card code,
.meta-block code {
  font-size: 0.72rem;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}

.hint {
  font-size: 0.75rem;
  color: #94a3b8;
}

.meta-block {
  padding: 14px 16px;
}

.meta-block h4 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}

.meta-block ul {
  margin: 0;
  padding-left: 18px;
  font-size: 0.82rem;
  color: #334155;
  line-height: 1.6;
}
</style>
