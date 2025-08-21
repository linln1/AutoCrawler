import os
import time
import json
import logging
import glob
import requests
import httpx
from datetime import datetime
from openai import OpenAI
from pathlib import Path

# 导入配置管理器
from config_manager import get_config

# ==================== Configuration ====================
# 从配置文件读取API配置，不再硬编码
config = get_config()

# 论文解读相关的配置
PAPER_DATA_DIR = './'  # 根目录，用于创建日期子目录

# 论文解读的提示模板
ABSTRACT_TRANSLATION_PROMPT = '''
请将以下英文论文摘要翻译成中文，保持学术性和准确性：

{abstract}

请直接输出中文翻译，不要添加其他内容。
'''

PAPER_ANALYSIS_PROMPT = '''
请基于以下论文信息回答问题。请用中文回答，保持专业性和准确性。

论文信息：
标题：{title}
作者：{authors}
摘要：{abstract}
学科分类：{subjects}
url：{url}

问题：{question}

请提供详细、准确的回答。
'''

# 论文解读的问题列表
ANALYSIS_QUESTIONS = [
    "总结一下论文的主要内容",
    "这篇论文试图解决什么问题？",
    "有哪些相关研究？引用不能只给出序号，需要结合pdf reference章节给出相关研究的论文标题。",
    "论文如何解决这个问题？",
    "论文做了哪些实验？实验结论如何？",
    "有什么可以进一步探索的点？"
]

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==================== 获取API配置的函数 ====================
def get_api_config():
    """从配置文件获取API配置"""
    try:
        llm_config = config.get("llm", {})
        provider = llm_config.get("provider", "kimi")
        
        if provider == "kimi":
            kimi_config = llm_config.get("kimi", {})
            return {
                "api_key": kimi_config.get("api_key"),
                "base_url": kimi_config.get("base_url", "https://api.moonshot.cn/v1"),
                "model": kimi_config.get("model", "kimi-k2-0711-preview"),
                "temperature": kimi_config.get("temperature", 0.3),
                "max_tokens": kimi_config.get("max_tokens", 4000)
            }
        elif provider == "openai":
            openai_config = llm_config.get("openai", {})
            return {
                "api_key": openai_config.get("api_key"),
                "base_url": openai_config.get("base_url", "https://api.openai.com/v1"),
                "model": openai_config.get("model", "gpt-4-turbo"),
                "temperature": openai_config.get("temperature", 0.3),
                "max_tokens": openai_config.get("max_tokens", 4000)
            }
        elif provider == "deepseek":
            deepseek_config = llm_config.get("deepseek", {})
            return {
                "api_key": deepseek_config.get("api_key"),
                "base_url": deepseek_config.get("base_url", "https://api.deepseek.com/v1"),
                "model": deepseek_config.get("model", "deepseek-chat"),
                "temperature": deepseek_config.get("temperature", 0.3),
                "max_tokens": deepseek_config.get("max_tokens", 4000)
            }
        else:
            logging.error(f"不支持的LLM提供商: {provider}")
            return None
            
    except Exception as e:
        logging.error(f"获取API配置失败: {e}")
        return None

def get_kimi_client():
    """获取Kimi客户端"""
    try:
        api_config = get_api_config()
        if not api_config or not api_config.get("api_key"):
            logging.error("未找到有效的API配置")
            return None
            
        return OpenAI(
            api_key=api_config["api_key"],
            base_url=api_config["base_url"]
        )
    except Exception as e:
        logging.error(f"创建Kimi客户端失败: {e}")
        return None

