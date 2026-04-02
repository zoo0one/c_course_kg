import React, { useEffect, useState } from 'react'
import { Spin, Tooltip, message } from 'antd'
import {
  ReloadOutlined, FilterOutlined,
  ApartmentOutlined, CloseOutlined,
} from '@ant-design/icons'
import { GraphViewer } from '@/components/Graph/GraphViewer'
import { DetailPanel } from '@/components/KnowledgePoint/DetailPanel'
import { useAppStore } from '@/services/store'
import { graphAPI, knowledgePointAPI } from '@/services/api'
import type { KnowledgePoint } from '@/types'

const EDGE_LEGEND = [
  { type: 'PREREQUISITE', color: '#38bdf8', lightColor: '#2563eb', label: '先修', dashed: false },
  { type: 'CONTAINS',     color: '#34d399', lightColor: '#16a34a', label: '包含', dashed: false },
  { type: 'EXTENDS',      color: '#a78bfa', lightColor: '#7c3aed', label: '扩展', dashed: false },
  { type: 'RELATED',      color: '#475569', lightColor: '#94a3b8', label: '关联', dashed: true },
]

export const GraphViewPage: React.FC<{ selectedChapter?: string | null; highlightKPId?: string | null }> = ({ selectedChapter }) => {
  const [loading, setLoading] = useState(true)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedKP, setSelectedKP] = useState<KnowledgePoint | null>(null)
  const [prerequisites, setPrerequisites] = useState<KnowledgePoint[]>([])
  const [successors, setSuccessors] = useState<KnowledgePoint[]>([])
  const [related, setRelated] = useState<KnowledgePoint[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [showLegend, setShowLegend] = useState(true)

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

  const filteredNodes = selectedChapter
    ? graphNodes.filter((n) => n.data.chapter_id === selectedChapter || n.type === 'chapter')
    : graphNodes

  const filteredEdges = selectedChapter
    ? graphEdges.filter((e) => {
        const src = graphNodes.find((n) => n.id === e.source)
        const tgt = graphNodes.find((n) => n.id === e.target)
        return (src?.data.chapter_id === selectedChapter || src?.type === 'chapter')
          && (tgt?.data.chapter_id === selectedChapter || tgt?.type === 'chapter')
      })
    : graphEdges

  const handleNodeClick = async (node: any) => {
    if (node.type !== 'knowledge_point') return
    setSelectedKP({ kp_id: node.id, name: node.label, chapter_id: node.data.chapter_id || '', section: node.data.section, aliases: node.data.aliases, source: node.data.source })
    setDetailOpen(true)
    setDetailLoading(true)
    try {
      const [pre, suc, rel] = await Promise.all([
        knowledgePointAPI.getPrerequisites(node.id).catch(() => []),
        knowledgePointAPI.getSuccessors(node.id).catch(() => []),
        knowledgePointAPI.getRelated(node.id).catch(() => []),
      ])
      setPrerequisites(pre); setSuccessors(suc); setRelated(rel)
    } finally { setDetailLoading(false) }
  }

  const handleReload = async () => {
    setLoading(true)
    try { const d = await graphAPI.getGraph(); setGraphData(d.nodes, d.edges); message.success('图谱已刷新') }
    catch { message.error('刷新失败') }
    finally { setLoading(false) }
  }

  const edgeLegendColors = isDark
    ? EDGE_LEGEND.map((e) => e.color)
    : EDGE_LEGEND.map((e) => e.lightColor)

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: 'var(--bg-base)' }}>

      {/* 工具栏 */}
      <div style={{ padding: '8px 16px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0, gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ApartmentOutlined style={{ color: 'var(--primary)', fontSize: 16 }} />
          <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 14 }}>知识图谱</span>
          {selectedChapter && (
            <span style={{ background: 'var(--accent-glow)', border: '1px solid var(--accent)', color: 'var(--accent)', borderRadius: 4, padding: '2px 8px', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
              {selectedChapter}
            </span>
          )}
          <span style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
            {filteredNodes.length} 节点 · {filteredEdges.length} 边
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
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

      {/* 图谱区 */}
      <div style={{ flex: 1, position: 'relative', minHeight: 0, overflow: 'hidden' }}>
        {loading && graphNodes.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', flexDirection: 'column', gap: 12 }}>
            <Spin size="large" />
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>加载知识图谱...</span>
          </div>
        ) : filteredNodes.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>暂无数据</div>
        ) : (
          <GraphViewer nodes={filteredNodes} edges={filteredEdges} onNodeClick={handleNodeClick} loading={loading} />
        )}

        {/* 悬浮图例 */}
        {showLegend && filteredNodes.length > 0 && (
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
              点击节点查看详情 · 双击居中
            </div>
          </div>
        )}
      </div>

      <DetailPanel open={detailOpen} onClose={() => setDetailOpen(false)} kp={selectedKP} prerequisites={prerequisites} successors={successors} related={related} loading={detailLoading} />
    </div>
  )
}
