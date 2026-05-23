import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/store/user'

const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    redirect: '/chat'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue')
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/chat/index.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  const token = localStorage.getItem('token')
  
  if (to.name !== 'Login' && to.name !== 'Register' && !token) {
    next({ name: 'Login' })
  } else {
    if (token && !userStore.userInfo) {
      await userStore.fetchUserInfo()
    }
    next()
  }
})

export default router
