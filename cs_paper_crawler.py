#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CS论文爬虫工具
基于MediaCrawler项目，去掉数据库存储部分，专门用于爬取CS领域的论文
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from bs4 import BeautifulSoup

# 配置
CRAWLER_CONFIG = {
    "request_delay": 2,  # 请求间隔时间（秒）
    "timeout": 10,  # 请求超时时间（秒）
}

# ArXiv CS领域分类 - 只爬取每日论文
ARXIV_CS_CATEGORIES = {
    "cs": "https://arxiv.org/list/cs/new",  # 计算机科学每日论文
}

# CS领域关键词
CS_KEYWORDS = {
    "大模型": ["large language model", "LLM", "GPT"],
    "智能体": ["agent", "intelligent agent", "multi-agent", "autonomous agent"],
    "强化学习": ["reinforcement learning", "RL", "PPO", "DPO"],
    "多模态": ["multimodal", "vision-language", "image-text", "audio-visual", "video", "VLM", "MLLM"],
    "微调": ["fine-tuning", "adapter", "LoRA", "QLoRA"],
    "预训练": ["pre-training", "pre-trained"],
    "优化算法": ["optimizer"],
    "检索增强生成": ["RAG", "retrieval-augmented generation", "retrieval-augmented generation", "RAG", "retrieval-augmented generation", "retrieval-augmented generation"],
    "后训练": ["post-training"]
}


