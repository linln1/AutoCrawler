#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告生成器
将论文分析结果转换为markdown格式的报告，并生成Kimi对话链接
"""

import os
import json
import logging
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any, Optional
from config_manager import get_config

class KimiChatLinkGenerator:
    """Kimi对话链接生成器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = logging.getLogger(__name__)
    
    def generate_chat_link(self, paper: Dict) -> str:
        """为论文生成Kimi对话链接"""
        try:
            title = paper.get("title", "")
            authors = paper.get("authors", "")
            abstract = paper.get("original_abstract", "")
            paper_id = paper.get("id", "")
            
            # 构建预填内容
            prefilled_content = f"""我已经分析了这篇论文，现在您可以继续提问：

**论文标题**: {title}
**作者**: {authors}
**论文ID**: {paper_id}
**摘要**: {abstract}

我已经回答过以下问题：
1. 总结一下论文的主要内容
2. 这篇论文试图解决什么问题？
3. 有哪些相关研究？
4. 论文如何解决这个问题？
5. 论文做了哪些实验？实验结论如何？
6. 有什么可以进一步探索的点？

请继续提问，我会基于论文内容为您解答。您可以问：
- 论文的具体技术细节
- 实验结果的详细分析
- 与其他研究的对比
- 实际应用场景
- 或者任何您感兴趣的问题

请直接提问："""
            
            # 编码内容并构建链接
            encoded_content = urllib.parse.quote(prefilled_content)
            base_url = "https://kimi.moonshot.cn/"
            
            return f"{base_url}?prefill={encoded_content}"
            
        except Exception as e:
            self.logger.error(f"生成对话链接失败: {e}")
            return "https://kimi.moonshot.cn/"
    
    def generate_enhanced_chat_link(self, paper: Dict, analysis_results: Dict) -> str:
        """生成增强版对话链接，包含已分析的结果"""
        try:
            title = paper.get("title", "")
            authors = paper.get("authors", "")
            abstract = paper.get("original_abstract", "")
            paper_id = paper.get("id", "")
            
            # 构建包含分析结果的预填内容
            analysis_summary = ""
            if analysis_results:
                analysis_summary = "\n\n**已完成的初步分析**:\n"
                for q_key, q_data in analysis_results.items():
                    if isinstance(q_data, dict):
                        question = q_data.get("question", "")
                        answer = q_data.get("answer", "")
                        # 截取答案的前100个字符作为摘要
                        answer_preview = answer[:100] + "..." if len(answer) > 100 else answer
                        analysis_summary += f"- {question}\n  答：{answer_preview}\n"
            
            prefilled_content = f"""我已经分析了这篇论文，现在您可以继续提问：

**论文标题**: {title}
**作者**: {authors}
**论文ID**: {paper_id}
**摘要**: {abstract}{analysis_summary}

基于以上分析，您可以继续深入探讨：
- 论文的具体技术细节和实现方法
- 实验结果的深层含义和局限性
- 与其他相关研究的对比分析
- 实际应用场景和部署考虑
- 未来研究方向和改进建议
- 或者任何您感兴趣的具体问题

请直接提问，我会基于论文内容为您提供详细解答："""
            
            # 编码内容并构建链接
            encoded_content = urllib.parse.quote(prefilled_content)
            base_url = "https://kimi.moonshot.cn/"
            
            return f"{base_url}?prefill={encoded_content}"
            
        except Exception as e:
            self.logger.error(f"生成增强版对话链接失败: {e}")
            return self.generate_chat_link(paper)

