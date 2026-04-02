import React, { useState } from 'react'
import { Layout, Tree, Spin } from 'antd'
import {
  SearchOutlined,
  BookOutlined,
  NodeIndexOutlined,
  ApartmentOutlined,
  DatabaseOutlined,
  LinkOutlined,
} from '@ant-design/icons'
import { useAppStore } from '@/services/store'
import { knowledgePointAPI } from '@/services/api'
import type { Chapter, KnowledgePoint } from '@/types'

const { Sider } = Layout

interface SidebarProps {
  collapsed: boolean
  chapters: Chapter[]
  onChapterSelect: (chapterId: string) => void
  onKPSelect?: (kp: KnowledgePoint) => void
  loading?: boolean
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  chapters,
  onChapterSelect,
  onKPSelect,
  loading = false,
}) => {
  const [searchText, setSearchText] = useState('')
  const [searchResults, setSearchResults] = useState<KnowledgePoint[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const statistics = useAppStore((state) => state.statistics)

  React.useEffect(() => {
    if (!searchText.trim()) { setSearchResults([]); return }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const results = await knowledgePointAPI.search(searchText)
        setSearchResults(results)
      } catch { setSearchResults([]) }
      finally { setSearching(false) }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchText])

  const treeData = chapters.map((ch) => ({
    title: (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 4 }}>
        <span style={{ color: 'var(--text-primary)', fontSize: 13 }}>{ch.title}</span>
        <span style={{
          color: 'var(--text-muted)',
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          background: 'var(--bg-hover)',
          padding: '1px 5px',
          borderRadius: 3,
        }}>{ch.chapter_id}</span>
      </div>
    ),
    key: ch.chapter_id,
    icon: <BookOutlined style={{ color: 'var(--primary)', fontSize: 12 }} />,
  }))

  const handleSelect = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length > 0) {
      const key = selectedKeys[0] as string
      setSelectedKey(key)
      onChapterSelect(key)
    }
  }

  if (collapsed) {
    return (
      <Sider
        trigger={null}
        collapsible
        collapsed
        width={260}
        collapsedWidth={48}
        style={{ background: 'var(--bg-surface)', borderRight: '1px solid var(--border)' }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 16, gap: 20 }}>
          <SearchOutlined style={{ color: 'var(--text-muted)', fontSize: 16 }} />
          <BookOutlined style={{ color: 'var(--text-muted)', fontSize: 16 }} />
          <ApartmentOutlined style={{ color: 'var(--text-muted)', fontSize: 16 }} />
        </div>
      </Sider>
    )
  }

  return (
    <Sider
      trigger={null}
      collapsible
      collapsed={false}
      width={260}
      style={{
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        overflowY: 'auto',
        overflowX: 'hidden',
        flexShrink: 0,
      }}
    >
      {/* 搜索区 */}
      <div style={{ padding: '14px 12px 8px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--bg-input)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '7px 10px',
            transition: 'border-color 0.2s, box-shadow 0.2s',
          }}
          onFocusCapture={(e) => {
            e.currentTarget.style.borderColor = 'var(--primary)'
            e.currentTarget.style.boxShadow = '0 0 0 2px var(--primary-glow)'
          }}
          onBlurCapture={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <SearchOutlined style={{ color: 'var(--text-muted)', fontSize: 13 }} />
          <input
            placeholder="搜索知识点..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontSize: 13,
              fontFamily: 'var(--font-ui)',
            }}
          />
          {searchText && (
            <span
              onClick={() => setSearchText('')}
              style={{ color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12 }}
            >✕</span>
          )}
        </div>

        {/* 搜索结果 */}
        {searchText && (
          <div
            style={{
              marginTop: 8,
              background: 'var(--bg-panel)',
              border: '1px solid var(--border-bright)',
              borderRadius: 8,
              overflow: 'hidden',
              maxHeight: 220,
              overflowY: 'auto',
            }}
          >
            {searching ? (
              <div style={{ textAlign: 'center', padding: '12px 0' }}><Spin size="small" /></div>
            ) : searchResults.length === 0 ? (
              <div style={{ padding: '10px 12px', color: 'var(--text-muted)', fontSize: 12 }}>无匹配结果</div>
            ) : (
              searchResults.map((kp, idx) => (
                <div
                  key={kp.kp_id}
                  onClick={() => { onKPSelect?.(kp); setSearchText('') }}
                  style={{
                    padding: '8px 12px',
                    cursor: 'pointer',
                    borderBottom: idx < searchResults.length - 1 ? '1px solid var(--border)' : 'none',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <NodeIndexOutlined style={{ color: 'var(--primary)', fontSize: 12 }} />
                    <span style={{ color: 'var(--text-primary)', fontSize: 13 }}>{kp.name}</span>
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2, paddingLeft: 18, fontFamily: 'var(--font-mono)' }}>
                    {kp.chapter_id} · {kp.section || '--'}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* 统计栏 */}
      {statistics && (
        <div
          style={{
            margin: '4px 12px 12px',
            padding: '10px 12px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          {[
            { label: '知识点', value: statistics.total_kps, color: 'var(--primary)', icon: <NodeIndexOutlined /> },
            { label: '章节', value: statistics.total_chapters, color: 'var(--success)', icon: <DatabaseOutlined /> },
            { label: '关系', value: statistics.total_relations, color: 'var(--accent)', icon: <LinkOutlined /> },
          ].map((item) => (
            <div key={item.label} style={{ textAlign: 'center' }}>
              <div style={{ color: item.color, fontSize: 18, fontWeight: 700, lineHeight: 1.2, fontFamily: 'var(--font-mono)' }}>
                {item.value}
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2 }}>{item.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* 章节标题 */}
      <div style={{ padding: '4px 16px 6px', display: 'flex', alignItems: 'center', gap: 6 }}>
        <ApartmentOutlined style={{ color: 'var(--text-muted)', fontSize: 10 }} />
        <span style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
          Chapters
        </span>
      </div>

      {/* 章节树 */}
      <div style={{ padding: '0 8px 16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}><Spin size="small" /></div>
        ) : (
          <Tree
            treeData={treeData}
            onSelect={handleSelect}
            selectedKeys={selectedKey ? [selectedKey] : []}
            showIcon
            blockNode
            style={{ background: 'transparent' }}
          />
        )}
      </div>
    </Sider>
  )
}
