import React from 'react'
import { Button, Menu, Tooltip } from 'antd'
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  HomeOutlined,
  ApartmentOutlined,
  SettingOutlined,
  BulbOutlined,
  BulbFilled,
} from '@ant-design/icons'
import { useAppStore } from '@/services/store'
import type { ThemeKey } from '@/styles/themes'

interface HeaderProps {
  onToggleSidebar: () => void
  currentPage: string
  onPageChange: (page: string) => void
  onToggleTheme: () => void
  currentTheme: ThemeKey
}

export const AppHeader: React.FC<HeaderProps> = ({
  onToggleSidebar,
  currentPage,
  onPageChange,
  onToggleTheme,
  currentTheme,
}) => {
  const sidebarOpen = useAppStore((state) => state.sidebarOpen)

  return (
    <div
      style={{
        height: 56,
        flexShrink: 0,
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: 12,
        position: 'relative',
        zIndex: 100,
      }}
    >
      {/* 折叠按钮 */}
      <Button
        type="text"
        icon={sidebarOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
        onClick={onToggleSidebar}
        style={{
          color: 'var(--text-secondary)',
          fontSize: 16,
          width: 36,
          height: 36,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      />

      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginRight: 32, flexShrink: 0 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            background: 'linear-gradient(135deg, var(--primary) 0%, var(--purple) 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 14,
            fontWeight: 700,
            color: '#080d1a',
            fontFamily: 'var(--font-mono)',
            boxShadow: '0 0 12px var(--primary-glow)',
          }}
        >
          C
        </div>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontWeight: 600,
            fontSize: 14,
            color: 'var(--text-primary)',
            letterSpacing: '0.05em',
            whiteSpace: 'nowrap',
          }}
        >
          知识图谱
          <span style={{ color: 'var(--primary)', marginLeft: 4 }}>·</span>
          <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: 12 }}> C语言</span>
        </span>
      </div>

      {/* 导航 */}
      <Menu
        mode="horizontal"
        selectedKeys={[currentPage]}
        onClick={(e) => onPageChange(e.key)}
        style={{
          background: 'transparent',
          borderBottom: 'none',
          flex: 1,
          minWidth: 0,
        }}
        items={[
          {
            key: 'dashboard',
            icon: <HomeOutlined />,
            label: '主页',
          },
          {
            key: 'graph',
            icon: <ApartmentOutlined />,
            label: '知识图谱',
          },
          {
            key: 'admin',
            icon: <SettingOutlined />,
            label: '管理',
            style: { marginLeft: 'auto' },
          },
        ]}
      />

      {/* 状态指示 + 主题切换 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <Tooltip title={currentTheme === 'dark' ? '切换浅色模式' : '切换深色模式'}>
          <Button
            type="text"
            icon={currentTheme === 'dark'
              ? <BulbOutlined style={{ fontSize: 17 }} />
              : <BulbFilled style={{ fontSize: 17, color: 'var(--accent)' }} />
            }
            onClick={onToggleTheme}
            style={{
              color: currentTheme === 'dark' ? 'var(--text-muted)' : 'var(--accent)',
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 6,
              transition: 'color 0.2s',
            }}
          />
        </Tooltip>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: 'var(--success)',
              boxShadow: '0 0 6px var(--success)',
            }}
          />
          <span style={{ color: 'var(--text-muted)', fontSize: 12, fontFamily: 'var(--font-mono)' }}>
            ONLINE
          </span>
        </div>
      </div>
    </div>
  )
}
