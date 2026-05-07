import React, { useEffect, useMemo, useRef } from 'react'
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
  layoutMode?: 'graph' | 'prerequisite' | 'extends' | 'related' | 'structure'
  visibleRelationTypes?: string[]
  activeNodeId?: string | null
  showLayerGuides?: boolean
  backboneMode?: boolean
  mainChainMode?: boolean
}

type GraphNode = {
  id: string
  label: string
  type: string
  data?: Record<string, any>
}

type GraphEdge = {
  id: string | number
  source: string
  target: string
  label?: string
  type: string
}

type Position = { x: number; y: number }
type LayeredLayoutResult = {
  positions: Record<string, Position>
  maxLayer: number
}

const LAYER_GAP_Y = 220
const NODE_GAP_X = 124

function distributeCentered(count: number, spacing: number) {
  if (count <= 1) return [0]
  const totalWidth = (count - 1) * spacing
  return Array.from({ length: count }, (_, index) => index * spacing - totalWidth / 2)
}

function buildRelationLayeredPositions(nodes: GraphNode[], edges: GraphEdge[], relationType: GraphEdge['type']): LayeredLayoutResult {
  const positions: Record<string, Position> = {}
  const nodeIds = new Set(nodes.map((node) => node.id))
  const relationEdges = edges.filter((edge) => edge.type === relationType && nodeIds.has(edge.source) && nodeIds.has(edge.target))

  if (relationEdges.length === 0) {
    const offsets = distributeCentered(nodes.length, NODE_GAP_X)
    nodes.forEach((node, index) => {
      positions[node.id] = { x: offsets[index] ?? 0, y: 0 }
    })
    return { positions, maxLayer: 0 }
  }

  const inDegree = new Map<string, number>()
  const outgoing = new Map<string, string[]>()
  const incoming = new Map<string, string[]>()
  const depth = new Map<string, number>()

  nodes.forEach((node) => {
    inDegree.set(node.id, 0)
    outgoing.set(node.id, [])
    incoming.set(node.id, [])
    depth.set(node.id, 0)
  })

  relationEdges.forEach((edge) => {
    outgoing.get(edge.source)?.push(edge.target)
    incoming.get(edge.target)?.push(edge.source)
    inDegree.set(edge.target, (inDegree.get(edge.target) ?? 0) + 1)
  })

  const queue = nodes.filter((node) => (inDegree.get(node.id) ?? 0) === 0).map((node) => node.id)
  const visited = new Set<string>()

  while (queue.length > 0) {
    const current = queue.shift()!
    visited.add(current)
    const currentDepth = depth.get(current) ?? 0

    for (const next of outgoing.get(current) ?? []) {
      depth.set(next, Math.max(depth.get(next) ?? 0, currentDepth + 1))
      const nextDegree = (inDegree.get(next) ?? 0) - 1
      inDegree.set(next, nextDegree)
      if (nextDegree === 0) queue.push(next)
    }
  }

  nodes.forEach((node) => {
    if (!visited.has(node.id)) depth.set(node.id, Math.max(1, depth.get(node.id) ?? 0))
  })

  const nodesById = new Map(nodes.map((node) => [node.id, node]))
  const layerCenter = new Map<number, number>()
  const layers = new Map<number, GraphNode[]>()

  nodes.forEach((node) => {
    const layer = depth.get(node.id) ?? 0
    const list = layers.get(layer) ?? []
    list.push(node)
    layers.set(layer, list)
  })

  const sortedLayers = Array.from(layers.entries()).sort((a, b) => a[0] - b[0])
  let maxLayer = 0

  sortedLayers.forEach(([layer, layerNodes]) => {
    maxLayer = Math.max(maxLayer, layer)

    layerNodes.sort((a, b) => {
      const parentsA = incoming.get(a.id) ?? []
      const parentsB = incoming.get(b.id) ?? []
      const parentAvgA = parentsA.length > 0
        ? parentsA.reduce((sum, id) => sum + (layerCenter.get((depth.get(id) ?? 0)) ?? 0), 0) / parentsA.length
        : 0
      const parentAvgB = parentsB.length > 0
        ? parentsB.reduce((sum, id) => sum + (layerCenter.get((depth.get(id) ?? 0)) ?? 0), 0) / parentsB.length
        : 0

      if (parentAvgA !== parentAvgB) return parentAvgA - parentAvgB
      return a.label.localeCompare(b.label, 'zh-CN')
    })

    const offsets = distributeCentered(layerNodes.length, NODE_GAP_X)
    layerNodes.forEach((node, index) => {
      positions[node.id] = {
        x: offsets[index] ?? 0,
        y: layer * LAYER_GAP_Y,
      }
    })

    if (layerNodes.length > 0) {
      const center = layerNodes.reduce((sum, node) => sum + (positions[node.id]?.x ?? 0), 0) / layerNodes.length
      layerCenter.set(layer, center)
    }
  })

  const relationSet = new Set(relationEdges.map((edge) => `${edge.source}__${edge.target}`))
  nodes.forEach((node) => {
    if (!positions[node.id]) {
      positions[node.id] = { x: 0, y: (depth.get(node.id) ?? 0) * LAYER_GAP_Y }
    }

    const neighbors = [
      ...(outgoing.get(node.id) ?? []),
      ...(incoming.get(node.id) ?? []),
    ].map((id) => nodesById.get(id)).filter(Boolean) as GraphNode[]

    if (neighbors.length === 0) return

    const targetX = neighbors.reduce((sum, neighbor) => sum + (positions[neighbor.id]?.x ?? 0), 0) / neighbors.length
    positions[node.id].x = positions[node.id].x * 0.55 + targetX * 0.45
  })

  relationEdges.forEach((edge) => {
    if (!relationSet.has(`${edge.source}__${edge.target}`)) return
    const sourcePos = positions[edge.source]
    const targetPos = positions[edge.target]
    if (!sourcePos || !targetPos) return

    if (Math.abs(sourcePos.x - targetPos.x) < 24) {
      targetPos.x += sourcePos.x <= targetPos.x ? 30 : -30
    }
  })

  return { positions, maxLayer }
}

