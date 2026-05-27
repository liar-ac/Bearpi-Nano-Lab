<script setup lang="ts">
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import { computed } from 'vue';

const props = defineProps<{
  content: string;
  dataSource?: string;
}>();

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: false,
  breaks: true,
});

const rendered = computed(() => {
  if (!props.content) return '';
  return DOMPurify.sanitize(md.render(props.content));
});

const sourceLabel = computed(() => {
  switch (props.dataSource) {
    case 'demo': return '数据来源：演示数据库';
    case 'live': return '数据来源：实时开发板';
    case 'empty': return '当前无设备接入';
    default: return '';
  }
});

const sourceType = computed(() => {
  switch (props.dataSource) {
    case 'demo': return 'warning';
    case 'live': return 'success';
    case 'empty': return 'info';
    default: return '';
  }
});
</script>

<template>
  <div class="markdown-body" v-html="rendered" />
  <div v-if="sourceLabel" :class="['source-tag', `source-${sourceType}`]">
    {{ sourceLabel }}
  </div>
</template>

<style scoped>
.markdown-body {
  line-height: 1.7;
  font-size: 14px;
  color: var(--text);
  word-wrap: break-word;
  overflow-wrap: anywhere;
}

.markdown-body :deep(p) {
  margin: 0 0 10px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(strong) {
  font-weight: 800;
  color: var(--text);
}

.markdown-body :deep(em) {
  font-style: italic;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(56, 189, 248, 0.1);
  color: var(--cyan);
  font-family: "Fira Code", Consolas, monospace;
  font-size: 13px;
}

.markdown-body :deep(pre) {
  margin: 10px 0;
  padding: 14px;
  overflow-x: auto;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border);
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: var(--text);
  font-size: 13px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(a) {
  color: var(--cyan);
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  margin: 12px 0;
  border: none;
  border-top: 1px solid var(--border);
}

.markdown-body :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  border-left: 3px solid var(--cyan);
  background: rgba(56, 189, 248, 0.05);
  color: var(--text-muted);
}

.source-tag {
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  display: inline-block;
}

.source-warning {
  color: #9a5b00;
  background: rgba(246, 184, 75, 0.12);
}

.source-success {
  color: #2f7d32;
  background: rgba(45, 212, 125, 0.12);
}

.source-info {
  color: var(--text-muted);
  background: rgba(155, 170, 180, 0.1);
}
</style>
