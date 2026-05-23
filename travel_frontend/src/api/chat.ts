import request from '@/utils/request'

export interface ChatSession {
  session_id: string
  title: string
  updated_at: string
}

export interface MapData {
  type: string
  tool: string
  data: any
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolCall?: string
  mapData?: MapData
  _originalContent?: string
}

// 获取所有会话
export function getSessions() {
  return request.get('/api/chat/sessions')
}

// 创建新会话
export function createSession() {
  return request.post('/api/chat/sessions')
}

// 获取某个会话的历史记录
export function getSessionHistory(sessionId: string) {
  return request.get(`/api/chat/history/${sessionId}`)
}

// 删除会话
export function deleteSession(sessionId: string) {
  return request.delete(`/api/chat/sessions/${sessionId}`)
}
