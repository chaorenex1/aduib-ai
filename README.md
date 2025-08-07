# 项目简介

本项目为 Python 后端服务，采用模块化架构，支持多种存储、向量数据库、模型管理等功能，适用于 AI 应用开发。

## 目录结构说明

- aduib_app.py / app_factory.py / app.py  
  应用入口及工厂方法，负责应用初始化和启动。

- alembic/  
  数据库迁移管理，包含迁移脚本和配置。

- backend/  
  后端核心模块，包含基础模型、数据库、引擎、服务、分词、工具、向量等子模块。

- component/  
  组件模块，包含日志、存储（本地、S3、OpenDAL）、向量数据库等实现。

- configs/  
  配置模块，包含应用、CORS、数据库、部署、图数据库、ID、日志、Sentry、远程、存储、向量数据库等配置。

- constants/  
  常量定义，如 TTS 相关常量。

- controllers/  
  控制器层，包含参数、路由及各业务子模块（如认证、聊天、文件等）。

- libs/  
  公共库，包含上下文、依赖等工具。

- models/  
  数据模型定义，包括 API Key、基础模型、引擎、模型、服务商等。

- runtime/  
  运行时管理，如模型管理、服务商管理、回调、客户端、实体、服务商实现等。

- service/  
  业务服务层，包含 API Key、补全、模型、服务商等服务及错误处理。

- test/  
  测试代码。

- utils/  
  工具类，如 API Key 工具、网络工具、雪花 ID 生成等。

## 快速开始

1. 安装依赖  
   ```bash
   pip install -r requirements.txt
