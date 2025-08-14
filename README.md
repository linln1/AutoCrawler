# 🚀 Gmail自动发送邮件脚本

这是一个功能完整的Python脚本，可以自动向Gmail邮箱发送邮件，支持Markdown格式和多种附件类型。

## ⚡ 5分钟快速上手

### 1. 安装依赖（推荐使用uv）
```bash
# 使用uv（推荐）
uv sync

# 或者使用传统pip
pip install -r requirements.txt
```

### 2. 配置Gmail
1. 开启两步验证
2. 生成应用专用密码
3. 修改 `main.py` 中的配置

### 3. 发送第一封邮件
```bash
# 使用uv运行（推荐）
uv run main.py

# 或者直接运行
python main.py
```

## 📁 文件说明

- `main.py` - 主要的Gmail发送器类和主程序
- `pyproject.toml` - UV项目配置文件
- `requirements.txt` - 传统依赖包列表
- `README.md` - 完整使用文档

## 🔧 常见问题

### Q: 为什么使用main.py？
A: 合并了所有功能，避免文件分散，便于管理

### Q: 如何获取应用专用密码？
A: 参考下面的详细说明

### Q: 支持哪些附件格式？
A: PDF、PNG、JPG、ZIP等常见格式

## 💡 使用建议

1. 使用 `uv sync` 安装依赖
2. 使用 `uv run main.py` 运行脚本
3. 查看下面的完整文档了解所有功能
4. 参考 `pyproject.toml` 了解UV配置

---

## 功能特性

- ✅ 支持Markdown格式邮件内容
- ✅ 支持多种附件类型（PDF、PNG、ZIP等）
- ✅ 支持抄送（CC）和密送（BCC）
- ✅ 自动识别文件类型并正确处理
- ✅ 完整的错误处理和日志记录
- ✅ 支持SSL/TLS安全连接

## 安装依赖

```bash
# 推荐使用UV
uv sync

# 或者使用传统方式
pip install -r requirements.txt
```

或者手动安装：

```bash
pip install markdown typing-extensions python-dotenv
```

## 配置说明

### 1. 获取Gmail应用专用密码

**重要：** 不要使用您的Gmail登录密码，需要使用应用专用密码！

1. 登录您的Google账户
2. 进入"安全性"设置
3. 开启"两步验证"
4. 生成"应用专用密码"
5. 选择"邮件"应用，生成16位密码

### 2. 修改脚本配置

编辑 `main.py` 文件中的以下配置：

```python
EMAIL = "your_email@gmail.com"      # 您的Gmail邮箱
PASSWORD = "your_app_password"      # 应用专用密码
```

## 使用方法

### 基本用法

```python
from main import GmailSender

# 创建发送器实例
sender = GmailSender("your_email@gmail.com", "your_app_password")

# 发送简单邮件
success = sender.send_email(
    to_emails="recipient@example.com",
    subject="测试邮件",
    content="这是一封测试邮件",
    content_type="plain"
)
```

### 发送Markdown格式邮件

```python
markdown_content = """
# 标题

这是**粗体**文本和*斜体*文本。

## 列表
- 项目1
- 项目2

## 代码
```python
print("Hello World!")
```
"""

success = sender.send_email(
    to_emails="recipient@example.com",
    subject="Markdown格式邮件",
    content=markdown_content,
    content_type="markdown"
)
```

### 发送带附件的邮件

```python
success = sender.send_email(
    to_emails="recipient@example.com",
    subject="带附件的邮件",
    content="请查看附件",
    content_type="plain",
    attachments=["document.pdf", "image.png", "data.zip"]
)
```

### 发送给多个收件人

```python
success = sender.send_email(
    to_emails=["user1@example.com", "user2@example.com"],
    subject="群发邮件",
    content="这是一封群发邮件",
    content_type="plain",
    cc_emails=["cc@example.com"],
    bcc_emails=["bcc@example.com"]
)
```

## 支持的附件类型

- **图片文件**: PNG, JPG, GIF, BMP等
- **文档文件**: PDF, DOC, DOCX, TXT等
- **压缩文件**: ZIP, RAR, 7Z等
- **其他文件**: 自动识别MIME类型

## 运行示例

1. 修改配置信息
2. 运行脚本：

```bash
# 使用UV（推荐）
uv run main.py

# 或者直接运行
python main.py
```

## UV环境管理

### 基本命令

```bash
# 安装依赖
uv sync

# 运行脚本
uv run main.py

# 查看依赖树
uv tree

# 添加新依赖
uv add package_name
```

### 项目配置

项目使用 `pyproject.toml` 管理配置，包含：
- 主要依赖：markdown, python-dotenv, typing-extensions
- 开发依赖：pytest, black, flake8
- Python版本要求：>=3.10

## 注意事项

1. **安全性**: 不要在代码中硬编码密码，建议使用环境变量
2. **附件大小**: Gmail有25MB的附件大小限制
3. **发送频率**: 避免过于频繁的发送，以免被标记为垃圾邮件
4. **错误处理**: 脚本包含完整的错误处理，请查看日志输出

## 故障排除

### 常见错误

1. **认证失败**: 检查邮箱和应用专用密码是否正确
2. **附件不存在**: 确保附件文件路径正确且文件存在
3. **网络问题**: 检查网络连接和防火墙设置
4. **SSL错误**: 确保Python版本支持SSL

### 日志查看

脚本会输出详细的日志信息，包括：
- 连接状态
- 附件处理状态
- 发送结果
- 错误详情

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！ 