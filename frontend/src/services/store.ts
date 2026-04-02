import { create } from 'zustand'
import type { Chapter, ChatMessage, Statistics } from '@/types'
import type { ThemeKey } from '@/styles/themes'

interface AppStore {
  // 数据状态
  chapters: Chapter[]
  statistics: Statistics | null

  // UI 状态
  sidebarOpen: boolean
  loading: boolean
  currentPage: string
  selectedChapter: string | null

  // 聊天状态
  chatMessages: ChatMessage[]
  chatInput: string

  // 主题
  theme: ThemeKey

  // 图谱状态
  graphNodes: any[]
  graphEdges: any[]

  // 操作方法
  setChapters: (chapters: Chapter[]) => void
  setStatistics: (stats: Statistics) => void
  setSidebarOpen: (open: boolean) => void
  setLoading: (loading: boolean) => void
  setCurrentPage: (page: string) => void
  setSelectedChapter: (id: string | null) => void
  addChatMessage: (message: ChatMessage) => void
  setChatMessages: (messages: ChatMessage[]) => void
  setChatInput: (input: string) => void
  setGraphData: (nodes: any[], edges: any[]) => void
  setTheme: (theme: ThemeKey) => void
}

export const useAppStore = create<AppStore>((set) => ({
  chapters: [],
  statistics: null,
  sidebarOpen: true,
  loading: false,
  currentPage: 'dashboard',
  selectedChapter: null,
  chatMessages: [],
  chatInput: '',
  theme: (localStorage.getItem('theme') as ThemeKey) || 'light',
  graphNodes: [],
  graphEdges: [],

  setChapters: (chapters) => set({ chapters }),
  setStatistics: (statistics) => set({ statistics }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setLoading: (loading) => set({ loading }),
  setCurrentPage: (currentPage) => set({ currentPage }),
  setSelectedChapter: (selectedChapter) => set({ selectedChapter }),
  addChatMessage: (message) =>
    set((state) => ({ chatMessages: [...state.chatMessages, message] })),
  setChatMessages: (chatMessages) => set({ chatMessages }),
  setChatInput: (chatInput) => set({ chatInput }),
  setGraphData: (graphNodes, graphEdges) => set({ graphNodes, graphEdges }),
  setTheme: (theme) => {
    localStorage.setItem('theme', theme)
    set({ theme })
  },
}))
