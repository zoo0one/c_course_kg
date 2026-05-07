import React, { useEffect, useMemo, useState } from 'react'
import { Card, Spin, Tooltip, message } from 'antd'
import {
  ReloadOutlined, FilterOutlined,
  ApartmentOutlined, CloseOutlined,
} from '@ant-design/icons'
import { GraphViewer } from '@/components/Graph/GraphViewer'
import { DetailPanel } from '@/components/KnowledgePoint/DetailPanel'
import { useAppStore } from '@/services/store'
import { chapterAPI, graphAPI, knowledgePointAPI } from '@/services/api'
import type { KnowledgePoint } from '@/types'

const EDGE_LEGEND = [
  { type: 'PREREQUISITE', color: '#38bdf8', lightColor: '#2563eb', label: '先修', dashed: false },
  { type: 'CONTAINS', color: '#34d399', lightColor: '#16a34a', label: '包含', dashed: false },
  { type: 'EXTENDS', color: '#a78bfa', lightColor: '#7c3aed', label: '扩展', dashed: false },
  { type: 'RELATED', color: '#475569', lightColor: '#94a3b8', label: '关联', dashed: true },
  { type: 'EXAMPLE_OF', color: '#f59e0b', lightColor: '#d97706', label: '例子', dashed: true },
]

type LayoutMode = 'graph' | 'prerequisite' | 'extends' | 'related' | 'structure'

const LAYOUT_OPTIONS: { key: LayoutMode; label: string }[] = [
  { key: 'graph', label: '图谱视图' },
  { key: 'prerequisite', label: '先修分层' },
  { key: 'extends', label: '扩展分层' },
  { key: 'related', label: '关联分层' },
  { key: 'structure', label: '结构模式' },
]

const RELATION_FILTER_OPTIONS = [
  { key: 'PREREQUISITE', label: '先修' },
  { key: 'EXTENDS', label: '扩展' },
  { key: 'RELATED', label: '关联' },
  { key: 'CONTAINS', label: '包含' },
  { key: 'EXAMPLE_OF', label: '例子' },
] as const

