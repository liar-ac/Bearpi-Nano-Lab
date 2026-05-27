<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  content: string;
  dataSource?: string;
}>();

const sourceLabel = computed(() => {
  switch (props.dataSource) {
    case 'demo': return '数据来源：演示数据库';
    case 'live': return '数据来源：实时开发板';
    default: return '';
  }
});

interface TextSegment {
  type: 'text' | 'bold' | 'code' | 'link';
  content: string;
  href?: string;
}

interface Line {
  type: 'p' | 'li' | 'codeblock' | 'heading';
  segments: TextSegment[];
  raw: string;
  level?: number;
}

function parseInline(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  // Match **bold**, `code`, [text](url)
  const regex = /(\*\*(.+?)\*\*)|(`(.+?)`)|(\[(.+?)\]\((.+?)\))/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    if (match[1]) {
      segments.push({ type: 'bold', content: match[2] });
    } else if (match[3]) {
      segments.push({ type: 'code', content: match[4] });
    } else if (match[5]) {
      segments.push({ type: 'link', content: match[6], href: match[7] });
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }
  return segments.length ? segments : [{ type: 'text', content: text }];
}

function parseLines(raw: string): Line[] {
  const lines: Line[] = [];
  let inCodeBlock = false;
  let codeBlockContent = '';

  for (const line of raw.split('\n')) {
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        lines.push({ type: 'codeblock', segments: [{ type: 'code', content: codeBlockContent.trim() }], raw: codeBlockContent });
        codeBlockContent = '';
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }
    if (inCodeBlock) {
      codeBlockContent += line + '\n';
      continue;
    }

    const trimmed = line.trim();
    if (!trimmed) continue;

    // Heading: ### text
    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      lines.push({ type: 'heading', segments: parseInline(headingMatch[2]), raw: trimmed, level: headingMatch[1].length });
      continue;
    }

    // Unordered list: - text or * text
    if (trimmed.match(/^[-*]\s+/)) {
      lines.push({ type: 'li', segments: parseInline(trimmed.replace(/^[-*]\s+/, '')), raw: trimmed });
      continue;
    }

    // Ordered list: 1. text
    if (trimmed.match(/^\d+\.\s+/)) {
      lines.push({ type: 'li', segments: parseInline(trimmed.replace(/^\d+\.\s+/, '')), raw: trimmed });
      continue;
    }

    lines.push({ type: 'p', segments: parseInline(trimmed), raw: trimmed });
  }

  // Close unclosed code block
  if (inCodeBlock && codeBlockContent.trim()) {
    lines.push({ type: 'codeblock', segments: [{ type: 'code', content: codeBlockContent.trim() }], raw: codeBlockContent });
  }

  return lines;
}

const parsedLines = computed(() => parseLines(props.content));
</script>

<template>
  <view class="md-body">
    <template v-for="(line, idx) in parsedLines" :key="idx">
      <view v-if="line.type === 'heading'" :class="['md-heading', `md-h${line.level}`]">
        <template v-for="(seg, si) in line.segments" :key="si">
          <text v-if="seg.type === 'bold'" class="md-bold">{{ seg.content }}</text>
          <text v-else-if="seg.type === 'code'" class="md-code">{{ seg.content }}</text>
          <text v-else>{{ seg.content }}</text>
        </template>
      </view>

      <view v-else-if="line.type === 'li'" class="md-li">
        <text class="md-li-dot">-</text>
        <view class="md-li-content">
          <template v-for="(seg, si) in line.segments" :key="si">
            <text v-if="seg.type === 'bold'" class="md-bold">{{ seg.content }}</text>
            <text v-else-if="seg.type === 'code'" class="md-code">{{ seg.content }}</text>
            <text v-else>{{ seg.content }}</text>
          </template>
        </view>
      </view>

      <view v-else-if="line.type === 'codeblock'" class="md-codeblock">
        <text>{{ line.segments[0].content }}</text>
      </view>

      <view v-else class="md-p">
        <template v-for="(seg, si) in line.segments" :key="si">
          <text v-if="seg.type === 'bold'" class="md-bold">{{ seg.content }}</text>
          <text v-else-if="seg.type === 'code'" class="md-code">{{ seg.content }}</text>
          <text v-else>{{ seg.content }}</text>
        </template>
      </view>
    </template>
  </view>

  <view v-if="sourceLabel" class="source-tag">
    <text>{{ sourceLabel }}</text>
  </view>
</template>

<style lang="scss" scoped>
.md-body {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.md-p {
  line-height: 1.7;
  font-size: 26rpx;
  color: #172033;
}

.md-heading {
  font-weight: 800;
  color: #172033;
}

.md-h1 { font-size: 34rpx; margin: 12rpx 0 8rpx; }
.md-h2 { font-size: 30rpx; margin: 10rpx 0 6rpx; }
.md-h3 { font-size: 28rpx; margin: 8rpx 0 4rpx; }

.md-li {
  display: flex;
  flex-direction: row;
  gap: 8rpx;
  padding-left: 12rpx;
}

.md-li-dot {
  color: #5b6770;
  font-size: 26rpx;
  line-height: 1.7;
}

.md-li-content {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  line-height: 1.7;
  font-size: 26rpx;
  color: #172033;
}

.md-bold {
  font-weight: 800;
  color: #172033;
  font-size: 26rpx;
}

.md-code {
  padding: 2rpx 8rpx;
  border-radius: 4rpx;
  background: #eef3fb;
  color: #245d99;
  font-size: 24rpx;
  font-family: monospace;
}

.md-codeblock {
  padding: 16rpx;
  margin: 8rpx 0;
  border-radius: 8rpx;
  background: #f0f2f5;
  border: 1rpx solid $uni-border-color;

  text {
    font-family: monospace;
    font-size: 24rpx;
    color: #172033;
    line-height: 1.5;
  }
}

.source-tag {
  margin-top: 12rpx;

  text {
    padding: 4rpx 14rpx;
    border-radius: 999rpx;
    background: #fff7e6;
    color: #9a5b00;
    font-size: 22rpx;
    font-weight: 700;
  }
}
</style>
