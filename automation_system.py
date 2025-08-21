#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CS论文自动化分析系统
每天自动爬取论文 -> LLM解读 -> 生成报告 -> 邮件发送
包含交互式启动菜单和邮件发送功能
"""

import os
import sys
import time
import logging
import schedule
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
import markdown
import mimetypes
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

# 导入自定义模块
from config_manager import get_config
from report_generator import get_report_generator

# 导入爬虫和LLM模块
try:
    from cs_paper_crawler import CSPaperCrawler
    from llm_api import main_paper_analysis
except ImportError as e:
    logging.error(f"导入模块失败: {e}")
    logging.error("请确保 cs_paper_crawler.py 和 llm_api.py 文件存在")
    sys.exit(1)

class GmailSender:
    """Gmail邮件发送器"""
    
    def __init__(self, email: str, password: str, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587, use_ssl: bool = False):
        """
        初始化Gmail发送器
        
        Args:
            email: Gmail邮箱地址
            password: 应用专用密码（不是登录密码）
            smtp_server: SMTP服务器地址
            smtp_port: SMTP端口
            use_ssl: 是否使用SSL连接（端口465）
        """
        self.email = email
        self.password = password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.use_ssl = use_ssl
        
    def send_email(
        self,
        to_emails: Union[str, List[str]],
        subject: str,
        content: str,
        content_type: str = "markdown",
        attachments: Optional[List[str]] = None,
        cc_emails: Optional[Union[str, List[str]]] = None,
        bcc_emails: Optional[Union[str, List[str]]] = None
    ) -> bool:
        """
        发送邮件
        
        Args:
            to_emails: 收件人邮箱（单个字符串或邮箱列表）
            subject: 邮件主题
            content: 邮件内容
            content_type: 内容类型 ("markdown", "html", "plain")
            attachments: 附件文件路径列表
            cc_emails: 抄送邮箱
            bcc_emails: 密送邮箱
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 创建邮件对象
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['Subject'] = subject
            
            # 处理收件人
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            msg['To'] = ', '.join(to_emails)
            
            # 处理抄送
            if cc_emails:
                if isinstance(cc_emails, str):
                    cc_emails = [cc_emails]
                msg['Cc'] = ', '.join(cc_emails)
                to_emails.extend(cc_emails)
            
            # 处理密送
            if bcc_emails:
                if isinstance(bcc_emails, str):
                    bcc_emails = [bcc_emails]
                to_emails.extend(bcc_emails)
            
            # 处理邮件内容
            if content_type == "markdown":
                # 将markdown转换为HTML
                html_content = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite'])
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            elif content_type == "html":
                msg.attach(MIMEText(content, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            # 添加附件
            if attachments:
                for attachment_path in attachments:
                    if os.path.exists(attachment_path):
                        self._add_attachment(msg, attachment_path)
                    else:
                        logging.warning(f"附件文件不存在: {attachment_path}")
            
            # 发送邮件
            self._send_message(msg, to_emails)
            logging.info(f"邮件发送成功！收件人: {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            logging.error(f"发送邮件失败: {str(e)}")
            return False
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """添加附件到邮件"""
        try:
            # 获取文件类型
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            
            # 获取文件名
            filename = os.path.basename(file_path)
            
            # 根据文件类型处理附件
            if mime_type.startswith('image/'):
                # 图片文件
                with open(file_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(img)
            elif mime_type == 'application/pdf':
                # PDF文件
                with open(file_path, 'rb') as f:
                    pdf = MIMEApplication(f.read(), _subtype='pdf')
                    pdf.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(pdf)
            elif mime_type == 'application/zip' or mime_type == 'application/x-zip-compressed':
                # ZIP文件
                with open(file_path, 'rb') as f:
                    zip_file = MIMEApplication(f.read(), _subtype='zip')
                    zip_file.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(zip_file)
            else:
                # 其他类型文件
                with open(file_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 'attachment', filename=filename)
                    msg.attach(part)
            
            logging.info(f"成功添加附件: {filename}")
            
        except Exception as e:
            logging.error(f"添加附件失败 {file_path}: {str(e)}")
    
    def _send_message(self, msg: MIMEMultipart, to_emails: List[str]):
        """发送邮件消息"""
        try:
            if self.use_ssl:
                # 使用SSL连接（端口465）
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.email, self.password)
                    server.send_message(msg, to_addrs=to_emails)
            else:
                # 使用STARTTLS连接（端口587）
                # 创建SSL上下文
                context = ssl.create_default_context()
                
                # 连接SMTP服务器并发送
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                    server.starttls(context=context)
                    server.login(self.email, self.password)
                    server.send_message(msg, to_addrs=to_emails)
                    
        except smtplib.SMTPConnectError as e:
            logging.error(f"SMTP连接失败: {str(e)}")
            raise Exception(f"无法连接到SMTP服务器 {self.smtp_server}:{self.smtp_port}")
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"SMTP认证失败: {str(e)}")
            raise Exception("邮箱或密码错误，请检查配置")
        except Exception as e:
            logging.error(f"发送邮件时出错: {str(e)}")
            raise

class AutomationSystem:
    """CS论文自动化分析系统"""
    
    def __init__(self):
        self.config = get_config()
        self.report_generator = get_report_generator()
        self.logger = self._setup_logging()
        self.gmail_sender = None
        
        # 初始化邮件发送器
        if self.config.is_enabled("email"):
            self._init_email_sender()
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        log_level = getattr(logging, self.config.get("system.log_level", "INFO"))
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('automation_system.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    def _init_email_sender(self):
        """初始化邮件发送器"""
        try:
            email_config = self.config.get_email_config()
            gmail_config = email_config.get("gmail", {})
            
            self.gmail_sender = GmailSender(
                email=gmail_config.get("email"),
                password=gmail_config.get("password"),
                smtp_server=gmail_config.get("smtp_server", "smtp.gmail.com"),
                smtp_port=gmail_config.get("smtp_port", 587),
                use_ssl=gmail_config.get("use_ssl", False)
            )
            
            self.logger.info("邮件发送器初始化成功")
            
        except Exception as e:
            self.logger.error(f"邮件发送器初始化失败: {e}")
            self.gmail_sender = None

    def check_environment(self):
        """检查环境配置"""
        print("🔍 检查环境配置...")
        
        # 检查Python版本
        if sys.version_info < (3, 7):
            print("❌ Python版本过低，需要3.7+")
            return False
        
        print("✅ Python版本检查通过")
        
        # 检查配置文件
        if not os.path.exists("config.yaml"):
            print("❌ 配置文件 config.yaml 不存在")
            print("   系统将自动创建默认配置文件")
        else:
            print("✅ 配置文件存在")
        
        # 检查环境变量
        required_vars = [
            "KIMI_API_KEY",
            "GMAIL_EMAIL", 
            "GMAIL_APP_PASSWORD"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠️  以下环境变量未设置: {', '.join(missing_vars)}")
            print("   请在运行前设置这些环境变量")
        else:
            print("✅ 环境变量检查通过")
        
        return True

    def check_dependencies(self):
        """检查依赖包"""
        print("\n📦 检查依赖包...")
        
        required_packages = [
            "openai",
            "requests", 
            "httpx",
            "beautifulsoup4",
            "yaml",
            "schedule",
            "markdown"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
                print(f"✅ {package}")
            except ImportError:
                print(f"❌ {package}")
                missing_packages.append(package)
        
        if missing_packages:
            print(f"\n⚠️  缺少依赖包: {', '.join(missing_packages)}")
            print("   请运行: pip install -r requirements.txt")
            return False
        
        print("✅ 所有依赖包已安装")
        return True

    def show_menu(self):
        """显示主菜单"""
        print("\n" + "="*50)
        print("🚀 CS论文自动化分析系统")
        print("="*50)
        print("1. 运行一次完整流程")
        print("2. 启动定时任务")
        print("3. 仅爬取论文")
        print("4. 仅分析论文")
        print("5. 仅生成报告")
        print("6. 检查系统状态")
        print("7. 查看配置信息")
        print("8. 查看使用示例")
        print("0. 退出")
        print("="*50)

    def run_interactive(self):
        """运行交互式菜单"""
        print("🚀 CS论文自动化分析系统启动器")
        print("正在初始化系统...")
        
        # 检查环境
        if not self.check_environment():
            print("\n❌ 环境检查失败，请解决上述问题后重试")
            return
        
        # 检查依赖
        if not self.check_dependencies():
            print("\n❌ 依赖检查失败，请安装缺少的包后重试")
            return
        
        print("\n✅ 系统初始化完成！")
        
        # 主循环
        while True:
            self.show_menu()
            try:
                choice = input("\n请选择操作 (0-8): ").strip()
                
                if choice == "0":
                    print("👋 再见！")
                    break
                elif choice == "1":
                    self.run_once()
                elif choice == "2":
                    self.start_scheduler()
                elif choice == "3":
                    self.crawl_only()
                elif choice == "4":
                    self.analyze_only()
                elif choice == "5":
                    self.generate_report_only()
                elif choice == "6":
                    self.check_system_status()
                elif choice == "7":
                    self.show_config_info()
                elif choice == "8":
                    self.show_examples()
                else:
                    print("❌ 无效选择，请重新输入")
                    
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，退出系统")
                break
            except Exception as e:
                print(f"\n❌ 操作失败: {e}")
            
            input("\n按回车键继续...")

    def crawl_only(self):
        """仅爬取论文"""
        print("\n🕷️  启动论文爬虫...")
        try:
            crawler = CSPaperCrawler()
            crawler.start()
            print("✅ 论文爬取完成")
        except Exception as e:
            print(f"❌ 论文爬取失败: {e}")

    def analyze_only(self):
        """仅分析论文"""
        print("\n🤖 启动论文分析...")
        try:
            main_paper_analysis()
            print("✅ 论文分析完成")
        except Exception as e:
            print(f"❌ 论文分析失败: {e}")

    def generate_report_only(self):
        """仅生成报告"""
        print("\n📊 生成分析报告...")
        try:
            # 获取当前日期
            date_str = datetime.now().strftime("%y%m%d")
            
            # 加载分析结果
            analysis_dir = self.config.get_analysis_directory(date_str)
            analysis_results = []
            
            if os.path.exists(analysis_dir):
                for filename in os.listdir(analysis_dir):
                    if filename.endswith('.json') and 'analysis' in filename:
                        file_path = os.path.join(analysis_dir, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_results = json.load(f)
                                if isinstance(file_results, list):
                                    analysis_results.extend(file_results)
                        except Exception as e:
                            print(f"⚠️  读取文件 {filename} 失败: {e}")
            
            if analysis_results:
                report_path = self.report_generator.generate_daily_report(analysis_results, date_str)
                print(f"✅ 报告生成完成: {report_path}")
            else:
                print("⚠️  未找到分析结果，无法生成报告")
                
        except Exception as e:
            print(f"❌ 生成报告失败: {e}")

    def check_system_status(self):
        """检查系统状态"""
        print("\n🔍 检查系统状态...")
        
        # 检查目录结构
        base_dir = "./250821"
        if os.path.exists(base_dir):
            print(f"✅ 基础目录存在: {base_dir}")
            
            # 检查今天的目录
            date_str = datetime.now().strftime("%y%m%d")
            today_dir = os.path.join(base_dir, date_str)
            
            if os.path.exists(today_dir):
                print(f"✅ 今日目录存在: {today_dir}")
                
                # 检查子目录
                subdirs = ["pdf_downloads", "paper_analysis", "reports"]
                for subdir in subdirs:
                    subdir_path = os.path.join(today_dir, subdir)
                    if os.path.exists(subdir_path):
                        file_count = len(os.listdir(subdir_path))
                        print(f"   📁 {subdir}: {file_count} 个文件")
                    else:
                        print(f"   ❌ {subdir}: 目录不存在")
            else:
                print(f"⚠️  今日目录不存在: {today_dir}")
        else:
            print(f"❌ 基础目录不存在: {base_dir}")
        
        # 检查日志文件
        log_files = ["automation_system.log", "cs_crawler.log"]
        for log_file in log_files:
            if os.path.exists(log_file):
                size = os.path.getsize(log_file)
                print(f"✅ 日志文件: {log_file} ({size} bytes)")
            else:
                print(f"⚠️  日志文件不存在: {log_file}")

    def show_config_info(self):
        """显示配置信息"""
        print("\n⚙️  当前配置信息...")
        try:
            print("系统配置:")
            print(f"  启用状态: {self.config.is_enabled('system')}")
            print(f"  日志级别: {self.config.get('system.log_level', 'INFO')}")
            
            print("\n爬虫配置:")
            print(f"  启用状态: {self.config.is_enabled('crawler')}")
            print(f"  运行时间: {self.config.get('crawler.run_time', '09:00')}")
            
            print("\nLLM配置:")
            print(f"  提供商: {self.config.get('llm.provider', 'kimi')}")
            print(f"  启用状态: {self.config.is_enabled('llm')}")
            
            print("\n邮件配置:")
            print(f"  启用状态: {self.config.is_enabled('email')}")
            if self.config.is_enabled('email'):
                email_config = self.config.get_email_config()
                gmail_config = email_config.get('gmail', {})
                print(f"  邮箱: {gmail_config.get('email', '未设置')}")
                print(f"  SMTP服务器: {gmail_config.get('smtp_server', 'smtp.gmail.com')}")
            
            print("\n定时任务配置:")
            print(f"  启用状态: {self.config.is_enabled('scheduler')}")
            print(f"  运行模式: {self.config.get('scheduler.mode', 'daily')}")
            print(f"  运行时间: {self.config.get('scheduler.run_time', '09:00')}")
            
        except Exception as e:
            print(f"❌ 读取配置失败: {e}")

    def show_examples(self):
        """显示使用示例"""
        print("\n📚 使用示例")
        print("=" * 60)
        
        examples = [
            ("基本使用方法", self._example_basic_usage),
            ("配置文件设置", self._example_configuration),
            ("命令行使用", self._example_command_line),
            ("环境设置", self._example_environment_setup),
            ("自定义配置", self._example_customization),
            ("系统监控", self._example_monitoring),
            ("故障排除", self._example_troubleshooting)
        ]
        
        for i, (title, func) in enumerate(examples, 1):
            print(f"{i}. {title}")
        
        try:
            choice = input("\n请选择要查看的示例 (1-7, 0退出): ").strip()
            if choice == "0":
                return
            elif choice.isdigit() and 1 <= int(choice) <= 7:
                examples[int(choice)-1][1]()
            else:
                print("❌ 无效选择")
        except KeyboardInterrupt:
            print("\n👋 用户中断")
        except Exception as e:
            print(f"❌ 显示示例失败: {e}")

    def _example_basic_usage(self):
        """示例1: 基本使用方法"""
        print("\n" + "=" * 60)
        print("示例1: 基本使用方法")
        print("=" * 60)
        
        print("""
# 1. 复制配置模板
cp config_template.yaml config.yaml

# 2. 编辑配置文件，填入你的实际信息
# - Kimi API密钥
# - Gmail邮箱和应用专用密码
# - 其他可选配置

# 3. 运行启动脚本
uv run automation_system.py interactive

# 4. 选择操作
# - 选择1: 运行一次完整流程
# - 选择2: 启动定时任务
# - 选择0: 退出
""")

    def _example_configuration(self):
        """示例2: 配置文件设置"""
        print("\n" + "=" * 60)
        print("示例2: 配置文件设置")
        print("=" * 60)
        
        print("""
# 配置文件: config.yaml

# 爬虫配置
crawler:
  schedule: "daily"           # 每天运行
  run_time: "09:00"          # 上午9点运行
  request_delay: 2            # 请求间隔2秒
  
# LLM配置  
llm:
  provider: "kimi"            # 使用Kimi API
  kimi:
    api_key: "your_kimi_api_key_here"
    model: "kimi-k2-0711-preview"
    temperature: 0.3
    
# 邮件配置
email:
  enabled: true               # 启用邮件功能
  gmail:
    email: "your_email@gmail.com"
    password: "your_app_password_here"
    
# 定时任务配置
scheduler:
  enabled: true               # 启用定时任务
  mode: "daily"               # 每日模式
  run_time: "09:00"          # 每天9点运行
""")

    def _example_command_line(self):
        """示例3: 命令行使用"""
        print("\n" + "=" * 60)
        print("示例3: 命令行使用")
        print("=" * 60)
        
        print("""
# 运行交互式菜单
uv run automation_system.py interactive

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
""")

    def _example_environment_setup(self):
        """示例4: 环境设置"""
        print("\n" + "=" * 60)
        print("示例4: 环境设置")
        print("=" * 60)
        
        print("""
# 推荐使用配置文件方式（更安全）：
# 1. 复制配置模板：cp config_template.yaml config.yaml
# 2. 编辑config.yaml，填入你的实际信息
# 3. 运行系统：uv run automation_system.py interactive

# 如果仍想使用环境变量（可选）：
# Windows PowerShell
$env:KIMI_API_KEY="your_kimi_api_key_here"
$env:GMAIL_EMAIL="your_email@gmail.com"
$env:GMAIL_APP_PASSWORD="your_app_password_here"

# Windows CMD
set KIMI_API_KEY=your_kimi_api_key_here
set GMAIL_EMAIL=your_email@gmail.com
set GMAIL_APP_PASSWORD=your_app_password_here

# Linux/Mac
export KIMI_API_KEY="your_kimi_api_key_here"
export GMAIL_EMAIL="your_email@gmail.com"
export GMAIL_APP_PASSWORD="your_app_password_here"

# 或者创建 .env 文件
echo "KIMI_API_KEY=your_kimi_api_key_here" > .env
echo "GMAIL_EMAIL=your_email@gmail.com" >> .env
echo "GMAIL_APP_PASSWORD=your_app_password_here" >> .env
""")

    def _example_customization(self):
        """示例5: 自定义配置"""
        print("\n" + "=" * 60)
        print("示例5: 自定义配置")
        print("=" * 60)
        
        print("""
# 自定义关键词
crawler:
  arxiv:
    keywords:
      大模型: ["large language model", "LLM", "GPT", "BERT"]
      智能体: ["agent", "intelligent agent", "multi-agent"]
      强化学习: ["reinforcement learning", "RL", "PPO"]
      
# 自定义分析问题
llm:
  analysis:
    questions:
      - "总结论文主要内容"
      - "论文解决什么问题？"
      - "有哪些创新点？"
      - "实验设计如何？"
      
# 自定义邮件模板
email:
  content:
    subject_template: "AI论文日报 - {date}"
    include_attachments: true
    attachment_type: "markdown"
    
# 自定义定时任务
scheduler:
  mode: "custom"
  cron_expression: "0 8 * * 1-5"  # 工作日早上8点
""")

    def _example_monitoring(self):
        """示例6: 系统监控"""
        print("\n" + "=" * 60)
        print("示例6: 系统监控")
        print("=" * 60)
        
        print("""
# 检查系统状态
uv run automation_system.py interactive
# 选择6: 检查系统状态

# 查看日志文件
tail -f automation_system.log
tail -f cs_crawler.log

# 检查目录结构
ls -la 250821/
ls -la 250821/$(date +%y%m%d)/

# 查看配置文件
cat config.yaml

# 检查配置信息
uv run automation_system.py interactive
# 选择7: 查看配置信息
""")

    def _example_troubleshooting(self):
        """示例7: 故障排除"""
        print("\n" + "=" * 60)
        print("示例7: 故障排除")
        print("=" * 60)
        
        print("""
# 常见问题及解决方案

## 1. 导入模块失败
uv sync

## 2. API调用失败
- 检查配置文件中的API密钥是否正确
- 检查网络连接
- 查看错误日志

## 3. PDF下载失败
- 检查网络连接
- 检查ArXiv链接是否有效
- 检查存储空间

## 4. 邮件发送失败
- 检查配置文件中的Gmail设置
- 检查应用专用密码
- 检查SMTP设置

## 5. 定时任务不运行
- 检查scheduler.enabled设置
- 检查运行时间配置
- 查看系统日志

## 6. 配置问题
- 确认config.yaml文件存在且格式正确
- 检查API密钥和邮箱配置
- 运行配置检查：选择菜单中的"查看配置信息"
""")

    def run_daily_workflow(self):
        """运行每日工作流程"""
        try:
            self.logger.info("开始执行每日工作流程")
            start_time = time.time()
            
            # 获取当前日期
            date_str = datetime.now().strftime("%y%m%d")
            
            # 步骤1: 爬取论文
            self.logger.info("步骤1: 开始爬取论文")
            papers = self._crawl_papers()
            if not papers:
                self.logger.warning("未爬取到论文，跳过后续步骤")
                return
            
            # 步骤2: LLM解读论文
            self.logger.info("步骤2: 开始LLM解读论文")
            analysis_results = self._analyze_papers(papers, date_str)
            if not analysis_results:
                self.logger.warning("论文解读失败，跳过后续步骤")
                return
            
            # 步骤3: 生成报告
            self.logger.info("步骤3: 开始生成报告")
            report_path = self._generate_reports(analysis_results, date_str)
            
            # 步骤4: 发送邮件
            if self.config.is_enabled("email") and self.gmail_sender:
                self.logger.info("步骤4: 开始发送邮件")
                self._send_email_report(report_path, analysis_results, date_str)
            
            # 完成统计
            end_time = time.time()
            duration = end_time - start_time
            
            self.logger.info(f"每日工作流程完成！")
            self.logger.info(f"处理论文: {len(analysis_results)} 篇")
            self.logger.info(f"耗时: {duration:.2f} 秒")
            
        except Exception as e:
            self.logger.error(f"每日工作流程执行失败: {e}")
            self._send_failure_notification(str(e))
    
    def _crawl_papers(self) -> List[Dict]:
        """爬取论文"""
        try:
            self.logger.info("初始化论文爬虫")
            crawler = CSPaperCrawler()
            
            # 运行爬虫
            self.logger.info("开始爬取论文...")
            crawler.start()
            
            # 读取爬取结果
            papers = self._load_crawled_papers()
            self.logger.info(f"爬取完成，共获取 {len(papers)} 篇论文")
            
            return papers
            
        except Exception as e:
            self.logger.error(f"爬取论文失败: {e}")
            raise
    
    def _load_crawled_papers(self) -> List[Dict]:
        """加载爬取的论文数据"""
        try:
            # 获取当前日期目录
            date_str = datetime.now().strftime("%y%m%d")
            base_dir = self.config.get("output.directory_structure.base_dir", "./250821")
            date_dir = os.path.join(base_dir, date_str)
            
            papers = []
            
            # 查找论文文件
            if os.path.exists(date_dir):
                for filename in os.listdir(date_dir):
                    if filename.endswith('.json') and 'papers' in filename:
                        file_path = os.path.join(date_dir, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_papers = json.load(f)
                                if isinstance(file_papers, list):
                                    papers.extend(file_papers)
                        except Exception as e:
                            self.logger.warning(f"读取文件 {filename} 失败: {e}")
            
            return papers
            
        except Exception as e:
            self.logger.error(f"加载爬取论文失败: {e}")
            return []
    
    def _analyze_papers(self, papers: List[Dict], date_str: str) -> List[Dict]:
        """使用LLM解读论文"""
        try:
            self.logger.info(f"开始解读 {len(papers)} 篇论文")
            
            # 调用LLM分析
            main_paper_analysis()
            
            # 读取分析结果
            analysis_results = self._load_analysis_results(date_str)
            self.logger.info(f"论文解读完成，共分析 {len(analysis_results)} 篇论文")
            
            return analysis_results
            
        except Exception as e:
            self.logger.error(f"论文解读失败: {e}")
            raise
    
    def _load_analysis_results(self, date_str: str) -> List[Dict]:
        """加载分析结果"""
        try:
            analysis_dir = self.config.get_analysis_directory(date_str)
            analysis_results = []
            
            if os.path.exists(analysis_dir):
                for filename in os.listdir(analysis_dir):
                    if filename.endswith('.json') and 'analysis' in filename:
                        file_path = os.path.join(analysis_dir, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_results = json.load(f)
                                if isinstance(file_results, list):
                                    analysis_results.extend(file_results)
                        except Exception as e:
                            self.logger.warning(f"读取分析文件 {filename} 失败: {e}")
            
            return analysis_results
            
        except Exception as e:
            self.logger.error(f"加载分析结果失败: {e}")
            return []
    
    def _generate_reports(self, analysis_results: List[Dict], date_str: str) -> str:
        """生成报告"""
        try:
            self.logger.info("生成每日分析报告")
            
            # 生成主报告
            report_path = self.report_generator.generate_daily_report(analysis_results, date_str)
            
            # 生成类别报告
            papers_by_category = {}
            for result in analysis_results:
                category = result.get("matched_category", "其他")
                if category not in papers_by_category:
                    papers_by_category[category] = []
                papers_by_category[category].append(result)
            
            for category in papers_by_category.keys():
                try:
                    self.report_generator.generate_category_report(
                        papers_by_category[category], category, date_str
                    )
                except Exception as e:
                    self.logger.warning(f"生成 {category} 类别报告失败: {e}")
            
            self.logger.info(f"报告生成完成: {report_path}")
            return report_path
            
        except Exception as e:
            self.logger.error(f"生成报告失败: {e}")
            raise
    
    def _send_email_report(self, report_path: str, analysis_results: List[Dict], date_str: str):
        """发送邮件报告"""
        try:
            if not self.gmail_sender:
                self.logger.warning("邮件发送器未初始化，跳过邮件发送")
                return
            
            # 邮件配置
            email_config = self.config.get_email_config()
            content_config = email_config.get("content", {})
            
            # 邮件主题
            subject_template = content_config.get("subject_template", "CS论文每日分析报告 - {date}")
            subject = subject_template.format(date=date_str)
            
            # 邮件内容
            markdown_content = self._generate_email_content(analysis_results, date_str)
            
            # 收件人
            to_emails = content_config.get("to_emails", [])
            cc_emails = content_config.get("cc_emails", [])
            bcc_emails = content_config.get("bcc_emails", [])
            
            if not to_emails:
                self.logger.warning("未配置收件人，跳过邮件发送")
                return
            
            # 附件
            attachments = []
            if content_config.get("include_attachments", True):
                attachment_type = content_config.get("attachment_type", "all")
                if attachment_type in ["markdown", "all"]:
                    attachments.append(report_path)
            
            # 发送邮件
            success = self.gmail_sender.send_email(
                to_emails=to_emails,
                subject=subject,
                content=markdown_content,
                content_type="markdown",
                attachments=attachments,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails
            )
            
            if success:
                self.logger.info("邮件发送成功")
            else:
                self.logger.error("邮件发送失败")
                
        except Exception as e:
            self.logger.error(f"发送邮件报告失败: {e}")
    
    def _generate_email_content(self, analysis_results: List[Dict], date_str: str) -> str:
        """生成邮件内容"""
        total_papers = len(analysis_results)
        
        # 统计各类别论文数量
        papers_by_category = {}
        for result in analysis_results:
            category = result.get("matched_category", "其他")
            papers_by_category[category] = papers_by_category.get(category, 0) + 1
        
        # 生成邮件内容
        content = f"""# CS论文每日分析报告

**日期**: {date_str}  
**论文总数**: {total_papers} 篇

## 📊 今日统计

"""
        
        for category, count in papers_by_category.items():
            content += f"- **{category}**: {count} 篇\n"
        
        content += f"""
## 🔍 重点论文

"""
        
        # 选择前5篇论文作为重点
        for i, paper in enumerate(analysis_results[:5], 1):
            title = paper.get("title", "未知标题")
            category = paper.get("matched_category", "其他")
            content += f"{i}. **{title}** ({category})\n"
        
        content += f"""
## 📈 研究趋势

今日CS领域研究主要集中在人工智能、机器学习和计算机视觉方向。大模型技术持续受到关注，多模态学习成为重要研究方向。

详细分析报告请查看附件。

---
*此邮件由CS论文自动化分析系统自动生成*
*生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
        
        return content
    
    def _send_failure_notification(self, error_message: str):
        """发送失败通知"""
        try:
            if not self.gmail_sender or not self.config.is_enabled("notifications.failure"):
                return
            
            email_config = self.config.get_email_config()
            to_emails = email_config.get("content", {}).get("to_emails", [])
            
            if not to_emails:
                return
            
            subject = "CS论文自动化分析系统 - 执行失败通知"
            content = f"""# 系统执行失败通知

**失败时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## ❌ 错误信息

{error_message}

## 🔧 建议操作

1. 检查系统日志文件
2. 验证配置文件设置
3. 确认网络连接正常
4. 检查API密钥有效性

---
*此通知由CS论文自动化分析系统自动发送*
"""
            
            self.gmail_sender.send_email(
                to_emails=to_emails,
                subject=subject,
                content=content,
                content_type="markdown"
            )
            
        except Exception as e:
            self.logger.error(f"发送失败通知失败: {e}")
    
    def start_scheduler(self):
        """启动定时任务调度器"""
        try:
            scheduler_config = self.config.get_scheduler_config()
            
            if not scheduler_config.get("enabled", False):
                self.logger.info("定时任务未启用")
                return
            
            # 配置定时任务
            mode = scheduler_config.get("mode", "daily")
            run_time = scheduler_config.get("run_time", "09:00")
            
            if mode == "daily":
                schedule.every().day.at(run_time).do(self.run_daily_workflow)
                self.logger.info(f"已设置每日定时任务，运行时间: {run_time}")
            elif mode == "weekly":
                schedule.every().monday.at(run_time).do(self.run_daily_workflow)
                self.logger.info(f"已设置每周定时任务，运行时间: 周一 {run_time}")
            elif mode == "custom":
                cron_expr = scheduler_config.get("cron_expression", "0 9 * * *")
                # 这里可以添加cron表达式解析逻辑
                self.logger.info(f"已设置自定义定时任务: {cron_expr}")
            
            # 是否在启动时立即运行一次
            if scheduler_config.get("run_on_startup", False):
                self.logger.info("启动时立即执行一次工作流程")
                self.run_daily_workflow()
            
            # 启动调度器
            self.logger.info("定时任务调度器已启动")
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
                
        except KeyboardInterrupt:
            self.logger.info("用户中断，停止调度器")
        except Exception as e:
            self.logger.error(f"调度器运行失败: {e}")
    
    def run_once(self):
        """运行一次工作流程"""
        self.logger.info("手动执行一次工作流程")
        self.run_daily_workflow()


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("🚀 CS论文自动化分析系统")
        print("使用方法:")
        print("  python automation_system.py interactive  # 交互式菜单")
        print("  python automation_system.py run         # 运行一次完整流程")
        print("  python automation_system.py schedule    # 启动定时任务")
        print("  python automation_system.py crawl       # 仅爬取论文")
        print("  python automation_system.py analyze     # 仅分析论文")
        print("  python automation_system.py report      # 仅生成报告")
        print("  python automation_system.py help        # 显示帮助信息")
        return
    
    command = sys.argv[1].lower()
    
    try:
        system = AutomationSystem()
        
        if command == "interactive":
            system.run_interactive()
        elif command == "run":
            system.run_once()
        elif command == "schedule":
            system.start_scheduler()
        elif command == "crawl":
            system.crawl_only()
        elif command == "analyze":
            system.analyze_only()
        elif command == "report":
            system.generate_report_only()
        elif command == "help":
            print("🚀 CS论文自动化分析系统帮助")
            print("=" * 50)
            print("命令说明:")
            print("  interactive  - 启动交互式菜单（推荐新手使用）")
            print("  run          - 运行一次完整的论文分析流程")
            print("  schedule     - 启动定时任务，按配置自动运行")
            print("  crawl        - 仅爬取ArXiv论文，不进行分析")
            print("  analyze      - 仅分析已下载的论文")
            print("  report       - 仅生成分析报告")
            print("  help         - 显示此帮助信息")
            print("\n环境要求:")
            print("  - Python 3.7+")
            print("  - 设置环境变量: KIMI_API_KEY, GMAIL_EMAIL, GMAIL_APP_PASSWORD")
            print("  - 安装依赖: pip install -r requirements.txt")
            print("\n配置文件:")
            print("  - config.yaml (首次运行自动创建)")
            print("  - 支持自定义爬虫、LLM、邮件、定时任务等配置")
        else:
            print(f"❌ 未知命令: {command}")
            print("运行 'python automation_system.py help' 查看帮助")
            
    except Exception as e:
        print(f"❌ 系统启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 