export const GraphViewPage: React.FC<{ selectedChapter?: string | null; highlightKPId?: string | null }> = ({ selectedChapter }) => {
  const [loading, setLoading] = useState(true)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedKP, setSelectedKP] = useState<KnowledgePoint | null>(null)
  const [prerequisites, setPrerequisites] = useState<KnowledgePoint[]>([])
  const [successors, setSuccessors] = useState<KnowledgePoint[]>([])
  const [related, setRelated] = useState<KnowledgePoint[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [showLegend, setShowLegend] = useState(true)
  const [layoutMode, setLayoutMode] = useState<LayoutMode>('graph')
  const [visibleRelationTypes, setVisibleRelationTypes] = useState<string[]>(['PREREQUISITE', 'EXTENDS', 'RELATED', 'EXAMPLE_OF'])
  const [backboneMode, setBackboneMode] = useState(true)
  const [mainChainMode, setMainChainMode] = useState(true)
  const [chapterDetail, setChapterDetail] = useState<any | null>(null)

  const graphNodes = useAppStore((s) => s.graphNodes)
  const graphEdges = useAppStore((s) => s.graphEdges)
  const setGraphData = useAppStore((s) => s.setGraphData)
  const theme = useAppStore((s) => s.theme)
  const isDark = theme === 'dark'

  useEffect(() => {
    if (graphNodes.length === 0) {
      setLoading(true)
      graphAPI.getGraph()
        .then((data) => { setGraphData(data.nodes, data.edges) })
        .catch(() => message.error('加载图谱失败'))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [graphNodes.length, setGraphData])

  useEffect(() => {
    if (!selectedChapter) {
      setChapterDetail(null)
      return
    }
    chapterAPI.getChapterDetail(selectedChapter)
      .then(setChapterDetail)
      .catch(() => setChapterDetail(null))
  }, [selectedChapter])

  const chapterNodes = useMemo(
    () => graphNodes.filter((node) => {
      if (!selectedChapter) return node.type === 'knowledge_point' || node.type === 'example'
      return (node.type === 'knowledge_point' || node.type === 'example') && node.data.chapter_id === selectedChapter
    }),
    [graphNodes, selectedChapter]
  )

  const chapterNodeIds = useMemo(() => new Set(chapterNodes.map((node) => node.id)), [chapterNodes])

  const filteredEdges = useMemo(
    () => graphEdges.filter((edge) => chapterNodeIds.has(edge.source) && chapterNodeIds.has(edge.target)),
    [graphEdges, chapterNodeIds]
  )

  const toggleRelationType = (type: string) => {
    setVisibleRelationTypes((prev) =>
      prev.includes(type) ? prev.filter((item) => item !== type) : [...prev, type]
    )
  }

  const handleNodeClick = async (node: any) => {
    if (node.type !== 'knowledge_point') {
      if (node.type === 'example') {
        message.info(`示例：${node.label}`)
      }
      return
    }
    setSelectedKP({ kp_id: node.id, name: node.label, chapter_id: node.data.chapter_id || '', section: node.data.section, aliases: node.data.aliases, source: node.data.source })
    setDetailOpen(true)
    setDetailLoading(true)
    try {
      const [pre, suc, rel] = await Promise.all([
        knowledgePointAPI.getPrerequisites(node.id).catch(() => []),
        knowledgePointAPI.getSuccessors(node.id).catch(() => []),
        knowledgePointAPI.getRelated(node.id).catch(() => []),
      ])
      const currentChapterOnly = (items: KnowledgePoint[]) => items.filter((item) => item.chapter_id === selectedChapter)
      setPrerequisites(selectedChapter ? currentChapterOnly(pre) : pre)
      setSuccessors(selectedChapter ? currentChapterOnly(suc) : suc)
      setRelated(selectedChapter ? currentChapterOnly(rel) : rel)
    } finally { setDetailLoading(false) }
  }

  const handleReload = async () => {
    setLoading(true)
    try {
      const d = await graphAPI.getGraph()
      setGraphData(d.nodes, d.edges)
      message.success('图谱已刷新')
    } catch {
      message.error('刷新失败')
    } finally {
      setLoading(false)
    }
  }

  const edgeLegendColors = isDark
    ? EDGE_LEGEND.map((e) => e.color)
    : EDGE_LEGEND.map((e) => e.lightColor)

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-base)' }}>
      <div style={{ padding: '8px 16px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0, gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <ApartmentOutlined style={{ color: 'var(--primary)', fontSize: 16 }} />
          <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 14 }}>知识图谱</span>
          <span style={{ background: 'var(--accent-glow)', border: '1px solid var(--accent)', color: 'var(--accent)', borderRadius: 4, padding: '2px 8px', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
            {selectedChapter || '未选择章节'}
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
            {chapterNodes.length} 节点 · {filteredEdges.length} 边
          </span>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {LAYOUT_OPTIONS.map((option) => (
            <button
              key={option.key}
              onClick={() => setLayoutMode(option.key)}
              style={{
                height: 32,
                padding: '0 10px',
                borderRadius: 6,
                border: '1px solid var(--border)',
                background: layoutMode === option.key ? 'var(--primary-glow)' : 'var(--bg-card)',
                color: layoutMode === option.key ? 'var(--primary)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              {option.label}
            </button>
          ))}

          <button
            onClick={() => setBackboneMode((prev) => !prev)}
            style={{
              height: 32,
              padding: '0 10px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: backboneMode ? 'rgba(56,189,248,0.16)' : 'var(--bg-card)',
              color: backboneMode ? 'var(--primary)' : 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            主干模式
          </button>

          <button
            onClick={() => setMainChainMode((prev) => !prev)}
            style={{
              height: 32,
              padding: '0 10px',
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: mainChainMode ? 'rgba(245,158,11,0.16)' : 'var(--bg-card)',
              color: mainChainMode ? 'var(--warning, #f59e0b)' : 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            主链提炼
          </button>

          {RELATION_FILTER_OPTIONS.map((option) => (
            <button
              key={option.key}
              onClick={() => toggleRelationType(option.key)}
              style={{
                height: 32,
                padding: '0 10px',
                borderRadius: 6,
                border: '1px solid var(--border)',
                background: visibleRelationTypes.includes(option.key) ? 'var(--accent-glow)' : 'var(--bg-card)',
                color: visibleRelationTypes.includes(option.key) ? 'var(--accent)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              {option.label}
            </button>
          ))}

          <Tooltip title={showLegend ? '隐藏图例' : '显示图例'}>
            <button onClick={() => setShowLegend(!showLegend)} style={{ width: 32, height: 32, borderRadius: 6, border: '1px solid var(--border)', background: showLegend ? 'var(--primary-glow)' : 'var(--bg-card)', color: showLegend ? 'var(--primary)' : 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>
              <FilterOutlined />
            </button>
          </Tooltip>
          <Tooltip title="刷新">
            <button onClick={handleReload} disabled={loading} style={{ width: 32, height: 32, borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, opacity: loading ? 0.5 : 1 }}>
              <ReloadOutlined spin={loading} />
            </button>
          </Tooltip>
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative', minHeight: 0, overflow: 'hidden' }}>
        {!selectedChapter ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            请先选择一个章节后再查看图谱
          </div>
        ) : loading && graphNodes.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
            <Spin size="large" />
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>加载知识图谱...</span>
          </div>
        ) : chapterNodes.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>当前章节暂无图谱数据</div>
        ) : (
          <div style={{ height: '100%', display: 'grid', gridTemplateColumns: chapterDetail ? 'minmax(0, 1fr) 320px' : '1fr', gap: 16, padding: 16 }}>
            <div style={{ minWidth: 0, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 14, overflow: 'hidden' }}>
              <GraphViewer
                nodes={chapterNodes}
                edges={filteredEdges}
                onNodeClick={handleNodeClick}
                loading={loading}
                layoutMode={layoutMode}
                visibleRelationTypes={visibleRelationTypes}
                activeNodeId={selectedKP?.kp_id ?? null}
                showLayerGuides={layoutMode !== 'graph'}
                backboneMode={backboneMode}
                mainChainMode={mainChainMode}
              />
            </div>

            {chapterDetail && (
              <Card
                title={chapterDetail.chapter.title}
                size="small"
                style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', height: 'fit-content' }}
                extra={<span style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}>{chapterDetail.chapter.chapter_id}</span>}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>本章知识点 {chapterDetail.kps.length} 个</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 'calc(100vh - 260px)', overflowY: 'auto' }}>
                    {chapterDetail.kps.map((kp: KnowledgePoint) => (
                      <button
                        key={kp.kp_id}
                        onClick={() => handleNodeClick({ id: kp.kp_id, label: kp.name, type: 'knowledge_point', data: kp })}
                        style={{
                          textAlign: 'left',
                          border: '1px solid var(--border)',
                          borderRadius: 10,
                          background: selectedKP?.kp_id === kp.kp_id ? 'var(--primary-glow)' : 'var(--bg-hover)',
                          padding: '10px 12px',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 13 }}>{kp.name}</div>
                        <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 4, lineHeight: 1.6 }}>
                          {kp.section || '未分节'} · {kp.source_book || kp.source || '来源未记录'}
                          {(kp.source_pages || kp.source_page) && (
                            <span> · {kp.source_pages || `第 ${kp.source_page} 页`}</span>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              </Card>
            )}
          </div>
        )}

        {showLegend && chapterNodes.length > 0 && selectedChapter && (
          <div style={{ position: 'absolute', bottom: 16, left: 16, background: 'var(--bg-panel)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px', zIndex: 10, minWidth: 160, boxShadow: '0 4px 20px rgba(0,0,0,0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ color: 'var(--text-muted)', fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>关系类型</span>
              <button onClick={() => setShowLegend(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12, padding: 0 }}><CloseOutlined /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {EDGE_LEGEND.map((leg, i) => (
                <div key={leg.type} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 24, height: 2, background: leg.dashed ? 'transparent' : edgeLegendColors[i], borderTop: leg.dashed ? `2px dashed ${edgeLegendColors[i]}` : 'none', flexShrink: 0 }} />
                  <span style={{ color: edgeLegendColors[i], fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600, minWidth: 80 }}>{leg.type}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{leg.label}</span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: 10 }}>
              结构模式会按入口、主链、分支、扩展来组织章节内容，帮助你看清章节骨架
            </div>
          </div>
        )}
      </div>

      <DetailPanel open={detailOpen} onClose={() => setDetailOpen(false)} kp={selectedKP} prerequisites={prerequisites} successors={successors} related={related} loading={detailLoading} />
    </div>
  )
}
