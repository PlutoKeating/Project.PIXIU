<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { site } from '../lib/site';
import {
  latestRelease,
  listReleases,
  ReleaseError,
  githubUrl,
  formatBytes,
  type Release,
} from '../lib/releases';
import ReleaseNotes from './ReleaseNotes.vue';
const props = defineProps<{ mode: 'download' | 'history' }>();
const releases = ref<Release[]>([]);
const loading = ref(true);
const error = ref('');
const page = ref(1);
const next = ref(false);
const includePreview = ref(true);
const checkedAt = ref('');
let controller: AbortController | undefined;
const visible = computed(() => releases.value.filter((r) => includePreview.value || !r.prerelease));
async function load(more = false) {
  controller?.abort();
  controller = new AbortController();
  const current = controller;
  const timer = setTimeout(() => current.abort('timeout'), 15000);
  loading.value = true;
  error.value = '';
  try {
    if (props.mode === 'download') releases.value = [await latestRelease(current.signal)];
    else {
      const target = more ? page.value + 1 : 1;
      const result = await listReleases(target, current.signal);
      releases.value = more
        ? [...new Map([...releases.value, ...result.releases].map((r) => [r.id, r])).values()]
        : result.releases;
      page.value = target;
      next.value = result.next;
    }
    checkedAt.value = new Date().toLocaleString('zh-CN');
  } catch (e) {
    if (current !== controller) return;
    if (current.signal.aborted) error.value = '请求超时，请检查网络后重试。';
    else if (e instanceof ReleaseError) {
      const messages = {
        rate: `GitHub 请求额度暂时用尽。${e.reset ? `可在 ${e.reset.toLocaleString('zh-CN')} 后重试。` : '请稍后重试。'}`,
        missing:
          props.mode === 'download'
            ? '未找到公开的正式版。可能尚未发布，或仓库暂时不可访问。'
            : '无法访问公开发布记录，请确认仓库可见性。',
        network: '无法连接 GitHub。请检查网络后重试。',
        invalid: 'GitHub 返回的数据格式不符合预期，暂不提供下载。',
        server: 'GitHub 暂时无法提供发布数据，请稍后重试。',
      };
      error.value = messages[e.kind];
    } else error.value = '发布数据读取失败，请重试。';
  } finally {
    clearTimeout(timer);
    if (current === controller) loading.value = false;
  }
}
onMounted(() => load());
onBeforeUnmount(() => {
  controller?.abort();
  controller = undefined;
});
const date = (value: string | null) =>
  value
    ? new Date(value).toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '未提供发布时间';
</script>

<template>
  <main class="release-page section-wrap">
    <div class="release-heading">
      <p class="eyebrow">{{ mode === 'download' ? 'GET PIXIU' : 'RELEASE NOTES' }}</p>
      <h1>{{ mode === 'download' ? '从这里，开始。' : '每一步，都有记录。' }}</h1>
      <p>
        {{
          mode === 'download'
            ? '获取公开正式版，查看发布说明与随版附件。'
            : '浏览公开发布记录，了解每一次变化。'
        }}
      </p>
    </div>
    <div class="release-controls">
      <span><span class="status-dot" /> GitHub Releases</span>
      <div>
        <label v-if="mode === 'history'"
          ><input v-model="includePreview" type="checkbox" /> 包含预发布</label
        ><button class="text-button" :disabled="loading" @click="load()">
          {{ loading ? '正在获取…' : '刷新' }}
        </button>
      </div>
    </div>
    <noscript><p>请启用 JavaScript，在线读取 GitHub 版本与下载信息。</p></noscript>
    <div v-if="loading && !releases.length" class="release-state" role="status">
      <span class="loading-line" />
      <p>正在读取公开发布信息…</p>
    </div>
    <div v-if="error" class="release-state error-state" role="alert">
      <h2>暂时无法获取发布信息</h2>
      <p>{{ error }}</p>
      <p v-if="releases.length">下方保留本页上次成功获取的结果，尚未刷新。</p>
      <button class="button small" :disabled="loading" @click="load()">重试</button
      ><a :href="`${site.github}/releases`" target="_blank" rel="noopener noreferrer"
        >前往 GitHub 核对 ↗</a
      >
    </div>
    <div v-if="!loading && !error && !visible.length" class="release-state">
      <h2>{{ releases.length ? '本批次没有符合筛选的版本' : '尚无公开发布记录' }}</h2>
      <p>{{ next ? '可以继续加载历史记录。' : '发布后，信息会自动显示在这里。' }}</p>
    </div>
    <article v-for="release in visible" :key="release.id" class="release-card">
      <div class="release-meta">
        <span class="release-tag">{{ release.tag_name }}</span
        ><span v-if="release.prerelease" class="preview-badge">预发布</span
        ><time :datetime="release.published_at || undefined">{{ date(release.published_at) }}</time>
      </div>
      <h2>{{ release.name || release.tag_name }}</h2>
      <ClientOnly><ReleaseNotes v-if="release.body" :body="release.body" /></ClientOnly>
      <p v-if="!release.body" class="muted">发布者未提供说明。</p>
      <div class="assets-heading">
        <h3>
          发布附件 <span>{{ release.assets.length }}</span>
        </h3>
        <a :href="githubUrl(release.html_url)" target="_blank" rel="noopener noreferrer"
          >原始发布页 ↗</a
        >
      </div>
      <p v-if="!release.assets.length" class="muted">此版本未附带可下载文件。</p>
      <ul v-else class="asset-list">
        <li v-for="asset in release.assets" :key="asset.id">
          <a :href="githubUrl(asset.browser_download_url, true)" rel="noopener noreferrer"
            ><span class="asset-symbol" aria-hidden="true">↓</span
            ><span class="asset-info"
              ><strong>{{ asset.name }}</strong
              ><small v-if="asset.digest">{{ asset.digest }}</small></span
            ><span class="asset-size">{{ formatBytes(asset.size) }}</span></a
          >
        </li>
      </ul>
    </article>
    <button
      v-if="mode === 'history' && next"
      class="button secondary load-more"
      :disabled="loading"
      @click="load(true)"
    >
      {{ loading ? '正在加载…' : '加载更多记录' }}
    </button>
    <p v-if="checkedAt" class="checked-at">
      本页获取时间：{{ checkedAt }} · 版本信息以发布者的 GitHub 记录为准。
    </p>
    <div class="release-help">
      <a href="/docs/start/install">安装与启动指南 ↗</a
      ><a :href="mode === 'download' ? '/releases' : '/download'"
        >{{ mode === 'download' ? '查看全部版本记录' : '获取正式版' }} ↗</a
      >
    </div>
  </main>
</template>