# ==================== 论文解读相关函数 ====================
def ensure_paper_analysis_dir():
    """确保论文解读结果目录存在"""
    today = datetime.now()
    date_dir = today.strftime("%y%m%d")
    analysis_dir = os.path.join(PAPER_DATA_DIR, date_dir, "paper_analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    return analysis_dir

def ensure_pdf_download_dir():
    """确保PDF下载目录存在"""
    today = datetime.now()
    date_dir = today.strftime("%y%m%d")
    pdf_dir = os.path.join(PAPER_DATA_DIR, date_dir, "pdf_downloads")
    os.makedirs(pdf_dir, exist_ok=True)
    return pdf_dir

def check_cache_exists(client, cache_tag):
    """检查缓存标签是否已存在"""
    try:
        response = httpx.get(f"{client.base_url}caching/refs/tags/{cache_tag}",
                           headers={
                               "Authorization": f"Bearer {client.api_key}",
                           })
        return response.status_code == 200
    except Exception as e:
        logging.warning(f"检查缓存标签时出错: {e}")
        return False

def cleanup_expired_caches(client, cache_tags):
    """清理过期的缓存标签"""
    for cache_tag in cache_tags:
        try:
            # 获取标签对应的缓存信息
            response = httpx.get(f"{client.base_url}caching/refs/tags/{cache_tag}/content",
                               headers={
                                   "Authorization": f"Bearer {client.api_key}",
                               })
            
            if response.status_code == 200:
                cache_info = response.json()
                if cache_info.get('status') == 'inactive':
                    # 删除过期的标签
                    httpx.delete(f"{client.base_url}caching/refs/tags/{cache_tag}",
                               headers={
                                   "Authorization": f"Bearer {client.api_key}",
                               })
                    logging.info(f"已清理过期缓存标签: {cache_tag}")
        except Exception as e:
            logging.warning(f"清理缓存标签 {cache_tag} 时出错: {e}")

def init_client():
    """初始化OpenAI客户端"""
    return OpenAI(
        api_key=OTHER_API_KEY,
        base_url=API_BASE_URL,
    )

def init_kimi_client():
    """初始化Kimi客户端"""
    return OpenAI(
        api_key=KIMI_API_KEY,
        base_url=KIMI_API_BASE_URL,
    )

def download_pdf(url, paper_id, pdf_dir):
    """下载PDF文件"""
    pdf_path = os.path.join(pdf_dir, f"{paper_id}.pdf")
    
    # 如果文件已存在，直接返回路径
    if os.path.exists(pdf_path):
        logging.info(f"PDF文件已存在: {pdf_path}")
        return pdf_path
    
    try:
        # 将abs链接转换为pdf链接
        pdf_url = url.replace('/abs/', '/pdf/') + '.pdf'
        logging.info(f"正在下载PDF: {pdf_url}")
        
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        with open(pdf_path, 'wb') as f:
            f.write(response.content)
        
        logging.info(f"PDF下载成功: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logging.error(f"下载PDF失败 {paper_id}: {e}")
        return None

def upload_files_with_cache(client, files, cache_tag=None):
    """
    上传文件并创建上下文缓存
    参考Kimi API文档的Context Caching功能
    """
    messages = []
    
    # 对每个文件路径，上传文件并抽取文件内容
    for file in files:
        try:
            logging.info(f"正在上传文件: {file}")
            file_object = client.files.create(file=Path(file), purpose="file-extract")
            file_content = client.files.content(file_id=file_object.id).text
            messages.append({
                "role": "system",
                "content": file_content,
            })
            logging.info(f"文件上传成功，ID: {file_object.id}")
        except Exception as e:
            logging.error(f"文件上传失败: {e}")
            return None
    
    if cache_tag:
        # 启用缓存，通过HTTP接口创建缓存
        try:
            r = httpx.post(f"{client.base_url}caching",
                           headers={
                               "Authorization": f"Bearer {client.api_key}",
                           },
                           json={
                               "model": "moonshot-v1",
                               "messages": messages,
                               "ttl": 3600,  # 缓存1小时
                               "tags": [cache_tag],
                               "name": f"论文分析缓存_{cache_tag}",
                               "description": f"论文 {cache_tag} 的PDF内容缓存，用于后续分析",
                           })
            
            if r.status_code != 200:
                logging.error(f"创建缓存失败: {r.text}")
                return None
            
            cache_response = r.json()
            cache_id = cache_response.get('id')
            logging.info(f"缓存创建成功，ID: {cache_id}")
            
            # 为缓存创建标签引用
            try:
                tag_response = httpx.post(f"{client.base_url}caching/refs/tags",
                                        headers={
                                            "Authorization": f"Bearer {client.api_key}",
                                        },
                                        json={
                                            "tag": cache_tag,
                                            "cache_id": cache_id
                                        })
                
                if tag_response.status_code == 200:
                    logging.info(f"标签 {cache_tag} 创建成功")
                else:
                    logging.warning(f"标签创建失败: {tag_response.text}")
            except Exception as e:
                logging.warning(f"创建标签时出错: {e}")
            
            # 返回缓存引用消息（使用标签）
            return [{
                "role": "cache",
                "content": f"tag={cache_tag};reset_ttl=3600",
            }]
            
        except Exception as e:
            logging.error(f"创建缓存时出错: {e}")
            return None
    else:
        # 不启用缓存，直接返回文件内容消息
        return messages

def analyze_paper_with_kimi_cache(client, paper_info, cache_tag):
    """使用Kimi缓存机制分析论文，支持多轮对话"""
    logging.info(f"开始使用Kimi缓存分析论文: {paper_info.get('title', 'Unknown')}")
    
    analysis_result = {
        "paper_id": paper_info.get('id'),
        "title": paper_info.get('title'),
        "authors": paper_info.get('authors'),
        "subjects": paper_info.get('subjects'),
        "original_abstract": paper_info.get('abstract'),
        "url": paper_info.get('url'),
        "analysis_time": datetime.now().isoformat(),
        "kimi_analysis": {},
        "cache_tag": cache_tag
    }
    
    # 构建系统消息
    system_messages = [
        {
            "role": "system",
            "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。同时，你会拒绝一切涉及恐怖主义，种族歧视，黄色暴力等问题的回答。Moonshot AI 为专有名词，不可翻译成其他语言。"
        }
    ]
    
    # 初始化对话历史，用于多轮对话
    conversation_messages = []
    
    # 逐个回答问题，利用多轮对话机制
    for i, question in enumerate(ANALYSIS_QUESTIONS):
        logging.info(f"正在回答问题 {i+1}/{len(ANALYSIS_QUESTIONS)}: {question}")
        
        # 构建当前轮次的消息列表
        current_messages = system_messages + conversation_messages + [
            {
                "role": "user", 
                "content": f"请基于论文内容回答以下问题：{question}"
            }
        ]
        
        try:
            # 使用缓存调用API
            resp = client.chat.completions.create(
                model="kimi-k2-0711-preview",
                messages=current_messages,
                temperature=0.3,
                extra_headers={
                    "X-Msh-Context-Cache": cache_tag,
                    "X-Msh-Context-Cache-Reset-TTL": "3600",
                },
            )
            answer = resp.choices[0].message.content.strip()
            
            # 打印每个问题的回答，用于调试
            print(f"\n{'='*50}")
            print(f"问题 {i+1}: {question}")
            print(f"回答: {answer}")
            print(f"{'='*50}\n")
            
            # 将问答对添加到对话历史中，用于后续问题的上下文
            conversation_messages.append({
                "role": "user",
                "content": f"请基于论文内容回答以下问题：{question}"
            })
            conversation_messages.append({
                "role": "assistant", 
                "content": answer
            })
            
            # 控制对话历史长度，避免Token过多（保留最新的10轮对话）
            if len(conversation_messages) > 20:  # 10轮问答 = 20条消息
                conversation_messages = conversation_messages[-20:]
            
            analysis_result["kimi_analysis"][f"Q{i+1}"] = {
                "question": question,
                "answer": answer
            }
            
            time.sleep(1)  # 避免API调用过于频繁
            
        except Exception as e:
            logging.error(f"分析论文问题时出错: {e}")
            answer = f"分析失败: {str(e)}"
            analysis_result["kimi_analysis"][f"Q{i+1}"] = {
                "question": question,
                "answer": answer
            }
            
            # 即使失败也要添加到对话历史中，保持一致性
            conversation_messages.append({
                "role": "user",
                "content": f"请基于论文内容回答以下问题：{question}"
            })
            conversation_messages.append({
                "role": "assistant", 
                "content": answer
            })
    
    logging.info(f"论文分析完成: {paper_info.get('title', 'Unknown')}")
    return analysis_result

def load_paper_data():
    """加载爬取的论文数据"""
    papers = []
    
    # 查找所有论文数据文件（从250821目录）
    pattern = os.path.join("250821", "*_papers_*.json")
    json_files = glob.glob(pattern)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                file_papers = json.load(f)
                if isinstance(file_papers, list):
                    papers.extend(file_papers)
                    logging.info(f"从 {json_file} 加载了 {len(file_papers)} 篇论文")
        except Exception as e:
            logging.error(f"读取文件 {json_file} 时出错: {e}")
    
    # 去重（基于论文ID）
    unique_papers = {}
    for paper in papers:
        paper_id = paper.get('id')
        if paper_id and paper_id not in unique_papers:
            unique_papers[paper_id] = paper
    
    papers = list(unique_papers.values())
    logging.info(f"总共加载了 {len(papers)} 篇唯一论文")
    return papers

def save_analysis_results(analysis_results, analysis_dir):
    """保存分析结果到文件"""
    # 使用传入的分析目录
    output_dir = analysis_dir
    
    # 保存所有分析结果
    all_results_file = os.path.join(output_dir, f"all_paper_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    try:
        with open(all_results_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        logging.info(f"所有分析结果已保存到: {all_results_file}")
    except Exception as e:
        logging.error(f"保存分析结果时出错: {e}")
    
    # 按类别分别保存
    papers_by_category = {}
    for result in analysis_results:
        # 从原始论文信息中获取类别
        category = result.get("matched_category", "其他")
        if category not in papers_by_category:
            papers_by_category[category] = []
        papers_by_category[category].append(result)
    
    for category, papers in papers_by_category.items():
        safe_category = category.replace('/', '_').replace('\\', '_')
        category_file = os.path.join(output_dir, f"{safe_category}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            with open(category_file, 'w', encoding='utf-8') as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            logging.info(f"{category} 类别分析结果已保存到: {category_file}")
        except Exception as e:
            logging.error(f"保存 {category} 类别结果时出错: {e}")

def main_paper_analysis():
    """论文解读主函数"""
    logging.info("开始论文解读流程...")
    
    # 确保目录存在并获取目录路径
    analysis_dir = ensure_paper_analysis_dir()
    pdf_dir = ensure_pdf_download_dir()
    
    logging.info(f"PDF下载目录: {pdf_dir}")
    logging.info(f"分析结果目录: {analysis_dir}")
    
    # 初始化Kimi客户端
    kimi_client = get_kimi_client()
    
    # 加载论文数据
    papers = load_paper_data()
    if not papers:
        logging.error("没有找到论文数据，请检查数据目录")
        return
    
    logging.info(f"开始分析 {len(papers)} 篇论文...")
    
    # 分析每篇论文
    analysis_results = []
    for i, paper in enumerate(papers):
        try:
            logging.info(f"进度: {i+1}/{len(papers)}")
            
            # 下载PDF
            pdf_path = download_pdf(paper.get('url'), paper.get('id'), pdf_dir)
            if not pdf_path:
                logging.warning(f"跳过论文 {paper.get('id')}，PDF下载失败")
                continue
            
            # 生成缓存标签（使用论文ID作为标签，更简洁易管理）
            cache_tag = f"paper_{paper.get('id')}"
            
            # 检查缓存是否已存在
            if check_cache_exists(kimi_client, cache_tag):
                logging.info(f"缓存标签 {cache_tag} 已存在，跳过文件上传")
                file_messages = [{
                    "role": "cache",
                    "content": f"tag={cache_tag};reset_ttl=3600",
                }]
            else:
                # 上传文件到Kimi并创建缓存
                file_messages = upload_files_with_cache(kimi_client, [pdf_path], cache_tag)
                if not file_messages:
                    logging.warning(f"跳过论文 {paper.get('id')}，文件上传或缓存创建失败")
                    continue
            
            # 使用Kimi缓存机制分析论文
            analysis_result = analyze_paper_with_kimi_cache(kimi_client, paper, cache_tag)
            analysis_results.append(analysis_result)
            
            # 每分析10篇论文保存一次中间结果
            if (i + 1) % 10 == 0:
                logging.info(f"已分析 {i+1} 篇论文，保存中间结果...")
                save_analysis_results(analysis_results, analysis_dir)
                
        except Exception as e:
            logging.error(f"分析论文 {paper.get('id', 'Unknown')} 时出错: {e}")
            continue
    
    # 保存最终结果
    logging.info("所有论文分析完成，保存最终结果...")
    save_analysis_results(analysis_results, analysis_dir)
    
    # 清理过期的缓存标签
    cache_tags = [result.get('cache_tag') for result in analysis_results if result.get('cache_tag')]
    if cache_tags:
        logging.info("开始清理过期缓存标签...")
        cleanup_expired_caches(kimi_client, cache_tags)
    
    logging.info(f"论文解读流程完成，共分析了 {len(analysis_results)} 篇论文")

# ==================== 主执行流程 ====================
if __name__ == '__main__':
    main_paper_analysis()