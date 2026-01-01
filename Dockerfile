# 使用 Python 3.12 官方镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖 (串口通信可能需要一些库)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# 复制项目源代码和配置文件
COPY src/ ./src/
COPY config.yaml ./

# 创建数据存储目录（如果 SQLite 路径包含目录）
RUN mkdir -p /app/data

# 暴露 Streamlit 端口
EXPOSE 8501

# 默认启动命令 (可以通过 docker-compose 覆盖)
CMD ["streamlit", "run", "src/oee/dashboardv1.py", "--server.port=8501", "--server.address=0.0.0.0"]
