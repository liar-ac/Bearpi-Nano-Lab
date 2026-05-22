# Changelog

本项目遵循 [Semantic Versioning](https://semver.org/) 规范。

## [1.0.0] - 2026-05-22

### 新增

- 设备自动注册与管理（BearPi-HM Nano 开发板）
- 实时遥测数据采集与存储（MySQL）
- WebSocket 实时数据推送（Django Channels）
- 阈值告警系统（info/warning/critical）
- 远程设备指令下发（重启/升级/参数设置）
- 批量设备控制（电机/补光灯同步控制）
- 传感器阈值规则配置
- 审计日志记录
- 用户权限管理（admin/experimenter/viewer）
- Web 前端控制台（Vue 3 + Element Plus）
- 移动端 H5/小程序（uni-app）
- 实时大屏展示
- 120 槽位拓扑视图
- 功耗监控与趋势分析
- 历史数据查询与 CSV/Excel 导出
- 华为云 IoTDA 集成接口
- 设备 Token 鉴权（HMAC-SHA256）
- JWT 用户认证
- Docker 部署支持

### 安全

- JWT Token 认证
- 设备独立 Token 鉴权
- CORS 精确配置
- Rate Limiting（登录/注册/刷新）
- CSV 公式注入防护
- 生产环境安全警告

## [0.1.0] - 2026-04-01

### 新增

- 项目初始化
- 基础架构搭建
