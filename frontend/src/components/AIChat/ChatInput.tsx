import React from 'react'
import { Tooltip } from 'antd'
import { SendOutlined } from '@ant-design/icons'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  loading?: boolean
  placeholder?: string
}

export const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
  onSend,
  loading = false,
  placeholder = '输入你的问题... (Ctrl+Enter 发送)',
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        alignItems: 'flex-end',
        padding: '12px 16px',
        background: 'var(--bg-panel)',
        borderTop: '1px solid var(--border)',
        flexShrink: 0,
      }}
    >
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        rows={3}
        disabled={loading}
        style={{
          flex: 1,
          background: 'var(--bg-input)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '10px 14px',
          color: 'var(--text-primary)',
          fontSize: 14,
          fontFamily: 'var(--font-ui)',
          resize: 'none',
          outline: 'none',
          lineHeight: 1.6,
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => (e.target.style.borderColor = 'var(--primary)')}
        onBlur={(e) => (e.target.style.borderColor = 'var(--border)')}
      />
      <Tooltip title="发送 (Ctrl+Enter)">
        <button
          onClick={onSend}
          disabled={loading || !value.trim()}
          style={{
            width: 44,
            height: 44,
            borderRadius: 10,
            border: 'none',
            background: value.trim() && !loading ? 'var(--primary)' : 'var(--bg-hover)',
            color: value.trim() && !loading ? '#080d1a' : 'var(--text-muted)',
            fontSize: 18,
            cursor: value.trim() && !loading ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s',
            flexShrink: 0,
            boxShadow: value.trim() && !loading ? '0 0 12px var(--primary-glow)' : 'none',
          }}
        >
          {loading ? (
            <span style={{ fontSize: 16, animation: 'blink 1s step-start infinite' }}>⏳</span>
          ) : (
            <SendOutlined />
          )}
        </button>
      </Tooltip>
    </div>
  )
}
