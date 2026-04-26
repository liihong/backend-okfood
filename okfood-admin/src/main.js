import { createApp } from 'vue'
import 'element-plus/dist/index.css'
import './style.css'
import './assets/admin-ui.css'
import './assets/element-plus-okfood-theme.css'
import App from './App.vue'
import router from './router'
import { escClose } from './directives/escClose.js'

const app = createApp(App)
app.use(router)
app.directive('esc-close', escClose)
app.mount('#app')
