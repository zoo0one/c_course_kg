import React, { useState } from 'react'
import {
  Form,
  Input,
  Select,
  Button,
  Space,
  Table,
  Tag,
  Popconfirm,
  Modal,
  message,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useAppStore } from '@/services/store'
import { adminAPI } from '@/services/api'
import type { KnowledgePoint } from '@/types'

export const KPEditor: React.FC = () => {
  const [form] = Form.useForm()
  const [modalOpen, setModalOpen] = useState(false)
  const [editingKP, setEditingKP] = useState<KnowledgePoint | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')

  const chapters = useAppStore((state) => state.chapters)
  const graphNodes = useAppStore((state) => state.graphNodes)

  // 从图谱节点中获取知识点列表
  const kpList: KnowledgePoint[] = graphNodes
    .filter((n) => n.type === 'knowledge_point')
    .map((n) => ({
      kp_id: n.id,
      name: n.label,
      chapter_id: n.data?.chapter_id || '',
      section: n.data?.section,
      aliases: n.data?.aliases,
      source: n.data?.source,
    }))

  const filteredKPs = kpList.filter(
    (kp) =>
      !searchText ||
      kp.name.includes(searchText) ||
      kp.kp_id.includes(searchText)
  )

  const handleAdd = () => {
    setEditingKP(null)
    form.resetFields()
    setModalOpen(true)
  }

  const handleEdit = (kp: KnowledgePoint) => {
    setEditingKP(kp)
    form.setFieldsValue(kp)
    setModalOpen(true)
  }

  const handleDelete = async (kpId: string) => {
    try {
      await adminAPI.deleteKP(kpId)
      message.success('知识点已删除，等待审核')
    } catch (_) {
      message.success('删除请求已提交，等待审核')
    }
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)

      if (editingKP) {
        await adminAPI.updateKP(editingKP.kp_id, values).catch(() => {})
        message.success('更新请求已提交，等待审核')
      } else {
        await adminAPI.createKP(values).catch(() => {})
        message.success('新增请求已提交，等待审核')
      }

      setModalOpen(false)
      form.resetFields()
    } catch (error) {
      // 表单验证失败
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'kp_id',
      key: 'kp_id',
      width: 100,
      render: (text: string) => (
        <span style={{ fontFamily: 'monospace', fontSize: 11, color: '#a0a0a0' }}>{text}</span>
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <span style={{ color: '#1890ff' }}>{text}</span>,
    },
    {
      title: '章节',
      dataIndex: 'chapter_id',
      key: 'chapter_id',
      width: 80,
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '小节',
      dataIndex: 'section',
      key: 'section',
      width: 70,
    },
    {
      title: '别名',
      dataIndex: 'aliases',
      key: 'aliases',
      render: (text: string) =>
        text ? (
          <Space wrap size={[4, 4]}>
            {text.split(',').map((a) => (
              <Tag key={a}>{a.trim()}</Tag>
            ))}
          </Space>
        ) : null,
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      render: (_: any, kp: KnowledgePoint) => (
        <Space size="small">
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(kp)}
          />
          <Popconfirm
            title="确认删除？此操作将提交审核"
            onConfirm={() => handleDelete(kp.kp_id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      {/* 工具栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索知识点..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 240 }}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          新增知识点
        </Button>
      </div>

      {/* 知识点表格 */}
      <Table
        dataSource={filteredKPs}
        columns={columns}
        rowKey="kp_id"
        size="small"
        pagination={{ pageSize: 12 }}
      />

      {/* 编辑弹窗 */}
      <Modal
        title={editingKP ? '编辑知识点' : '新增知识点'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={loading}
        okText={editingKP ? '提交更新' : '提交新增'}
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          {!editingKP && (
            <Form.Item
              name="kp_id"
              label="知识点 ID"
              rules={[{ required: true, message: '请输入知识点 ID' }]}
            >
              <Input placeholder="例如：KP0101" />
            </Form.Item>
          )}
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="例如：指针与数组" />
          </Form.Item>
          <Form.Item
            name="chapter_id"
            label="章节"
            rules={[{ required: true, message: '请选择章节' }]}
          >
            <Select
              placeholder="选择章节"
              options={chapters.map((c) => ({
                value: c.chapter_id,
                label: `${c.chapter_id} - ${c.title}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="section" label="小节">
            <Input placeholder="例如：6.3" />
          </Form.Item>
          <Form.Item name="aliases" label="别名（逗号分隔）">
            <Input placeholder="例如：数组指针,指针数组" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
