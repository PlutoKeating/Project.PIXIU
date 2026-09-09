<script setup lang="ts">
import { onMounted, ref, watch, useId } from 'vue';
import { useData } from 'vitepress';
const props = defineProps<{ source: string }>();
const { isDark } = useData();
const svg = ref('');
const error = ref(false);
const id = `diagram-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
let generation = 0;
async function render() {
  const current = ++generation;
  try {
    const { default: mermaid } = await import('mermaid');
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: isDark.value ? 'dark' : 'neutral',
      fontFamily: 'system-ui, sans-serif',
    });
    const result = await mermaid.render(`${id}-${current}`, decodeURIComponent(props.source));
    if (current === generation) {
      svg.value = result.svg;
      error.value = false;
    }
  } catch {
    if (current === generation) error.value = true;
  }
}
onMounted(render);
watch([isDark, () => props.source], render);
</script>

<template>
  <figure class="diagram">
    <div
      v-if="svg && !error"
      class="diagram-svg"
      role="img"
      aria-label="文档流程图，下方可展开文字源码"
      v-html="svg"
    />
    <p v-else role="status">{{ error ? '图表渲染失败，请查看下方文字源码。' : '正在绘制图表…' }}</p>
    <details>
      <summary>查看图表源码</summary>
      <pre>{{ decodeURIComponent(source) }}</pre>
    </details>
  </figure>
</template>
