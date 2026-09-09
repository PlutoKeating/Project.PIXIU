<script setup lang="ts">
import MemoryDemo from './MemoryDemo.vue';
import { site } from '../lib/site';
const features = [
  {
    no: '01',
    label: 'CAPTURE',
    title: '值得记住的，都有来处。',
    text: '从确认过的事实、对话与工具结果中沉淀知识。查看原始证据，把答案和来源连在一起。',
    link: '/docs/guide/memory',
    cta: '了解记忆与证据',
    icon: '▤',
  },
  {
    no: '02',
    label: 'RECALL',
    title: '不必记得，你是怎么说的。',
    text: '关键词、语义和实体关系协同检索。从模糊的线索出发，找回相关信息。',
    link: '/docs/concepts/architecture',
    cta: '了解混合检索',
    icon: '⌕',
  },
  {
    no: '03',
    label: 'CONTROL',
    title: '记住什么，由你掌握。',
    text: '私人记忆留在本机，共享范围由你选择。更正可回溯，遗忘先预览，采集需要主动开启。',
    link: '/docs/guide/privacy',
    cta: '了解隐私控制',
    icon: '◎',
  },
];
</script>

<template>
  <main class="landing">
    <section class="hero section-wrap">
      <div class="eyebrow"><span class="status-dot" /> 为你的 Agent，接上记忆。</div>
      <h1>
        让记忆，<br /><span class="hero-second">随你而行<span class="blue-period">。</span></span>
      </h1>
      <p class="hero-description">
        你说过的偏好，做过的事，值得留住的知识。<br
          class="desktop-break"
        />让它们在可信设备间相通，成为下一次对话的起点。
      </p>
      <div class="hero-actions">
        <a class="button" href="/download">下载 PIXIU <span aria-hidden="true">↗</span></a
        ><a class="button secondary" href="/docs/start/install"
          >从这里开始 <span aria-hidden="true">→</span></a
        >
      </div>
      <div class="hero-platforms">
        <span>银河麒麟优先</span><span>本地记忆</span><span>开放源码</span>
      </div>
      <div class="hero-orbit" aria-hidden="true">
        <div class="orbit-ring one" />
        <div class="orbit-ring two" />
        <div class="orbit-ring three" />
        <span class="orbit-node n1" /><span class="orbit-node n2" /><span
          class="orbit-node n3"
        /><span class="orbit-core"><img src="/logo.svg" alt="" /></span
        ><span class="orbit-caption c1">书房 · 工作站</span
        ><span class="orbit-caption c2">客厅 · 一体机</span
        ><span class="orbit-caption c3">随身 · 笔记本</span>
      </div>
    </section>
    <section class="experience section-wrap" aria-labelledby="experience-title">
      <div class="section-kicker">
        <span>一段记忆，更多可能</span><a href="/docs/start/playground">打开完整演示 ↗</a>
      </div>
      <h2 id="experience-title" class="sr-only">交互式记忆演示</h2>
      <MemoryDemo compact />
      <p class="visual-caption">
        可操作的网页演示 · 使用合成数据说明记忆流程，不连接桌面软件或真实设备。
      </p>
    </section>
    <div class="principle-strip section-wrap">
      <span>不止于一次对话</span>
      <p>从「告诉过你」，<br class="mobile-break" />到「你还记得」。</p>
      <a href="/docs/">认识 PIXIU ↗</a>
    </div>
    <section class="features section-wrap" aria-labelledby="features-title">
      <div class="section-heading">
        <p class="eyebrow">BUILT AROUND MEMORY</p>
        <h2 id="features-title">把记忆变成<br />真正可用的东西。</h2>
      </div>
      <div class="feature-grid">
        <article v-for="feature in features" :key="feature.no">
          <div class="feature-top">
            <span>{{ feature.no }} / {{ feature.label }}</span
            ><span class="feature-icon" aria-hidden="true">{{ feature.icon }}</span>
          </div>
          <h3>{{ feature.title }}</h3>
          <p>{{ feature.text }}</p>
          <a :href="feature.link">{{ feature.cta }} <span>↗</span></a>
        </article>
      </div>
    </section>
    <section class="network-section">
      <div class="section-wrap network-grid">
        <div>
          <p class="eyebrow">YOUR DEVICES. CONNECTED.</p>
          <h2>换一台设备，<br />不用从头说起。</h2>
          <p class="section-description">
            让书房、客厅和随身设备，拥有共同的记忆。<br />可信配对后，共享记忆在设备间直接同步；<br />离线时继续使用本地记忆，重连后再对账。
          </p>
          <a class="button secondary" href="/docs/guide/sync">了解多设备同步 <span>↗</span></a>
        </div>
        <div
          class="network-visual"
          role="img"
          aria-label="原理示意：三台可信设备对等同步共享记忆，私人记忆保留本机"
        >
          <svg viewBox="0 0 460 310" aria-hidden="true">
            <path
              d="M230 55L65 248H395Z"
              fill="none"
              stroke="currentColor"
              stroke-width="1"
              stroke-dasharray="5 7"
            />
            <circle cx="230" cy="158" r="47" fill="none" stroke="currentColor" opacity=".25" />
          </svg>
          <div class="device workstation">
            <span>▱</span><strong>书房工作站</strong><small>共享记忆</small>
          </div>
          <div class="device living">
            <span>▱</span><strong>客厅一体机</strong><small>可信设备</small>
          </div>
          <div class="device laptop">
            <span>▱</span><strong>随身笔记本</strong><small>本地副本</small>
          </div>
          <span class="network-center">P2P<br /><small>无中心节点</small></span>
        </div>
      </div>
    </section>
    <section class="guide-section section-wrap">
      <div>
        <p class="eyebrow">A LITTLE GUIDE GOES A LONG WAY</p>
        <h2>从第一次记住，<br />到每一天用得上。</h2>
        <p class="section-description">
          分步手册、流程图与交互示例，<br />帮你理解每一次记忆的来龙去脉。
        </p>
      </div>
      <div class="guide-links">
        <a href="/docs/start/install"
          ><span><small>01 / GET STARTED</small><strong>安装，开始你的第一段记忆</strong></span
          ><span>↗</span></a
        ><a href="/docs/guide/agent"
          ><span><small>02 / EVERYDAY USE</small><strong>在 Agent 中工作与思考</strong></span
          ><span>↗</span></a
        ><a href="/docs/guide/privacy"
          ><span><small>03 / STAY IN CONTROL</small><strong>管理采集、共享与遗忘</strong></span
          ><span>↗</span></a
        >
      </div>
    </section>
    <section class="closing section-wrap">
      <img src="/logo.svg" width="52" height="52" alt="" />
      <h2>下一次，<br />从记得开始。</h2>
      <div class="hero-actions">
        <a class="button" href="/download">获取 PIXIU ↗</a
        ><a class="text-button" :href="site.github" target="_blank" rel="noopener noreferrer"
          >在 GitHub 探索源码 ↗</a
        >
      </div>
      <p>面向银河麒麟 · 保留 Debian 系核心能力降级路径</p>
    </section>
  </main>
</template>
