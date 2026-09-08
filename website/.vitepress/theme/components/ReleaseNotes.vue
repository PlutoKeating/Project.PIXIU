<script setup lang="ts">
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
const props = defineProps<{ body: string }>();
// Release bodies are untrusted data, never compiled as Vue/MDX or raw HTML.
const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
const html = computed(() =>
  DOMPurify.sanitize(md.render(props.body), {
    USE_PROFILES: { html: true },
    FORBID_TAGS: ['img', 'video', 'audio', 'iframe', 'style', 'form', 'input'],
    FORBID_ATTR: ['style'],
  }),
);
</script>
<template><div class="vp-doc release-notes" v-html="html" /></template>
