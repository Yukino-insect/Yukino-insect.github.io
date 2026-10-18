+++
date = '2025-12-31T22:13:57+08:00'
draft = false
title = 'SSH'
+++

SSH，全称 Secure Shell，是一种用于远程登录和安全通信的协议。

它常用于：

1. 登录 Linux 服务器。
2. 执行远程命令。
3. 传输文件。
4. 做端口转发。
5. 自动化部署。

SSH 的核心价值是：**在不可信网络中建立一条加密通道，保护登录凭证和传输内容。**

## 一、SSH 解决什么问题

如果直接用明文协议远程登录，用户名、密码、命令和返回结果都可能被中间网络看到。

SSH 会在客户端和服务端之间建立加密连接，避免：

1. 密码明文泄露。
2. 命令内容被窃听。
3. 传输文件被篡改。
4. 中间人伪装服务器。

默认端口是：

```text
22
```

## 二、SSH 登录方式

常见登录方式有两种：

1. 密码登录。
2. 密钥登录。

生产环境更推荐密钥登录，并尽量关闭密码登录，以降低暴力破解风险。

## 三、密钥登录原理

密钥登录依赖一对密钥：

| 文件 | 存放位置 | 作用 |
| --- | --- | --- |
| 私钥 | 客户端 | 必须保密，用来证明身份 |
| 公钥 | 服务端 | 放入 `authorized_keys`，用来验证客户端 |

常见生成方式：

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

生成后通常会得到：

```text
~/.ssh/id_ed25519
~/.ssh/id_ed25519.pub
```

把公钥内容追加到服务器目标用户的：

```text
~/.ssh/authorized_keys
```

之后登录时，服务端会验证客户端是否持有与该公钥匹配的私钥。

私钥不会被直接发送到网络中。服务端会发起挑战，客户端用私钥签名，服务端用公钥验证签名。

## 四、第一次连接为什么会提示 fingerprint

第一次连接服务器时，SSH 客户端通常会提示：

```text
The authenticity of host ... can't be established.
```

这是在让你确认服务器主机公钥指纹。

确认后，客户端会把服务器信息写入：

```text
~/.ssh/known_hosts
```

以后再次连接时，如果服务器主机密钥变化，SSH 会警告。这可以防止中间人伪装服务器。

注意：这里的服务器主机密钥和你自己的登录密钥不是同一个东西。

## 五、常见文件

客户端常见文件：

```text
~/.ssh/id_ed25519
~/.ssh/id_ed25519.pub
~/.ssh/config
~/.ssh/known_hosts
```

服务端常见文件：

```text
~/.ssh/authorized_keys
/etc/ssh/sshd_config
```

其中：

1. `authorized_keys` 保存允许登录当前用户的公钥。
2. `known_hosts` 保存客户端信任过的服务器主机公钥。
3. `sshd_config` 配置 SSH 服务端行为。

## 六、文件权限

Linux 上权限太宽可能导致 SSH 拒绝使用密钥。

常见权限：

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 600 ~/.ssh/authorized_keys
```

私钥一定不能上传到代码仓库，也不要通过聊天工具随意传输。

## 七、SSH config 简化登录

可以在客户端配置：

```text
Host dev-server
    HostName 192.168.1.10
    User deploy
    Port 22
    IdentityFile ~/.ssh/id_ed25519
```

之后登录只需要：

```bash
ssh dev-server
```

## 八、常用命令

### 1. 远程登录

```bash
ssh user@server_ip
```

### 2. 执行远程命令

```bash
ssh user@server_ip "systemctl status nginx"
```

### 3. 复制文件到服务器

```bash
scp app.jar user@server_ip:/opt/app/app.jar
```

### 4. 从服务器复制文件

```bash
scp user@server_ip:/var/log/app.log ./app.log
```

### 5. 本地端口转发

把本机 `3307` 转发到远程服务器能访问的 MySQL：

```bash
ssh -L 3307:127.0.0.1:3306 user@server_ip
```

访问本机：

```text
127.0.0.1:3307
```

就相当于访问远程服务器上的：

```text
127.0.0.1:3306
```

### 6. 远程端口转发

把本地服务暴露到远程服务器端口：

```bash
ssh -R 9000:127.0.0.1:8080 user@server_ip
```

这就是一种简单的反向隧道能力。

## 九、自动化部署示例

CI/CD 中可以通过 SSH 上传文件并执行部署命令。

Python 示例使用 `paramiko`：

```python
import paramiko

host = "192.168.1.10"
user = "deploy"
key_path = r"C:\Users\you\.ssh\id_ed25519"

key = paramiko.Ed25519Key.from_private_key_file(key_path)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.load_system_host_keys()
client.connect(hostname=host, username=user, pkey=key)

stdin, stdout, stderr = client.exec_command("systemctl restart my-app")

print(stdout.read().decode())
print(stderr.read().decode())

client.close()
```

实际生产中更常用 Jenkins、GitHub Actions、GitLab CI、Ansible 等工具管理 SSH 凭证和部署流程。

## 十、安全建议

1. 使用密钥登录，避免长期开放密码登录。
2. 私钥设置 passphrase。
3. 禁止 root 直接登录。
4. 限制允许登录的用户。
5. 对公网 SSH 配置防火墙白名单。
6. 定期轮换密钥。
7. 部署任务使用权限最小化账号。

`sshd_config` 中常见配置：

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

修改后需要重启 SSH 服务。操作前要确认还有可用登录方式，否则把自己锁在门外就不太体面了。

## 十一、一句话总结

SSH 是远程登录和安全通信的基础协议。密钥登录不是“没有认证”，而是用私钥签名替代密码输入；私钥一旦泄露，就等同于登录凭证泄露。
