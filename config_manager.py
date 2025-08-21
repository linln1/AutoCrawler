#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器
用于加载和管理CS论文自动化分析系统的配置
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = {}
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_path):
                self._create_default_config()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # 处理环境变量
            self._process_environment_variables()
            
            # 验证配置
            self._validate_config()
            
            logging.info(f"配置文件加载成功: {self.config_path}")
            
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "system": {
                "enabled": True,
                "log_level": "INFO",
                "work_dir": "./",
                "keep_temp_files": False
            },
            "crawler": {
                "schedule": "daily",
                "run_time": "09:00",
                "request_delay": 2,
                "timeout": 10,
                "max_papers": 0
            },
            "llm": {
                "provider": "kimi",
                "kimi": {
                    "api_key": "${KIMI_API_KEY}",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2-0711-preview",
                    "temperature": 0.3,
                    "max_tokens": 4000
                }
            },
            "email": {
                "enabled": False,
                "gmail": {
                    "email": "${GMAIL_EMAIL}",
                    "password": "${GMAIL_APP_PASSWORD}",
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "use_ssl": False
                }
            }
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
            logging.info(f"默认配置文件已创建: {self.config_path}")
            self.config = default_config
        except Exception as e:
            logging.error(f"创建默认配置文件失败: {e}")
    
    def _process_environment_variables(self):
        """处理环境变量替换"""
        def replace_env_vars(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    obj[key] = replace_env_vars(value)
            elif isinstance(obj, list):
                for i, value in enumerate(obj):
                    obj[i] = replace_env_vars(value)
            elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                env_var = obj[2:-1]
                env_value = os.getenv(env_var)
                if env_value:
                    return env_value
                else:
                    logging.warning(f"环境变量 {env_var} 未设置")
                    return obj
            return obj
        
        self.config = replace_env_vars(self.config)
    
    def _validate_config(self):
        """验证配置有效性"""
        required_sections = ["system", "crawler", "llm"]
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"配置文件缺少必需的 {section} 部分")
        
        # 验证LLM配置
        if "provider" not in self.config["llm"]:
            raise ValueError("LLM配置缺少provider字段")
        
        provider = self.config["llm"]["provider"]
        if provider not in ["kimi", "openai", "deepseek"]:
            raise ValueError(f"不支持的LLM提供商: {provider}")
        
        # 验证邮件配置
        if self.config.get("email", {}).get("enabled", False):
            if "gmail" not in self.config["email"]:
                raise ValueError("邮件配置缺少gmail部分")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key_path: 配置键路径，如 "crawler.request_delay"
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            keys = key_path.split('.')
            value = self.config
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return self.config.get("crawler", {})
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self.config.get("llm", {})
    
    def get_email_config(self) -> Dict[str, Any]:
        """获取邮件配置"""
        return self.config.get("email", {})
    
    def get_output_config(self) -> Dict[str, Any]:
        """获取输出配置"""
        return self.config.get("output", {})
    
    def get_scheduler_config(self) -> Dict[str, Any]:
        """获取定时任务配置"""
        return self.config.get("scheduler", {})
    
    def is_enabled(self, section: str) -> bool:
        """检查某个功能是否启用"""
        return self.config.get(section, {}).get("enabled", False)
    
    def get_llm_provider_config(self) -> Dict[str, Any]:
        """获取当前LLM提供商的配置"""
        provider = self.get("llm.provider", "kimi")
        return self.config.get("llm", {}).get(provider, {})
    
    def get_analysis_questions(self) -> list:
        """获取分析问题列表"""
        return self.get("llm.analysis.questions", [
            "总结一下论文的主要内容",
            "这篇论文试图解决什么问题？",
            "有哪些相关研究？引用不能只给出序号，需要结合pdf reference章节给出相关研究的论文标题。",
            "论文如何解决这个问题？",
            "论文做了哪些实验？实验结论如何？",
            "有什么可以进一步探索的点？"
        ])
    
    def get_keywords(self) -> Dict[str, list]:
        """获取关键词配置"""
        return self.get("crawler.arxiv.keywords", {})
    
    def get_categories(self) -> Dict[str, str]:
        """获取ArXiv分类配置"""
        return self.get("crawler.arxiv.categories", {"cs": "https://arxiv.org/list/cs/new"})
    
    def reload(self):
        """重新加载配置"""
        self.load_config()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            logging.info(f"配置文件已保存: {self.config_path}")
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
    
    def update_config(self, updates: Dict[str, Any]):
        """
        更新配置
        
        Args:
            updates: 要更新的配置项
        """
        def deep_update(d, u):
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = deep_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
        
        self.config = deep_update(self.config, updates)
        self.save_config()
    
    def get_work_directory(self) -> str:
        """获取工作目录"""
        work_dir = self.get("system.work_dir", "./")
        return os.path.abspath(work_dir)
    
    def get_date_directory(self, date_str: str) -> str:
        """获取日期目录路径"""
        base_dir = self.get("output.directory_structure.base_dir", "./250821")
        return os.path.join(base_dir, date_str)
    
    def get_pdf_directory(self, date_str: str) -> str:
        """获取PDF下载目录路径"""
        base_dir = self.get("output.directory_structure.base_dir", "./250821")
        pdf_dir = self.get("output.directory_structure.pdf_dir", "./{date}/pdf_downloads")
        return os.path.join(base_dir, date_str, "pdf_downloads")
    
    def get_analysis_directory(self, date_str: str) -> str:
        """获取分析结果目录路径"""
        base_dir = self.get("output.directory_structure.base_dir", "./250821")
        analysis_dir = self.get("output.directory_structure.analysis_dir", "./{date}/paper_analysis")
        return os.path.join(base_dir, date_str, "paper_analysis")
    
    def get_report_directory(self, date_str: str) -> str:
        """获取报告目录路径"""
        base_dir = self.get("output.directory_structure.base_dir", "./250821")
        report_dir = self.get("output.directory_structure.report_dir", "./{date}/reports")
        return os.path.join(base_dir, date_str, "reports")


# 全局配置管理器实例
config_manager = ConfigManager()

def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    return config_manager 