function collectReachable(edgeMap: Map<string, string[]>, startId: string) {
  const visited = new Set<string>()
  const stack = [...(edgeMap.get(startId) ?? [])]

  while (stack.length > 0) {
    const current = stack.pop()!
    if (visited.has(current)) continue
    visited.add(current)
    for (const next of edgeMap.get(current) ?? []) stack.push(next)
  }

  return visited
}

function buildMainChain(prereqEdges: GraphEdge[]) {
  if (prereqEdges.length === 0) return { nodeIds: new Set<string>(), edgeIds: new Set<string | number>(), path: [] as string[] }

  const outgoing = new Map<string, string[]>()
  const incomingCount = new Map<string, number>()
  const nodes = new Set<string>()

  prereqEdges.forEach((edge) => {
    nodes.add(edge.source)
    nodes.add(edge.target)
    outgoing.set(edge.source, [...(outgoing.get(edge.source) ?? []), edge.target])
    incomingCount.set(edge.target, (incomingCount.get(edge.target) ?? 0) + 1)
    if (!incomingCount.has(edge.source)) incomingCount.set(edge.source, incomingCount.get(edge.source) ?? 0)
  })

  const startNodes = [...nodes].filter((id) => (incomingCount.get(id) ?? 0) === 0)
  const memo = new Map<string, string[]>()
  const visiting = new Set<string>()

  const dfs = (nodeId: string): string[] => {
    if (memo.has(nodeId)) return memo.get(nodeId)!
    if (visiting.has(nodeId)) return [nodeId]
    visiting.add(nodeId)

    const nextNodes = outgoing.get(nodeId) ?? []
    let bestPath = [nodeId]

    for (const next of nextNodes) {
      const subPath = dfs(next)
      const candidate = [nodeId, ...subPath]
      if (candidate.length > bestPath.length) bestPath = candidate
    }

    visiting.delete(nodeId)
    memo.set(nodeId, bestPath)
    return bestPath
  }

  let mainPath: string[] = []
  const searchRoots = startNodes.length > 0 ? startNodes : [...nodes]
  for (const start of searchRoots) {
    const path = dfs(start)
    if (path.length > mainPath.length) mainPath = path
  }

  const nodeIds = new Set(mainPath)
  const edgeIds = new Set<string | number>()
  for (let i = 0; i < mainPath.length - 1; i += 1) {
    const source = mainPath[i]
    const target = mainPath[i + 1]
    const matched = prereqEdges.find((edge) => edge.source === source && edge.target === target)
    if (matched) edgeIds.add(matched.id)
  }

  return { nodeIds, edgeIds, path: mainPath }
}

