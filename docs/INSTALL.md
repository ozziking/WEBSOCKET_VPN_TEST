# WebSocket TUN VPN 安装指南

## 为什么选择TUN模式？

您提到的Claude Code在macOS上需要科学上网的问题，正是普通代理无法解决的。TUN模式的优势：

### 普通代理的局限性
- ❌ 只能处理HTTP/HTTPS流量
- ❌ 无法处理CLI应用程序的网络请求
- ❌ 无法处理系统级网络流量
- ❌ 无法处理非HTTP协议的应用程序

### TUN模式的优势
- ✅ 拦截所有系统网络流量
- ✅ 支持CLI应用程序（如Claude Code）
- ✅ 实现真正的VPN功能
- ✅ 支持所有协议（TCP/UDP/ICMP等）
- ✅ 系统级全局代理

## 系统要求

### Linux
- Ubuntu 18.04+ / Debian 9+ / CentOS 7+
- Python 3.8+
- 内核支持TUN模块
- 管理员权限（sudo）

### macOS
- macOS 10.15+
- Python 3.8+
- Homebrew
- 管理员权限（sudo）

### Windows
- Windows 10+
- Python 3.8+
- WSL2（推荐）或管理员权限

## 快速安装

### 1. 下载项目

```bash
# 克隆项目
git clone https://github.com/your-username/websocket-tun-vpn.git
cd websocket-tun-vpn

# 或者下载ZIP
wget https://github.com/your-username/websocket-tun-vpn/archive/refs/heads/main.zip
unzip main.zip
cd websocket-tun-vpn-main
```

### 2. 自动安装（推荐）

```bash
# 运行自动安装脚本
sudo ./scripts/deploy.sh deploy
```

### 3. 手动安装

#### Linux (Ubuntu/Debian)

```bash
# 安装系统依赖
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv build-essential libssl-dev libffi-dev

# 加载TUN模块
sudo modprobe tun

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装Python依赖
pip install --upgrade pip
pip install -r server/requirements.txt
pip install -r client/cli/requirements.txt

# 生成SSL证书
mkdir -p certs
openssl genrsa -out certs/server.key 2048
openssl req -new -x509 -key certs/server.key -out certs/server.crt -days 365 -subj "/C=US/ST=CA/L=San Francisco/O=WebSocket VPN/CN=localhost"
```

#### macOS

```bash
# 安装Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装依赖
brew install python3 openssl

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装Python依赖
pip install --upgrade pip
pip install -r server/requirements.txt
pip install -r client/cli/requirements.txt

# 生成SSL证书
mkdir -p certs
openssl genrsa -out certs/server.key 2048
openssl req -new -x509 -key certs/server.key -out certs/server.crt -days 365 -subj "/C=US/ST=CA/L=San Francisco/O=WebSocket VPN/CN=localhost"
```

## 配置说明

### 1. 服务器配置

编辑 `config/settings.json`：

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "ssl": {
      "enabled": true,
      "cert": "certs/server.crt",
      "key": "certs/server.key"
    },
    "tun": {
      "enabled": true,
      "interface": "tun0",
      "mtu": 1500,
      "ip_range": "10.0.0.0/24"
    },
    "auth": {
      "enabled": true,
      "tokens": ["your-secret-token-here"]
    }
  }
}
```

### 2. 节点配置

编辑 `config/nodes.json`，添加您的服务器：

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
      "enabled": true
    }
  ]
}
```

## 使用方法

### 启动服务器

```bash
# 使用自动脚本
sudo ./scripts/deploy.sh start

# 或手动启动
sudo python3 server/main.py
```

### 启动客户端

```bash
# 启动VPN客户端
sudo python3 client/cli/client.py

# 连接到指定节点
sudo python3 client/cli/client.py --node us-east-1

# 查看可用节点
sudo python3 client/cli/client.py --list-nodes

# 测试连接
sudo python3 client/cli/client.py --test

# 查看状态
sudo python3 client/cli/client.py --status
```

### 验证连接

启动客户端后，所有系统网络流量都会通过VPN：

```bash
# 测试网络连接
curl ifconfig.me  # 应该显示服务器IP

# 测试DNS
nslookup google.com  # 通过VPN解析

# 测试应用程序
ping google.com  # ICMP流量也会通过VPN

# 测试CLI应用程序
# 现在Claude Code等CLI应用也能正常使用
```

## 故障排除

### 常见问题

#### 1. 权限不足
```bash
# 确保使用sudo运行
sudo python3 client/cli/client.py
```

#### 2. TUN设备创建失败
```bash
# 检查TUN模块
lsmod | grep tun

# 加载TUN模块
sudo modprobe tun
```

#### 3. 网络路由问题
```bash
# 检查路由表
ip route show

# 手动添加路由
sudo ip route add default via 10.0.0.1 dev tun0
```

#### 4. SSL证书问题
```bash
# 重新生成证书
openssl genrsa -out certs/server.key 2048
openssl req -new -x509 -key certs/server.key -out certs/server.crt -days 365 -subj "/C=US/ST=CA/L=San Francisco/O=WebSocket VPN/CN=localhost"
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

## 性能优化

### 1. TUN性能优化

```bash
# 调整MTU大小
sudo ip link set tun0 mtu 1400

# 启用TCP优化
echo 'net.core.rmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
echo 'net.core.wmem_max = 16777216' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 2. 网络优化

```bash
# 启用BBR拥塞控制
echo 'net.core.default_qdisc = fq' | sudo tee -a /etc/sysctl.conf
echo 'net.ipv4.tcp_congestion_control = bbr' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## 安全注意事项

### 1. TUN设备安全
- 确保TUN设备权限正确
- 定期更新加密密钥
- 监控异常流量

### 2. 网络安全
- 使用强密码和认证
- 启用防火墙规则
- 定期安全审计

### 3. 数据保护
- 加密所有传输数据
- 不记录敏感信息
- 定期清理日志

## 高级配置

### 1. 多节点配置

```json
{
  "nodes": [
    {
      "id": "us-east-1",
      "name": "US East 1",
      "host": "us-east-1.your-vpn.com",
      "port": 443,
      "protocol": "wss",
      "priority": 1
    },
    {
      "id": "us-west-1",
      "name": "US West 1", 
      "host": "us-west-1.your-vpn.com",
      "port": 443,
      "protocol": "wss",
      "priority": 2
    }
  ]
}
```

### 2. 自定义路由

```bash
# 只代理特定流量
sudo ip route add 8.8.8.8/32 via 10.0.0.1 dev tun0

# 排除本地网络
sudo ip route add 192.168.1.0/24 dev eth0
```

### 3. DNS配置

```bash
# 使用自定义DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf
```

## 监控和维护

### 1. 服务管理

```bash
# 启动服务
sudo ./scripts/deploy.sh start

# 停止服务
sudo ./scripts/deploy.sh stop

# 查看状态
sudo ./scripts/deploy.sh status
```

### 2. 日志管理

```bash
# 查看实时日志
tail -f logs/server.log

# 清理旧日志
find logs/ -name "*.log" -mtime +7 -delete
```

### 3. 性能监控

```bash
# 查看网络统计
ip -s link show tun0

# 查看连接状态
ss -tuln | grep 8080
```

## 支持

如果遇到问题，请：

1. 查看日志文件
2. 检查系统要求
3. 验证网络配置
4. 提交Issue到GitHub

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](../LICENSE) 文件。