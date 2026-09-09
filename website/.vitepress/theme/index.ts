import DefaultTheme from 'vitepress/theme';
import type { Theme } from 'vitepress';
import Landing from './components/Landing.vue';
import ReleaseBrowser from './components/ReleaseBrowser.vue';
import MemoryDemo from './components/MemoryDemo.vue';
import Diagram from './components/Diagram.vue';
import './style.css';
export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Landing', Landing);
    app.component('ReleaseBrowser', ReleaseBrowser);
    app.component('MemoryDemo', MemoryDemo);
    app.component('Diagram', Diagram);
  },
} satisfies Theme;
