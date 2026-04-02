import React, { useEffect, useMemo, useState } from 'react'
import {
  Table,
  Tag,
  Button,
  Space,
  Modal,
  Descriptions,
  message,
  Select,
  Input,
  Popconfirm,
  Badge,
} from 'antd'
import { CheckOutlined, CloseOutlined, EyeOutlined, ReloadOutlined } from '@ant-design/icons'
import { adminAPI } from '@/services/api'
import dayjs from 'dayjs'

interface ReviewItem {
  id: string
  type: 'kp' | 'relation' | 'chapter'
  action: 'add' | 'update' | 'delete'
  data: any
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  source?: string
}

export const ReviewQueue: React.FC = () => {
  const [items, setItems] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(false)
  const [previewItem, setPreviewItem] = useState<ReviewItem | null>(null)
  const [filterStatus, setFilterStatus] = useState<string>('pending')
  const [searchText, setSearchText] = useState('')
  const [applying, setApplying] = useState<'replace' | 'append' | null>(null)

  const loadQueue = async () => {
    setLoading(true)
    try {
      const rows = await adminAPI.getReviewQueue('all')
      setItems(rows)
    } catch (error) {
      message.error('加载审核队列失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadQueue()
  }, [])

  const handleApprove = async (id: string) => {
    try {
      await adminAPI.approveReview(id)
      message.success('已批准（待应用）')
      setItems((prev) => prev.map((item) => (item.id === id ? { ...item, status: 'approved' } : item)))
    } catch {
      message.error('批准失败')
    }
  }

  const handleReject = async (id: string) => {
    try {
      await adminAPI.rejectReview(id)
      message.info('已拒绝')
      setItems((prev) => prev.map((item) => (item.id === id ? { ...item, status: 'rejected' } : item)))
    } catch {
      message.error('拒绝失败')
    }
  }

  const handleApproveAll = async () => {
    try {
      const result = await adminAPI.approveAllReview()
      message.success(`已批准 ${result.approved} 条`)
      await loadQueue()
    } catch {
      message.error('全部批准失败')
    }
  }

  const handleApply = async (mode: 'replace' | 'append') => {
    setApplying(mode)
    try {
      const result = await adminAPI.applyReviewed(mode)
      const msg = mode === 'replace' ? '已完成全量替换' : '已完成增量追加'
      message.success(`${msg}：应用 ${result.applied} 条`)
      await loadQueue()
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail || '应用失败')
    } finally {
      setApplying(null)
    }
  }

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchStatus = filterStatus === 'all' || item.status === filterStatus
      const content = JSON.stringify(item.data || {})
      const matchSearch = !searchText || item.id.includes(searchText) || content.includes(searchText)
      return matchStatus && matchSearch
    })
  }, [items, filterStatus, searchText])

  const pendingCount = items.filter((i) => i.status === 'pending').length
  const approvedCount = items.filter((i) => i.status === 'approved').length

  const typeConfig: Record<string, { color: string; label: string }> = {
    kp: { color: 'blue', label: '知识点' },
    relation: { color: 'purple', label: '关系' },
    chapter: { color: 'green', label: '章节' },
  }

  const actionConfig: Record<string, { color: string; label: string }> = {
    add: { color: 'green', label: '新增' },
    update: { color: 'orange', label: '更新' },
    delete: { color: 'red', label: '删除' },
  }

  const statusConfig: Record<string, { color: string; label: string }> = {
    pending: { color: 'gold', label: '待审核' },
    approved: { color: 'green', label: '已批准' },
    rejected: { color: 'red', label: '已拒绝' },
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 90,
      render: (text: string) => <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#a0a0a0' }}>{text}</span>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (type: string) => <Tag color={typeConfig[type]?.color}>{typeConfig[type]?.label}</Tag>,
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 70,
      render: (action: string) => <Tag color={actionConfig[action]?.color}>{actionConfig[action]?.label}</Tag>,
    },
    {
      title: '内容',
      key: 'content',
      render: (_: any, item: ReviewItem) => (
        <div>
          <div style={{ color: '#1890ff', fontWeight: 500 }}>
            {item.data?.name || item.data?.kp_id || `${item.data?.source || item.data?.source_kp_id} → ${item.data?.target || item.data?.target_kp_id}`}
          </div>
          <div style={{ color: '#a0a0a0', fontSize: 12 }}>
            {item.data?.chapter_id && <Tag color="blue" style={{ marginRight: 4 }}>{item.data.chapter_id}</Tag>}
            {item.data?.kp_id && <span style={{ fontFamily: 'monospace' }}>{item.data.kp_id}</span>}
            {(item.data?.relation_type || item.data?.type) && <Tag color="purple" style={{ marginLeft: 6 }}>{item.data?.relation_type || item.data?.type}</Tag>}
          </div>
        </div>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (text: string) => <span style={{ color: '#a0a0a0', fontSize: 12 }}>{text}</span>,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
      render: (text: string) => <span style={{ color: '#a0a0a0', fontSize: 12 }}>{dayjs(text).format('MM-DD HH:mm')}</span>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => <Tag color={statusConfig[status]?.color}>{statusConfig[status]?.label}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_: any, item: ReviewItem) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => setPreviewItem(item)} />
          {item.status === 'pending' && (
            <>
              <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => handleApprove(item.id)}>批准</Button>
              <Popconfirm title="确认拒绝？" onConfirm={() => handleReject(item.id)}>
                <Button size="small" danger icon={<CloseOutlined />}>拒绝</Button>
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
        <Space wrap>
          <Input.Search
            placeholder="搜索审核项..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 220 }}
          />
          <Select
            value={filterStatus}
            onChange={setFilterStatus}
            style={{ width: 120 }}
            options={[
              { value: 'all', label: '全部' },
              { value: 'pending', label: '待审核' },
              { value: 'approved', label: '已批准' },
              { value: 'rejected', label: '已拒绝' },
            ]}
          />
          <Button icon={<ReloadOutlined />} onClick={loadQueue}>刷新</Button>
        </Space>

        <Space wrap>
          <Badge count={pendingCount}>
            <span style={{ color: '#a0a0a0' }}>待审核</span>
          </Badge>
          <Badge count={approvedCount} style={{ backgroundColor: '#52c41a' }}>
            <span style={{ color: '#a0a0a0' }}>已批准</span>
          </Badge>

          {pendingCount > 0 && (
            <Popconfirm title={`确认批准全部 ${pendingCount} 条待审核项？`} onConfirm={handleApproveAll}>
              <Button type="primary" icon={<CheckOutlined />}>全部批准</Button>
            </Popconfirm>
          )}

          <Popconfirm
            title={`将用已批准数据全量替换图谱（${approvedCount}条），确认继续？`}
            onConfirm={() => handleApply('replace')}
            okText="替换"
            cancelText="取消"
            disabled={approvedCount === 0}
          >
            <Button danger loading={applying === 'replace'} disabled={approvedCount === 0}>确认并全部替换</Button>
          </Popconfirm>

          <Popconfirm
            title={`将已批准数据增量追加到图谱（${approvedCount}条），确认继续？`}
            onConfirm={() => handleApply('append')}
            okText="追加"
            cancelText="取消"
            disabled={approvedCount === 0}
          >
            <Button type="primary" loading={applying === 'append'} disabled={approvedCount === 0}>确认并增加</Button>
          </Popconfirm>
        </Space>
      </div>

      <Table
        dataSource={filteredItems}
        columns={columns}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{ pageSize: 10 }}
      />

      <Modal
        title="审核详情"
        open={!!previewItem}
        onCancel={() => setPreviewItem(null)}
        footer={[<Button key="close" onClick={() => setPreviewItem(null)}>关闭</Button>]}
      >
        {previewItem && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="审核 ID">{previewItem.id}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={typeConfig[previewItem.type]?.color}>{typeConfig[previewItem.type]?.label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="操作">
              <Tag color={actionConfig[previewItem.action]?.color}>{actionConfig[previewItem.action]?.label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="数据">
              <pre style={{ margin: 0, fontSize: 12, color: '#e0e0e0', background: '#1f2937', padding: 8, borderRadius: 4 }}>
                {JSON.stringify(previewItem.data, null, 2)}
              </pre>
            </Descriptions.Item>
            <Descriptions.Item label="来源">{previewItem.source}</Descriptions.Item>
            <Descriptions.Item label="时间">{dayjs(previewItem.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusConfig[previewItem.status]?.color}>{statusConfig[previewItem.status]?.label}</Tag>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
