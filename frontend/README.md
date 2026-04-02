# C 语言知识图谱前端

基于 React + TypeScript + Cytoscape.js 的知识图谱可视化系统

## 功能特性

- 📚 **知识图谱可视化** - 交互式展示知识点和关系
- 🤖 **AI 学习助手** - 与 AI 交互获取学习建议
- 🔍 **智能搜索** - 快速查找知识点
- 📖 **章节浏览** - 按教材章节组织学习
- 📊 **统计分析** - 查看知识体系概览

## 快速开始

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:3000

### 生产构建

```bash
npm run build
npm run preview
```

## 项目结构

```
src/
├── components/          # React 组件
│   ├── Layout/         # 布局组件
│   ├── Graph/          # 图谱可视化
│   ├── AIChat/         # AI 聊天
│   ├── Search/         # 搜索功能
│   ├── KnowledgePoint/ # 知识点详情
│   └── pages/          # 页面组件
├── services/           # API 和状态管理
│   ├── api.ts         # API 调用
│   └── store.ts       # Zustand 状态管理
├── types/              # TypeScript 类型定义
├── styles/             # 全局样式
├── App.tsx             # 主应用
└── main.tsx            # 入口文件
```

## 技术栈

- React 18
- TypeScript
- Ant Design 5
- Cytoscape.js
- Zustand
- Tailwind CSS
- Vite
## 环境变量

创建 `.env` 文件（如需要）：

```
VITE_API_BASE=http://localhost:8000/api
```

## 后端 API 要求

确保后端提供以下 API 端点：

- `GET /api/health` - 健康检查
- `GET /api/chapters` - 获取所有章节
- `GET /api/chapters/{chapter_id}` - 获取章节详情
- `GET /api/kps/search?q=keyword` - 搜索知识点
- `GET /api/graph` - 获取完整图谱
- `POST /api/ai/chat` - AI 聊天

## 许可证

MIT