function buildStructureLayout(nodes: GraphNode[], edges: GraphEdge[], mainChain: ReturnType<typeof buildMainChain>): LayeredLayoutResult {
  const positions: Record<string, Position> = {}
  const prereqEdges = edges.filter((edge) => edge.type === 'PREREQUISITE')
  const extendsEdges = edges.filter((edge) => edge.type === 'EXTENDS')
  const relatedEdges = edges.filter((edge) => edge.type === 'RELATED')
  const exampleEdges = edges.filter((edge) => edge.type === 'EXAMPLE_OF')

  const roleByNode = new Map<string, 'entry' | 'main' | 'branch' | 'extension' | 'related' | 'isolated' | 'example'>()
  const mainPath = mainChain.path
  const exampleTargetMap = new Map<string, string[]>()

  exampleEdges.forEach((edge) => {
    const list = exampleTargetMap.get(edge.target) ?? []
    list.push(edge.source)
    exampleTargetMap.set(edge.target, list)
  })

  nodes.forEach((node) => {
    if (node.type === 'example') {
      roleByNode.set(node.id, 'example')
      return
    }

    if (mainChain.nodeIds.has(node.id)) {
      roleByNode.set(node.id, node.id === mainPath[0] ? 'entry' : 'main')
      return
    }

    const connectedToMainByPrereq = prereqEdges.some((edge) =>
      (mainChain.nodeIds.has(edge.source) && edge.target === node.id) ||
      (mainChain.nodeIds.has(edge.target) && edge.source === node.id)
    )
    if (connectedToMainByPrereq) {
      roleByNode.set(node.id, 'branch')
      return
    }

    const connectedToMainByExtends = extendsEdges.some((edge) =>
      (mainChain.nodeIds.has(edge.source) && edge.target === node.id) ||
      (mainChain.nodeIds.has(edge.target) && edge.source === node.id)
    )
    if (connectedToMainByExtends) {
      roleByNode.set(node.id, 'extension')
      return
    }

    const connectedToMainByRelated = relatedEdges.some((edge) =>
      (mainChain.nodeIds.has(edge.source) && edge.target === node.id) ||
      (mainChain.nodeIds.has(edge.target) && edge.source === node.id)
    )
    if (connectedToMainByRelated) {
      roleByNode.set(node.id, 'related')
      return
    }

    roleByNode.set(node.id, 'isolated')
  })

  const mainSpacingY = 190
  const branchOffsetX = 200
  const extensionOffsetX = 320
  const relatedOffsetX = -170
  const isolatedOffsetX = -280
  const exampleOffsetX = -220

  mainPath.forEach((nodeId, index) => {
    positions[nodeId] = { x: 0, y: index * mainSpacingY }
  })

  const nearestMainIndex = (nodeId: string) => {
    let bestIdx = 0
    let bestDistance = Number.MAX_SAFE_INTEGER

    prereqEdges.forEach((edge) => {
      if (edge.source === nodeId && mainChain.nodeIds.has(edge.target)) {
        const idx = mainPath.indexOf(edge.target)
        if (idx >= 0 && idx < bestDistance) {
          bestIdx = idx
          bestDistance = idx
        }
      }
      if (edge.target === nodeId && mainChain.nodeIds.has(edge.source)) {
        const idx = mainPath.indexOf(edge.source)
        if (idx >= 0 && idx < bestDistance) {
          bestIdx = idx
          bestDistance = idx
        }
      }
    })

    extendsEdges.forEach((edge) => {
      const neighbor = edge.source === nodeId ? edge.target : edge.target === nodeId ? edge.source : null
      if (neighbor && mainChain.nodeIds.has(neighbor)) {
        const idx = mainPath.indexOf(neighbor)
        if (idx >= 0 && idx < bestDistance) {
          bestIdx = idx
          bestDistance = idx
        }
      }
    })

    relatedEdges.forEach((edge) => {
      const neighbor = edge.source === nodeId ? edge.target : edge.target === nodeId ? edge.source : null
      if (neighbor && mainChain.nodeIds.has(neighbor)) {
        const idx = mainPath.indexOf(neighbor)
        if (idx >= 0 && idx < bestDistance) {
          bestIdx = idx
          bestDistance = idx
        }
      }
    })

    return bestIdx
  }

  const groupedByRole = new Map<string, GraphNode[]>()
  nodes.forEach((node) => {
    if (mainChain.nodeIds.has(node.id) || node.type === 'example') return
    const role = roleByNode.get(node.id) ?? 'isolated'
    const list = groupedByRole.get(role) ?? []
    list.push(node)
    groupedByRole.set(role, list)
  })

  ;['branch', 'extension', 'related', 'isolated'].forEach((role) => {
    const roleNodes = groupedByRole.get(role) ?? []
    roleNodes.sort((a, b) => nearestMainIndex(a.id) - nearestMainIndex(b.id) || a.label.localeCompare(b.label, 'zh-CN'))

    const slotCount = new Map<number, number>()
    roleNodes.forEach((node) => {
      const anchorIndex = nearestMainIndex(node.id)
      const slot = slotCount.get(anchorIndex) ?? 0
      slotCount.set(anchorIndex, slot + 1)

      const baseY = anchorIndex * mainSpacingY
      const stackOffsetY = slot * 74
      const x = role === 'branch'
        ? branchOffsetX + (slot % 2) * 26
        : role === 'extension'
          ? extensionOffsetX + (slot % 2) * 26
          : role === 'related'
            ? relatedOffsetX - (slot % 2) * 26
            : isolatedOffsetX - (slot % 2) * 26

      positions[node.id] = {
        x,
        y: baseY + stackOffsetY,
      }
    })
  })

  const exampleSlotCount = new Map<string, number>()
  nodes.filter((node) => node.type === 'example').forEach((exampleNode) => {
    const targets = exampleEdges.filter((edge) => edge.source === exampleNode.id).map((edge) => edge.target)
    const targetId = targets[0]
    const targetPosition = targetId ? positions[targetId] : null

    if (targetPosition) {
      const slot = exampleSlotCount.get(targetId) ?? 0
      exampleSlotCount.set(targetId, slot + 1)
      positions[exampleNode.id] = {
        x: targetPosition.x + exampleOffsetX - slot * 10,
        y: targetPosition.y + slot * 50 - 8,
      }
      return
    }

    positions[exampleNode.id] = {
      x: exampleOffsetX,
      y: Object.keys(positions).length * 36,
    }
  })

  const maxLayer = Math.max(0, ...Object.values(positions).map((pos) => Math.round(pos.y / mainSpacingY)))
  return { positions, maxLayer }
}

