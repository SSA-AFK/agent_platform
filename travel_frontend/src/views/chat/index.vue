<template>
  <div class="chat-layout">
    <!-- 左侧会话列表 -->
    <aside class="sidebar">
      <div class="brand">
        <div class="logo"></div>
        <span>Travel AI</span>
      </div>
      
      <div class="new-chat-btn">
        <el-button type="primary" plain class="full-width" @click="handleNewChat" :icon="Plus">
          新建对话
        </el-button>
      </div>

      <div class="session-list">
        <div 
          v-for="session in sessionList" 
          :key="session.session_id"
          class="session-item"
          :class="{ active: currentSessionId === session.session_id }"
          @click="selectSession(session.session_id)"
        >
          <div class="session-title">{{ session.title }}</div>
          <div class="session-actions">
            <el-icon @click.stop="handleDeleteSession(session.session_id)"><Delete /></el-icon>
          </div>
        </div>
        <div v-if="sessionList.length === 0" class="empty-hint">
          暂无历史对话
        </div>
      </div>

      <div class="user-profile">
        <el-dropdown trigger="click">
          <span class="el-dropdown-link">
            <el-avatar :size="32" src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" />
            <span class="username">{{ userStore.userInfo?.username || 'User' }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- 右侧聊天区 -->
    <main class="chat-main">
      <header class="chat-header">
        <h3>智能旅游规划助手</h3>
        <el-tag size="small" type="info">INS 风格</el-tag>
      </header>
      
      <div class="message-list" ref="messageListRef">
        <template v-for="(msg, index) in messages" :key="index">
          <!-- 工具调用状态展示 -->
          <div class="tool-call-wrapper" v-if="msg.toolCall">
            <div class="tool-call-badge">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ msg.toolCall }}</span>
            </div>
          </div>
          
          <div class="message-wrapper" :class="msg.role">
            <el-avatar v-if="msg.role === 'assistant'" :size="36" class="msg-avatar ai-avatar">AI</el-avatar>
            <div class="message-content">
              <!-- 如果是普通文本（包含 Markdown） -->
              <div v-if="msg.content" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
              <!-- 如果包含解析出的地图数据 -->
              <AMapCard v-if="msg.mapData" :mapData="msg.mapData" />
              <!-- 输入中提示（仅在 AI 尚未输出内容时显示） -->
              <div v-if="!msg.content && !msg.mapData && msg.role === 'assistant' && isReceiving && index === messages.length - 1" class="typing-indicator">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </div>
            </div>
            <el-avatar v-if="msg.role === 'user'" :size="36" class="msg-avatar user-avatar">U</el-avatar>
          </div>
        </template>
      </div>

      <footer class="chat-footer">
        <div class="input-container">
          <el-input
            v-model="inputQuery"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            placeholder="问问我去哪儿玩，或者查查天气..."
            @keydown.enter.prevent="sendMessage"
          />
          <el-button type="primary" circle class="send-btn" @click="sendMessage" :disabled="isReceiving || !inputQuery.trim()">
            <el-icon><Position /></el-icon>
          </el-button>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useUserStore } from '@/store/user'
import { useRouter } from 'vue-router'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import MarkdownIt from 'markdown-it'
import AMapCard from '@/components/AMapCard.vue'
import { Loading, Position, Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSessions, createSession, getSessionHistory, deleteSession, type ChatSession, type ChatMessage } from '@/api/chat'

const userStore = useUserStore()
const router = useRouter()
const md = new MarkdownIt({ html: true, breaks: true })

const sessionList = ref<ChatSession[]>([])
const currentSessionId = ref<string | null>(null)

const messages = ref<ChatMessage[]>([])
const inputQuery = ref('')
const isReceiving = ref(false)
const messageListRef = ref<HTMLElement>()

// 初始化
onMounted(async () => {
  await fetchSessions()
  if (sessionList.value.length > 0) {
    await selectSession(sessionList.value[0].session_id)
  } else {
    await handleNewChat()
  }
})

