import React, { useEffect, useRef, useState } from 'react'
import { Button, Tooltip } from 'antd'
import { DeleteOutlined, RobotOutlined, CloseOutlined } from '@ant-design/icons'
import { ChatMessageComponent } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { useAppStore } from '@/services/store'
import { aiAPI } from '@/services/api'
import type { ChatMessage } from '@/types'
import dayjs from 'dayjs'

interface ChatDrawerProps {
  open: boolean
  onClose: () => void
}

const quickQuestions = [
  '什么是指针？',
  'for 循环怎么写？',
  '函数和递归有何区别？',
  '数组和指针的关系？',
  'malloc 怎么用？',
  '结构体是什么？',
]

export const ChatDrawer: React.FC<ChatDrawerProps> = ({ open, onClose }) => {
  const chatMessages = useAppStore((state) => state.chatMessages)
  const chatInput = useAppStore((state) => state.chatInput)
  const setChatInput = useAppStore((state) => state.setChatInput)
  const addChatMessage = useAppStore((state) => state.addChatMessage)
  const setChatMessages = useAppStore((state) => state.setChatMessages)

  const [sending, setSending] = useState(false)
  const [aiReady, setAiReady] = useState<boolean | null>(null)
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open && aiReady === null) {
      aiAPI.health().then((h) => setAiReady(h.ready))
    }
  }, [open, aiReady])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  const handleSend = async () => {
    if (!chatInput.trim() || sending) return
    const userText = chatInput.trim()
    setChatInput('')
    setSending(true)

    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: userText,
      timestamp: dayjs().toISOString(),
    }
    addChatMessage(userMsg)

    const aiMsgId = `msg_${Date.now() + 1}`
    const aiMsg: ChatMessage = {
      id: aiMsgId,
      type: 'ai',
      content: '',
      timestamp: dayjs().toISOString(),
    }
    addChatMessage(aiMsg)
    setStreamingId(aiMsgId)

    try {
      let fullContent = ''
      for await (const chunk of aiAPI.chatStream(userText)) {
        fullContent += chunk
        useAppStore.setState((state) => ({
          chatMessages: state.chatMessages.map((m) =>
            m.id === aiMsgId ? { ...m, content: fullContent } : m
          ),
        }))
      }
      if (!fullContent) {
        const resp = await aiAPI.chat(userText)
        useAppStore.setState((state) => ({
          chatMessages: state.chatMessages.map((m) =>
            m.id === aiMsgId ? { ...m, content: resp.response, suggestions: resp.suggestions } : m
          ),
        }))
      }
    } catch {
      try {
        const resp = await aiAPI.chat(userText)
        useAppStore.setState((state) => ({
          chatMessages: state.chatMessages.map((m) =>
            m.id === aiMsgId ? { ...m, content: resp.response, suggestions: resp.suggestions } : m
          ),
        }))
      } catch {
        useAppStore.setState((state) => ({
          chatMessages: state.chatMessages.map((m) =>
            m.id === aiMsgId ? { ...m, content: '抱歉，AI 服务暂时不可用，请确保 Ollama 已启动。' } : m
          ),
        }))
      }
    } finally {
      setSending(false)
      setStreamingId(null)
    }
  }

  if (!open) return null

  return (
    <div>
      {/* 遮罩 */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.5)',
          zIndex: 1000,
          backdropFilter: 'blur(2px)',
        }}
      />

      {/* 抽屉主体 */}
      <div
        style={{
          position: 'fixed',
          bottom: 0, left: 0, right: 0,
          height: '56vh',
          zIndex: 1001,
          background: 'var(--bg-surface)',
          borderTop: '1px solid var(--border-bright)',
          borderRadius: '16px 16px 0 0',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          boxShadow: '0 -8px 40px rgba(0,0,0,0.4)',
          animation: 'slideUp 0.25s ease',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '14px 20px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-panel)',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'linear-gradient(135deg, var(--primary) 0%, var(--purple) 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 10px var(--primary-glow)',
            }}>
              <RobotOutlined style={{ color: '#080d1a', fontSize: 16 }} />
            </div>
            <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 15 }}>AI 学习助手</span>
            <span
              style={{
                padding: '2px 8px', borderRadius: 4, fontSize: 11,
                fontFamily: 'var(--font-mono)',
                background: aiReady ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)',
                border: `1px solid ${aiReady ? 'rgba(52,211,153,0.3)' : 'rgba(248,113,113,0.3)'}`,
                color: aiReady ? 'var(--success)' : 'var(--danger)',
                cursor: 'pointer',
              }}
              onClick={() => aiAPI.health().then((h) => setAiReady(h.ready))}
            >
              {aiReady === null ? 'checking...' : aiReady ? '● ONLINE' : '● OFFLINE'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Tooltip title="清空对话">
              <Button type="text" icon={<DeleteOutlined />}
                onClick={() => setChatMessages([])}
                style={{ color: 'var(--danger)', opacity: 0.7 }}
              />
            </Tooltip>
            <Button type="text" icon={<CloseOutlined />}
              onClick={onClose}
              style={{ color: 'var(--text-muted)' }}
            />
          </div>
        </div>

        {/* 消息列表 */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', minHeight: 0 }}>
          {chatMessages.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 16 }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 20 }}>
                有什么 C 语言问题尽管问！
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
                {quickQuestions.map((q) => (
                  <span
                    key={q}
                    onClick={() => setChatInput(q)}
                    style={{
                      padding: '6px 14px', borderRadius: 20,
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      color: 'var(--text-secondary)',
                      fontSize: 13, cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--primary)'
                      e.currentTarget.style.color = 'var(--primary)'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border)'
                      e.currentTarget.style.color = 'var(--text-secondary)'
                    }}
                  >
                    {q}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <>
              {chatMessages.map((msg) => (
                <ChatMessageComponent
                  key={msg.id}
                  message={msg}
                  isStreaming={msg.id === streamingId}
                />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* 输入区 */}
        <ChatInput
          value={chatInput}
          onChange={setChatInput}
          onSend={handleSend}
          loading={sending}
        />
      </div>
    </div>
  )
}
