import type { ThemeConfig } from 'antd'

export type ThemeKey = 'dark' | 'light'

export interface AppTheme {
  key: ThemeKey
  label: string
  antdTheme: ThemeConfig
  cssVars: Record<string, string>
}

export const THEMES: Record<ThemeKey, AppTheme> = {
  dark: {
    key: 'dark',
    label: '深色',
    antdTheme: {
      token: {
        colorPrimary: '#38bdf8',
        colorBgBase: '#080d1a',
        colorBgContainer: '#111d35',
        colorBgElevated: '#162040',
        colorBgLayout: '#080d1a',
        colorTextBase: '#e2e8f0',
        colorText: '#e2e8f0',
        colorTextSecondary: '#7d90b0',
        colorBorder: '#1e2d4a',
        colorBorderSecondary: '#1e2d4a',
        colorSplit: '#1e2d4a',
        borderRadius: 8,
        colorSuccess: '#34d399',
        colorWarning: '#f59e0b',
        colorError: '#f87171',
        colorInfo: '#38bdf8',
        fontFamily: 'Noto Sans SC, -apple-system, sans-serif',
      },
      components: {
        Menu: {
          itemBg: 'transparent',
          itemColor: '#7d90b0',
          itemHoverColor: '#38bdf8',
          itemSelectedColor: '#38bdf8',
          itemSelectedBg: 'rgba(56,189,248,0.1)',
          horizontalItemSelectedColor: '#38bdf8',
        },
        Layout: {
          bodyBg: '#080d1a',
          headerBg: '#0d1526',
          siderBg: '#0d1526',
        },
      },
    },
    cssVars: {
      '--primary': '#38bdf8',
      '--primary-dim': '#0ea5e9',
      '--primary-glow': 'rgba(56, 189, 248, 0.25)',
      '--accent': '#f59e0b',
      '--accent-glow': 'rgba(245, 158, 11, 0.2)',
      '--success': '#34d399',
      '--danger': '#f87171',
      '--purple': '#a78bfa',
      '--bg-base': '#080d1a',
      '--bg-surface': '#0d1526',
      '--bg-panel': '#111d35',
      '--bg-card': '#162040',
      '--bg-hover': '#1c2a50',
      '--bg-input': '#0d1828',
      '--text-primary': '#e2e8f0',
      '--text-secondary': '#7d90b0',
      '--text-muted': '#4a5a78',
      '--text-accent': '#38bdf8',
      '--border': '#1e2d4a',
      '--border-bright': '#2d4170',
      '--border-glow': 'rgba(56, 189, 248, 0.4)',
    },
  },

  light: {
    key: 'light',
    label: '浅色',
    antdTheme: {
      token: {
        colorPrimary: '#2563eb',
        colorBgBase: '#f8fafc',
        colorBgContainer: '#ffffff',
        colorBgElevated: '#ffffff',
        colorBgLayout: '#f1f5f9',
        colorTextBase: '#0f172a',
        colorText: '#1e293b',
        colorTextSecondary: '#64748b',
        colorBorder: '#e2e8f0',
        colorBorderSecondary: '#e2e8f0',
        colorSplit: '#e2e8f0',
        borderRadius: 8,
        colorSuccess: '#16a34a',
        colorWarning: '#d97706',
        colorError: '#dc2626',
        colorInfo: '#2563eb',
        fontFamily: 'Noto Sans SC, -apple-system, sans-serif',
      },
      components: {
        Menu: {
          itemBg: 'transparent',
          itemColor: '#64748b',
          itemHoverColor: '#2563eb',
          itemSelectedColor: '#2563eb',
          itemSelectedBg: 'rgba(37,99,235,0.08)',
          horizontalItemSelectedColor: '#2563eb',
        },
        Layout: {
          bodyBg: '#f1f5f9',
          headerBg: '#ffffff',
          siderBg: '#ffffff',
        },
      },
    },
    cssVars: {
      '--primary': '#2563eb',
      '--primary-dim': '#1d4ed8',
      '--primary-glow': 'rgba(37, 99, 235, 0.15)',
      '--accent': '#d97706',
      '--accent-glow': 'rgba(217, 119, 6, 0.15)',
      '--success': '#16a34a',
      '--danger': '#dc2626',
      '--purple': '#7c3aed',
      '--bg-base': '#f1f5f9',
      '--bg-surface': '#ffffff',
      '--bg-panel': '#f8fafc',
      '--bg-card': '#ffffff',
      '--bg-hover': '#f1f5f9',
      '--bg-input': '#f8fafc',
      '--text-primary': '#0f172a',
      '--text-secondary': '#475569',
      '--text-muted': '#94a3b8',
      '--text-accent': '#2563eb',
      '--border': '#e2e8f0',
      '--border-bright': '#cbd5e1',
      '--border-glow': 'rgba(37, 99, 235, 0.3)',
    },
  },
}

export function applyTheme(theme: AppTheme) {
  const root = document.documentElement
  Object.entries(theme.cssVars).forEach(([key, value]) => {
    root.style.setProperty(key, value)
  })
  root.setAttribute('data-theme', theme.key)
}
