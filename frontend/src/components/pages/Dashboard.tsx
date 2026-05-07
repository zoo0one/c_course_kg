import React, { useEffect } from 'react'
import {
  NodeIndexOutlined, BookOutlined, LinkOutlined,
  RobotOutlined, ApartmentOutlined, SettingOutlined,
  SearchOutlined, ThunderboltOutlined, FireOutlined,
} from '@ant-design/icons'
import { useAppStore } from '@/services/store'
import { statsAPI } from '@/services/api'

interface DashboardProps {
  onNavigate: (page: string) => void
  onOpenChat: () => void
  chapters: { chapter_id: string; title: string; order: number }[]
  onSelectChapter: (chapterId: string) => void
}

const RELATION_LEGEND = [
  { label: 'PREREQUISITE', color: '#38bdf8', desc: '先修关系' },
  { label: 'CONTAINS', color: '#34d399', desc: '章节包含' },
  { label: 'EXTENDS', color: '#a78bfa', desc: '深化扩展' },
  { label: 'RELATED', color: '#475569', desc: '相关关联', dashed: true },
]

export const Dashboard: React.FC<DashboardProps> = ({ onNavigate, onOpenChat, chapters, onSelectChapter }) => {
  const statistics = useAppStore((state) => state.statistics)
  const setStatistics = useAppStore((state) => state.setStatistics)
  useEffect(() => {
    if (!statistics) statsAPI.getStats().then(setStatistics).catch(console.error)
  }, [statistics, setStatistics])

  const statItems = [
    { label: '知识点', value: statistics?.total_kps ?? '--', color: 'var(--primary)', glow: 'var(--primary-glow)', icon: <NodeIndexOutlined />, onClick: () => onNavigate('graph') },
    { label: '章节', value: statistics?.total_chapters ?? '--', color: 'var(--success)', glow: 'rgba(52,211,153,0.2)', icon: <BookOutlined />, onClick: () => onNavigate('graph') },
    { label: '关系边', value: statistics?.total_relations ?? '--', color: 'var(--accent)', glow: 'var(--accent-glow)', icon: <LinkOutlined />, onClick: () => onNavigate('graph') },
  ]

  const actions = [
    { key: 'graph', icon: <ApartmentOutlined style={{ fontSize: 26 }} />, title: '知识图谱', desc: '交互式可视化，探索知识关联与先修路径', color: 'var(--primary)', glow: 'var(--primary-glow)', onClick: () => onNavigate('graph') },
    { key: 'ai', icon: <RobotOutlined style={{ fontSize: 26 }} />, title: 'AI 助手', desc: '个性化学习建议和知识解析', color: 'var(--success)', glow: 'rgba(52,211,153,0.2)', onClick: onOpenChat },
    { key: 'search', icon: <SearchOutlined style={{ fontSize: 26 }} />, title: '智能搜索', desc: '按名称或别名快速定位知识点', color: 'var(--purple)', glow: 'rgba(167,139,250,0.2)', onClick: () => {} },
    { key: 'admin', icon: <SettingOutlined style={{ fontSize: 26 }} />, title: '管理面板', desc: '增删改查知识点，批量导入数据', color: 'var(--accent)', glow: 'var(--accent-glow)', onClick: () => onNavigate('admin') },
  ]

  const chapterNodes = [...chapters]
    .sort((a, b) => a.order - b.order)
    .slice(0, 24)

  return (
    <div className="grid-bg" style={{ height: '100%', overflowY: 'auto', background: 'var(--bg-base)' }}>
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '36px 32px' }}>

        {/* Hero */}
        <div className="fade-up" style={{ marginBottom: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div className="glow-pulse" style={{ width: 46, height: 46, borderRadius: 12, background: 'linear-gradient(135deg, var(--primary) 0%, var(--purple) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 700, color: '#080d1a', fontFamily: 'var(--font-mono)' }}>C</div>
            <div>
              <h1 style={{ color: 'var(--text-primary)', fontSize: 26, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
                C 语言知识图谱
                <span style={{ marginLeft: 10, fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--primary)', fontWeight: 400, verticalAlign: 'middle', background: 'var(--primary-glow)', border: '1px solid rgba(56,189,248,0.3)', padding: '2px 8px', borderRadius: 4 }}>v2.0</span>
              </h1>
              <p style={{ color: 'var(--text-muted)', marginTop: 4, fontSize: 13, margin: 0 }}>基于 Neo4j &amp; AI 的 C 语言课程知识图谱系统</p>
            </div>
          </div>
        </div>

        {/* 两栏布局 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, alignItems: 'start' }}>

          {/* 左栏 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

            {/* 统计卡片 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14 }}>
              {statItems.map((item, i) => (
                <div key={item.label} className="fade-up"
                  style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, padding: '20px 22px', position: 'relative', overflow: 'hidden', animationDelay: `${i*60}ms`, transition: 'border-color 0.2s, box-shadow 0.2s', cursor: 'pointer' }}
                  onClick={item.onClick}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = item.color; e.currentTarget.style.boxShadow = `0 0 20px ${item.glow}` }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none' }}
                >
                  <div style={{ position: 'absolute', top: -8, right: -8, width: 64, height: 64, borderRadius: '50%', background: `radial-gradient(circle, ${item.glow} 0%, transparent 70%)`, pointerEvents: 'none' }} />
                  <div style={{ color: item.color, fontSize: 18, marginBottom: 10 }}>{item.icon}</div>
                  <div style={{ fontSize: 34, fontWeight: 700, color: item.color, fontFamily: 'var(--font-mono)', lineHeight: 1, marginBottom: 4 }}>{item.value}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{item.label}</div>
                </div>
              ))}
            </div>

            {/* 快速入口 */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <ThunderboltOutlined style={{ color: 'var(--accent)', fontSize: 13 }} />
                <span style={{ color: 'var(--text-secondary)', fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>Quick Access</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 16 }}>
                {actions.map((action, i) => (
                  <div key={action.key} className="fade-up" onClick={action.onClick}
                    style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, padding: '24px 20px', cursor: 'pointer', transition: 'all 0.2s', animationDelay: `${i*80}ms`, position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 12, minHeight: 140 }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = action.color; e.currentTarget.style.boxShadow = `0 4px 24px ${action.glow}`; e.currentTarget.style.transform = 'translateY(-3px)' }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.transform = 'translateY(0)' }}
                  >
                    <div style={{ position: 'absolute', bottom: -14, right: -14, width: 70, height: 70, borderRadius: '50%', background: `radial-gradient(circle, ${action.glow} 0%, transparent 70%)`, pointerEvents: 'none' }} />
                    <div style={{ width: 48, height: 48, borderRadius: 12, flexShrink: 0, background: `${action.color}18`, border: `1px solid ${action.color}44`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: action.color }}>{action.icon}</div>
                    <div>
                      <div style={{ color: 'var(--text-primary)', fontWeight: 700, fontSize: 16, marginBottom: 5 }}>{action.title}</div>
                      <div style={{ color: 'var(--text-muted)', fontSize: 13, lineHeight: 1.6 }}>{action.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 章节导航图（主页下半区） */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <ApartmentOutlined style={{ color: 'var(--primary)', fontSize: 13 }} />
                  <span style={{ color: 'var(--text-secondary)', fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>
                    章节知识图谱入口
                  </span>
                </div>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>点击章节跳转</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12 }}>
                {chapterNodes.map((ch) => (
                  <button
                    key={ch.chapter_id}
                    onClick={() => onSelectChapter(ch.chapter_id)}
                    style={{
                      position: 'relative',
                      border: '1px solid var(--border)',
                      borderRadius: 10,
                      background: 'var(--bg-hover)',
                      padding: '12px 12px 10px',
                      textAlign: 'left',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--primary)'
                      e.currentTarget.style.boxShadow = '0 0 0 2px var(--primary-glow)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border)'
                      e.currentTarget.style.boxShadow = 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                      <BookOutlined style={{ color: 'var(--primary)', fontSize: 12 }} />
                      <span style={{ color: 'var(--primary)', fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{ch.chapter_id}</span>
                    </div>
                    <div style={{ color: 'var(--text-primary)', fontSize: 13, fontWeight: 600, lineHeight: 1.4 }}>
                      {ch.title}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* 右栏 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* 关系图例 */}
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, padding: '18px 20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <FireOutlined style={{ color: 'var(--primary)', fontSize: 14 }} />
                <span style={{ color: 'var(--text-secondary)', fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>关系图例</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {RELATION_LEGEND.map((r) => (
                  <div key={r.label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 28, height: 2, background: r.dashed ? 'transparent' : r.color, borderTop: r.dashed ? `2px dashed ${r.color}` : 'none', opacity: r.dashed ? 0.5 : 1, flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <span style={{ color: r.color, fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{r.label}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 6 }}>{r.desc}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
