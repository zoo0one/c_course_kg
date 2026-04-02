import React from 'react'
import { Tooltip, Button } from 'antd'
import { CopyOutlined, CheckOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons'
import type { ChatMessage } from '@/types'
import dayjs from 'dayjs'

interface ChatMessageProps {
  message: ChatMessage
  onActionClick?: (action: string, params?: Record<string, any>) => void
  isStreaming?: boolean
}

const renderContent = (content: string) => {
  if (!content) return null
  const parts = content.split(/(```[\s\S]*?```)/g)
  return parts.map((part, i) => {
    if (part.startsWith('```')) {
      const lang = part.match(/^```(\w*)/)?.[1] || ''
      const code = part.replace(/^```\w*\n?/, '').replace(/```$/, '')
      return (
        <div key={i} style={{ margin: '10px 0', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)' }}>
          {lang && (
            <div style={{ background: 'var(--bg-hover)', padding: '4px 12px', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', borderBottom: '1px solid var(--border)' }}>
              {lang}
            </div>
          )}
          <pre style={{
            background: 'var(--bg-base)',
            padding: '12px 14px',
            overflowX: 'auto',
            fontSize: 13,
            lineHeight: 1.7,
            color: 'var(--text-primary)',
            margin: 0,
            fontFamily: 'var(--font-mono)',
          }}><code>{code}</code></pre>
        </div>
      )
    }
    return (
      <span key={i}>
        {part.split('\n').map((line, j) => (
          <span key={j}>
            {j > 0 && <br />}
            {line.split(/(`[^`]+`)/g).map((seg, k) =>
              seg.startsWith('`') && seg.endsWith('`') ? (
                <code key={k} style={{
                  background: 'var(--bg-hover)',
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontSize: 12,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--primary)',
                  border: '1px solid var(--border)',
                }}>{seg.slice(1, -1)}</code>
              ) : seg
            )}
          </span>
        ))}
      </span>
    )
  })
}

export const ChatMessageComponent: React.FC<ChatMessageProps> = ({
  message,
  onActionClick,
  isStreaming = false,
}) => {
  const [copied, setCopied] = React.useState(false)
  const isUser = message.type === 'user'

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 16,
      gap: 10,
      alignItems: 'flex-start',
    }}>
      {/* AI 头像 */}
      {!isUser && (
        <div style={{
          width: 34,
          height: 34,
          borderRadius: 8,
          background: 'linear-gradient(135deg, var(--primary) 0%, var(--purple) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          marginTop: 2,
          boxShadow: '0 0 10px var(--primary-glow)',
        }}>
          <RobotOutlined style={{ color: '#080d1a', fontSize: 16 }} />
        </div>
      )}

      {/* 消息气泡 */}
      <div style={{
        maxWidth: '78%',
        background: isUser ? 'var(--primary)' : 'var(--bg-card)',
        border: isUser ? 'none' : '1px solid var(--border)',
        borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
        padding: '10px 14px',
        boxShadow: isUser ? '0 2px 12px var(--primary-glow)' : 'none',
      }}>
        <div style={{
          color: isUser ? '#080d1a' : 'var(--text-primary)',
          lineHeight: 1.75,
          fontSize: 14,
          fontFamily: 'var(--font-ui)',
          wordBreak: 'break-word',
        }}>
          {isUser ? message.content : (
            <>
              {renderContent(message.content)}
              {isStreaming && (
                <span style={{
                  display: 'inline-block',
                  width: 2,
                  height: '1em',
                  background: 'var(--primary)',
                  marginLeft: 2,
                  verticalAlign: 'text-bottom',
                  animation: 'blink 1s step-start infinite',
                }} />
              )}
            </>
          )}
        </div>

        {/* 底部：时间 + 复制 */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6, gap: 8 }}>
          <span style={{ fontSize: 11, color: isUser ? 'rgba(8,13,26,0.5)' : 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {dayjs(message.timestamp).format('HH:mm')}
          </span>
          {!isUser && !isStreaming && (
            <Tooltip title={copied ? '已复制' : '复制'}>
              <Button
                type="text" size="small"
                icon={copied
                  ? <CheckOutlined style={{ color: 'var(--success)' }} />
                  : <CopyOutlined style={{ color: 'var(--text-muted)' }} />
                }
                onClick={handleCopy}
                style={{ padding: '0 4px', height: 'auto' }}
              />
            </Tooltip>
          )}
        </div>

        {/* 相关知识点 */}
        {message.suggestions && message.suggestions.length > 0 && (
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, marginBottom: 6, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>相关知识点</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {message.suggestions.map((s: any) => (
                <span
                  key={s.id}
                  onClick={() => onActionClick?.('show_kp', { kp_id: s.id })}
                  style={{
                    padding: '3px 10px',
                    borderRadius: 4,
                    fontSize: 12,
                    background: 'var(--bg-hover)',
                    border: '1px solid var(--border-bright)',
                    color: 'var(--primary)',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-mono)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(56,189,248,0.1)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                >
                  {s.name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div style={{
          width: 34,
          height: 34,
          borderRadius: 8,
          background: 'var(--bg-hover)',
          border: '1px solid var(--border-bright)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          marginTop: 2,
        }}>
          <UserOutlined style={{ color: 'var(--text-secondary)', fontSize: 16 }} />
        </div>
      )}
    </div>
  )
}
