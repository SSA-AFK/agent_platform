<template>
  <div class="auth-container">
    <div class="auth-card">
      <div class="auth-header">
        <div class="logo">
          <div class="logo-circle"></div>
          <h2>创建账号</h2>
        </div>
        <p class="subtitle">开启您的专属旅游规划之旅</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" class="auth-form" @submit.prevent>
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input 
            v-model="form.password" 
            type="password" 
            placeholder="请输入密码" 
            size="large" 
            show-password
            :prefix-icon="Lock"
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input 
            v-model="form.confirmPassword" 
            type="password" 
            placeholder="请再次确认密码" 
            size="large" 
            show-password
            :prefix-icon="Lock"
            @keyup.enter="handleRegister"
          />
        </el-form-item>

        <el-button 
          type="primary" 
          class="submit-btn" 
          size="large" 
          :loading="loading" 
          @click="handleRegister"
        >
          立即注册
        </el-button>
        
        <div class="auth-links">
          <span class="hint">已有账号？</span>
          <router-link to="/login" class="link">去登录</router-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store/user'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { User, Lock } from 'lucide-vue-next'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const validatePass2 = (rule: any, value: any, callback: any) => {
  if (value === '') {
    callback(new Error('请再次输入密码'))
  } else if (value !== form.password) {
    callback(new Error('两次输入密码不一致!'))
  } else {
    callback()
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  confirmPassword: [{ required: true, validator: validatePass2, trigger: 'blur' }]
}

const handleRegister = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const res: any = await request.post('/api/user/register', {
          username: form.username,
          password: form.password
        })
        userStore.setToken(res.data.token)
        userStore.setUserInfo(res.data.userInfo)
        ElMessage.success('注册成功')
        router.push('/chat')
      } catch (error) {
        console.error(error)
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped lang="scss">
/* 注册页面样式与登录页基本一致 */
.auth-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
}

.auth-card {
  width: 100%;
  max-width: 400px;
  background: #ffffff;
  border-radius: 24px;
  padding: 48px 40px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.04);
  margin: 20px;
  transition: transform 0.3s ease;
  
  &:hover {
    transform: translateY(-4px);
  }
}

.auth-header {
  text-align: center;
  margin-bottom: 40px;

  .logo {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 12px;

    .logo-circle {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, var(--el-color-primary), #b3caff);
      border-radius: 50%;
    }

    h2 {
      margin: 0;
      font-size: 28px;
      font-weight: 700;
      color: #1a1a1a;
      letter-spacing: -0.5px;
    }
  }

  .subtitle {
    margin: 0;
    color: #888;
    font-size: 14px;
  }
}

.auth-form {
  .el-form-item {
    margin-bottom: 24px;
  }
  
  .submit-btn {
    width: 100%;
    margin-top: 12px;
    border-radius: 12px;
    height: 48px;
    font-size: 16px;
    background: linear-gradient(135deg, var(--el-color-primary), #a8c4ff);
    border: none;
    
    &:hover {
      background: linear-gradient(135deg, #7a9fef, #9ab7f5);
      box-shadow: 0 8px 16px rgba(138, 175, 255, 0.3);
    }
  }
}

.auth-links {
  margin-top: 24px;
  text-align: center;
  font-size: 14px;

  .hint {
    color: #888;
  }

  .link {
    color: var(--el-color-primary);
    text-decoration: none;
    font-weight: 600;
    margin-left: 4px;
    
    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
