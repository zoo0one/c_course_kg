import axios from 'axios'
import type { Chapter, ChapterDetail, KnowledgePoint, Statistics } from '@/types'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

export const chapterAPI = {
  listChapters: async (): Promise<Chapter[]> => {
    const { data } = await api.get('/chapters')
    return data
  },
  getChapterDetail: async (chapterId: string): Promise<ChapterDetail> => {
    const { data } = await api.get(`/chapters/${chapterId}`)
    return data
  },
}

export const knowledgePointAPI = {
  search: async (query: string): Promise<KnowledgePoint[]> => {
    const { data } = await api.get('/kps/search', { params: { q: query } })
    return data
  },
  getDetail: async (kpId: string): Promise<KnowledgePoint> => {
    const { data } = await api.get(`/kps/${kpId}`)
    return data
  },
  getPrerequisites: async (kpId: string): Promise<KnowledgePoint[]> => {
    const { data } = await api.get(`/kps/${kpId}/prerequisites`)
    return data
  },
  getSuccessors: async (kpId: string): Promise<KnowledgePoint[]> => {
    const { data } = await api.get(`/kps/${kpId}/successors`)
    return data
  },
  getRelated: async (kpId: string): Promise<KnowledgePoint[]> => {
    const { data } = await api.get(`/kps/${kpId}/related`)
    return data
  },
}

export const graphAPI = {
  getGraph: async (): Promise<{ nodes: any[]; edges: any[] }> => {
    const { data } = await api.get('/graph')
    return data
  },
}

export const aiAPI = {
  chat: async (message: string, context?: Record<string, any>): Promise<{
    response: string
    suggestions?: any[]
  }> => {
    const { data } = await api.post('/ai/chat', { message, context }, { timeout: 120000 })
    return data
  },

  chatStream: async function* (message: string, context?: Record<string, any>): AsyncGenerator<string> {
    const params = new URLSearchParams({ message })
    if (context) params.set('context', JSON.stringify(context))
    const response = await fetch(`${API_BASE}/ai/chat/stream?${params}`, { method: 'GET' })
    if (!response.ok || !response.body) throw new Error('流式请求失败')
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      if (chunk) yield chunk
    }
  },

  explain: async (kpId: string): Promise<string> => {
    const { data } = await api.post('/ai/explain', { kp_id: kpId }, { timeout: 120000 })
    return data.explanation
  },

  recommendPath: async (kpId: string): Promise<any[]> => {
    const { data } = await api.post('/ai/recommend-path', { kp_id: kpId }, { timeout: 120000 })
    return data.path
  },

  reviewCode: async (code: string): Promise<string> => {
    const { data } = await api.post('/ai/code-review', { code }, { timeout: 120000 })
    return data.review
  },

  health: async (): Promise<{ ready: boolean; model: string; status: string; message: string }> => {
    try {
      const { data } = await api.get('/ai/health')
      return data
    } catch {
      return { ready: false, model: 'qwen2.5:7b', status: '未连接', message: '请启动 Ollama 服务' }
    }
  },
}

export const statsAPI = {
  getStats: async (): Promise<Statistics> => {
    const { data } = await api.get('/stats')
    return data
  },
}

export const adminAPI = {
  uploadPdf: async (file: File): Promise<any> => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/admin/upload-pdf', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    return data
  },

  startExtract: async (jobId: string): Promise<any> => {
    const { data } = await api.post(`/admin/extract/${jobId}/start`)
    return data
  },

  getExtractStatus: async (jobId: string): Promise<any> => {
    const { data } = await api.get(`/admin/extract/${jobId}/status`)
    return data
  },

  getExtractPreview: async (jobId: string, limit = 20): Promise<any> => {
    const { data } = await api.get(`/admin/extract/${jobId}/preview`, { params: { limit } })
    return data
  },

  extractToReview: async (jobId: string): Promise<any> => {
    const { data } = await api.post(`/admin/extract/${jobId}/to-review`)
    return data
  },

  parseUpload: async (formData: FormData): Promise<any> => {
    const { data } = await api.post('/admin/parse-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  confirmImport: async (result: any): Promise<void> => {
    await api.post('/admin/confirm-import', result)
  },

  getReviewQueue: async (status = 'pending'): Promise<any[]> => {
    const { data } = await api.get('/admin/review', { params: { status } })
    return data
  },

  approveReview: async (id: string): Promise<void> => {
    await api.post(`/admin/review/${id}/approve`)
  },

  approveAllReview: async (): Promise<{ ok: boolean; approved: number }> => {
    const { data } = await api.post('/admin/review/batch/approve-all')
    return data
  },

  rejectReview: async (id: string): Promise<void> => {
    await api.post(`/admin/review/${id}/reject`)
  },

  applyReviewed: async (mode: 'replace' | 'append'): Promise<any> => {
    const { data } = await api.post('/admin/apply-reviewed', { mode })
    return data
  },

  createKP: async (kp: any): Promise<void> => {
    await api.post('/admin/kps', kp)
  },

  updateKP: async (kpId: string, kp: any): Promise<void> => {
    await api.put(`/admin/kps/${kpId}`, kp)
  },

  deleteKP: async (kpId: string): Promise<void> => {
    await api.delete(`/admin/kps/${kpId}`)
  },
}

export const healthCheck = async (): Promise<boolean> => {
  try {
    const { data } = await api.get('/health')
    return data.ok === 1
  } catch {
    return false
  }
}

export default api
