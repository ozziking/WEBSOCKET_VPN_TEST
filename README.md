# WebSocket TUN VPN 项目

这是一个基于WebSocket + TUN技术的真正VPN项目，支持系统级网络流量代理。

## 为什么需要TUN模式？

普通的WebSocket代理只能处理应用层的HTTP/HTTPS流量，无法处理：
- CLI应用程序的网络请求
- 系统级网络流量
- 非HTTP协议的应用程序
- 需要全局代理的场景

TUN模式可以：
- ✅ 拦截所有系统网络流量
- ✅ 支持CLI应用程序
- ✅ 实现真正的VPN功能
- ✅ 支持所有协议（TCP/UDP/ICMP等）

## 项目特性

- 🔒 基于WebSocket + TUN的安全隧道
- 🌍 多节点支持（美国节点）
- ⚡ 自动节点切换
- 🛡️ 流量加密
- 📱 跨平台支持（Linux/macOS/Windows）
- 🔧 易于配置和部署
- 🚀 系统级网络代理

## 技术架构

```
用户应用程序 → 系统网络栈 → TUN设备 → WebSocket隧道 → 远程服务器 → 目标网站
```

## 快速开始

### 1. 从GitHub下载项目

```bash
# 克隆项目到本地
git clone https://github.com/your-username/websocket-tun-vpn.git
cd websocket-tun-vpn

# 或者直接下载ZIP文件
wget https://github.com/your-username/websocket-tun-vpn/archive/refs/heads/main.zip
unzip main.zip
cd websocket-tun-vpn-main
```

### 2. 安装依赖

#### 系统依赖（Linux）
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
sudo apt-get install -y build-essential libssl-dev libffi-dev

# CentOS/RHEL
sudo yum install -y python3 python3-pip gcc openssl-devel libffi-devel
```

#### 系统依赖（macOS）
```bash
# 安装Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装依赖
brew install python3 openssl
```

#### Python依赖
```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# 安装Python依赖
pip install -r requirements.txt
```

### 3. 配置节点

编辑 `config/nodes.json` 文件，配置您的服务器节点：

```json
{
  "nodes": [
    {
      "id": "us-east-1",
      "name": "US East 1 (New York)",
      "host": "your-server-1.com",
      "port": 443,
      "protocol": "wss",
      "location": "US",
      "country": "United States",
      "city": "New York",
      "priority": 1,
      "enabled": true,
      "description": "Primary US East Coast node"
    }
  ]
}
```

### 4. 启动服务器

```bash
# 启动主服务器
cd server
sudo python3 main.py  # 需要sudo权限来创建TUN设备

# 或者使用Docker
docker-compose up -d
```

### 5. 启动客户端

```bash
# 启动CLI客户端
cd client/cli
sudo python3 client.py  # 需要sudo权限来创建TUN设备

# 或者启动Web管理界面
cd client/web
npm start
```

## 项目结构

```
websocket-tun-vpn/
├── server/                 # 服务器端代码
│   ├── main.py            # 主服务器
│   ├── tun_manager.py     # TUN设备管理
│   ├── websocket_tunnel.py # WebSocket隧道
│   ├── config/            # 配置文件
│   └── requirements.txt   # Python依赖
├── client/                # 客户端代码
│   ├── cli/              # 命令行客户端
│   ├── web/              # Web管理界面
│   └── tun_client.py     # TUN客户端
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
  "tun": {
    "enabled": true,
    "interface": "tun0",
    "mtu": 1500,
    "ip_range": "10.0.0.0/24"
  },
  "auth": {
    "enabled": true,
    "tokens": ["your-secret-token"]
  }
}
```

2. **TUN配置**
- `interface`: TUN接口名称
- `mtu`: 最大传输单元
- `ip_range`: 分配的IP地址范围

### 客户端配置

1. **CLI客户端** (`client/cli/config.py`)
```python
CONFIG = {
    'server_url': 'wss://your-server.com',
    'auth_token': 'your-secret-token',
    'tun_interface': 'tun0',
    'tun_ip': '10.0.0.2',
    'tun_netmask': '255.255.255.0',
    'auto_reconnect': True,
    'reconnect_interval': 5
}
```

## 部署指南

### 服务器部署

1. **VPS部署**
```bash
# 在您的VPS上执行
git clone https://github.com/your-username/websocket-tun-vpn.git
cd websocket-tun-vpn/server
sudo pip3 install -r requirements.txt
sudo python3 main.py
```

2. **Docker部署**
```bash
# 构建镜像
docker build -t websocket-tun-vpn .

# 运行容器（需要特权模式）
docker run --privileged -d -p 8080:8080 websocket-tun-vpn
```

### 客户端部署

1. **CLI客户端**
```bash
cd client/cli
sudo pip3 install -r requirements.txt
sudo python3 client.py
```

2. **Web管理界面**
```bash
cd client/web
npm install
npm start
```

## 使用说明

### CLI客户端使用

```bash
# 启动客户端
sudo python3 client.py

# 连接到指定节点
sudo python3 client.py --node us-east-1

# 查看可用节点
sudo python3 client.py --list-nodes

# 测试连接
sudo python3 client.py --test

# 查看状态
sudo python3 client.py --status
```

### 系统级代理

启动客户端后，所有系统网络流量都会通过VPN隧道：

```bash
# 测试网络连接
curl ifconfig.me  # 应该显示服务器IP

# 测试DNS
nslookup google.com  # 通过VPN解析

# 测试应用程序
ping google.com  # ICMP流量也会通过VPN
```

## 故障排除

### 常见问题

1. **权限不足**
   ```bash
   # 确保有sudo权限
   sudo python3 client.py
   ```

2. **TUN设备创建失败**
   ```bash
   # 检查内核模块
   lsmod | grep tun
   
   # 加载TUN模块
   sudo modprobe tun
   ```

3. **网络路由问题**
   ```bash
   # 检查路由表
   ip route show
   
   # 手动添加路由
   sudo ip route add default via 10.0.0.1 dev tun0
   ```

### 日志查看

```bash
# 服务器日志
tail -f server/logs/server.log

# 客户端日志
tail -f client/logs/client.log

# 系统日志
sudo journalctl -f -u websocket-vpn
```

## 安全注意事项

1. **TUN设备安全**
   - 确保TUN设备权限正确
   - 定期更新加密密钥
   - 监控异常流量

2. **网络安全**
   - 使用强密码和认证
   - 启用防火墙规则
   - 定期安全审计

3. **数据保护**
   - 加密所有传输数据
   - 不记录敏感信息
   - 定期清理日志

## 性能优化

1. **TUN性能**
   - 调整MTU大小
   - 使用内核加速
   - 优化缓冲区大小

2. **网络优化**
   - 启用TCP优化
   - 使用压缩
   - 实现流量整形

## 开发指南

### 添加新协议支持

1. 修改 `server/tun_manager.py`
2. 实现协议处理逻辑
3. 更新客户端支持

### 扩展功能

1. 添加流量统计
2. 实现负载均衡
3. 增加更多加密算法

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 项目主页: https://github.com/your-username/websocket-tun-vpn
- 问题反馈: https://github.com/your-username/websocket-tun-vpn/issues
- 邮箱: your-email@example.com

---

**免责声明**: 本项目仅供学习和研究使用。请遵守当地法律法规，合理使用网络资源。