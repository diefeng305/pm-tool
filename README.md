# 项目管理系统

基于 FastAPI + MySQL + 原生 HTML/CSS/JS 的项目管理系统。

## 功能特点

- 用户认证与权限管理
- 项目管理（创建、编辑、删除、搜索）
- 任务管理（发布、执行、审核）
- 里程碑管理
- 操作日志记录
- 实时事件推送
- 系统配置管理

## 技术栈

- **后端**: FastAPI (Python 3.10)
- **数据库**: MySQL 8.0
- **前端**: 原生 HTML/CSS/JS
- **容器化**: Docker & Docker Compose

## 快速启动

下载源码放到指定你指定目录

# 启动服务
docker compose up -d

注:在飞牛中启动服务时，会因为无法拉取python:3.1-slim依赖而启动失败，解决的办法是用root帐号来启动。具体原因不明，需要问飞牛开发团队。
备用命令清除缓存重新构建：docker compose down -v && docker compose build --no-cache && docker compose up -d && docker compose logs -f pm-backend

# 访问系统
http://localhost:8000
默认管理员:admin  密码:admin123
其它用户及权限管理员可自行添加。
