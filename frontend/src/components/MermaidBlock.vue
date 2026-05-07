<script setup>
import mermaid from "mermaid";
import { nextTick, onBeforeUnmount, ref, watch } from "vue";

const props = defineProps({
  code: { type: String, default: "" },
});

const host = ref(null);
let seq = 0;
let inited = false;

function initOnce() {
  if (inited) return;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    theme: "neutral",
    flowchart: { useMaxWidth: true, htmlLabels: true },
  });
  inited = true;
}

async function draw() {
  const raw = String(props.code || "").trim();
  if (!host.value) return;
  host.value.innerHTML = "";
  if (!raw) return;
  initOnce();
  try {
    seq += 1;
    const id = `mmd-${Date.now()}-${seq}`;
    const { svg } = await mermaid.render(id, raw);
    host.value.innerHTML = svg;
  } catch {
    host.value.innerHTML = "<p class='mermaid-err'>Mermaid 渲染失败</p>";
  }
}

watch(
  () => props.code,
  () => {
    nextTick(draw);
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  if (host.value) host.value.innerHTML = "";
});
</script>

<template>
  <div class="mermaid-block">
    <div ref="host" class="mermaid-host" />
  </div>
</template>

<style scoped>
.mermaid-block {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 8px;
}

.mermaid-host :deep(svg) {
  max-width: 100%;
  height: auto;
}

.mermaid-err {
  margin: 0;
  font-size: 0.8rem;
  color: #b91c1c;
}
</style>