class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = logging.getLogger(__name__)
        self.kimi_link_generator = KimiChatLinkGenerator()
    
    def generate_daily_report(self, analysis_results: List[Dict], date_str: str) -> str:
        """
        生成每日分析报告
        
        Args:
            analysis_results: 论文分析结果列表
            date_str: 日期字符串 (YYMMDD)
            
        Returns:
            生成的markdown报告内容
        """
        try:
            self.logger.info(f"开始生成每日报告，日期: {date_str}")
            
            # 创建报告目录
            report_dir = self.config.get_report_directory(date_str)
            os.makedirs(report_dir, exist_ok=True)
            
            # 生成报告内容
            report_content = self._generate_report_content(analysis_results, date_str)
            
            # 保存报告文件
            report_filename = self.config.get("output.naming.report_file", "daily_report_{date}_{time}.md")
            report_filename = report_filename.format(
                date=date_str,
                time=datetime.now().strftime("%Y%m%d_%H%M%S")
            )
            report_path = os.path.join(report_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            self.logger.info(f"每日报告已生成: {report_path}")
            
            return report_path
            
        except Exception as e:
            self.logger.error(f"生成每日报告失败: {e}")
            raise
    
    def _generate_report_content(self, analysis_results: List[Dict], date_str: str) -> str:
        """生成报告内容"""
        # 报告标题
        title = self.config.get("email.report.title", "CS论文每日分析报告")
        subtitle = self.config.get("email.report.subtitle", "基于ArXiv最新论文的智能解读")
        
        # 统计信息
        total_papers = len(analysis_results)
        papers_by_category = {}
        for result in analysis_results:
            category = result.get("matched_category", "其他")
            if category not in papers_by_category:
                papers_by_category[category] = 0
            papers_by_category[category] += 1
        
        # 生成报告内容
        content = f"""# {title}

{subtitle}

**生成时间**: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}  
**分析日期**: {date_str}  
**论文总数**: {total_papers} 篇

## 📊 统计概览

### 论文分类统计
"""
        
        # 添加分类统计
        for category, count in papers_by_category.items():
            content += f"- **{category}**: {count} 篇\n"
        
        content += f"""
### 关键词匹配统计
- **大模型**: {papers_by_category.get('大模型', 0)} 篇
- **智能体**: {papers_by_category.get('智能体', 0)} 篇  
- **强化学习**: {papers_by_category.get('强化学习', 0)} 篇
- **多模态**: {papers_by_category.get('多模态', 0)} 篇
- **微调**: {papers_by_category.get('微调', 0)} 篇
- **预训练**: {papers_by_category.get('预训练', 0)} 篇
- **检索增强生成**: {papers_by_category.get('检索增强生成', 0)} 篇
- **后训练**: {papers_by_category.get('后训练', 0)} 篇

---

## 📚 论文详细分析

"""
        
        # 按类别分组生成论文分析
        for category in sorted(papers_by_category.keys()):
            category_papers = [r for r in analysis_results if r.get("matched_category") == category]
            if not category_papers:
                continue
            
            content += f"### 🔍 {category} 领域论文\n\n"
            
            for i, paper in enumerate(category_papers, 1):
                content += self._generate_paper_section(paper, i)
                content += "\n---\n\n"
        
        # 添加总结
        content += self._generate_summary_section(analysis_results)
        
        return content
    
    def _generate_paper_section(self, paper: Dict, index: int) -> str:
        """生成单篇论文的分析部分"""
        title = paper.get("title", "未知标题")
        authors = paper.get("authors", "未知作者")
        abstract = paper.get("original_abstract", "无摘要")
        url = paper.get("url", "")
        matched_keyword = paper.get("matched_keyword", "")
        paper_id = paper.get("id", "")
        
        # 生成Kimi对话链接
        kimi_analysis = paper.get("kimi_analysis", {})
        kimi_chat_link = self.kimi_link_generator.generate_enhanced_chat_link(paper, kimi_analysis)
        
        content = f"""#### {index}. {title}

**作者**: {authors}  
**关键词匹配**: {matched_keyword}  
**论文链接**: [{url}]({url})  
**与Kimi继续对话**: [{kimi_chat_link}]({kimi_chat_link})

**摘要**: {abstract}

**智能分析结果**:
"""
        
        # 添加LLM分析结果
        kimi_analysis = paper.get("kimi_analysis", {})
        for q_key, q_data in kimi_analysis.items():
            if isinstance(q_data, dict):
                question = q_data.get("question", "")
                answer = q_data.get("answer", "")
                content += f"\n**{question}**\n\n{answer}\n"
        
        return content
    
    def _generate_summary_section(self, analysis_results: List[Dict]) -> str:
        """生成总结部分"""
        content = """
---

## 📈 今日研究趋势分析

### 🔥 热门研究方向
"""
        
        # 分析热门方向
        category_counts = {}
        for result in analysis_results:
            category = result.get("matched_category", "其他")
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # 按数量排序
        sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        
        for i, (category, count) in enumerate(sorted_categories[:3], 1):
            content += f"{i}. **{category}** ({count} 篇论文)\n"
        
        content += """
### 💡 研究洞察
- 今日CS领域研究主要集中在人工智能和机器学习方向
- 大模型和智能体技术持续受到关注
- 多模态学习成为重要研究方向
- 模型优化和训练技术不断演进

### 🚀 未来展望
- 大模型技术将继续快速发展
- 智能体系统将更加智能和自主
- 多模态融合将成为重要趋势
- 模型效率和可解释性将得到更多关注

---

## 📋 技术说明

本报告由CS论文自动化分析系统生成，包含以下技术特点：

- **智能爬取**: 自动从ArXiv获取最新CS领域论文
- **关键词匹配**: 基于预定义关键词进行智能筛选
- **LLM解读**: 使用大语言模型进行深度论文分析
- **多轮对话**: 通过上下文理解提供连贯的分析
- **自动生成**: 自动生成结构化的markdown报告

---

*报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*由CS论文自动化分析系统生成*
"""
        
        return content
    
    def _generate_kimi_chat_link(self, paper: Dict) -> str:
        """
        生成Kimi对话链接
        使用Partial Mode预填论文信息，让用户可以直接与Kimi继续对话
        """
        try:
            title = paper.get("title", "")
            authors = paper.get("authors", "")
            abstract = paper.get("original_abstract", "")
            paper_id = paper.get("id", "")
            
            # 构建预填内容，包含论文基本信息
            prefilled_content = f"""我已经分析了这篇论文，现在您可以继续提问：

**论文标题**: {title}
**作者**: {authors}
**摘要**: {abstract}

我已经回答过以下问题：
1. 总结一下论文的主要内容
2. 这篇论文试图解决什么问题？
3. 有哪些相关研究？
4. 论文如何解决这个问题？
5. 论文做了哪些实验？实验结论如何？
6. 有什么可以进一步探索的点？

请继续提问，我会基于论文内容为您解答。您可以问：
- 论文的具体技术细节
- 实验结果的详细分析
- 与其他研究的对比
- 实际应用场景
- 或者任何您感兴趣的问题

请直接提问："""
            
            # 构建Kimi对话链接
            # 使用Kimi的web界面，通过URL参数传递预填内容
            base_url = "https://kimi.moonshot.cn/"
            
            # 编码预填内容
            encoded_content = urllib.parse.quote(prefilled_content)
            
            # 构建对话链接（这里使用Kimi的web界面，实际使用时可能需要调整）
            chat_link = f"{base_url}?prefill={encoded_content}"
            
            return chat_link
            
        except Exception as e:
            self.logger.warning(f"生成Kimi对话链接失败: {e}")
            # 返回默认链接
            return "https://kimi.moonshot.cn/"
    
    def generate_category_report(self, analysis_results: List[Dict], category: str, date_str: str) -> str:
        """
        生成特定类别的分析报告
        
        Args:
            analysis_results: 论文分析结果列表
            category: 论文类别
            date_str: 日期字符串
            
        Returns:
            生成的markdown报告内容
        """
        try:
            # 筛选指定类别的论文
            category_papers = [r for r in analysis_results if r.get("matched_category") == category]
            
            if not category_papers:
                self.logger.warning(f"类别 {category} 没有找到论文")
                return ""
            
            # 创建报告目录
            report_dir = self.config.get_report_directory(date_str)
            os.makedirs(report_dir, exist_ok=True)
            
            # 生成报告内容
            content = f"""# {category} 领域论文分析报告

**生成时间**: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}  
**分析日期**: {date_str}  
**论文数量**: {len(category_papers)} 篇

## 📚 论文列表

"""
            
            for i, paper in enumerate(category_papers, 1):
                content += self._generate_paper_section(paper, i)
                content += "\n---\n\n"
            
            # 保存报告文件
            safe_category = category.replace('/', '_').replace('\\', '_')
            report_filename = f"{safe_category}_report_{date_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            report_path = os.path.join(report_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"{category} 类别报告已生成: {report_path}")
            
            return report_path
            
        except Exception as e:
            self.logger.error(f"生成 {category} 类别报告失败: {e}")
            raise
    
    def generate_executive_summary(self, analysis_results: List[Dict], date_str: str) -> str:
        """
        生成执行摘要（简化版报告）
        
        Args:
            analysis_results: 论文分析结果列表
            date_str: 日期字符串
            
        Returns:
            生成的markdown摘要内容
        """
        try:
            # 统计信息
            total_papers = len(analysis_results)
            papers_by_category = {}
            for result in analysis_results:
                category = result.get("matched_category", "其他")
                papers_by_category[category] = papers_by_category.get(category, 0) + 1
            
            # 生成摘要内容
            content = f"""# CS论文每日分析摘要

**日期**: {date_str}  
**论文总数**: {total_papers} 篇

## 📊 快速统计

"""
            
            for category, count in papers_by_category.items():
                content += f"- {category}: {count} 篇\n"
            
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

---
*摘要生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
            
            return content
            
        except Exception as e:
            self.logger.error(f"生成执行摘要失败: {e}")
            raise


# 全局报告生成器实例
report_generator = ReportGenerator()

def get_report_generator() -> ReportGenerator:
    """获取全局报告生成器实例"""
    return report_generator 