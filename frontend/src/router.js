import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

// nginx already serves /index.html for unmatched paths (try_files ... /index.html),
// so history mode needs no server change.
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: App },
    {
      path: '/drift',
      name: 'drift',
      // Split out: the dashboard should not carry the audio engine's weight.
      component: () => import('./views/Drift.vue')
    },
    // /logs is a plain href in the dashboard and used to land here by way of
    // nginx's index.html fallback. Keep that: without it the router matches
    // nothing and renders a blank page where the dashboard used to be.
    { path: '/:pathMatch(.*)*', component: App }
  ]
})
