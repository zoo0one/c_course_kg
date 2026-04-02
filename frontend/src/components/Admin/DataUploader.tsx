import React, { useEffect, useMemo, useState } from 'react'
import { Upload, Button, message, Steps, Table, Tag, Alert, Space, Divider, Typography, Card, Progress } from 'antd'
import { CheckCircleOutlined, LoadingOutlined, FilePdfOutlined, InboxOutlined, UploadOutlined, PlayCircleOutlined, SendOutlined, EyeOutlined } from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd'
import { adminAPI } from '@/services/api'

interface ParsedKP {
  kp_id: string
  name: string
  chapter_id: string
  section?: string
  aliases?: string
  status: 'new' | 'update' | 'duplicate'
}

interface ParsedRelation {
  source: string
  target: string
  relation_type: string
  description?: string
}

interface UploadResult {
  chapters: number
  kps: ParsedKP[]
  relations: number
  relation_rows?: ParsedRelation[]
  errors: string[]
}

export const DataUploader: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [importing, setImporting] = useState(false)

  const [pdfFileList, setPdfFileList] = useState<UploadFile[]>([])
  const [selectedPdfFile, setSelectedPdfFile] = useState<File | null>(null)
  const [pdfJobInfo, setPdfJobInfo] = useState<any>(null)
  const [extractStatus, setExtractStatus] = useState<any>(null)
  const [extractPolling, setExtractPolling] = useState(false)
  const [toReviewLoading, setToReviewLoading] = useState(false)
  const [extractPreview, setExtractPreview] = useState<any>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const [structuredFileList, setStructuredFileList] = useState<UploadFile[]>([])
  const [parseResult, setParseResult] = useState<UploadResult | null>(null)

  const pdfUploadProps: UploadProps = {
    accept: '.pdf',
    maxCount: 1,
    fileList: pdfFileList,
    beforeUpload: (file) => {
      setPdfFileList([file])
      setSelectedPdfFile(file as unknown as File)
      return false
    },
    onRemove: () => {
      setPdfFileList([])
      setSelectedPdfFile(null)
    },
  }

  const structuredUploadProps: UploadProps = {
    accept: '.csv,.json,.txt',
    multiple: true,
    fileList: structuredFileList,
    beforeUpload: (file) => {
      setStructuredFileList((prev) => [...prev, file])
      return false
    },
    onRemove: (file) => {
      setStructuredFileList((prev) => prev.filter((f) => f.uid !== file.uid))
    },
  }

  const jobId = pdfJobInfo?.job_id || extractStatus?.job_id

  useEffect(() => {
    if (!jobId || !extractPolling) return
    const t = setInterval(async () => {
      try {
        const status = await adminAPI.getExtractStatus(jobId)
        setExtractStatus(status)
        if (['extracted', 'failed', 'queued'].includes(status.status)) {
          setExtractPolling(false)
        }
      } catch {
        setExtractPolling(false)
      }
    }, 2000)
    return () => clearInterval(t)
  }, [jobId, extractPolling])

  const handlePdfUpload = async () => {
    if (!selectedPdfFile) {
      message.warning('请先点击“选择 PDF 文件”')
      return
    }

    setUploading(true)
    try {
      const result = await adminAPI.uploadPdf(selectedPdfFile)
      setPdfJobInfo(result)
      setExtractStatus(result)
      setExtractPreview(null)
      message.success(`PDF 上传成功，任务ID：${result.job_id}`)
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail || 'PDF 上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleStartExtract = async () => {
    if (!jobId) {
      message.warning('请先上传 PDF')
      return
    }
    try {
      await adminAPI.startExtract(jobId)
      setExtractPolling(true)
      message.success('已开始抽取，请稍候...')
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail || '启动抽取失败')
    }
  }

  const handleRefreshStatus = async () => {
    if (!jobId) return
    try {
      const status = await adminAPI.getExtractStatus(jobId)
      setExtractStatus(status)
    } catch {
      message.error('查询状态失败')
    }
  }

  const handleExtractToReview = async () => {
    if (!jobId) return
    setToReviewLoading(true)
    try {
      const result = await adminAPI.extractToReview(jobId)
      message.success(`已加入审核队列：${result.queued} 条`) 
      await handleRefreshStatus()
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail || '加入审核队列失败')
    } finally {
      setToReviewLoading(false)
    }
  }

  const handleLoadExtractPreview = async () => {
    if (!jobId) {
      message.warning('请先上传并抽取 PDF')
      return
    }
    setPreviewLoading(true)
    try {
      const data = await adminAPI.getExtractPreview(jobId, 20)
      setExtractPreview(data)
      message.success('已加载抽取预览')
    } catch (error: any) {
      const detail = error?.response?.data?.detail
      message.error(detail || '加载预览失败')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleParse = async () => {
    if (structuredFileList.length === 0) {
      message.warning('请先选择 CSV/JSON/TXT 文件')
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      structuredFileList.forEach((file) => {
        if (file.originFileObj) {
          formData.append('files', file.originFileObj)
        }
      })
      const result = await adminAPI.parseUpload(formData)
      setParseResult(result)
      setCurrentStep(1)
      message.success(`解析完成：${result.kps.length} 个知识点，${result.relations} 条关系`)
    } catch {
      message.error('文件解析失败，请检查文件格式')
    } finally {
      setUploading(false)
    }
  }

  const handleImport = async () => {
    if (!parseResult) return
    setImporting(true)
    try {
      await adminAPI.confirmImport(parseResult)
      setCurrentStep(2)
      message.success('已送审成功！请到审核队列中批准并应用')
    } catch {
      message.error('送审失败')
    } finally {
      setImporting(false)
    }
  }

  const handleReset = () => {
    setCurrentStep(0)
    setPdfFileList([])
    setSelectedPdfFile(null)
    setStructuredFileList([])
    setParseResult(null)
    setPdfJobInfo(null)
    setExtractStatus(null)
    setExtractPreview(null)
    setExtractPolling(false)
  }

  const kpColumns = [
    {
      title: '知识点 ID',
      dataIndex: 'kp_id',
      key: 'kp_id',
      width: 110,
      render: (text: string) => <span style={{ fontFamily: 'monospace', fontSize: 12, color: '#a0a0a0' }}>{text}</span>,
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
      width: 90,
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const config: Record<string, { color: string; label: string }> = {
          new: { color: 'green', label: '新增' },
          update: { color: 'orange', label: '更新' },
          duplicate: { color: 'red', label: '重复' },
        }
        return <Tag color={config[status]?.color}>{config[status]?.label}</Tag>
      },
    },
  ]

  const extractSummary = useMemo(() => extractStatus?.summary || null, [extractStatus])

  return (
    <div>
      <Steps
        current={currentStep}
        items={[{ title: '上传文件' }, { title: '预览并送审' }, { title: '送审完成' }]}
        style={{ marginBottom: 24 }}
      />

      {currentStep === 0 && (
        <div>
          <Alert
            message="推荐流程"
            description={<div><p>1. 上传 PDF</p><p>2. 点击“开始抽取”并等待完成</p><p>3. 点击“抽取结果加入审核队列”</p><p>4. 到审核队列执行“全部替换/增加”</p></div>}
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Card size="small" title="① PDF 上传并抽取" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Space wrap>
                <Upload {...pdfUploadProps} showUploadList>
                  <Button icon={<FilePdfOutlined />}>选择 PDF 文件</Button>
                </Upload>
                <Button
                  type="primary"
                  onClick={handlePdfUpload}
                  loading={uploading}
                  icon={uploading ? <LoadingOutlined /> : <UploadOutlined />}
                  disabled={pdfFileList.length === 0}
                >
                  上传 PDF
                </Button>
                <Button
                  onClick={handleStartExtract}
                  icon={extractPolling ? <LoadingOutlined /> : <PlayCircleOutlined />}
                  loading={extractPolling}
                  disabled={!jobId}
                >
                  开始抽取
                </Button>
                <Button onClick={handleRefreshStatus} disabled={!jobId}>刷新状态</Button>
                <Button
                  onClick={handleLoadExtractPreview}
                  icon={previewLoading ? <LoadingOutlined /> : <EyeOutlined />}
                  loading={previewLoading}
                  disabled={!jobId || !['extracted', 'queued'].includes(extractStatus?.status || '')}
                >
                  查看抽取预览
                </Button>
                <Button
                  type="primary"
                  onClick={handleExtractToReview}
                  icon={toReviewLoading ? <LoadingOutlined /> : <SendOutlined />}
                  loading={toReviewLoading}
                  disabled={extractStatus?.status !== 'extracted'}
                >
                  抽取结果加入审核队列
                </Button>
              </Space>

              {jobId && (
                <Typography.Text type="secondary">任务ID：<Typography.Text code>{jobId}</Typography.Text></Typography.Text>
              )}

              {extractStatus && (
                <Alert
                  type={extractStatus.status === 'failed' ? 'error' : extractStatus.status === 'extracted' ? 'success' : 'info'}
                  showIcon
                  message={`当前状态：${extractStatus.status}`}
                  description={
                    <div>
                      <div>{extractStatus.message}</div>
                      {extractSummary && (
                        <div style={{ marginTop: 6 }}>
                          章节 {extractSummary.chapters} · 知识点 {extractSummary.kps} · 关系 {extractSummary.relations}
                        </div>
                      )}
                    </div>
                  }
                />
              )}

              {extractStatus?.status === 'failed' && (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginTop: 8 }}
                  message="抽取失败排查建议"
                  description="请确认 Ollama 正在运行；若是扫描版 PDF，系统会自动 OCR，但首次识别可能较慢，可点击“开始抽取”重试。"
                />
              )}

              {extractPreview && (
                <Card size="small" title="抽取结果预览（前 20 条）" style={{ marginTop: 8 }}>
                  <Space style={{ marginBottom: 10 }} wrap>
                    <Tag color="green">章节: {extractPreview.summary?.chapters ?? 0}</Tag>
                    <Tag color="blue">知识点: {extractPreview.summary?.kps ?? 0}</Tag>
                    <Tag color="purple">关系: {extractPreview.summary?.relations ?? 0}</Tag>
                    {extractPreview.transform?.converted_from_legacy_schema && (
                      <Tag color="orange">已从旧结构自动转换</Tag>
                    )}
                  </Space>

                  <Typography.Text strong>知识点预览</Typography.Text>
                  <Table
                    size="small"
                    rowKey={(r: any, idx) => `${r.kp_id || 'kp'}-${idx}`}
                    pagination={false}
                    style={{ margin: '8px 0 12px' }}
                    dataSource={extractPreview.kps || []}
                    columns={[
                      { title: 'kp_id', dataIndex: 'kp_id', width: 110 },
                      { title: '名称', dataIndex: 'name' },
                      { title: '章节', dataIndex: 'chapter_id', width: 90 },
                    ]}
                  />

                  <Typography.Text strong>关系预览</Typography.Text>
                  <Table
                    size="small"
                    rowKey={(r: any, idx) => `${r.source || 's'}-${r.target || 't'}-${idx}`}
                    pagination={false}
                    dataSource={extractPreview.relations || []}
                    columns={[
                      { title: 'source', dataIndex: 'source' },
                      { title: 'target', dataIndex: 'target' },
                      { title: 'type', dataIndex: 'relation_type', width: 140 },
                    ]}
                  />

                  <Divider style={{ margin: '12px 0' }} />
                  <Typography.Text strong>扫描日志（调试）</Typography.Text>
                  <pre style={{ marginTop: 6, maxHeight: 180, overflow: 'auto', background: '#f7f9fc', border: '1px solid #e5e7eb', padding: 8, borderRadius: 6 }}>
                    {JSON.stringify(extractPreview.scan_log ?? {}, null, 2)}
                  </pre>

                  <Typography.Text strong>抽取日志（调试）</Typography.Text>
                  <pre style={{ marginTop: 6, maxHeight: 180, overflow: 'auto', background: '#f7f9fc', border: '1px solid #e5e7eb', padding: 8, borderRadius: 6 }}>
                    {JSON.stringify(extractPreview.extract_log ?? {}, null, 2)}
                  </pre>

                  <Typography.Text strong>fallback 结果（调试）</Typography.Text>
                  <pre style={{ marginTop: 6, maxHeight: 180, overflow: 'auto', background: '#f7f9fc', border: '1px solid #e5e7eb', padding: 8, borderRadius: 6 }}>
                    {JSON.stringify(extractPreview.fallback_payload ?? {}, null, 2)}
                  </pre>

                  <Typography.Text strong>模型原始返回（调试）</Typography.Text>
                  <pre style={{ marginTop: 6, maxHeight: 180, overflow: 'auto', background: '#f7f9fc', border: '1px solid #e5e7eb', padding: 8, borderRadius: 6 }}>
                    {JSON.stringify(extractPreview.raw_payload ?? {}, null, 2)}
                  </pre>

                  <Typography.Text strong>转换后结构（调试）</Typography.Text>
                  <pre style={{ marginTop: 6, maxHeight: 180, overflow: 'auto', background: '#f7f9fc', border: '1px solid #e5e7eb', padding: 8, borderRadius: 6 }}>
                    {JSON.stringify(extractPreview.normalized_payload ?? {}, null, 2)}
                  </pre>
                </Card>
              )}

              {extractPolling && <Progress percent={65} status="active" showInfo={false} />}
            </Space>
          </Card>

          <Card size="small" title="② 结构化文件上传（手动预览并送审，备用）">
            <Upload.Dragger {...structuredUploadProps} style={{ marginBottom: 16 }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined style={{ fontSize: 44, color: '#1890ff' }} />
              </p>
              <p className="ant-upload-text">点击或拖拽 CSV/JSON/TXT 文件到此处</p>
              <p className="ant-upload-hint">用于预览和送审（不含 PDF）</p>
            </Upload.Dragger>

            <Button
              type="primary"
              onClick={handleParse}
              loading={uploading}
              disabled={structuredFileList.length === 0}
              icon={uploading ? <LoadingOutlined /> : <CheckCircleOutlined />}
            >
              解析结构化文件并预览
            </Button>
          </Card>

          {pdfJobInfo && (
            <Alert
              style={{ marginTop: 16 }}
              type="success"
              message="PDF 上传成功"
              description={<div><div>任务ID：<Typography.Text code>{pdfJobInfo.job_id}</Typography.Text></div><div>存储路径：<Typography.Text code>{pdfJobInfo.stored_pdf}</Typography.Text></div></div>}
              showIcon
            />
          )}
        </div>
      )}

      {currentStep === 1 && parseResult && (
        <div>
          <Space style={{ marginBottom: 16 }} wrap>
            <Tag color="green">章节: {parseResult.chapters}</Tag>
            <Tag color="blue">知识点: {parseResult.kps.length}</Tag>
            <Tag color="purple">关系: {parseResult.relations}</Tag>
            {parseResult.errors.length > 0 && <Tag color="red">错误: {parseResult.errors.length}</Tag>}
          </Space>

          {parseResult.errors.length > 0 && (
            <Alert type="warning" message="解析警告" description={parseResult.errors.join('\n')} style={{ marginBottom: 16 }} />
          )}

          <Table
            dataSource={parseResult.kps}
            columns={kpColumns}
            rowKey="kp_id"
            size="small"
            pagination={{ pageSize: 10 }}
            style={{ marginBottom: 16 }}
          />

          <Divider style={{ borderColor: '#2d3748' }} />

          <Space>
            <Button onClick={() => setCurrentStep(0)}>上一步</Button>
            <Button type="primary" onClick={handleImport} loading={importing} icon={<CheckCircleOutlined />}>
              确认送审
            </Button>
          </Space>
        </div>
      )}

      {currentStep === 2 && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <CheckCircleOutlined style={{ fontSize: 64, color: '#52c41a', marginBottom: 16 }} />
          <p style={{ fontSize: 18, color: '#e0e0e0', marginBottom: 8 }}>送审成功！</p>
          <p style={{ color: '#a0a0a0', marginBottom: 24 }}>请切换到“审核队列”进行批准，然后选择“全部替换”或“增加”</p>
          <Button type="primary" onClick={handleReset}>继续上传</Button>
        </div>
      )}
    </div>
  )
}
