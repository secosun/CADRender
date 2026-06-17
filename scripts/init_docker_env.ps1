# CADRender Docker 开发环境初始化
# 在安装完 Docker Desktop 后，以管理员身份运行

Write-Output "=== CADRender Docker 环境初始化 ==="

# 1. 启用 WSL2
Write-Output "[1/5] 启用 WSL2..."
wsl --update
wsl --set-default-version 2

# 2. 拉取基础镜像
Write-Output "[2/5] 拉取镜像..."
docker pull redis:7-alpine
docker pull minio/minio:latest
docker pull amrit3701/freecad-cli:latest

# 3. 构建 blenderserver 镜像
Write-Output "[3/5] 构建 blenderserver..."
docker compose -f docker-compose.dev.yml build blenderserver

# 4. 构建 blenderworker 镜像
Write-Output "[4/5] 构建 blenderworker..."
docker compose -f docker-compose.dev.yml build blenderworker

# 5. 验证
Write-Output "[5/5] 验证..."
docker compose -f docker-compose.dev.yml --profile full config --services

Write-Output ""
Write-Output "=== 初始化完成 ==="
Write-Output ""
Write-Output "启动开发环境:"
Write-Output "  docker compose -f docker-compose.dev.yml --profile full up -d"
Write-Output ""
Write-Output "宿主机启动 Blender:"
Write-Output "  blender -b -P blender_launcher.py -- --port 19876"
