<script setup>
import { ListChecks, Upload } from "lucide-vue-next";
import { computed, ref } from "vue";
import * as XLSX from "xlsx";

const props = defineProps({
  selectedWorkflowId: { type: String, default: "" },
  batchRunState: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["batch-run"]);

const batch = ref({ concurrency: 2, rawItems: [], sourceName: "" });
const uploaderRef = ref(null);

const parsedItems = computed(() =>
  (batch.value.rawItems || []).map((line) => String(line || "").trim()).filter(Boolean),
);

function parseBatchText(text) {
  const raw = String(text || "").trim();
  if (!raw) return [];
  if (raw.startsWith("[") || raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.map((x) => (typeof x === "string" ? x : x?.input || x?.question || JSON.stringify(x)));
      }
      if (Array.isArray(parsed?.items)) {
        return parsed.items.map((x) => (typeof x === "string" ? x : x?.input || x?.question || JSON.stringify(x)));
      }
    } catch {
      // fallback below
    }
  }
  return raw
    .split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean)
    .map((line) => {
      if (line.includes("\t")) return line.split("\t").pop();
      if (line.includes(",")) return line.split(",").pop();
      return line;
    });
}

function parseSheetRows(rows) {
  if (!Array.isArray(rows) || !rows.length) return [];
  const header = Array.isArray(rows[0]) ? rows[0].map((x) => String(x || "").trim().toLowerCase()) : [];
  const preferredIdx = header.findIndex((key) => ["input", "question", "content", "文本", "问题", "内容"].includes(key));
  const pickLast = (row) => row[row.length - 1];
  return rows
    .slice(header.length ? 1 : 0)
    .map((row) => {
      if (!Array.isArray(row)) return "";
      const val = preferredIdx >= 0 ? row[preferredIdx] : pickLast(row);
      return String(val ?? "").trim();
    })
    .filter(Boolean);
}

function openUploader() {
  uploaderRef.value?.click();
}

function onFileChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  const name = String(file.name || "").toLowerCase();

  if (name.endsWith(".xlsx") || name.endsWith(".xls")) {
    const reader = new FileReader();
    reader.onload = () => {
      const workbook = XLSX.read(reader.result, { type: "array" });
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      const rows = XLSX.utils.sheet_to_json(firstSheet, { header: 1, raw: false });
      batch.value.rawItems = parseSheetRows(rows);
      batch.value.sourceName = file.name;
    };
    reader.readAsArrayBuffer(file);
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    const text = String(reader.result || "");
    batch.value.rawItems = parseBatchText(text);
    batch.value.sourceName = file.name;
  };
  reader.readAsText(file, "utf-8");
}

async function runBatch() {
  if (!props.selectedWorkflowId || !parsedItems.value.length || props.batchRunState?.running) return;
  await emit("batch-run", {
    workflow_id: props.selectedWorkflowId,
    inputs: [...parsedItems.value],
    concurrency: Math.max(1, Math.min(8, Number(batch.value.concurrency || 1))),
  });
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function downloadBatchCsv() {
  const rows = Array.isArray(props.batchRunState?.results) ? props.batchRunState.results : [];
  if (!rows.length) return;
  const header = ["index", "ok", "input", "latencyMs", "routeAgent", "finalizerOutput", "modelDialogue", "assistantOutput", "error", "traceCount"];
  const lines = [header.join(",")];
  rows.forEach((row, idx) => {
    lines.push([
      idx + 1,
      row.ok ? "true" : "false",
      csvEscape(row.input),
      row.latencyMs ?? "",
      csvEscape(row.routeAgent || ""),
      csvEscape(row.finalizerOutput || ""),
      csvEscape(row.modelDialogue || ""),
      csvEscape(row.output || ""),
      csvEscape(row.error || ""),
      row.traceCount ?? 0,
    ].join(","));
  });
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `batch-results-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function clearBatch() {
  batch.value.rawItems = [];
  batch.value.sourceName = "";
  if (uploaderRef.value) uploaderRef.value.value = "";
}
</script>

<template>
  <section class="glass-panel batch-runner-box-right">
    <div class="batch-runner-head">
      <div class="batch-title"><ListChecks :size="14" /> 批量测试</div>
      <button class="ghost-button" type="button" @click="openUploader"><Upload :size="14" /> 上传文件</button>
      <input ref="uploaderRef" type="file" accept=".txt,.csv,.json,.jsonl,.xlsx,.xls" class="hidden-upload" @change="onFileChange" />
    </div>
    <div class="batch-controls">
      <label>
        并发
        <input v-model.number="batch.concurrency" type="number" min="1" max="8" />
      </label>
      <span class="batch-meta">{{ batch.sourceName || "未上传文件" }} · {{ parsedItems.length }} 条</span>
      <button class="ghost-button" type="button" @click="clearBatch">清空</button>
      <button class="ghost-button" type="button" :disabled="!(batchRunState?.results?.length)" @click="downloadBatchCsv">下载结果</button>
      <button class="accent-button accent-button-violet" type="button" :disabled="!parsedItems.length || !selectedWorkflowId || batchRunState?.running" @click="runBatch">
        {{ batchRunState?.running ? `执行中 ${batchRunState.done || 0}/${batchRunState.total || 0}` : "开始批量测试" }}
      </button>
    </div>
    <div v-if="batchRunState?.results?.length" class="batch-result-list">
      <div v-for="(r, idx) in batchRunState.results.slice(0, 12)" :key="idx" class="batch-result-item" :class="{ ok: r.ok, fail: !r.ok }">
        <strong>#{{ idx + 1 }} {{ r.ok ? "成功" : "失败" }}</strong>
        <span class="truncate">{{ r.input }}</span>
        <small v-if="r.ok" class="truncate">Finalizer: {{ r.finalizerOutput || r.output }}</small>
        <small v-if="r.ok && r.modelDialogue" class="truncate">对话: {{ r.modelDialogue }}</small>
        <small v-else-if="!r.ok">{{ r.error }}</small>
      </div>
    </div>
  </section>
</template>

<style scoped>
.batch-runner-box-right {
  min-height: 0;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fbff, #f1f7ff);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.batch-runner-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.batch-title { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; color: #475569; }
.batch-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.batch-controls label { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #64748b; }
.batch-controls input[type="number"] { width: 64px; border: 1px solid #cbd5e1; border-radius: 8px; background: #ffffff; color:#0f172a; padding: 4px 6px; }
.batch-meta { font-size: 11px; color: #64748b; }
.hidden-upload { display: none; }
.batch-result-list { max-height: 210px; overflow: auto; display: flex; flex-direction: column; gap: 6px; }
.batch-result-item { border: 1px solid rgba(148,163,184,.25); border-radius: 8px; padding: 6px; display: flex; flex-direction: column; gap: 2px; }
.batch-result-item.ok { border-color: rgba(52,211,153,.35); }
.batch-result-item.fail { border-color: rgba(248,113,113,.35); }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
