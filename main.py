#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gmail自动发送邮件脚本
支持markdown格式和多种附件类型（PDF、PNG、ZIP等）
"""

import os
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
from typing import List, Optional, Union
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
                        logger.warning(f"附件文件不存在: {attachment_path}")
            
            # 发送邮件
            self._send_message(msg, to_emails)
            logger.info(f"邮件发送成功！收件人: {', '.join(to_emails)}")
            return True
            
        except Exception as e:
            logger.error(f"发送邮件失败: {str(e)}")
            return False
    
    def _add_attachment(self, msg: MIMEMultipart, file_path: str):
        """
        添加附件到邮件
        
        Args:
            msg: 邮件对象
            file_path: 附件文件路径
        """
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
            
            logger.info(f"成功添加附件: {filename}")
            
        except Exception as e:
            logger.error(f"添加附件失败 {file_path}: {str(e)}")
    
    def _send_message(self, msg: MIMEMultipart, to_emails: List[str]):
        """
        发送邮件消息
        
        Args:
            msg: 邮件对象
            to_emails: 收件人邮箱列表
        """
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
            logger.error(f"SMTP连接失败: {str(e)}")
            raise Exception(f"无法连接到SMTP服务器 {self.smtp_server}:{self.smtp_port}")
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP认证失败: {str(e)}")
            raise Exception("邮箱或密码错误，请检查配置")
        except Exception as e:
            logger.error(f"发送邮件时出错: {str(e)}")
            raise


def main():
    """主函数 - Gmail自动发送邮件示例"""
    print("🚀 Gmail自动发送邮件脚本")
    print("=" * 50)
    
    # 检查依赖
    try:
        import markdown
        print("✅ 所有依赖已安装，可以运行脚本")
    except ImportError:
        print("❌ 缺少依赖包，请先安装：")
        print("   uv sync")
        print("   或者: pip install -r requirements.txt")
        return
    
    # 配置信息 - 请修改为您的实际信息
    EMAIL = "lzy19801335167@gmail.com"  # 您的Gmail邮箱
    PASSWORD = "mhbo fkcs sjiu vfcp"   # 应用专用密码
    
    # 检查配置
    if EMAIL == "1234567890@gmail.com" or PASSWORD == "your_app_password":
        print("\n⚠️  请先配置Gmail邮箱信息！")
        print("   编辑 main.py 文件中的 EMAIL 和 PASSWORD 变量")
        print("   或者使用环境变量配置")
        return
    
    # 邮件内容（Markdown格式）
    markdown_content = """
# 测试邮件

这是一封**测试邮件**，用于验证Gmail自动发送功能。

## 功能特性

- ✅ 支持Markdown格式
- ✅ 支持多种附件类型
- ✅ 支持抄送和密送
- ✅ 自动处理文件类型

## 代码示例

```python
print("Hello, World!")
```

## 表格示例

| 功能 | 状态 | 说明 |
|------|------|------|
| Markdown | ✅ | 完全支持 |
| 附件 | ✅ | PDF、PNG、ZIP等 |
| 发送 | ✅ | 自动发送 |

---
*此邮件由Python脚本自动生成*
    """
    
    # 附件文件路径（请确保这些文件存在）
    attachments = [
        # "example.pdf",      # PDF文件
        # "screenshot.png",   # PNG图片
        # "data.zip"         # ZIP压缩包
    ]
    
    print(f"\n📧 准备发送邮件到: {EMAIL}")
    print("📎 附件数量:", len(attachments))
    
    # 尝试多种连接方式
    connection_methods = [
        ("端口587 (STARTTLS)", False, 587),
        ("端口465 (SSL)", True, 465),
    ]
    
    success = False
    for method_name, use_ssl, port in connection_methods:
        print(f"\n🔌 尝试连接方式: {method_name}")
        try:
            # 创建发送器实例
            sender = GmailSender(EMAIL, PASSWORD, smtp_port=port, use_ssl=use_ssl)
            
            # 发送邮件
            success = sender.send_email(
                to_emails=[EMAIL],  # 发送给自己
                subject="Gmail自动发送测试邮件",
                content=markdown_content,
                content_type="markdown",
                attachments=attachments
            )
            
            if success:
                print(f"✅ 使用 {method_name} 发送成功！")
                break
            else:
                print(f"❌ 使用 {method_name} 发送失败")
                
        except Exception as e:
            print(f"❌ {method_name} 连接失败: {str(e)}")
            continue
    
    if success:
        print("\n🎉 邮件发送成功！请检查您的收件箱。")
    else:
        print("\n❌ 所有连接方式都失败了！")
        print("\n💡 可能的解决方案：")
        print("1. 检查网络连接")
        print("2. 检查防火墙设置")
        print("3. 尝试使用VPN")
        print("4. 检查Gmail应用专用密码是否正确")


if __name__ == "__main__":
    main()