// 获取会话列表
const fetchSessions = async () => {
  try {
    const res: any = await getSessions()
    sessionList.value = res.data
  } catch (error) {
    console.error('获取会话列表失败', error)
  }
}

// 选择某个会话
const selectSession = async (sessionId: string) => {
  if (currentSessionId.value === sessionId) return
  currentSessionId.value = sessionId
  messages.value = [] // 清空当前消息
  try {
    const res: any = await getSessionHistory(sessionId)
    const history = res.data || []
    
    // 如果没有历史记录，添加欢迎语
    if (history.length === 0) {
      messages.value = [{ role: 'assistant', content: '您好！我是您的智能旅游规划助手。您可以问我天气、路线、或者旅游攻略。', toolCall: '' }]
    } else {
      // 遍历解析历史消息中可能包含的地图 JSON
      messages.value = history.map((msg: any) => {
        const cleaned = parseContentAndExtractMap(msg.content, msg)
        return { ...msg, content: cleaned }
      })
    }
    scrollToBottom()
  } catch (error) {
    console.error('获取会话历史失败', error)
  }
}

// 新建会话
const handleNewChat = async () => {
  try {
    const res: any = await createSession()
    const newSession = res.data
    await fetchSessions()
    currentSessionId.value = newSession.session_id
    messages.value = [{ role: 'assistant', content: '您好！我是您的智能旅游规划助手。您可以问我天气、路线、或者旅游攻略。', toolCall: '' }]
  } catch (error) {
    console.error('创建会话失败', error)
  }
}

// 删除会话
const handleDeleteSession = async (sessionId: string) => {
  try {
    await ElMessageBox.confirm('确定要删除该对话吗？', '提示', { type: 'warning' })
    await deleteSession(sessionId)
    ElMessage.success('删除成功')
    await fetchSessions()
    if (currentSessionId.value === sessionId) {
      if (sessionList.value.length > 0) {
        await selectSession(sessionList.value[0].session_id)
      } else {
        await handleNewChat()
      }
    }
  } catch (error) {
    // cancelled or error
  }
}

// 拦截并解析 MAP_DATA
const parseContentAndExtractMap = (content: string, msgObj: ChatMessage) => {
  const mapRegex = /```json\s*(\{[\s\S]*?"type":\s*"MAP_DATA"[\s\S]*?\})\s*```/
  const match = content.match(mapRegex)
  if (match) {
    try {
      const mapData = JSON.parse(match[1])
      msgObj.mapData = mapData
      // 从显示内容中移除这段 json 代码块
      return content.replace(match[0], '')
    } catch (e) {
      console.error('Failed to parse MAP_DATA JSON', e)
    }
  }
  return content
}

