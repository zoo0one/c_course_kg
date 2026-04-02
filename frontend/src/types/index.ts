// 知识点类型
export interface KnowledgePoint {
  kp_id: string
  name: string
  chapter_id: string
  section?: string
  aliases?: string
  source?: string
}

// 章节类型
export interface Chapter {
  chapter_id: string
  title: string
  order: number
}

// 章节详情
export interface ChapterDetail {
  chapter: Chapter
  kps: KnowledgePoint[]
}

// AI 聊天消息
export interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: string
  suggestions?: ChatSuggestion[]
  actions?: ChatAction[]
}

// 聊天建议
export interface ChatSuggestion {
  type: 'knowledge_point' | 'chapter'
  id: string
  name: string
}

// 聊天操作
export interface ChatAction {
  label: string
  action: string
  params?: Record<string, any>
}

// 统计信息
export interface Statistics {
  total_kps: number
  total_chapters: number
  total_relations: number
  total_segments: number
}