class CSPaperCrawler:
    """CS论文爬虫类"""
    
    def __init__(self):
        self.setup_logging()
        self.setup_keywords()
        self.output_dir = self._create_output_dir()
        self.crawled_papers: Set[str] = set()
        
    def setup_logging(self):
        """设置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('cs_crawler.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_keywords(self):
        """设置关键词"""
        self.keywords = {}
        for category, keyword_list in CS_KEYWORDS.items():
            for keyword in keyword_list:
                self.keywords[keyword.lower()] = category
        
        self.logger.info(f"加载了 {len(self.keywords)} 个关键词，涵盖 {len(CS_KEYWORDS)} 个领域")
    
    def _create_output_dir(self) -> str:
        """创建输出目录，格式为YYMMDD"""
        today = datetime.now()
        dir_name = today.strftime("%y%m%d")
        
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            self.logger.info(f"创建输出目录: {dir_name}")
        
        return dir_name
    
    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """获取页面内容"""
        try:
            req = urlopen(url)
            return BeautifulSoup(req.read(), 'html.parser')
        except HTTPError:
            self.logger.warning("HTTP错误，等待60秒后重试")
            time.sleep(60)
            return self.get_page(url)
        except URLError:
            self.logger.warning("URL错误，等待60秒后重试")
            time.sleep(60)
            return self.get_page(url)
        except Exception as e:
            self.logger.error(f"获取页面时出错: {e}")
            return None
    
    def start(self):
        """启动爬虫"""
        self.logger.info("开始爬取CS领域每日论文...")
        
        try:
            # 爬取ArXiv CS领域每日论文
            self.crawl_arxiv_papers()
            
            # 生成汇总报告
            self.generate_summary_report()
            
        except Exception as e:
            self.logger.error(f"爬取过程中出错: {e}")
        
        self.logger.info(f"爬取完成！论文已保存到 {self.output_dir} 目录")
    
    def crawl_arxiv_papers(self):
        """爬取ArXiv论文"""
        self.logger.info("正在爬取ArXiv CS领域每日论文...")
        
        all_papers = []
        for category, url in ARXIV_CS_CATEGORIES.items():
            self.logger.info(f"爬取类别: {category}")
            try:
                papers = self.crawl_arxiv_category(url, category)
                if papers:
                    all_papers.extend(papers)
                    self.logger.info(f"类别 {category}: 找到 {len(papers)} 篇论文")
                time.sleep(CRAWLER_CONFIG["request_delay"])
            except Exception as e:
                self.logger.error(f"爬取 {category} 时出错: {e}")
        
        if all_papers:
            filtered_papers = self.filter_papers_by_keywords(all_papers)
            self.logger.info(f"关键词筛选后，共找到 {len(filtered_papers)} 篇相关论文")
            self.save_papers(filtered_papers)
        else:
            self.logger.warning("未找到任何论文")
    
    def crawl_arxiv_category(self, url: str, category: str) -> List[Dict]:
        """爬取特定ArXiv类别的论文"""
        papers = []
        
        try:
            bs = self.get_page(url)
            if bs:
                papers = self.extract_arxiv_papers(bs, category)
        except Exception as e:
            self.logger.error(f"爬取 {category} 页面时出错: {e}")
        
        return papers
    
    def extract_arxiv_papers(self, bs: BeautifulSoup, category: str) -> List[Dict]:
        """从ArXiv页面提取论文信息"""
        papers = []
        
        try:
            # 根据实际HTML结构，论文信息在dt和dd标签对中
            dt_elements = bs.find_all("dt")
            
            for dt_element in dt_elements:
                try:
                    # 获取对应的dd元素（论文详细信息）
                    dd_element = dt_element.find_next_sibling("dd")
                    if not dd_element:
                        continue
                    
                    # 提取论文ID
                    link_element = dt_element.find("a", title="Abstract")
                    if not link_element:
                        continue
                    
                    paper_id = link_element.get("id")
                    if not paper_id:
                        continue
                    
                    # 检查是否已经爬取过
                    if paper_id in self.crawled_papers:
                        continue
                    
                    # 创建论文信息字典
                    paper_info = {
                        "id": paper_id,
                        "url": f"https://arxiv.org/abs/{paper_id}",
                        "category": category,
                        "source": "arxiv",
                        "crawl_time": datetime.now().isoformat()
                    }
                    
                    # 提取标题
                    title_element = dd_element.find("div", class_="list-title")
                    if title_element:
                        # 去掉"Title:"标签，只保留标题文本
                        title_text = title_element.get_text()
                        if "Title:" in title_text:
                            title_text = title_text.split("Title:", 1)[1].strip()
                        paper_info["title"] = title_text
                    
                    # 提取作者
                    authors_element = dd_element.find("div", class_="list-authors")
                    if authors_element:
                        # 提取所有作者链接的文本
                        author_links = authors_element.find_all("a")
                        if author_links:
                            authors = [link.get_text().strip() for link in author_links]
                            paper_info["authors"] = ", ".join(authors)
                        else:
                            # 如果没有链接，直接获取文本
                            authors_text = authors_element.get_text()
                            if "Authors:" in authors_text:
                                authors_text = authors_text.split("Authors:", 1)[1].strip()
                            paper_info["authors"] = authors_text
                    
                    # 提取学科分类
                    subjects_element = dd_element.find("div", class_="list-subjects")
                    if subjects_element:
                        subjects_text = subjects_element.get_text()
                        if "Subjects:" in subjects_text:
                            subjects_text = subjects_text.split("Subjects:", 1)[1].strip()
                        paper_info["subjects"] = subjects_text
                    
                    # 提取摘要
                    abstract_element = dd_element.find("p", class_="mathjax")
                    if abstract_element:
                        paper_info["abstract"] = abstract_element.get_text().strip()
                    
                    # 提取评论信息（如果有）
                    comments_element = dd_element.find("div", class_="list-comments")
                    if comments_element:
                        comments_text = comments_element.get_text()
                        if "Comments:" in comments_text:
                            comments_text = comments_text.split("Comments:", 1)[1].strip()
                        paper_info["comments"] = comments_text
                    
                    # 检查是否有必要的字段
                    if paper_info.get("title") and paper_info.get("id"):
                        papers.append(paper_info)
                        self.crawled_papers.add(paper_id)
                        
                except Exception as e:
                    self.logger.warning(f"提取论文元素时出错: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"提取论文列表时出错: {e}")
        
        return papers
    
    def filter_papers_by_keywords(self, papers: List[Dict]) -> List[Dict]:
        """根据关键词筛选论文"""
        filtered_papers = []
        
        for paper in papers:
            title = paper.get("title", "").lower()
            
            matched_keywords = []
            for keyword, category in self.keywords.items():
                if keyword.lower() in title:
                    matched_keywords.append((keyword, category))
            
            if matched_keywords:
                best_match = max(matched_keywords, key=lambda x: len(x[0]))
                paper["matched_keyword"] = best_match[0]
                paper["matched_category"] = best_match[1]
                filtered_papers.append(paper)
        
        return filtered_papers
    
    def save_papers(self, papers: List[Dict]):
        """保存论文到本地文件"""
        if not papers:
            return
        
        papers_by_category = {}
        for paper in papers:
            category = paper.get("matched_category", "其他")
            if category not in papers_by_category:
                papers_by_category[category] = []
            papers_by_category[category].append(paper)
        
        for category, paper_list in papers_by_category.items():
            safe_category = re.sub(r'[<>:"/\\|?*]', '_', category)
            filename = f"{self.output_dir}/{safe_category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(paper_list, f, ensure_ascii=False, indent=2)
                self.logger.info(f"保存 {len(paper_list)} 篇论文到 {filename}")
            except Exception as e:
                self.logger.error(f"保存文件 {filename} 时出错: {e}")
        
        all_papers_filename = f"{self.output_dir}/all_papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(all_papers_filename, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            self.logger.info(f"保存所有论文到 {all_papers_filename}")
        except Exception as e:
            self.logger.error(f"保存汇总文件时出错: {e}")
    
    def generate_summary_report(self):
        """生成汇总报告"""
        try:
            summary = {
                "crawl_time": datetime.now().isoformat(),
                "output_directory": self.output_dir,
                "total_papers": len(self.crawled_papers),
                "files": []
            }
            
            for filename in os.listdir(self.output_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.output_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                summary["files"].append({
                                    "filename": filename,
                                    "paper_count": len(data),
                                    "file_size": os.path.getsize(file_path)
                                })
                    except Exception as e:
                        self.logger.warning(f"读取文件 {filename} 时出错: {e}")
            
            summary_filename = f"{self.output_dir}/crawl_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(summary_filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"生成汇总报告: {summary_filename}")
            
        except Exception as e:
            self.logger.error(f"生成汇总报告时出错: {e}")


def check_dependencies():
    """检查依赖是否安装"""
    try:
        from bs4 import BeautifulSoup
        print("✓ BeautifulSoup 已安装")
    except ImportError:
        print("✗ BeautifulSoup 未安装，请运行: pip install beautifulsoup4")
        return False
    
    return True


def main():
    """主函数"""
    print("CS论文爬虫启动检查...")
    print("=" * 50)
    
    if not check_dependencies():
        print("\n请先安装所需依赖！")
        sys.exit(1)
    
    print("\n所有检查通过，开始爬取论文...")
    print("=" * 50)
    
    try:
        crawler = CSPaperCrawler()
        crawler.start()
    except Exception as e:
        print(f"爬虫运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
    except Exception as e:
        print(f"程序运行出错: {e}")
        sys.exit(1) 