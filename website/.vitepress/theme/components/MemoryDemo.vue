<script setup lang="ts">
import { computed, ref } from 'vue';
const props = withDefaults(defineProps<{ compact?: boolean }>(), { compact: false });
const stage = ref(0);
const tabs = ['记住', '找回', '更正', '遗忘'];
const bills = ref([
  { name: '电费', amount: 210 },
  { name: '水费', amount: 68.5 },
  { name: '燃气费', amount: 156 },
]);
const total = computed(() => bills.value.reduce((sum, item) => sum + item.amount, 0).toFixed(2));
const amount = ref(186);
const updated = ref(false);
const forgotten = ref(false);
const preview = ref(false);
const evidence = ref(false);
function update() {
  if (!Number.isFinite(amount.value) || amount.value < 0 || amount.value > 1000000) return;
  bills.value[2].amount = amount.value;
  updated.value = true;
  forgotten.value = false;
}
function reset() {
  bills.value[2].amount = 156;
  amount.value = 186;
  updated.value = false;
  forgotten.value = false;
  preview.value = false;
  stage.value = 0;
}
</script>

<template>
  <div class="memory-demo" :class="{ compact }">
    <div class="demo-toolbar">
      <span><span class="status-dot" /> 记忆体验台</span
      ><span class="demo-label">网页交互演示 · 合成数据</span>
    </div>
    <div class="demo-body">
      <div class="demo-sidebar">
        <img src="/logo.svg" alt="" width="32" height="32" /><strong>一段记忆的旅程</strong
        ><button
          v-for="(tab, index) in tabs"
          :key="tab"
          :aria-pressed="stage === index"
          @click="stage = index"
        >
          <span>0{{ index + 1 }}</span
          >{{ tab }}<span aria-hidden="true">↗</span>
        </button>
        <div class="demo-scope">作用域<br /><code>shared:home</code><br />仅模拟共享流程</div>
      </div>
      <div class="demo-conversation" aria-live="polite">
        <div class="demo-context"><span>家庭支出</span><span>来源可追溯</span></div>
        <template v-if="stage === 0"
          ><p class="demo-question">帮我记住这份家庭支出清单。</p>
          <div class="demo-answer">
            <span class="answer-mark">P</span>
            <div>
              <strong>零散的信息，成为下次可用的记忆。</strong>
              <p>这份示例清单包含电费、水费和燃气费。切换到「找回」，查看计算结果与来源。</p>
              <div class="mini-bills">
                <div v-for="bill in bills" :key="bill.name">
                  <span>{{ bill.name }}</span
                  ><strong>¥ {{ bill.amount.toFixed(2) }}</strong>
                </div>
              </div>
            </div>
          </div></template
        >
        <template v-else-if="stage === 1"
          ><p class="demo-question">家里水电燃气一共花了多少钱？</p>
          <div class="demo-answer">
            <span class="answer-mark">P</span>
            <div v-if="!forgotten">
              <strong
                >合计 <span class="amount">¥ {{ total }}</span></strong
              >
              <p>
                根据这份家庭支出清单计算。{{
                  updated ? '已使用更正后的燃气费。' : '你不需要记住原来的关键词。'
                }}
              </p>
              <button
                class="evidence-button"
                :aria-expanded="evidence"
                @click="evidence = !evidence"
              >
                ▤ 查看来源清单 <span>↗</span>
              </button>
              <div v-if="evidence" class="mini-bills">
                <div v-for="bill in bills" :key="bill.name">
                  <span>{{ bill.name }}</span
                  ><strong>¥ {{ bill.amount.toFixed(2) }}</strong>
                </div>
              </div>
            </div>
            <div v-else>
              <strong>这条记忆已在演示中隐藏。</strong>
              <p>点击重新体验，恢复初始示例。</p>
            </div>
          </div></template
        >
        <template v-else-if="stage === 2"
          ><p class="demo-question">燃气费记错了，帮我更正一下。</p>
          <div class="demo-answer">
            <span class="answer-mark">P</span>
            <div>
              <strong>让记忆跟上变化。</strong>
              <p>修改金额后返回「找回」，合计会随之变化。</p>
              <form class="demo-form" @submit.prevent="update">
                <label
                  >燃气费（元）<input
                    v-model.number="amount"
                    type="number"
                    min="0"
                    max="1000000"
                    step="0.01"
                    required /></label
                ><button class="button small" type="submit">保存更正</button>
              </form>
              <p v-if="updated" class="success-text">已更正 · 当前合计 ¥ {{ total }}</p>
            </div>
          </div></template
        >
        <template v-else
          ><p class="demo-question">忘记这份家庭支出清单。</p>
          <div class="demo-answer">
            <span class="answer-mark">P</span>
            <div>
              <strong>先看范围，再做决定。</strong>
              <p>示例只影响当前网页中的这一条记忆。实际产品遗忘不等于原始数据全部物理擦除。</p>
              <button
                v-if="!preview && !forgotten"
                class="button small secondary"
                @click="preview = true"
              >
                预览遗忘范围
              </button>
              <div v-if="preview && !forgotten" class="forget-preview">
                <p>将隐藏：家庭支出清单（1 条）</p>
                <button
                  class="button small"
                  @click="
                    forgotten = true;
                    preview = false;
                  "
                >
                  确认遗忘</button
                ><button class="text-button" @click="preview = false">取消</button>
              </div>
              <p v-if="forgotten" class="success-text">已隐藏。可切换「找回」检查结果。</p>
            </div>
          </div></template
        >
        <div class="demo-bottom">
          <span>在这个页面，亲手试一试。</span
          ><button class="text-button" @click="reset">重新体验 ↺</button>
        </div>
      </div>
    </div>
    <p v-if="!props.compact" class="demo-disclaimer">
      本演示在浏览器内计算与切换状态，不连接
      PIXIU、模型或其他设备；刷新即重置。用于解释操作顺序，不代表桌面界面、真实检索效果或同步验收。
    </p>
  </div>
</template>
