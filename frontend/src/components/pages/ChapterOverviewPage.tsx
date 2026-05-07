import React from 'react'
import { BookOutlined, ArrowRightOutlined } from '@ant-design/icons'
import type { Chapter } from '@/types'

interface ChapterOverviewPageProps {
  chapters: Chapter[]
  onSelectChapter: (chapterId: string) => void
}

const chapterColors = [
  { bg: 'linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%)', border: '#93c5fd', accent: '#2563eb' },
  { bg: 'linear-gradient(135deg, #dcfce7 0%, #f0fdf4 100%)', border: '#86efac', accent: '#16a34a' },
  { bg: 'linear-gradient(135deg, #fef3c7 0%, #fffbeb 100%)', border: '#fcd34d', accent: '#d97706' },
  { bg: 'linear-gradient(135deg, #f3e8ff 0%, #faf5ff 100%)', border: '#d8b4fe', accent: '#7c3aed' },
  { bg: 'linear-gradient(135deg, #ffe4e6 0%, #fff1f2 100%)', border: '#fda4af', accent: '#e11d48' },
  { bg: 'linear-gradient(135deg, #cffafe 0%, #ecfeff 100%)', border: '#67e8f9', accent: '#0891b2' },
]

export const ChapterOverviewPage: React.FC<ChapterOverviewPageProps> = ({ chapters, onSelectChapter }) => {
  const sorted = [...chapters].sort((a, b) => a.order - b.order)

  return (
    <div style={{ height: '100%', overflowY: 'auto', background: 'var(--bg-base)' }}>
      <div style={{ maxWidth: 1260, margin: '0 auto', padding: '32px 28px 40px' }}>
        <div style={{ marginBottom: 22 }}>
          <h1 style={{ margin: 0, color: 'var(--text-primary)', fontSize: 30, letterSpacing: '-0.02em' }}>章节导航</h1>
          <p style={{ margin: '8px 0 0', color: 'var(--text-muted)', fontSize: 14 }}>
            点击章节卡片，直接跳转到对应知识图谱
          </p>
        </div>

        {sorted.length === 0 ? (
          <div
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 14,
              padding: '28px 24px',
              color: 'var(--text-muted)',
              fontSize: 14,
            }}
          >
            暂无章节数据，请先检查后端数据加载是否正常。
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: 16,
            }}
          >
            {sorted.map((ch, idx) => {
              const palette = chapterColors[idx % chapterColors.length]
              return (
                <button
                  key={ch.chapter_id}
                  onClick={() => onSelectChapter(ch.chapter_id)}
                  style={{
                    textAlign: 'left',
                    border: `1px solid ${palette.border}`,
                    borderRadius: 14,
                    background: palette.bg,
                    padding: '18px 18px 16px',
                    cursor: 'pointer',
                    transition: 'transform 0.15s ease, box-shadow 0.2s ease, border-color 0.2s ease',
                    boxShadow: '0 3px 14px rgba(2,6,23,0.08)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.transform = 'translateY(-2px)'
                    e.currentTarget.style.boxShadow = '0 8px 22px rgba(2,6,23,0.14)'
                    e.currentTarget.style.borderColor = palette.accent
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)'
                    e.currentTarget.style.boxShadow = '0 3px 14px rgba(2,6,23,0.08)'
                    e.currentTarget.style.borderColor = palette.border
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '4px 9px',
                        borderRadius: 999,
                        fontSize: 12,
                        fontWeight: 600,
                        color: palette.accent,
                        background: 'rgba(255,255,255,0.7)',
                      }}
                    >
                      <BookOutlined /> {ch.chapter_id}
                    </span>
                    <ArrowRightOutlined style={{ color: palette.accent, fontSize: 14 }} />
                  </div>

                  <div style={{ color: '#0f172a', fontSize: 18, fontWeight: 700, lineHeight: 1.35, minHeight: 48 }}>
                    {ch.title}
                  </div>

                  <div style={{ marginTop: 10, color: '#475569', fontSize: 12 }}>
                    进入本章图谱
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
