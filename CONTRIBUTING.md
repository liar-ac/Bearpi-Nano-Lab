# Contributing to BearPi Nano Lab

感谢你对 BearPi Nano Lab 项目的关注！我们欢迎任何形式的贡献。

## 如何贡献

### 报告 Bug

1. 在 [Issues](../../issues) 中搜索是否已有相同问题
2. 如果没有，创建一个新的 Issue，包含：
   - 清晰的标题和描述
   - 复现步骤
   - 期望行为 vs 实际行为
   - 环境信息（OS、Python 版本、Node 版本等）

### 提交功能建议

1. 在 [Issues](../../issues) 中创建功能请求
2. 说明使用场景和预期效果
3. 等待维护者反馈后再开始实现

### 提交代码

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'feat: add your feature'`
4. 推送到 Fork：`git push origin feature/your-feature`
5. 创建 Pull Request

## 开发规范

### Commit Message

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

类型说明：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

### 代码风格

**后端 (Python)**
- 遵循 PEP 8
- 使用 Black 格式化
- 使用 isort 排序 import

**前端 (TypeScript/Vue)**
- 使用 ESLint + Prettier
- Vue 组件使用 `<script setup>` 语法
- TypeScript 严格模式

### 分支策略

- `main`: 稳定版本
- `develop`: 开发分支
- `feature/*`: 功能分支
- `fix/*`: 修复分支

## 开发环境

请参考 [README.md](README.md) 的"快速开始"部分配置开发环境。

## 行为准则

- 尊重每位参与者
- 接受建设性批评
- 专注于对社区最有利的事情
- 对他人表示同理心

## 问题？

如有疑问，请在 [Issues](../../issues) 中提问。
