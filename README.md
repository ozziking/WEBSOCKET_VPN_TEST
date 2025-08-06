# WebSocket VPN 项目

这是一个基于WebSocket技术的VPN项目，支持多节点配置和自动切换。

## 项目特性

- 🔒 基于WebSocket的安全隧道
- 🌍 多节点支持（美国节点）
- ⚡ 自动节点切换
- 🛡️ 流量加密
- 📱 跨平台支持
- 🔧 易于配置和部署

## 快速开始

### 1. 从GitHub下载项目

```bash
# 克隆项目到本地
git clone https://github.com/your-username/websocket-vpn.git
cd websocket-vpn

# 或者直接下载ZIP文件
wget https://github.com/your-username/websocket-vpn/archive/refs/heads/main.zip
unzip main.zip
cd websocket-vpn-main
```

### 2. 安装依赖

#### 服务器端依赖
```bash
# 进入服务器目录
cd server

# 安装Python依赖
pip install -r requirements.txt

# 或者使用虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

#### 客户端依赖
```bash
# 进入客户端目录
cd client

# 安装依赖
npm install
# 或者
yarn install
```

### 3. 配置节点

编辑 `config/nodes.json` 文件，配置您的服务器节点：

```json
{
  "nodes": [
    {
      "id": "us-east-1",
      "name": "US East 1",
      "host": "your-server-1.com",
      "port": 443,
      "protocol": "wss",
      "location": "US",
      "priority": 1
    },
    {
      "id": "us-west-1", 
      "name": "US West 1",
      "host": "your-server-2.com",
      "port": 443,
      "protocol": "wss",
      "location": "US",
      "priority": 2
    }
  ]
}
```

### 4. 启动服务器

```bash
# 启动主服务器
cd server
python main.py

# 或者使用Docker
docker-compose up -d
```

### 5. 启动客户端

```bash
# 启动Web客户端
cd client
npm start

# 或者启动命令行客户端
cd client/cli
python client.py
```

## 项目结构

```
websocket-vpn/
├── server/                 # 服务器端代码
│   ├── main.py            # 主服务器
│   ├── proxy.py           # 代理处理
│   ├── tunnel.py          # 隧道管理
│   ├── config/            # 配置文件
│   └── requirements.txt   # Python依赖
├── client/                # 客户端代码
│   ├── web/              # Web界面
│   ├── cli/              # 命令行客户端
│   └── package.json      # Node.js依赖
├── config/               # 全局配置
│   ├── nodes.json        # 节点配置
│   └── settings.json     # 应用设置
├── docs/                 # 文档
└── scripts/              # 部署脚本
```

## 配置说明

### 服务器配置

1. **基础配置** (`server/config/server.json`)
```json
{
  "host": "0.0.0.0",
  "port": 8080,
  "ssl": {
    "enabled": true,
    "cert": "path/to/cert.pem",
    "key": "path/to/key.pem"
  },
  "auth": {
    "enabled": true,
    "tokens": ["your-secret-token"]
  }
}
```

2. **节点配置** (`config/nodes.json`)
- `id`: 节点唯一标识
- `name`: 节点显示名称
- `host`: 服务器地址
- `port`: 端口号
- `protocol`: 协议 (ws/wss)
- `location`: 地理位置
- `priority`: 优先级

### 客户端配置

1. **Web客户端** (`client/web/src/config.js`)
```javascript
const config = {
  serverUrl: 'wss://your-server.com',
  authToken: 'your-secret-token',
  autoReconnect: true,
  reconnectInterval: 5000
};
```

2. **CLI客户端** (`client/cli/config.py`)
```python
CONFIG = {
    'server_url': 'wss://your-server.com',
    'auth_token': 'your-secret-token',
    'auto_reconnect': True,
    'reconnect_interval': 5
}
```

## 部署指南

### 服务器部署

1. **VPS部署**
```bash
# 在您的VPS上执行
git clone https://github.com/your-username/websocket-vpn.git
cd websocket-vpn/server
pip install -r requirements.txt
python main.py
```

2. **Docker部署**
```bash
# 构建镜像
docker build -t websocket-vpn .

# 运行容器
docker run -d -p 8080:8080 websocket-vpn
```

3. **使用Docker Compose**
```bash
docker-compose up -d
```

### 客户端部署

1. **Web客户端**
```bash
cd client/web
npm run build
# 将dist目录部署到Web服务器
```

2. **CLI客户端**
```bash
cd client/cli
pip install -r requirements.txt
python client.py
```

## 使用说明

### Web客户端使用

1. 打开浏览器访问 `http://localhost:3000`
2. 在设置中配置服务器地址和认证令牌
3. 点击"连接"按钮开始使用
4. 状态栏显示连接状态和当前节点

### CLI客户端使用

```bash
# 启动客户端
python client.py

# 连接到指定节点
python client.py --node us-east-1

# 查看可用节点
python client.py --list-nodes

# 测试连接
python client.py --test
```

## 故障排除

### 常见问题

1. **连接失败**
   - 检查服务器地址和端口
   - 确认防火墙设置
   - 验证SSL证书

2. **认证失败**
   - 检查认证令牌
   - 确认服务器配置

3. **节点不可用**
   - 检查节点配置
   - 测试网络连接
   - 查看服务器日志

### 日志查看

```bash
# 服务器日志
tail -f server/logs/server.log

# 客户端日志
tail -f client/logs/client.log
```

## 安全注意事项

1. **SSL/TLS配置**
   - 使用有效的SSL证书
   - 定期更新证书
   - 启用HSTS

2. **认证机制**
   - 使用强密码
   - 定期更换令牌
   - 限制访问IP

3. **网络安全**
   - 配置防火墙规则
   - 监控异常流量
   - 定期安全审计

## 开发指南

### 添加新节点

1. 编辑 `config/nodes.json`
2. 添加节点配置
3. 重启服务器

### 自定义协议

1. 修改 `server/tunnel.py`
2. 实现新的协议处理
3. 更新客户端支持

### 扩展功能

1. 添加流量统计
2. 实现负载均衡
3. 增加更多协议支持

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 项目主页: https://github.com/your-username/websocket-vpn
- 问题反馈: https://github.com/your-username/websocket-vpn/issues
- 邮箱: your-email@example.com

---

**免责声明**: 本项目仅供学习和研究使用。请遵守当地法律法规，合理使用网络资源。