export const GraphViewer: React.FC<GraphViewerProps> = ({
  nodes,
  edges,
  onNodeClick,
  loading = false,
  layoutMode = 'graph',
  visibleRelationTypes = ['PREREQUISITE', 'CONTAINS', 'EXTENDS', 'RELATED', 'EXAMPLE_OF'],
  activeNodeId = null,
  showLayerGuides = false,
  backboneMode = false,
  mainChainMode = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const theme = useAppStore((state) => state.theme)

  const isDark = theme === 'dark'
  const typedNodes = useMemo(() => nodes as GraphNode[], [nodes])
  const typedEdges = useMemo(() => edges as GraphEdge[], [edges])
  const filteredEdges = useMemo(
    () => typedEdges.filter((edge) => visibleRelationTypes.includes(edge.type)),
    [typedEdges, visibleRelationTypes]
  )
  const backboneNodeIds = useMemo(() => {
    if (!backboneMode) return null

    const prereqEdges = filteredEdges.filter((edge) => edge.type === 'PREREQUISITE')
    if (prereqEdges.length === 0) return null

    const ids = new Set<string>()
    prereqEdges.forEach((edge) => {
      ids.add(edge.source)
      ids.add(edge.target)
    })
    return ids
  }, [backboneMode, filteredEdges])
  const mainChain = useMemo(
    () => buildMainChain(filteredEdges.filter((edge) => edge.type === 'PREREQUISITE')),
    [filteredEdges]
  )

  const T = isDark
    ? {
        bg: '#080d1a',
        nodeBg: (cat: string) =>
          (
            {
              control: '#1e3a5f',
              datatype: '#1a3a2a',
              function: '#2a1e3f',
              memory: '#3a2a1a',
              syntax: '#1a2a3a',
              algorithm: '#2a1a2a',
            } as any
          )[cat] || '#162040',
        nodeBorder: (cat: string) =>
          (
            {
              control: '#38bdf8',
              datatype: '#34d399',
              function: '#a78bfa',
              memory: '#f59e0b',
              syntax: '#60a5fa',
              algorithm: '#f472b6',
            } as any
          )[cat] || '#2d4170',
        nodeLabel: '#cbd5e1',
        edgeColor: (type: string) =>
          (
            {
              PREREQUISITE: '#38bdf8',
              CONTAINS: '#34d399',
              EXTENDS: '#a78bfa',
              RELATED: '#64748b',
              EXAMPLE_OF: '#f59e0b',
            } as any
          )[type] || '#334155',
        activeGlow: '#fde68a',
        activeEdge: '#fbbf24',
        backboneEdge: '#38bdf8',
        mainChainEdge: '#f59e0b',
        mainChainNodeBorder: '#fde68a',
        roleColors: {
          entry: '#f59e0b',
          main: '#38bdf8',
          branch: '#34d399',
          extension: '#a78bfa',
          related: '#94a3b8',
          isolated: '#64748b',
        },
        auxNodeOpacity: 0.4,
        auxEdgeOpacity: 0.1,
        mutedNodeOpacity: 0.3,
        mutedEdgeOpacity: 0.08,
      }
    : {
        bg: '#f8fafc',
        nodeBg: (cat: string) =>
          (
            {
              control: '#eff6ff',
              datatype: '#f0fdf4',
              function: '#faf5ff',
              memory: '#fffbeb',
              syntax: '#eff6ff',
              algorithm: '#fdf2f8',
            } as any
          )[cat] || '#f1f5f9',
        nodeBorder: (cat: string) =>
          (
            {
              control: '#2563eb',
              datatype: '#16a34a',
              function: '#7c3aed',
              memory: '#d97706',
              syntax: '#2563eb',
              algorithm: '#db2777',
            } as any
          )[cat] || '#94a3b8',
        nodeLabel: '#1e293b',
        edgeColor: (type: string) =>
          (
            {
              PREREQUISITE: '#2563eb',
              CONTAINS: '#16a34a',
              EXTENDS: '#7c3aed',
              RELATED: '#94a3b8',
              EXAMPLE_OF: '#d97706',
            } as any
          )[type] || '#cbd5e1',
        activeGlow: '#f59e0b',
        activeEdge: '#d97706',
        backboneEdge: '#2563eb',
        mainChainEdge: '#d97706',
        mainChainNodeBorder: '#f59e0b',
        roleColors: {
          entry: '#d97706',
          main: '#2563eb',
          branch: '#16a34a',
          extension: '#7c3aed',
          related: '#64748b',
          isolated: '#94a3b8',
        },
        auxNodeOpacity: 0.42,
        auxEdgeOpacity: 0.12,
        mutedNodeOpacity: 0.32,
        mutedEdgeOpacity: 0.1,
      }

  useEffect(() => {
    if (!containerRef.current || typedNodes.length === 0) return

    const relationType =
      layoutMode === 'prerequisite'
        ? 'PREREQUISITE'
        : layoutMode === 'extends'
          ? 'EXTENDS'
          : layoutMode === 'related'
            ? 'RELATED'
            : null

    const layered = layoutMode === 'structure'
      ? buildStructureLayout(typedNodes, filteredEdges, mainChain)
      : relationType
        ? buildRelationLayeredPositions(typedNodes, filteredEdges, relationType)
        : null
    const positions = layered?.positions ?? null
    const maxLayer = layered?.maxLayer ?? 0

    const guideNodes = positions && showLayerGuides
      ? Array.from({ length: maxLayer + 1 }, (_, layer) => ({
          data: {
            id: `guide-layer-${layer}`,
            label: layoutMode === 'structure'
              ? layer === 0
                ? '入口/主线'
                : `阶段 ${layer}`
              : `L${layer}`,
            type: 'layer-guide',
            layer,
          },
          position: { x: layoutMode === 'structure' ? -520 : -260, y: layer * LAYER_GAP_Y },
          selectable: false,
          grabbable: false,
          locked: true,
        }))
      : []

    const cy = cytoscape({
      container: containerRef.current,
      elements: {
        nodes: [
          ...typedNodes.map((node) => ({
            data: {
              id: node.id,
              label: node.label,
              type: node.type,
              ...node.data,
            },
            ...(positions ? { position: positions[node.id] ?? { x: 0, y: 0 } } : {}),
          })),
          ...guideNodes,
        ],
        edges: filteredEdges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.label,
            type: edge.type,
          },
        })),
      },
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: NodeSingular) => T.nodeBg(ele.data('category')),
            'border-color': (ele: NodeSingular) => T.nodeBorder(ele.data('category')),
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
            opacity: 1,
          },
        },
        {
          selector: 'node[type="example"]',
          style: {
            shape: 'round-rectangle',
            width: 92,
            height: 46,
            'background-color': isDark ? '#3a2a12' : '#fff7ed',
            'border-color': isDark ? '#f59e0b' : '#d97706',
            'border-width': 2,
            color: isDark ? '#fde68a' : '#9a3412',
            'font-size': '10px',
            'font-style': 'italic',
            'text-max-width': '96px',
            'padding': '6px',
            'z-index': 8,
          },
        },
        {
          selector: 'node.role-entry',
          style: {
            'border-width': 5,
            'border-color': T.roleColors.entry,
            width: 74,
            height: 74,
          },
        },
        {
          selector: 'node.role-main',
          style: {
            'border-width': 4,
            'border-color': T.roleColors.main,
          },
        },
        {
          selector: 'node.role-branch',
          style: {
            'border-width': 3,
            'border-color': T.roleColors.branch,
          },
        },
        {
          selector: 'node.role-extension',
          style: {
            'border-width': 3,
            'border-color': T.roleColors.extension,
            shape: 'round-rectangle',
          },
        },
        {
          selector: 'node.role-related',
          style: {
            'border-width': 2,
            'border-color': T.roleColors.related,
          },
        },
        {
          selector: 'node.role-isolated',
          style: {
            'border-width': 2,
            'border-color': T.roleColors.isolated,
            opacity: 0.72,
          },
        },
        {
          selector: 'node.main-chain-node',
          style: {
            'border-width': 5,
            'border-color': T.mainChainNodeBorder,
            opacity: 1,
            'z-index': 14,
          },
        },
        {
          selector: 'node.backbone-node',
          style: {
            opacity: T.backboneNodeOpacity,
            'border-width': 3,
            'z-index': 9,
          },
        },
        {
          selector: 'node.aux-node',
          style: {
            opacity: T.auxNodeOpacity,
          },
        },
        {
          selector: 'node[type="layer-guide"]',
          style: {
            width: 40,
            height: 40,
            shape: 'round-rectangle',
            'background-color': 'transparent',
            'border-color': isDark ? '#1f334f' : '#cbd5e1',
            'border-width': 1,
            label: 'data(label)',
            color: isDark ? '#7dd3fc' : '#475569',
            'font-size': '10px',
            'font-family': 'var(--font-mono)',
            'text-wrap': 'none',
            opacity: 0.9,
            events: 'no',
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
          selector: 'node.active-node',
          style: {
            'border-width': 4,
            'border-color': T.activeGlow,
            'overlay-color': T.activeGlow,
            'overlay-opacity': 0.12,
            'overlay-padding': 10,
            opacity: 1,
            'z-index': 12,
          },
        },
        {
          selector: 'node.active-neighbor',
          style: {
            'border-width': 3,
            'border-color': T.activeEdge,
            opacity: 1,
            'z-index': 11,
          },
        },
        {
          selector: 'node.dimmed',
          style: {
            opacity: T.mutedNodeOpacity,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 1.4,
            'line-color': (ele: any) => T.edgeColor(ele.data('type')),
            'target-arrow-color': (ele: any) => T.edgeColor(ele.data('type')),
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: isDark ? 0.55 : 0.5,
            'arrow-scale': 0.9,
          },
        },
        {
          selector: 'edge[type="PREREQUISITE"]',
          style: {
            width: 3,
            opacity: 0.92,
            'arrow-scale': 1.1,
          },
        },
        {
          selector: 'edge[type="CONTAINS"]',
          style: {
            width: 1.2,
            opacity: isDark ? 0.16 : 0.12,
          },
        },
        {
          selector: 'edge[type="EXTENDS"]',
          style: {
            width: 2.1,
            opacity: 0.72,
          },
        },
        {
          selector: 'edge[type="RELATED"]',
          style: {
            width: 1.2,
            'line-style': 'dashed',
            opacity: isDark ? 0.3 : 0.26,
            'target-arrow-shape': 'none',
          },
        },
        {
          selector: 'edge[type="EXAMPLE_OF"]',
          style: {
            width: 2.2,
            'line-style': 'dashed',
            opacity: 0.9,
            'curve-style': 'unbundled-bezier',
            'control-point-distances': [-24, 24],
            'target-arrow-shape': 'none',
          },
        },
        {
          selector: 'edge.main-chain-edge',
          style: {
            width: 5.4,
            'line-color': T.mainChainEdge,
            'target-arrow-color': T.mainChainEdge,
            opacity: 1,
            'z-index': 14,
          },
        },
        {
          selector: 'edge.backbone-edge',
          style: {
            width: 4.2,
            'line-color': T.backboneEdge,
            'target-arrow-color': T.backboneEdge,
            opacity: 0.98,
            'z-index': 9,
          },
        },
        {
          selector: 'edge.aux-edge',
          style: {
            opacity: T.auxEdgeOpacity,
          },
        },
        {
          selector: 'edge.active-edge',
          style: {
            width: 4,
            'line-color': T.activeEdge,
            'target-arrow-color': T.activeEdge,
            opacity: 1,
            'z-index': 13,
          },
        },
        {
          selector: 'edge.dimmed',
          style: {
            opacity: T.mutedEdgeOpacity,
          },
        },
      ],
      layout: positions
        ? { name: 'preset', fit: true, padding: 70 }
        : ({
            name: 'cose-bilkent',
            nodeDimensionsIncludeLabels: true,
            idealEdgeLength: 110,
            nodeRepulsion: 4500,
            edgeElasticity: 0.45,
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

    if (layoutMode === 'structure') {
      const prereqNodeSet = mainChain.nodeIds
      cy.nodes().forEach((node) => {
        const type = String(node.data('type'))
        if (type === 'layer-guide') return
        const id = String(node.data('id'))
        node.removeClass('role-entry role-main role-branch role-extension role-related role-isolated')

        if (mainChain.path[0] === id) {
          node.addClass('role-entry')
          return
        }
        if (prereqNodeSet.has(id)) {
          node.addClass('role-main')
          return
        }

        const edgeList = filteredEdges
        const branchConnected = edgeList.some((edge) => edge.type === 'PREREQUISITE' && ((mainChain.nodeIds.has(edge.source) && edge.target === id) || (mainChain.nodeIds.has(edge.target) && edge.source === id)))
        const extendConnected = edgeList.some((edge) => edge.type === 'EXTENDS' && (edge.source === id || edge.target === id))
        const relatedConnected = edgeList.some((edge) => edge.type === 'RELATED' && (edge.source === id || edge.target === id))

        if (branchConnected) node.addClass('role-branch')
        else if (extendConnected) node.addClass('role-extension')
        else if (relatedConnected) node.addClass('role-related')
        else node.addClass('role-isolated')
      })
    }

    if (backboneMode && backboneNodeIds) {
      cy.nodes().forEach((node) => {
        const type = String(node.data('type'))
        if (type === 'layer-guide') return
        const id = String(node.data('id'))
        node.removeClass('main-chain-node backbone-node aux-node')
        if (mainChainMode && mainChain.nodeIds.has(id)) node.addClass('main-chain-node')
        else if (backboneNodeIds.has(id)) node.addClass('backbone-node')
        else node.addClass('aux-node')
      })

      cy.edges().forEach((edge) => {
        const type = String(edge.data('type'))
        const edgeId = edge.data('id')
        edge.removeClass('main-chain-edge backbone-edge aux-edge')
        if (mainChainMode && mainChain.edgeIds.has(edgeId)) edge.addClass('main-chain-edge')
        else if (type === 'PREREQUISITE') edge.addClass('backbone-edge')
        else edge.addClass('aux-edge')
      })
    }

    if (activeNodeId) {
      const outgoingMap = new Map<string, string[]>()
      const incomingMap = new Map<string, string[]>()

      typedNodes.forEach((node) => {
        outgoingMap.set(node.id, [])
        incomingMap.set(node.id, [])
      })

      filteredEdges.forEach((edge) => {
        outgoingMap.get(edge.source)?.push(edge.target)
        incomingMap.get(edge.target)?.push(edge.source)
      })

      const forward = collectReachable(outgoingMap, activeNodeId)
      const backward = collectReachable(incomingMap, activeNodeId)
      const activeNodes = new Set<string>([activeNodeId, ...forward, ...backward])

      cy.nodes().forEach((node) => {
        const id = String(node.data('id'))
        node.removeClass('active-node active-neighbor dimmed')
        if (id === activeNodeId) node.addClass('active-node')
        else if (activeNodes.has(id)) node.addClass('active-neighbor')
        else node.addClass('dimmed')
      })

      cy.edges().forEach((edge) => {
        const source = String(edge.data('source'))
        const target = String(edge.data('target'))
        edge.removeClass('active-edge dimmed')
        if (activeNodes.has(source) && activeNodes.has(target)) edge.addClass('active-edge')
        else edge.addClass('dimmed')
      })
    }

    cy.on('tap', 'node', (event) => {
      const node = event.target
      if (String(node.data('type')) === 'layer-guide') return
      onNodeClick?.({ id: node.data('id'), label: node.data('label'), type: node.data('type'), data: node.data() })
    })

    cy.on('dbltap', 'node', (event) => {
      cy.animate({ center: { eles: event.target }, zoom: 1.8, duration: 400 })
    })

    cyRef.current = cy
    return () => {
      cy.destroy()
    }
  }, [typedNodes, filteredEdges, onNodeClick, layoutMode, isDark, T, activeNodeId, showLayerGuides, backboneMode, backboneNodeIds, mainChain, mainChainMode])

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
