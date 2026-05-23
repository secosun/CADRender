# Claude Code + DeepSeek 代理开机启动

## 原理

```
Claude Code  →  http://localhost:8099  →  deepseek_proxy.py  →  api.deepseek.com/anthropic
```

`%USERPROFILE%\.claude\settings.json` 中已配置 `ANTHROPIC_BASE_URL` 指向本机代理即可。

**勿同时设置** `ANTHROPIC_AUTH_TOKEN` 与 `ANTHROPIC_API_KEY`（会触发 Auth conflict 并导致反复重试）。走本地代理时只保留 **`ANTHROPIC_API_KEY`**。

## 一次性准备

```powershell
cd D:\咸阳\框架评审\CADRender

# 虚拟环境（推荐，避免污染全局 Python）
python -m venv .venv-proxy
.\.venv-proxy\Scripts\pip install -r requirements-proxy.txt

# API Key（勿提交 git）
copy .env.example .env
# 编辑 .env，设置 DEEPSEEK_API_KEY=sk-...
```

## 注册开机自启

**以当前用户**在 PowerShell 中执行（无需管理员）：

```powershell
powershell -ExecutionPolicy Bypass -File install_deepseek_proxy_startup.ps1
```

会创建计划任务 **`CADRender-DeepSeek-Proxy`**，在用户登录时后台启动代理。

## 手动启停

```powershell
# 启动
powershell -ExecutionPolicy Bypass -File start_deepseek_proxy.ps1

# 健康检查
Invoke-WebRequest http://127.0.0.1:8099/health -UseBasicParsing

# 取消开机自启
powershell -ExecutionPolicy Bypass -File uninstall_deepseek_proxy_startup.ps1
```

## 日志

`%LOCALAPPDATA%\CADRender\deepseek_proxy.log`

## 取消自启

```powershell
powershell -ExecutionPolicy Bypass -File uninstall_deepseek_proxy_startup.ps1
```
