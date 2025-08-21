# CS论文自动化分析系统

## 这是什么？

这是一个自动化的CS论文分析工具，可以：
- 自动爬取ArXiv上的最新CS论文
- 使用AI分析论文内容
- 生成中文分析报告
- 自动发送邮件报告

**本项目使用uv进行依赖管理，确保环境一致性和快速安装。**

## 快速开始

### 1. 安装uv（如果还没有安装）
```bash
pip install uv
```

### 2. 配置系统
```bash
# 复制配置模板
cp config_template.yaml config.yaml

# 编辑配置文件，填入你的实际信息
# 主要需要配置：
# - Kimi API密钥
# - Gmail邮箱和应用专用密码
# - 其他可选配置
```

### 3. 运行系统
```bash
# 方式1：使用uv直接运行（推荐）
uv run automation_system.py interactive

# 方式2：使用启动脚本
# Windows: 双击 run.bat
# Linux/Mac: ./run.sh

# 方式3：使用Python启动脚本
python start.py
```

## 主要功能

### 🔍 论文爬虫
- 自动爬取ArXiv每日最新CS论文
- **智能语义过滤**: 使用LLM分析论文内容，准确判断相关性
- 按研究领域分类（大模型、智能体、多模态等）
- 自动下载PDF文件

### 🤖 AI分析
- 使用Kimi API分析论文内容
- **LLM语义过滤**: 避免硬件、芯片设计等不相关论文
- 回答6个关键问题：
  1. 论文主要内容
  2. 解决的问题
  3. 相关研究
  4. 解决方案
  5. 实验结果
  6. 未来方向

### 📊 报告生成
- 自动生成Markdown格式报告
- 按类别分类统计
- 包含Kimi对话链接

### 📧 邮件发送
- 自动发送分析报告
- 支持Markdown格式
- 可添加PDF附件

### ⏰ 定时任务
- 支持每日自动运行
- 可自定义运行时间
- 失败自动重试

## 使用方法

### 交互式菜单
```bash
uv run automation_system.py interactive
```
选择对应功能：
1. 运行一次完整流程
2. 启动定时任务
3. 仅爬取论文
4. 仅分析论文
5. 仅生成报告
6. 检查系统状态
7. 查看配置信息
8. 查看使用示例

### 命令行模式
```bash
# 运行一次完整流程
uv run automation_system.py run

# 启动定时任务
uv run automation_system.py schedule

# 仅爬取论文
uv run automation_system.py crawl

# 仅分析论文
uv run automation_system.py analyze

# 仅生成报告
uv run automation_system.py report

# 查看帮助
uv run automation_system.py help
```

### 依赖管理
```bash
# 安装/更新依赖
uv sync

# 添加新依赖
uv add package_name

# 添加开发依赖
uv add --dev package_name

# 查看依赖树
uv tree
```

## 配置文件

### 配置模板
系统提供`config_template.yaml`作为配置模板，包含所有可配置项但不包含敏感信息。

### 实际配置
复制模板为`config.yaml`并填入你的实际信息：
- **API密钥**: Kimi、OpenAI等API的密钥
- **邮箱配置**: Gmail邮箱和应用专用密码
- **爬虫设置**: 运行时间、请求间隔、关键词等
- **LLM设置**: 模型参数、分析问题等
- **邮件设置**: 发送时间、模板等
- **定时任务**: 运行模式、时间设置等

### 安全说明
- `config.yaml`已添加到`.gitignore`，不会被上传到git
- 请妥善保管你的API密钥和邮箱密码
- 建议使用应用专用密码而不是邮箱登录密码

## 输出结果

分析结果保存在以下位置：
- `./YYMMDD/paper_analysis/` - 论文分析结果
- `./YYMMDD/reports/` - 生成的报告
- `./YYMMDD/pdf_downloads/` - 下载的PDF文件

## 注意事项

1. **API限制**: 需要有效的Kimi API密钥
2. **网络要求**: 需要稳定的网络连接
3. **存储空间**: PDF文件会占用本地存储
4. **处理时间**: 每篇论文分析需要时间

## 故障排除

### 常见问题
1. **模块导入失败**: 运行`uv sync`
2. **API调用失败**: 检查API密钥和网络连接
3. **邮件发送失败**: 检查Gmail配置和应用密码
4. **PDF下载失败**: 检查网络连接和存储空间

### 查看日志
- `automation_system.log` - 系统运行日志
- `cs_crawler.log` - 爬虫运行日志

## 技术特点

- **智能缓存**: 使用Kimi API的上下文缓存，避免重复传输
- **多轮对话**: 问题之间相互关联，形成完整分析
- **智能链接**: 为每篇论文生成Kimi对话链接，支持继续深入讨论
- **自动分类**: 按研究领域自动分类论文
- **邮件集成**: 支持Gmail自动发送，包含完整报告
- **uv管理**: 使用现代Python包管理器，确保依赖一致性

## 系统架构

```
论文爬取 → AI分析 → 报告生成 → 邮件发送
    ↓         ↓         ↓         ↓
ArXiv API  Kimi API  Markdown   Gmail SMTP
```

## 支持的研究领域

- **大模型**: LLM、GPT、BERT等
- **智能体**: 多智能体、自主智能体等
- **多模态**: 视觉语言、图像文本等
- **强化学习**: RL、PPO、DPO等
- **微调**: LoRA、QLoRA、Adapter等
- **检索增强**: RAG、知识检索等

## 更新日志

- **v1.0**: 基础功能实现
- **v1.1**: 添加交互式菜单
- **v1.2**: 集成邮件发送功能
- **v1.3**: 优化代码结构，合并功能模块
- **v1.4**: 配置安全化，支持模板配置
- **v1.5**: 完全使用uv管理项目，增强依赖管理

## 技术支持

如遇问题，请：
1. 检查配置文件设置
2. 查看日志文件
3. 确认API密钥有效
4. 检查网络连接状态
5. 运行`uv sync`确保依赖正确安装 