const renderMarkdown = (text: string) => {
  return md.render(text)
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const sendMessage = async () => {
  const text = inputQuery.value.trim()
  if (!text || isReceiving.value) return
  
  inputQuery.value = ''
  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  isReceiving.value = true
  
  // 创建空的 AI 消息
  const aiMsg: ChatMessage = { 
    role: 'assistant', 
    content: '', 
    toolCall: '' 
  }
  messages.value.push(aiMsg)
  const msgIndex = messages.value.length - 1 // 拿到当前消息索引

  const token = localStorage.getItem('token')
  let sessionIdToUse = currentSessionId.value

  // 自动创建会话
  if (!sessionIdToUse) {
    try {
      const res: any = await createSession()
      sessionIdToUse = res.data.session_id
      currentSessionId.value = sessionIdToUse
      await fetchSessions()
    } catch (e) {
      console.error('创建会话失败', e)
      isReceiving.value = false
      return
    }
  }

  try {
    await fetchEventSource('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'X-Model-Provider': 'qwen',
      },
      body: JSON.stringify({
        query: text,
        session_id: sessionIdToUse
      }),
      onmessage(ev) {
        // 拿到当前正在编辑的消息
        const currentMsg = messages.value[msgIndex]
        
        if (ev.event === 'session_id') {
          console.log('会话ID:', ev.data)
          return
        }

        if (ev.data === '[DONE]') {
          console.log('流式传输完成')
          return
        }

        try {
          const data = JSON.parse(ev.data)
          
          // 1. 文本流（增量拼接）
          if (data.type === 'message_chunk') {
            currentMsg.toolCall = ''
            // 增量追加内容
            currentMsg.content += data.content
            // 自动解析地图数据
            currentMsg.content = parseContentAndExtractMap(currentMsg.content, currentMsg)
            scrollToBottom()
          }

          // 2. 工具/智能体调用
          else if (data.type === 'agent_call' || data.type === 'tool_call') {
            currentMsg.toolCall = data.content
            scrollToBottom()
          }

          // 3. 工具执行完毕
          else if (data.type === 'tool_result') {
            currentMsg.toolCall = '处理结果中...'
          }

          // 4. 地图数据
          else if (data.type === 'map_data') {
            currentMsg.mapData = data
            scrollToBottom()
          }

        } catch (e) {
          console.error('SSE 解析错误:', e)
        }
      },
      onerror(err) {
        console.error('SSE 连接异常:', err)
        ElMessage.error('连接中断，请重试')
        throw err // 断开连接
      }
    })
  } catch (error) {
    const currentMsg = messages.value[msgIndex]
    currentMsg.content += '\n\n**请求出错或连接中断**'
  } finally {
    const currentMsg = messages.value[msgIndex]
    currentMsg.toolCall = '' // 清空加载状态
    // 最后再做一次完整解析
    currentMsg.content = parseContentAndExtractMap(currentMsg.content, currentMsg)
    isReceiving.value = false
    scrollToBottom()
  }
}

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped lang="scss">
.chat-layout {
  display: flex;
  height: 100vh;
  background-color: var(--ins-bg);
}

