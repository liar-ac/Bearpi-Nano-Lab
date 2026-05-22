# BearPi Nano Lab

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2-092E20?style=flat-square&logo=django&logoColor=white)
![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?style=flat-square&logo=typescript&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

**面向嵌入式实验室的 IoT 设备管理平台**

实时监控 · 远程控制 · 告警管理 · 数据分析

</div>

---

## 功能特性

### 核心功能

- **设备管理** - 自动注册、状态监控、120 槽位拓扑
- **实时数据** - WebSocket 推送、传感器实时曲线
- **告警系统** - 阈值告警、多级告警（info/warning/critical）
- **远程控制** - 单设备/批量指令下发（重启/升级/参数设置）
- **批量任务** - 电机/补光灯同步控制，任务进度追踪
- **规则配置** - 传感器阈值在线调整
- **历史查询** - 时间范围查询、1m/5m/1h/1d 聚合、CSV/Excel 导出
- **功耗监控** - 电压/电流/功耗实时监测、趋势分析
- **审计日志** - 全操作记录追踪
- **用户权限** - admin/experimenter/viewer 三级权限

### 技术亮点

- **实时通信** - Django Channels + WebSocket，设备状态秒级推送
- **设备鉴权** - HMAC-SHA256 每板独立 Token
- **批量同步** - 多设备指令同步执行，支持重试
- **自动控制** - 温湿度阈值自动启停电机

## 技术架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  BearPi-HM  │     │   Vue 3 +   │     │   uni-app   │
│    Nano     │────▶│ Element Plus│     │  H5/小程序  │
│  (设备端)   │ HTTP │  (Web 前端) │     │  (移动端)   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │                   ▼                   │
       │            ┌─────────────┐            │
       └───────────▶│   Django    │◀───────────┘
                    │   REST +    │
                    │  Channels   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  MySQL   │ │  Redis   │ │ 华为云   │
        │  数据库  │ │  缓存    │ │  IoTDA   │
        └──────────┘ └──────────┘ └──────────┘
```

## 快速开始

### 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.9+ |
| Node.js | 18+ |
| MySQL | 8.0+ |
| Redis | 6.0+（可选，用于 WebSocket） |

### 1. 克隆项目

```bash
git clone https://github.com/your-username/bearpi-nano-lab.git
cd bearpi-nano-lab
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，配置 MySQL 连接等

# 数据库迁移
python manage.py migrate

# 创建演示数据（可选）
python manage.py seed_demo

# 启动服务
python manage.py runserver 0.0.0.0:8000
```

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产打包
npm run build
```

### 4. 移动端设置

```bash
cd mobile

# 安装依赖
npm install

# H5 开发
npm run dev:h5

# 微信小程序
npm run dev:mp-weixin
```

## 项目结构

```
bearpi-nano-lab/
├── backend/                    # Django 后端
│   ├── apps/
│   │   ├── accounts/          # 用户认证
│   │   ├── devices/           # 设备管理
│   │   ├── telemetry/         # 遥测数据
│   │   ├── alarms/            # 告警系统
│   │   ├── audit/             # 审计日志
│   │   ├── cloud/             # 云平台集成
│   │   └── common/            # 公共模块
│   ├── backend/               # Django 配置
│   └── manage.py
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/               # API 调用
│   │   ├── components/        # 组件
│   │   ├── views/             # 页面
│   │   ├── stores/            # Pinia 状态
│   │   ├── router/            # 路由
│   │   ├── types/             # TypeScript 类型
│   │   └── utils/             # 工具函数
│   └── package.json
├── mobile/                     # uni-app 移动端
│   ├── src/
│   │   ├── pages/             # 页面
│   │   ├── api/               # API 调用
│   │   ├── stores/            # 状态管理
│   │   └── types/             # 类型定义
│   └── package.json
└── docker-compose.yml          # Docker 部署
```

## API 文档

### 认证

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/login` | POST | 用户登录 |
| `/api/v1/auth/register` | POST | 用户注册 |
| `/api/v1/auth/refresh` | POST | 刷新 Token |

### 设备

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/devices` | GET | 设备列表 |
| `/api/v1/devices/:id` | GET | 设备详情 |
| `/api/v1/devices/:id/commands` | POST | 下发指令 |
| `/api/v1/devices/bulk-commands` | POST | 批量指令 |

### 遥测

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ingest/telemetry` | POST | 设备数据上报 |
| `/api/v1/sensors/:id/history` | GET | 历史数据 |

### 告警

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/alarms` | GET | 告警列表 |
| `/api/v1/alarms/:id/ack` | POST | 确认告警 |

### 设备端

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/device/commands/pull` | POST | 拉取指令 |
| `/api/v1/device/commands/ack` | POST | 指令回执 |

## 部署

### Docker 部署

```bash
docker-compose up -d
```

### 手动部署

1. 配置 Nginx 反向代理（参考 `frontend/nginx.conf`）
2. 使用 Gunicorn + Daphne 运行后端
3. 打包前端并部署到静态文件目录

## 默认账号

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | 管理员 |
| exp | admin123 | 实验员 |
| lab | admin123 | 实验员 |
| viewer | admin123 | 只读 |

> 首次使用请执行 `python manage.py seed_demo` 初始化演示数据

## 传感器列表

| Code | 名称 | 单位 | 说明 |
|------|------|------|------|
| temp | 温度 | ℃ | 板载温度传感器 |
| hum | 湿度 | % | 环境湿度 |
| light | 光照 | lx | 光照强度 |
| motor | 电机 | - | 通风电机状态 |
| voltage | 电压 | V | 工作电压 |
| current | 电流 | mA | 工作电流 |
| power | 功耗 | mW | 瞬时功耗 |

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 致谢

- [BearPi](https://bearpi.aliyun.com/) - 小熊派开发板
- [Django](https://www.djangoproject.com/) - Web 框架
- [Vue.js](https://vuejs.org/) - 前端框架
- [Element Plus](https://element-plus.org/) - UI 组件库
- [uni-app](https://uniapp.dcloud.net.cn/) - 跨平台框架
