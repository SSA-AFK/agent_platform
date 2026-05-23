import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '',
  timeout: 15000
})

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
    (response) => {
        const res = response.data
        // FastAPI 后端返回格式如果是 { code, message, data }
        if (res.code && res.code !== 200) {
            ElMessage.error(res.message || '请求错误')
            return Promise.reject(new Error(res.message || 'Error'))
        }
        return res
    },
    (error) => {
        if (error.response) {
            const detail = error.response.data?.detail
            if (error.response.status === 401) {
                ElMessage.error(detail || '未授权或登录已过期，请重新登录')
                localStorage.removeItem('token')
                window.location.href = '/login'
            } else {
                ElMessage.error(detail || error.message || '网络错误')
            }
        } else {
            ElMessage.error(error.message || '网络错误')
        }
        return Promise.reject(error)
    }
)

export default request
