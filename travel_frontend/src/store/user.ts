import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getUserInfo, type UserInfo } from '@/api/user'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token') || null)
  const userInfo = ref<UserInfo | null>(null)

  const setToken = (newToken: string) => {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  const setUserInfo = (info: UserInfo) => {
    userInfo.value = info
  }

  const fetchUserInfo = async () => {
    if (!token.value) {
      return null
    }
    try {
      const res: any = await getUserInfo()
      userInfo.value = res.data
      return res.data
    } catch (error) {
      console.error('获取用户信息失败', error)
      return null
    }
  }

  const logout = () => {
    token.value = null
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, setToken, setUserInfo, fetchUserInfo, logout }
})
