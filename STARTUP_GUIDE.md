# 🚀 C 语言知识图谱系统 - 完整启动指南

## 前置条件检查

### 1. 确保 Ollama 已启动
```bash
# 打开一个新的终端窗口，运行：
ollama serve
```
你应该看到类似的输出：
```
Listening on 127.0.0.1:11434
```
**保持这个终端窗口打开，不要关闭！**

### 2. 确保 Neo4j 已启动
```bash
# 打开另一个新的终端窗口，运行：
neo4j start
```
或者如果你用 Docker：
```bash
docker run -d -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

---

## 第一次启动（导入数据）

### 步骤 1：打开终端，进入项目目录
```bash
cd /Users/zuyi/Desktop/毕业设计/c_course_kg
```

### 步骤 2：激活虚拟环境
```bash
source venv/bin/activate
```
你应该看到终端前面出现 `(venv)` 标记

### 步骤 3：导入知识图谱数据（包括关系）
```bash
python src/import_neo4j.py
```

你应该看到类似的输出：
```
发现关系数据: 86 条
导入知识点关系...
  PREREQUISITE: 54 条
  RELATED: 26 条
  EXTENDS: 6 条
、Import done: 8 chapters, 28 kps, 28 contains edges, 86 relations (db=neo4j, uri=bolt://localhost:7687)
```

**这表示导入成功！** ✅

---

## 第二次及以后启动（启动完整系统）

### 步骤 1：打开终端，进入项目目录
```bash
cd /Users/zuyi/Desktop/毕业设计/c_course_kg
```

### 步骤 2：启动系统
```bash
./start.sh
```

你应该看到：
```
🚀 启动 C 语言知识图谱系统...

📦 启动后端服务...
启动后端 (http://localhost:8000)...

📱 启动前端服务...
启动前端 (http://localhost:3000)...

✅ 系统已启动！

📍 访问地址：
   前端: http://localhost:3000
   后端: http://localhost:8000
   API 文档: http://localhost:8000/docs

按 Ctrl+C 停止服务
```

### 步骤 3：打开浏览器访问系统

在浏览器中打开：
```
http://localhost:3000
```

你应该看到：
- 左侧：章节树和知识点统计
- 中间：完整的知识图谱（蓝色和绿色的节点）
- 右下角：蓝色的 AI 聊天按钮

---

## 各个功能的使用

### 1. 查看知识图谱
- 直接在中间区域看到所有知识点和关系
- 蓝色节点 = 知识点
- 绿色节点 = 章节
- 箭头 = 关系（先修、相关等）

### 2. 点击左侧章节筛选
- 点击左侧任何章节（如"CH01 C语言概述"）
- 图谱会自动筛选只显示该章节的知识点
- 工具栏会显示"已筛选章节"

### 3. 点击知识点查看详情
- 在图谱中点击任何蓝色节点
- 右侧会弹出详情面板
- 显示先修知识点、后继知识点、相关知识点

### 4. 使用 AI 聊天
- 点击右下角蓝色的机器人按钮
- 聊天框顶部显示"已连接"（绿色）表示 Ollama 正常
- 直接提问 C 语言问题，如：
  - "什么是指针？"
  - "for 循环怎么用？"
  - "函数和递归的区别？"
- 看到 AI 一个字一个字打出来（流式响应）

### 5. 访问管理员界面
- 点击顶部菜单"管理员"
- 可以上传新数据、审核、编辑知识点

### 6. 查看 API 文档
- 在浏览器打开：http://localhost:8000/docs
- 可以测试所有后端 API

---

## 常见问题排查

### 问题 1：前端无法连接到后端
**症状**：浏览器显示"无法连接到后端"

**解决**：
```bash
# 检查后端是否运行
curl http://localhost:8000/api/health

# 如果没有响应，重启系统
./start.sh
```

### 问题 2：AI 聊天显示"未连接"
**症状**：聊天框顶部显示红色"未连接"

**解决**：
```bash
# 确保 Ollama 在运行
ollama serve

# 测试 Ollama
curl http://localhost:11434/api/tags
```

### 问题 3：知识图谱显示为空
**症状**：中间区域没有节点

**解决**：
```bash
# 重新导入数据
source venv/bin/activate
python src/import_neo4j.py

# 然后刷新浏览器（F5）
```

### 问题 4：Neo4j 连接失败
**症状**：后端日志显示"Couldn't connect to localhost:7687"

**解决**：
```bash
# 检查 Neo4j 是否运行
lsof -i :7687

# 如果没有，启动 Neo4j
neo4j start

# 或用 Docker
docker run -d -p 7687:7687 -p 7474:7474 -e NEO4J_AUTH=neo4j/password neo4j:latest
```

---

## 停止系统

### 方法 1：在启动终端按 Ctrl+C
```
按 Ctrl+C 停止服务
```

### 方法 2：停止各个服务
```bash
# 停止 Ollama（在 Ollama 终端按 Ctrl+C）
# 停止 Neo4j
neo4j stop
```

---

## 完整的启动流程总结

```
1. 打开终端 1：ollama serve
   ↓
2. 打开终端 2：neo4j start（或 docker run ...）
   ↓
3. 打开终端 3：cd /Users/zuyi/Desktop/毕业设计/c_course_kg
   ↓
4. source venv/bin/activate
   ↓
5. python src/import_neo4j.py（第一次）
   ↓
6. ./start.sh
   ↓
7. 打开浏览器：http://localhost:3000
   ↓
8. 开始使用！
```

---

## 快速参考

| 服务 | 地址 | 端口 | 启动命令 |
|------|------|------|---------|
| 前端 | http://localhost:3000 | 3000 | ./start.sh |
| 后端 | http://localhost:8000 | 8000 | ./start.sh |
| API 文档 | http://localhost:8000/docs | 8000 | 自动 |
| Neo4j | http://localhost:7474 | 7474 | neo4j start |
| Ollama | http://localhost:11434 | 11434 | ollama serve |

---

## 需要帮助？

如果遇到问题，按这个顺序检查：
1. ✅ Ollama 是否在运行？（ollama serve）
2. ✅ Neo4j 是否在运行？（neo4j start）
3. ✅ 虚拟环境是否激活？（source venv/bin/activate）
4. ✅ 数据是否导入？（python src/import_neo4j.py）
5. ✅ 系统是否启动？（./start.sh）
6. ✅ 浏览器是否刷新？（F5）

祝你使用愉快！🎉
