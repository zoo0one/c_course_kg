import { useState, useEffect } from 'react'
import { ConfigProvider, Button, message } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import { AppLayout } from '@/components/Layout/Layout'
import { Dashboard } from '@/components/pages/Dashboard'
import { ChapterOverviewPage } from '@/components/pages/ChapterOverviewPage'
import { GraphViewPage } from '@/components/pages/GraphViewPage'
import { AdminPage } from '@/components/pages/AdminPage'
import { ChatDrawer } from '@/components/AIChat/ChatDrawer'
import { useAppStore } from '@/services/store'
import { chapterAPI, healthCheck } from '@/services/api'
import { THEMES, applyTheme } from '@/styles/themes'
import type { KnowledgePoint } from '@/types'
import '@/styles/globals.css'

type PageType = 'dashboard' | 'chapter-overview' | 'graph' | 'admin'

function App() {
  const [chatOpen, setChatOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [selectedKPId, setSelectedKPId] = useState<string | null>(null)

  const chapters = useAppStore((state) => state.chapters)
  const setChapters = useAppStore((state) => state.setChapters)
  const currentPage = useAppStore((state) => state.currentPage) as PageType
  const setCurrentPage = useAppStore((state) => state.setCurrentPage)
  const selectedChapter = useAppStore((state) => state.selectedChapter)
  const setSelectedChapter = useAppStore((state) => state.setSelectedChapter)
  const theme = useAppStore((state) => state.theme)
  const setTheme = useAppStore((state) => state.setTheme)

  const currentTheme = THEMES[theme]

  // 初始化时应用主题 CSS 变量
  useEffect(() => {
    applyTheme(currentTheme)
  }, [theme])

  useEffect(() => {
    const init = async () => {
      try {
        const isHealthy = await healthCheck()
        if (!isHealthy) message.error('无法连接到后端服务，请确保后端已启动')
        const chaptersData = await chapterAPI.listChapters()
        setChapters(chaptersData)
      } catch (error) {
        console.error('Failed to initialize app:', error)
        message.error('应用初始化失败')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [setChapters])

  const handleChapterSelect = (chapterId: string) => {
    setSelectedChapter(chapterId === selectedChapter ? null : chapterId)
    setCurrentPage('graph')
  }

  const handleKPSelect = (kp: KnowledgePoint) => {
    setSelectedKPId(kp.kp_id)
    setCurrentPage('graph')
  }

  const handlePageChange = (page: string) => {
    setCurrentPage(page)
    if (page !== 'graph') setSelectedChapter(null)
  }

  const handleToggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return (
          <Dashboard
            onNavigate={handlePageChange}
            onOpenChat={() => setChatOpen(true)}
            chapters={chapters}
            onSelectChapter={handleChapterSelect}
          />
        )
      case 'chapter-overview':
        return <ChapterOverviewPage chapters={chapters} onSelectChapter={handleChapterSelect} />
      case 'graph':
        return <GraphViewPage selectedChapter={selectedChapter} highlightKPId={selectedKPId} />
      case 'admin':
        return <AdminPage />
      default:
        return (
          <Dashboard
            onNavigate={handlePageChange}
            onOpenChat={() => setChatOpen(true)}
            chapters={chapters}
            onSelectChapter={handleChapterSelect}
          />
        )
    }
  }

  return (
    <ConfigProvider theme={currentTheme.antdTheme}>
      <AppLayout
        chapters={chapters}
        onChapterSelect={handleChapterSelect}
        onKPSelect={handleKPSelect}
        loading={loading}
        currentPage={currentPage}
        onPageChange={handlePageChange}
        onToggleTheme={handleToggleTheme}
        currentTheme={theme}
      >
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
          {renderPage()}

          {currentPage !== 'admin' && (
            <Button
              type="primary"
              shape="circle"
              size="large"
              icon={<RobotOutlined />}
              onClick={() => setChatOpen(true)}
              style={{
                position: 'fixed',
                bottom: 24,
                right: 24,
                width: 56,
                height: 56,
                fontSize: 24,
                zIndex: 999,
                boxShadow: '0 4px 16px var(--primary-glow)',
              }}
              title="打开 AI 助手"
            />
          )}
        </div>
      </AppLayout>

      <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
    </ConfigProvider>
  )
}

export default App