.sidebar {
  width: 260px;
  background: #ffffff;
  border-right: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  padding: 24px 16px;
  box-shadow: 2px 0 12px rgba(0,0,0,0.02);
  z-index: 10;
  
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 40px;
    padding: 0 8px;
    
    .logo {
      width: 28px;
      height: 28px;
      background: linear-gradient(135deg, var(--el-color-primary), #b3caff);
      border-radius: 8px;
    }
    
    span {
      font-size: 18px;
      font-weight: 700;
      color: #1a1a1a;
    }
  }

  .new-chat-btn {
    padding: 0 16px 20px;
    
    .full-width {
      width: 100%;
      border-radius: 12px;
    }
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 8px;
    
    &::-webkit-scrollbar {
      width: 4px;
    }
    
    .session-item {
      padding: 12px 16px;
      border-radius: 12px;
      cursor: pointer;
      color: #666;
      font-size: 14px;
      transition: all 0.2s;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 4px;
      
      .session-title {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
      }
      
      .session-actions {
        opacity: 0;
        transition: opacity 0.2s;
        
        .el-icon {
          padding: 4px;
          border-radius: 4px;
          &:hover {
            background: rgba(0,0,0,0.05);
            color: #ff4d4f;
          }
        }
      }
      
      &.active {
        background: var(--el-color-primary-light-9);
        color: var(--el-color-primary);
        font-weight: 600;
        
        .session-actions {
          opacity: 1;
        }
      }
      
      &:hover:not(.active) {
        background: #f5f5f5;
        .session-actions {
          opacity: 1;
        }
      }
    }
    
    .empty-hint {
      text-align: center;
      color: #999;
      font-size: 13px;
      margin-top: 40px;
    }
  }

  .user-profile {
    padding-top: 16px;
    border-top: 1px solid #f0f0f0;
    
    .el-dropdown-link {
      display: flex;
      align-items: center;
      gap: 12px;
      cursor: pointer;
      padding: 8px;
      border-radius: 12px;
      transition: background 0.2s;
      
      &:hover {
        background: #f5f5f5;
      }
      
      .username {
        font-weight: 600;
        color: #333;
      }
    }
  }
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

.chat-header {
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #f0f0f0;
  z-index: 5;
  
  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #1a1a1a;
  }
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 10%;
  scroll-behavior: smooth;
  
  .tool-call-wrapper {
    display: flex;
    justify-content: flex-start;
    margin-bottom: 8px;
    padding-left: 52px; // 对齐头像
    
    .tool-call-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      background: #f0f4ff;
      color: var(--el-color-primary);
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
    }
  }
  
  .message-wrapper {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
    
    &.user {
      justify-content: flex-end;
      
      .message-content {
        background: linear-gradient(135deg, #a8c4ff, #8aafff);
        color: #fff;
        border-radius: 20px 20px 4px 20px;
        box-shadow: 0 4px 12px rgba(138, 175, 255, 0.2);
        
        :deep(p) {
          margin: 0;
        }
      }
    }
    
    &.assistant {
      .message-content {
        background: #ffffff;
        color: #333;
        border-radius: 20px 20px 20px 4px;
        box-shadow: var(--ins-shadow);
        border: 1px solid #f5f5f5;
      }
    }
    
    .msg-avatar {
      flex-shrink: 0;
      font-weight: bold;
      &.user-avatar { background: var(--el-color-primary-light-3); color: #fff; }
      &.ai-avatar { background: #1a1a1a; color: #fff; }
    }
    
    .message-content {
      max-width: 75%;
      padding: 14px 20px;
      line-height: 1.6;
      font-size: 15px;
      word-wrap: break-word;
      
      /* Markdown 样式极简适配 */
      :deep(.markdown-body) {
        p { margin-top: 0; margin-bottom: 1em; }
        p:last-child { margin-bottom: 0; }
        pre {
          background: #f5f5f5;
          padding: 12px;
          border-radius: 8px;
          overflow-x: auto;
        }
        code {
          background: rgba(0,0,0,0.05);
          padding: 2px 4px;
          border-radius: 4px;
          font-family: monospace;
          font-size: 13px;
        }
      }
    }
  }
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  
  .dot {
    width: 6px;
    height: 6px;
    background-color: #ccc;
    border-radius: 50%;
    animation: typing 1.4s infinite ease-in-out both;
    
    &:nth-child(1) { animation-delay: -0.32s; }
    &:nth-child(2) { animation-delay: -0.16s; }
  }
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.chat-footer {
  padding: 20px 10%;
  background: linear-gradient(to top, #fafafa 60%, rgba(250,250,250,0));
  
  .input-container {
    position: relative;
    background: #fff;
    border-radius: 24px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.06);
    padding: 8px 16px;
    display: flex;
    align-items: center;
    border: 1px solid #eaeaea;
    transition: all 0.3s;
    
    &:focus-within {
      border-color: var(--el-color-primary-light-5);
      box-shadow: 0 8px 32px rgba(138, 175, 255, 0.15);
    }
    
    :deep(.el-textarea__inner) {
      border: none !important;
      box-shadow: none !important;
      background: transparent;
      padding: 8px 0;
      resize: none;
      font-size: 15px;
      line-height: 1.5;
      
      &::-webkit-scrollbar {
        width: 4px;
      }
    }
    
    .send-btn {
      flex-shrink: 0;
      margin-left: 12px;
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, var(--el-color-primary), #a8c4ff);
      border: none;
      
      &:hover:not(:disabled) {
        transform: translateY(-2px) scale(1.05);
        box-shadow: 0 4px 12px rgba(138, 175, 255, 0.4);
      }
      
      &:disabled {
        background: #e0e0e0;
      }
    }
  }
}
</style>
