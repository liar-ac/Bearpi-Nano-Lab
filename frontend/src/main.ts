import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import App from '@/App.vue';
import { router } from '@/router';
import 'element-plus/dist/index.css';
import 'element-plus/theme-chalk/dark/css-vars.css';
import '@/styles/main.css';
import '@/styles/effects.css';

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app');
