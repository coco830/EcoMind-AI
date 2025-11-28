# GitHub 认证配置指南

本文档说明如何配置 GitHub 认证，避免每次推送都需要输入 Token。

## 方法一：使用 SSH Key（推荐）

### 1. 生成 SSH 密钥

```bash
ssh-keygen -t ed25519 -C "yangkaidi1129@gmail.com"
```

一路回车使用默认设置（或设置密码保护）。

### 2. 查看公钥

```bash
cat ~/.ssh/id_ed25519.pub
```

### 3. 添加到 GitHub

1. 登录 GitHub
2. 点击右上角头像 → Settings
3. 左侧菜单选择 SSH and GPG keys
4. 点击 New SSH key
5. 粘贴公钥内容，保存

### 4. 修改仓库 remote 为 SSH

```bash
cd /home/candy/project/EcoMind-AI
git remote set-url origin git@github.com:coco830/EcoMind-AI.git
```

### 5. 测试连接

```bash
ssh -T git@github.com
```

成功后会显示：`Hi coco830! You've successfully authenticated`

---

## 方法二：使用 Git Credential Manager

### 1. 安装 Git Credential Manager

```bash
# Ubuntu/Debian
sudo apt install git-credential-manager

# 或者手动安装
wget https://github.com/git-ecosystem/git-credential-manager/releases/latest/download/gcm-linux_amd64.deb
sudo dpkg -i gcm-linux_amd64.deb
```

### 2. 配置

```bash
git config --global credential.helper manager
git config --global credential.credentialStore secretservice
```

### 3. 首次推送

第一次推送时会弹出认证窗口，之后会自动记住。

---

## 方法三：使用 GitHub CLI（gh）

### 1. 安装 gh

```bash
# Ubuntu/Debian
sudo apt install gh

# 或
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh
```

### 2. 登录认证

```bash
gh auth login
```

按提示选择：
- GitHub.com
- HTTPS
- 使用浏览器登录

### 3. 配置 git 使用 gh 认证

```bash
gh auth setup-git
```

完成后，所有 git 操作都会自动使用 gh 的认证。

---

## 方法四：使用 Personal Access Token + 缓存

### 1. 创建 Token

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. 勾选 `repo` 权限
4. 生成并复制 Token

### 2. 配置 Git 缓存

```bash
# 缓存 1 小时（3600 秒）
git config --global credential.helper 'cache --timeout=3600'

# 或永久存储（注意安全风险）
git config --global credential.helper store
```

### 3. 首次推送

```bash
git push -u origin 001-ecomind-mvp
```

输入用户名和 Token，之后会被缓存。

---

## 当前仓库配置

```bash
# 查看当前配置
git remote -v

# 切换到 SSH（推荐）
git remote set-url origin git@github.com:coco830/EcoMind-AI.git

# 切换回 HTTPS
git remote set-url origin https://github.com/coco830/EcoMind-AI.git
```

## 推送命令

```bash
# 首次推送并设置上游分支
git push -u origin 001-ecomind-mvp

# 之后推送
git push
```
