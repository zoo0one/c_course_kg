import React, { useState } from 'react'
import { Tabs, Card, Statistic, Row, Col } from 'antd'
import {
  UploadOutlined,
  AuditOutlined,
  EditOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { DataUploader } from '@/components/Admin/DataUploader'
import { ReviewQueue } from '@/components/Admin/ReviewQueue'
import { KPEditor } from '@/components/Admin/KPEditor'
import { useAppStore } from '@/services/store'

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('upload')
  const graphNodes = useAppStore((state) => state.graphNodes)
  const graphEdges = useAppStore((state) => state.graphEdges)
  const chapters = useAppStore((state) => state.chapters)

  const kpCount = graphNodes.filter((n) => n.type === 'knowledge_point').length
  const chapterCount = chapters.length

  const tabItems = [
    {
      key: 'upload',
      label: (
        <span>
          <UploadOutlined /> 数据上传
        </span>
      ),
      children: (
        <Card
          style={{
            background: '#ffffff',
            border: '1px solid #dbe1ea',
          }}
        >
          <DataUploader />
        </Card>
      ),
    },
    {
      key: 'review',
      label: (
        <span>
          <AuditOutlined /> 审核队列
        </span>
      ),
      children: (
        <Card
          style={{
            background: '#ffffff',
            border: '1px solid #dbe1ea',
          }}
        >
          <ReviewQueue />
        </Card>
      ),
    },
    {
      key: 'editor',
      label: (
        <span>
          <EditOutlined /> 知识点编辑
        </span>
      ),
      children: (
        <Card
          style={{
            background: '#ffffff',
            border: '1px solid #dbe1ea',
          }}
        >
          <KPEditor />
        </Card>
      ),
    },
  ]

  return (
    <div style={{ padding: 24, height: '100%', overflowY: 'auto' }}>
      {/* 标题 */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ color: '#111827', margin: 0 }}>管理员控制台</h2>
        <p style={{ color: '#6b7280', marginTop: 4 }}>
          管理知识图谱数据，上传新数据并审核后自动更新图谱
        </p>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card
            style={{
              background: '#ffffff',
              border: '1px solid #dbe1ea',
              borderRadius: 8,
            }}
          >
            <Statistic
              title="知识点总数"
              value={kpCount}
              valueStyle={{ color: '#1890ff' }}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card
            style={{
              background: '#ffffff',
              border: '1px solid #dbe1ea',
              borderRadius: 8,
            }}
          >
            <Statistic
              title="章节数"
              value={chapterCount}
              valueStyle={{ color: '#52c41a' }}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card
            style={{
              background: '#ffffff',
              border: '1px solid #dbe1ea',
              borderRadius: 8,
            }}
          >
            <Statistic
              title="关系总数"
              value={graphEdges.length}
              valueStyle={{ color: '#faad14' }}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 功能标签页 */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        style={{ color: '#1f2937' }}
      />
    </div>
  )
}
