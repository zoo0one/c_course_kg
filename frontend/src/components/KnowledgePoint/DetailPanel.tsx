import React, { useMemo } from 'react'
import { Drawer, Tabs, Space, Empty, Spin, Tag } from 'antd'
import { BookOutlined, LinkOutlined, InfoCircleOutlined } from '@ant-design/icons'
import type { KnowledgePoint } from '@/types'

interface DetailPanelProps {
  open: boolean
  onClose: () => void
  kp: KnowledgePoint | null
  prerequisites?: KnowledgePoint[]
  successors?: KnowledgePoint[]
  related?: KnowledgePoint[]
  loading?: boolean
}

const formatSource = (kp: KnowledgePoint) => {
  const book = kp.source_book || kp.source || '未记录来源'
  const pageText = kp.source_pages || (kp.source_page ? `第 ${kp.source_page} 页` : '')
  return pageText ? `${book} · ${pageText}` : book
}

const buildIntro = (kp: KnowledgePoint) => {
  const parts: string[] = []
  if (kp.section) parts.push(`位于 ${kp.section}`)
  if (kp.aliases) parts.push(`别名：${kp.aliases.split(',').map((a) => a.trim()).filter(Boolean).slice(0, 3).join('、')}`)
  if (kp.source_book || kp.source || kp.source_page || kp.source_pages) parts.push(`来源：${formatSource(kp)}`)
  return parts.length > 0 ? parts.join('；') : '暂无简介，后续可以在导入数据时补充知识点说明。'
}

const KPCard: React.FC<{ kp: KnowledgePoint; color: string }> = ({ kp, color }) => (
  <div style={{
    background: 'var(--bg-hover)',
    padding: '10px 14px',
    borderRadius: 8,
    cursor: 'pointer',
    border: '1px solid var(--border)',
    transition: 'border-color 0.15s',
  }}
    onMouseEnter={(e) => (e.currentTarget.style.borderColor = color)}
    onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
  >
    <div style={{ color, fontWeight: 500, fontSize: 14 }}>{kp.name}</div>
    <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 3, fontFamily: 'var(--font-mono)' }}>
      {kp.kp_id} · {kp.chapter_id}
    </div>
  </div>
)

export const DetailPanel: React.FC<DetailPanelProps> = ({
  open, onClose, kp,
  prerequisites = [], successors = [], related = [],
  loading = false,
}) => {
  if (!kp) return null

  const intro = useMemo(() => buildIntro(kp), [kp])
  const sourceText = useMemo(() => formatSource(kp), [kp])

  const items = [
    {
      key: '1',
      label: '基本信息',
      icon: <BookOutlined />,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>ID</div>
            <div style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>{kp.kp_id}</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>章节</div>
            <span style={{ background: 'var(--primary-glow)', border: '1px solid rgba(56,189,248,0.3)', color: 'var(--primary)', borderRadius: 4, padding: '2px 8px', fontSize: 12, fontFamily: 'var(--font-mono)' }}>{kp.chapter_id}</span>
          </div>
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>简介</div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.7 }}>{intro}</div>
          </div>
          {kp.section && (
            <div>
              <div style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>小节</div>
              <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{kp.section}</div>
            </div>
          )}
          {kp.aliases && (
            <div>
              <div style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>别名</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {kp.aliases.split(',').map((a) => (
                  <span key={a} style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-secondary)', borderRadius: 4, padding: '2px 8px', fontSize: 12 }}>{a.trim()}</span>
                ))}
              </div>
            </div>
          )}
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>来源</div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 12, lineHeight: 1.6 }}>{sourceText}</div>
            {kp.source_page && !kp.source_pages && (
              <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 4 }}>
                页面：第 {kp.source_page} 页
              </div>
            )}
          </div>
        </div>
      ),
    },
    {
      key: '2',
      label: `先修 (${prerequisites.length})`,
      icon: <LinkOutlined />,
      children: prerequisites.length === 0
        ? <Empty description={<span style={{ color: 'var(--text-muted)' }}>暂无先修知识点</span>} />
        : <Space direction="vertical" style={{ width: '100%' }}>{prerequisites.map((p) => <KPCard key={p.kp_id} kp={p} color="var(--primary)" />)}</Space>,
    },
    {
      key: '3',
      label: `后继 (${successors.length})`,
      icon: <LinkOutlined />,
      children: successors.length === 0
        ? <Empty description={<span style={{ color: 'var(--text-muted)' }}>暂无后继知识点</span>} />
        : <Space direction="vertical" style={{ width: '100%' }}>{successors.map((s) => <KPCard key={s.kp_id} kp={s} color="var(--success)" />)}</Space>,
    },
    {
      key: '4',
      label: `相关 (${related.length})`,
      icon: <LinkOutlined />,
      children: related.length === 0
        ? <Empty description={<span style={{ color: 'var(--text-muted)' }}>暂无相关知识点</span>} />
        : <Space direction="vertical" style={{ width: '100%' }}>{related.map((r) => <KPCard key={r.kp_id} kp={r} color="var(--accent)" />)}</Space>,
    },
  ]

  return (
    <Drawer
      title={
        <div>
          <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--primary)' }}>{kp.name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, fontFamily: 'var(--font-mono)' }}>{kp.kp_id}</div>
        </div>
      }
      placement="right"
      onClose={onClose}
      open={open}
      width={400}
      styles={{
        body: { background: 'var(--bg-panel)', padding: 16 },
        header: { background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' },
        mask: { backdropFilter: 'blur(2px)' },
      }}
    >
      <Spin spinning={loading}>
        <Tabs items={items} />
      </Spin>
    </Drawer>
  )
}
