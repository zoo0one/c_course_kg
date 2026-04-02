import React, { useEffect, useRef } from 'react'
import cytoscape, { Core, NodeSingular } from 'cytoscape'
// @ts-ignore
import coseBilkent from 'cytoscape-cose-bilkent'
import { Spin } from 'antd'
import { useAppStore } from '@/services/store'

cytoscape.use(coseBilkent)

interface GraphViewerProps {
  nodes: any[]
  edges: any[]
  onNodeClick?: (node: any) => void
  loading?: boolean
}

export const GraphViewer: React.FC<GraphViewerProps> = ({ nodes, edges, onNodeClick, loading = false }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const theme = useAppStore((state) => state.theme)

  const isDark = theme === 'dark'

  // 主题色定义
  const T = isDark ? {
    bg: '#080d1a',
    nodeBg: (cat: string) => (({ control:'#1e3a5f', datatype:'#1a3a2a', function:'#2a1e3f', memory:'#3a2a1a', syntax:'#1a2a3a', algorithm:'#2a1a2a' } as any)[cat] || '#162040'),
    chapterBg: '#1e3a5f',
    nodeBorder: (cat: string) => (({ control:'#38bdf8', datatype:'#34d399', function:'#a78bfa', memory:'#f59e0b', syntax:'#60a5fa', algorithm:'#f472b6' } as any)[cat] || '#2d4170'),
    chapterBorder: '#38bdf8',
    nodeLabel: '#cbd5e1',
    chapterLabel: '#e2e8f0',
    edgeColor: (type: string) => (({ PREREQUISITE:'#38bdf8', CONTAINS:'#34d399', EXTENDS:'#a78bfa', RELATED:'#475569' } as any)[type] || '#334155'),
    selectedBg: '#3a2e10',
    selectedBorder: '#f59e0b',
  } : {
    bg: '#f8fafc',
    nodeBg: (cat: string) => (({ control:'#eff6ff', datatype:'#f0fdf4', function:'#faf5ff', memory:'#fffbeb', syntax:'#eff6ff', algorithm:'#fdf2f8' } as any)[cat] || '#f1f5f9'),
    chapterBg: '#eff6ff',
    nodeBorder: (cat: string) => (({ control:'#2563eb', datatype:'#16a34a', function:'#7c3aed', memory:'#d97706', syntax:'#2563eb', algorithm:'#db2777' } as any)[cat] || '#94a3b8'),
    chapterBorder: '#2563eb',
    nodeLabel: '#1e293b',
    chapterLabel: '#0f172a',
    edgeColor: (type: string) => (({ PREREQUISITE:'#2563eb', CONTAINS:'#16a34a', EXTENDS:'#7c3aed', RELATED:'#94a3b8' } as any)[type] || '#cbd5e1'),
    selectedBg: '#fef3c7',
    selectedBorder: '#d97706',
  }

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return

    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: nodes.map((n) => ({ data: { id: n.id, label: n.label, type: n.type, ...n.data } })),
        edges: edges.map((e) => ({ data: { id: e.id, source: e.source, target: e.target, label: e.label, type: e.type } })),
      },
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: NodeSingular) =>
              ele.data('type') === 'chapter' ? T.chapterBg : T.nodeBg(ele.data('category')),
            'border-color': (ele: NodeSingular) =>
              ele.data('type') === 'chapter' ? T.chapterBorder : T.nodeBorder(ele.data('category')),
            label: 'data(label)',
            color: T.nodeLabel,
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'font-family': 'Noto Sans SC, sans-serif',
            width: 62,
            height: 62,
            'border-width': 2,
            'text-wrap': 'wrap',
            'text-max-width': '68px',
          },
        },
        {
          selector: 'node[type="chapter"]',
          style: {
            width: 82,
            height: 82,
            'font-size': '13px',
            'font-weight': 600,
            'border-width': 3,
            color: T.chapterLabel,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': T.selectedBorder,
            'background-color': T.selectedBg,
          },
        },
        {
          selector: 'node:hover',
          style: {
            'border-width': 3,
            opacity: 1,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.5,
            'line-color': (ele: any) => T.edgeColor(ele.data('type')),
            'target-arrow-color': (ele: any) => T.edgeColor(ele.data('type')),
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: isDark ? 0.7 : 0.6,
          },
        },
        {
          selector: 'edge[type="RELATED"]',
          style: { 'line-style': 'dashed', opacity: isDark ? 0.4 : 0.35 },
        },
        {
          selector: 'edge:selected',
          style: {
            'line-color': T.selectedBorder,
            'target-arrow-color': T.selectedBorder,
            width: 3,
            opacity: 1,
          },
        },
      ],
      layout: ({
        name: 'cose-bilkent',
        nodeDimensionsIncludeLabels: true,
        idealEdgeLength: 100,
        nodeRepulsion: 4500,
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        tile: true,
        tilingPaddingVertical: 10,
        tilingPaddingHorizontal: 10,
      } as any),
      minZoom: 0.2,
      maxZoom: 4,
      wheelSensitivity: 0.2,
    })

    cy.on('tap', 'node', (event) => {
      const node = event.target
      onNodeClick?.({ id: node.data('id'), label: node.data('label'), type: node.data('type'), data: node.data() })
    })

    cy.on('dbltap', 'node', (event) => {
      cy.animate({ center: { eles: event.target }, zoom: 1.8, duration: 400 })
    })

    cyRef.current = cy
    return () => { cy.destroy() }
  }, [nodes, edges, onNodeClick, theme])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {loading && (
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', zIndex: 10 }}>
          <Spin size="large" />
        </div>
      )}
      <div ref={containerRef} style={{ width: '100%', height: '100%', background: T.bg }} />
    </div>
  )
}
