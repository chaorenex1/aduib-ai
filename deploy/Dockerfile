# dockerfile
FROM aduib-ai-base:latest

# 基本设置
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TZ=Asia/Shanghai
ENV DOCKER_ENV=true
ENV APP_HOST=10.0.0.96
WORKDIR /app

# 先复制依赖描述文件以利用缓存
# COPY pyproject.toml uv.lock* .env.production ./
# 复制项目源码
COPY . .

# 安装 uv 包管理器并使用 uv 安装依赖（只安装非 dev 依赖）
RUN  pip install uv \
    && uv venv \
    && uv sync --frozen --no-dev \
    && uv add uvloop httptools

ENTRYPOINT ["uvicorn","app:app","--host", "0.0.0.0", "--port", "5001", "--workers", "4",  "--loop", "uvloop", "--http", "httptools"]