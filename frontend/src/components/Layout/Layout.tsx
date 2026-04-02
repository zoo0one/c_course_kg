import React, { ReactNode } from 'react'
import { Layout } from 'antd'
import { AppHeader } from './Header'
import { Sidebar } from './Sidebar'
import { useAppStore } from '@/services/store'
import type { ThemeKey } from '@/styles/themes'
import type { Chapter, KnowledgePoint } from '@/types'

const { Content } = Layout

interface LayoutProps {
  children: ReactNode
  chapters: Chapter[]
  onChapterSelect: (chapterId: string) => void
  onKPSelect?: (kp: KnowledgePoint) => void
  loading?: boolean
  currentPage: string
  onPageChange: (page: string) => void
  onToggleTheme: () => void
  currentTheme: ThemeKey
}

export const AppLayout: React.FC<LayoutProps> = ({
  children,
  chapters,
  onChapterSelect,
  onKPSelect,
  loading = false,
  currentPage,
  onPageChange,
  onToggleTheme,
  currentTheme,
}) => {
  const sidebarOpen = useAppStore((state) => state.sidebarOpen)
  const setSidebarOpen = useAppStore((state) => state.setSidebarOpen)

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <AppHeader
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        currentPage={currentPage}
        onPageChange={onPageChange}
        onToggleTheme={onToggleTheme}
        currentTheme={currentTheme}
      />
      <Layout style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Sidebar
          collapsed={!sidebarOpen}
          chapters={chapters}
          onChapterSelect={onChapterSelect}
          onKPSelect={onKPSelect}
          loading={loading}
        />
        <Content
          style={{
            background: 'var(--bg-base)',
            overflow: 'hidden',
            position: 'relative',
            height: '100%',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  )
}
