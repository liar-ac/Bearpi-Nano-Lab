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

## 目录

- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [嵌入式固件](#嵌入式固件)
- [项目结构](#项目结构)
- [API 文档](#api-文档)
- [部署](#部署)
- [贡献](#贡献)
- [许可证](#许可证)

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

---

## 技术架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   BearPi-HM     │     │   Vue 3 +       │     │   uni-app       │
│     Nano        │────▶│   Element Plus  │     │   H5 / 小程序   │
│   (嵌入式设备)   │ HTTP│   (Web 前端)    │     │   (移动端)      │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       ▼                       │
         │               ┌─────────────────┐             │
         └──────────────▶│     Django      │◀────────────┘
                         │   REST API +    │
                         │   Channels      │
                         └────────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  MySQL   │ │  Redis   │ │ 华为云   │
              │  数据库  │ │  缓存    │ │  IoTDA   │
              └──────────┘ └──────────┘ └──────────┘
```

---

## 快速开始

### 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.9+ | 后端运行环境 |
| Node.js | 18+ | 前端 / 移动端构建 |
| MySQL | 8.0+ | 数据存储 |
| Redis | 6.0+ | WebSocket 消息队列（可选） |

### 1. 克隆项目

```bash
git clone https://github.com/liar-ac/Bearpi-Nano-Lab.git
cd Bearpi-Nano-Lab
```

### 2. 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，配置 MySQL 连接信息

# 数据库迁移
python manage.py migrate

# 初始化演示数据（可选）
python manage.py seed_demo

# 启动服务
python manage.py runserver 0.0.0.0:8000
```

### 3. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 开发模式（端口 5174）
npm run dev

# 生产打包
npm run build
```

### 4. 移动端启动

```bash
cd mobile

# 安装依赖
npm install

# H5 开发
npm run dev:h5

# 微信小程序
npm run dev:mp-weixin
```

---

## 嵌入式固件

### 简介

`firmware/` 目录包含 BearPi-HM Nano（OpenHarmony / Hi3861）的示例固件代码。

### 核心模块

| 目录 | 功能 |
|------|------|
| `my_bearpi_lab_http` | **IoT 主固件** — 传感器采集 + HTTP 上报 + 指令拉取 + 执行器控制 |
| `my_wifi_sta_connect` | WiFi STA 连接示例 |
| `my_wifi_ap` | WiFi AP 热点示例 |
| `my_tcp_server` | TCP 服务器示例 |
| `my_udp_client` | UDP 客户端示例 |
| `my_mqtt` | MQTT 客户端示例 |
| `my_e53_ia1` | E53_IA1 传感器板驱动（温湿度 + 光照 + 电机 + 补光灯） |
| `my_e53_sc2` | E53_SC2 传感器板驱动（MPU6050 六轴） |
| `my_led` / `my_led_blink` | LED 控制示例 |
| `my_pwm_led` | PWM 呼吸灯示例 |
| `my_button` | 按键中断示例 |
| `my_thread` / `my_mutex` / `my_semaphore` / `my_message` / `my_event` / `my_timer` | RTOS 基础示例 |

### 配置

编辑 `firmware/my_bearpi_lab_http/include/bearpi_lab_config.h`：

```c
#define BEARPI_WIFI_SSID           "YOUR_WIFI_SSID"        // 你的热点名称
#define BEARPI_WIFI_PASSWORD       "YOUR_WIFI_PASSWORD"     // 你的热点密码
#define BEARPI_SERVER_HOST         "YOUR_SERVER_IP"         // 后端服务器 IP
#define BEARPI_SERVER_HOST_FALLBACK "192.168.137.1"         // 备用 IP（电脑热点）
#define BEARPI_SERVER_PORT         8000                     // 后端端口
#define BEARPI_DEVICE_SN           "BEARPI-NANO-A001"       // 设备唯一序列号
#define BEARPI_DEVICE_TOKEN_SECRET "replace-me-device-token-secret" // 与后端一致
#define BEARPI_REPORT_INTERVAL_MS  2000                     // 上报间隔（毫秒）
```

### 烧录步骤

1. 安装 [DevEco Device Tool](https://device.harmonyos.com/cn/ide)
2. 将 `firmware/my_bearpi_lab_http` 目录复制到 OpenHarmony SDK 的应用目录
3. 修改 `bearpi_lab_config.h` 中的 WiFi 和服务器配置
4. 编译并烧录到 BearPi-HM Nano 开发板
5. 串口查看日志输出

---

## 项目结构

```
Bearpi-Nano-Lab/
│
├── firmware/                        # 嵌入式固件（BearPi-HM Nano）
│   ├── my_bearpi_lab_http/         #   IoT 主固件
│   ├── my_e53_ia1/                 #   E53_IA1 传感器驱动
│   ├── my_wifi_sta_connect/        #   WiFi 连接示例
│   └── ...                         #   其他示例
│
├── backend/                         # Django 后端
│   ├── apps/
│   │   ├── accounts/               #   用户认证与权限
│   │   ├── devices/                #   设备管理与指令
│   │   ├── telemetry/              #   遥测数据采集
│   │   ├── alarms/                 #   告警系统
│   │   ├── audit/                  #   审计日志
│   │   ├── cloud/                  #   华为云 IoTDA 集成
│   │   └── common/                 #   公共模块（设备网关）
│   ├── backend/                    #   Django 配置
│   └── manage.py
│
├── frontend/                        # Vue 3 Web 前端
│   ├── src/
│   │   ├── api/                    #   API 调用层
│   │   ├── components/             #   公共组件
│   │   ├── views/                  #   页面视图
│   │   ├── stores/                 #   Pinia 状态管理
│   │   └── router/                 #   路由配置
│   └── package.json
│
├── mobile/                          # uni-app 移动端
│   ├── src/
│   │   ├── pages/                  #   页面
│   │   ├── api/                    #   API 调用层
│   │   └── stores/                 #   状态管理
│   └── package.json
│
├── README.md
├── LICENSE
├── CONTRIBUTING.md
└── CHANGELOG.md
```

---

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
| `/api/v1/sensors/:id/history` | GET | 历史数据查询 |

### 告警

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/alarms` | GET | 告警列表 |
| `/api/v1/alarms/:id/ack` | POST | 确认告警 |

### 设备端

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/device/commands/pull` | POST | 拉取待执行指令 |
| `/api/v1/device/commands/ack` | POST | 指令执行回执 |

---

## 部署

### Docker 部署

```bash
docker-compose up -d
```

### 手动部署

1. 配置 Nginx 反向代理（参考 `frontend/nginx.conf`）
2. 使用 Gunicorn + Daphne 运行后端
3. 执行 `npm run build` 打包前端，部署到静态文件目录

---

## 默认账号

| 账号 | 密码 | 角色 | 权限 |
|------|------|------|------|
| admin | admin123 | 管理员 | 全部权限 |
| exp | admin123 | 实验员 | 查看 + 指令 + 告警确认 |
| lab | admin123 | 实验员 | 查看 + 指令 + 告警确认 |
| viewer | admin123 | 只读 | 仅查看 |

> 首次使用请执行 `python manage.py seed_demo` 初始化演示数据

---

## 传感器列表

| Code | 名称 | 单位 | 说明 |
|------|------|------|------|
| temp | 温度 | ℃ | 板载温度传感器 |
| hum | 湿度 | % | 环境湿度 |
| light | 光照 | lx | 光照强度 |
| motor | 电机 | — | 通风电机状态（0/1） |
| voltage | 电压 | V | 工作电压 |
| current | 电流 | mA | 工作电流 |
| power | 功耗 | mW | 瞬时功耗 |

---

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 致谢

- [BearPi](https://bearpi.aliyun.com/) - 小熊派开发板
- [Django](https://www.djangoproject.com/) - Web 框架
- [Vue.js](https://vuejs.org/) - 前端框架
- [Element Plus](https://element-plus.org/) - UI 组件库
- [uni-app](https://uniapp.dcloud.net.cn/) - 跨平台框架
