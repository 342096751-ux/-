<script setup>
import WorkflowManager from "../components/WorkflowManager.vue";

defineProps({
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

defineEmits(["create", "update", "delete", "select", "add-agent", "edit-agent"]);
</script>

<template>
  <WorkflowManager
    :templates="templates"
    :agents="agents"
    :workflows="workflows"
    :selected-workflow-id="selectedWorkflowId"
    @create="$emit('create', $event)"
    @update="$emit('update', $event)"
    @delete="$emit('delete', $event)"
    @select="$emit('select', $event)"
    @add-agent="$emit('add-agent')"
    @edit-agent="$emit('edit-agent', $event)"
  />
</template>
