import os
import time
import json
import logging
import glob
import requests
import httpx
import base64
from datetime import datetime
from openai import OpenAI
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 导入配置管理器
from config_manager import get_config

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token统计类
class TokenUsageTracker:
    """Token使用量跟踪器"""
    
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_estimate = 0.0
        self.api_calls = 0
        self.start_time = datetime.now()
    
    def add_usage(self, input_tokens: int, output_tokens: int, model: str = "unknown"):
        """添加token使用量"""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.api_calls += 1
        
        # 估算成本（基于常见模型的定价）
        cost = self._estimate_cost(input_tokens, output_tokens, model)
        self.total_cost_estimate += cost
        
        logging.info(f"Token使用量: 输入={input_tokens}, 输出={output_tokens}, 估算成本=${cost:.4f}")
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """估算API调用成本"""
        # 基于常见模型的定价（每1000 tokens）
        pricing = {
            "deepseek-reasoner": {"input": 0.0007, "output": 0.0014},  # DeepSeek R1
            "kimi-k2-0711-preview": {"input": 0.0007, "output": 0.0014},  # Kimi
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},  # OpenAI
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},  # OpenAI GPT-4
        }
        
        # 获取模型定价，如果没有则使用默认值
        model_pricing = pricing.get(model, {"input": 0.001, "output": 0.002})
        
        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        
        return input_cost + output_cost
    
    def get_summary(self) -> Dict:
        """获取使用量摘要"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "api_calls": self.api_calls,
            "total_cost_estimate": self.total_cost_estimate,
            "duration_seconds": duration,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
    
    def print_summary(self):
        """打印使用量摘要"""
        summary = self.get_summary()
        
        print("=" * 60)
        print("📊 Token使用量统计")
        print("=" * 60)
        print(f"总输入Token: {summary['total_input_tokens']:,}")
        print(f"总输出Token: {summary['total_output_tokens']:,}")
        print(f"总Token: {summary['total_tokens']:,}")
        print(f"API调用次数: {summary['api_calls']}")
        print(f"估算总成本: ${summary['total_cost_estimate']:.4f}")
        print(f"运行时长: {summary['duration_seconds']:.1f} 秒")
        print(f"开始时间: {summary['start_time']}")
        print(f"结束时间: {summary['end_time']}")
        print("=" * 60)
    
    def save_summary(self, filename: str = None):
        """保存使用量摘要到文件"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"token_usage_summary_{timestamp}.json"
        
        summary = self.get_summary()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            logging.info(f"Token使用量摘要已保存到: {filename}")
        except Exception as e:
            logging.error(f"保存Token使用量摘要失败: {e}")
    
    def reset_tracker(self):
        """重置跟踪器"""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_estimate = 0.0
        self.api_calls = 0
        self.start_time = datetime.now()
        logging.info("Token使用量跟踪器已重置")

# 全局token跟踪器
token_tracker = TokenUsageTracker()

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
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
                "max_tokens": kimi_config.get("max_tokens", 4000)
            }
        elif provider == "deepseek":
            deepseek_config = llm_config.get("deepseek", {})
            return {
                "api_key": deepseek_config.get("api_key"),
                "base_url": deepseek_config.get("base_url", "https://api.deepseek.com/v1"),
                "model": deepseek_config.get("model", "deepseek-chat"),
                "temperature": deepseek_config.get("temperature", 0.3),
                "max_tokens": kimi_config.get("max_tokens", 4000)
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

def get_deepseek_client():
    """获取DeepSeek客户端"""
    try:
        config = get_config()
        deepseek_config = config.get("llm", {}).get("deepseek", {})
        
        if not deepseek_config.get("api_key"):
            logging.error("DeepSeek API密钥未配置")
            return None
        
        # DeepSeek R1使用不同的base_url格式
        base_url = deepseek_config.get("base_url", "https://api.deepseek.com")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        
        client = OpenAI(
            api_key=deepseek_config["api_key"],
            base_url=base_url
        )
        
        logging.info("DeepSeek客户端初始化成功")
        return client
        
    except Exception as e:
        logging.error(f"初始化DeepSeek客户端失败: {e}")
        return None

def get_temperature_for_scenario(scenario: str) -> float:
    """
    根据使用场景获取合适的temperature值
    
    Args:
        scenario: 使用场景
        
    Returns:
        float: 合适的temperature值
    """
    config = get_config()
    temperature_config = config.get("llm", {}).get("temperature_by_scenario", {})
    
    # 场景化temperature配置
    scenario_temperatures = {
        "paper_relevance": 0.1,      # 论文相关性分析 - 需要一致性和准确性
        "paper_analysis": 0.3,       # 论文内容分析 - 需要准确性和完整性
        "report_generation": 0.7,    # 报告生成 - 需要一定的创造性但保持准确性
        "general_conversation": 1.3, # 通用对话 - 需要灵活性和创造性
        "creative_writing": 1.5,     # 创意写作 - 需要高创造性
        "code_generation": 0.0,      # 代码生成 - 需要精确性
        "data_extraction": 1.0,      # 数据抽取 - 需要准确性
        "translation": 1.3,          # 翻译任务 - 需要灵活性
    }
    
    # 从配置文件读取，如果没有则使用默认值
    temperature = temperature_config.get(scenario, scenario_temperatures.get(scenario, 1.0))
    
    logging.info(f"场景 '{scenario}' 使用 temperature: {temperature}")
    return temperature

def get_api_config_with_scenario(scenario: str = "general"):
    """
    根据场景获取API配置，包括合适的temperature
    
    Args:
        scenario: 使用场景
        
    Returns:
        Dict: API配置字典
    """
    try:
        llm_config = config.get("llm", {})
        provider = llm_config.get("provider", "kimi")
        
        if provider == "kimi":
            kimi_config = llm_config.get("kimi", {})
            return {
                "api_key": kimi_config.get("api_key"),
                "base_url": kimi_config.get("base_url", "https://api.moonshot.cn/v1"),
                "model": kimi_config.get("model", "kimi-k2-0711-preview"),
                "temperature": get_temperature_for_scenario(scenario),
                "max_tokens": kimi_config.get("max_tokens", 4000)
            }
        elif provider == "openai":
            openai_config = llm_config.get("openai", {})
            return {
                "api_key": openai_config.get("api_key"),
                "base_url": openai_config.get("base_url", "https://api.openai.com/v1"),
                "model": openai_config.get("model", "gpt-4-turbo"),
                "temperature": get_temperature_for_scenario(scenario),
                "max_tokens": openai_config.get("max_tokens", 4000)
            }
        elif provider == "deepseek":
            deepseek_config = llm_config.get("deepseek", {})
            return {
                "api_key": deepseek_config.get("api_key"),
                "base_url": deepseek_config.get("base_url", "https://api.deepseek.com/v1"),
                "model": deepseek_config.get("model", "deepseek-chat"),
                "temperature": get_temperature_for_scenario(scenario),
                "max_tokens": deepseek_config.get("max_tokens", 4000)
            }
        else:
            logging.error(f"不支持的LLM提供商: {provider}")
            return None
    except Exception as e:
        logging.error(f"获取API配置失败: {e}")
        return None

# ==================== 论文解读相关函数 ====================
def analyze_paper_with_questions(paper_title: str, paper_abstract: str, paper_url: str = None, paper_id: str = None, save_results: bool = True) -> Dict:
    """
    使用LLM分析论文，一次性回答所有问题，减少token消耗
    
    Args:
        paper_title: 论文标题
        paper_abstract: 论文摘要
        paper_url: 论文URL（用于下载PDF）
        paper_id: 论文ID（用于保存结果）
        save_results: 是否保存分析结果到文件
    
    Returns:
        Dict: 包含所有问题答案的字典
    """
    try:
        # 根据配置选择客户端
        config = get_config()
        provider = config.get("llm", {}).get("provider", "deepseek")
        
        if provider == "deepseek":
            client = get_deepseek_client()
        elif provider == "kimi":
            client = get_kimi_client()
        elif provider == "openai":
            client = get_openai_client()
        else:
            logging.error(f"不支持的LLM提供商: {provider}")
            return {}
        
        if not client:
            logging.error("无法获取LLM客户端")
            return {}
        
        # 尝试下载PDF文件
        pdf_path = None
        pdf_content = None
        
        if paper_url and paper_id:
            try:
                pdf_path = download_pdf(paper_url, paper_id)
                if pdf_path:
                    logging.info(f"PDF下载成功: {pdf_path}")
                    # 对于DeepSeek，我们可以尝试使用文件上传功能
                    if provider == "deepseek":
                        # 检查文件大小，如果太大则使用base64编码
                        file_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
                        if file_size_mb > 20:  # 如果PDF大于20MB，使用base64编码
                            pdf_content = encode_pdf_to_base64(pdf_path)
                            logging.info(f"PDF文件较大，使用base64编码 (大小: {file_size_mb:.1f}MB)")
                        else:
                            logging.info(f"PDF文件大小适中，可以直接使用 (大小: {file_size_mb:.1f}MB)")
                else:
                    logging.warning("PDF下载失败，将仅使用摘要进行分析")
            except Exception as e:
                logging.warning(f"PDF处理失败: {e}，将仅使用摘要进行分析")
        
        # 构建优化的prompt，一次性回答所有问题
        if pdf_path and pdf_content:
            prompt = f"""
请分析以下论文，一次性回答所有6个问题。请严格按照JSON格式输出，不要添加任何其他内容。

论文标题: {paper_title}
论文摘要: {paper_abstract}
PDF内容: [已提供PDF文件，请仔细阅读全文内容]

请按以下JSON格式回答所有问题:
{{
    "q1_main_content": "论文主要内容总结",
    "q2_problem": "论文试图解决的具体问题",
    "q3_related_work": "相关研究（结合PDF reference章节，给出具体论文标题）",
    "q4_solution": "论文的解决方案和方法",
    "q5_experiments": "实验设计和结论",
    "q6_future_work": "可以进一步探索的方向"
}}

注意:
1. 必须严格按照JSON格式输出
2. 每个答案要简洁但完整
3. 相关研究要结合PDF中的具体引用
4. 不要添加序号、标题等额外格式
"""
        elif pdf_path:
            prompt = f"""
请分析以下论文，一次性回答所有6个问题。请严格按照JSON格式输出，不要添加任何其他内容。

论文标题: {paper_title}
论文摘要: {paper_abstract}
PDF文件: [已提供PDF文件，请仔细阅读全文内容]

请按以下JSON格式回答所有问题:
{{
    "q1_main_content": "论文主要内容总结",
    "q2_problem": "论文试图解决的具体问题",
    "q3_related_work": "相关研究（结合PDF reference章节，给出具体论文标题）",
    "q4_solution": "论文的解决方案和方法",
    "q5_experiments": "实验设计和结论",
    "q6_future_work": "可以进一步探索的方向"
}}

注意:
1. 必须严格按照JSON格式输出
2. 每个答案要简洁但完整
3. 相关研究要结合PDF中的具体引用
4. 不要添加序号、标题等额外格式
"""
        else:
            prompt = f"""
请分析以下论文，一次性回答所有6个问题。请严格按照JSON格式输出，不要添加任何其他内容。

论文标题: {paper_title}
论文摘要: {paper_abstract}

请按以下JSON格式回答所有问题:
{{
    "q1_main_content": "论文主要内容总结",
    "q2_problem": "论文试图解决的具体问题",
    "q3_related_work": "相关研究（基于摘要内容分析）",
    "q4_solution": "论文的解决方案和方法",
    "q5_experiments": "实验设计和结论",
    "q6_future_work": "可以进一步探索的方向"
}}

注意:
1. 必须严格按照JSON格式输出
2. 每个答案要简洁但完整
3. 不要添加序号、标题等额外格式
"""

        # 根据提供商构建不同的API调用参数
        if provider == "deepseek":
            # DeepSeek R1特殊处理
            messages = [
                {"role": "system", "content": "你是一个专业的AI研究论文分析专家。请严格按照要求的JSON格式输出，不要添加任何其他内容。"},
                {"role": "user", "content": prompt}
            ]
            
            # 如果有PDF文件，尝试添加到消息中
            if pdf_path:
                try:
                    # 对于DeepSeek，我们可以尝试使用文件上传
                    # 注意：这里需要根据DeepSeek的具体API文档来调整
                    if pdf_content:
                        # 如果PDF太大，在prompt中说明
                        messages[1]["content"] += f"\n\n注意：由于PDF文件较大，请基于摘要和标题进行分析。"
                    else:
                        # 如果PDF适中，可以尝试直接使用
                        messages[1]["content"] += f"\n\n注意：请基于提供的PDF文件内容进行分析。"
                except Exception as e:
                    logging.warning(f"PDF文件处理失败: {e}")
            
            api_params = {
                "model": get_api_config_with_scenario("paper_analysis")["model"],
                "messages": messages,
                "max_tokens": get_api_config_with_scenario("paper_analysis").get("max_tokens", 32000)
                # 注意：DeepSeek R1不支持temperature、top_p等参数
            }
        else:
            # 其他提供商使用标准参数
            api_params = {
                "model": get_api_config_with_scenario("paper_analysis")["model"],
                "messages": [
                    {"role": "system", "content": "你是一个专业的AI研究论文分析专家。请严格按照要求的JSON格式输出，不要添加任何其他内容。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": get_temperature_for_scenario("paper_analysis"),
                "max_tokens": get_api_config_with_scenario("paper_analysis").get("max_tokens", 4000)
            }

        # 调用LLM
        response = client.chat.completions.create(**api_params)
        
        # 记录token使用量
        if hasattr(response, 'usage') and response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            model_name = get_api_config_with_scenario("paper_analysis")["model"] if get_api_config_with_scenario("paper_analysis") else "unknown"
            token_tracker.add_usage(input_tokens, output_tokens, model_name)
        
        # 解析响应
        if provider == "deepseek":
            # DeepSeek R1特殊处理：同时获取reasoning_content和content
            reasoning_content = getattr(response.choices[0].message, 'reasoning_content', None)
            content = response.choices[0].message.content.strip()
            
            if reasoning_content:
                logging.info(f"DeepSeek R1推理过程: {reasoning_content[:200]}...")
        else:
            content = response.choices[0].message.content.strip()
        
        # 提取JSON部分
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
                
                # 验证所有问题都有答案
                required_keys = [
                    "q1_main_content", "q2_problem", "q3_related_work",
                    "q4_solution", "q5_experiments", "q6_future_work"
                ]
                
                for key in required_keys:
                    if key not in result or not result[key]:
                        result[key] = "未提供答案"
                
                # 添加论文基本信息
                result.update({
                    'paper_title': paper_title,
                    'paper_abstract': paper_abstract,
                    'paper_url': paper_url,
                    'paper_id': paper_id,
                    'analysis_time': datetime.now().isoformat(),
                    'llm_provider': provider,
                    'pdf_used': pdf_path is not None
                })
                
                # 如果是DeepSeek R1，添加推理过程
                if provider == "deepseek" and reasoning_content:
                    result["reasoning_process"] = reasoning_content
                
                # 保存分析结果
                if save_results and paper_id:
                    save_analysis_result(result, paper_id)
                
                return result
            else:
                logging.warning("未找到JSON格式，尝试解析文本")
                return _parse_text_response(content)
                
        except json.JSONDecodeError as e:
            logging.warning(f"JSON解析失败: {e}，尝试解析文本")
            return _parse_text_response(content)
            
    except Exception as e:
        logging.error(f"LLM分析论文失败: {e}")
        return {}

def _parse_text_response(content: str) -> Dict:
    """从LLM的文本响应中解析答案"""
    try:
        # 尝试从文本中提取答案
        lines = content.split('\n')
        result = {}
        
        # 简单的文本解析逻辑
        current_question = None
        current_answer = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检查是否是问题
            if any(q in line.lower() for q in ["主要内容", "问题", "相关研究", "解决方案", "实验", "探索"]):
                # 保存之前的答案
                if current_question and current_answer:
                    result[current_question] = " ".join(current_answer).strip()
                
                # 开始新问题
                if "主要内容" in line:
                    current_question = "q1_main_content"
                elif "问题" in line:
                    current_question = "q2_problem"
                elif "相关研究" in line:
                    current_question = "q3_related_work"
                elif "解决方案" in line:
                    current_question = "q4_solution"
                elif "实验" in line:
                    current_question = "q5_experiments"
                elif "探索" in line:
                    current_question = "q6_future_work"
                
                current_answer = []
            else:
                # 累积答案内容
                if current_question:
                    current_answer.append(line)
        
        # 保存最后一个答案
        if current_question and current_answer:
            result[current_question] = " ".join(current_answer).strip()
        
        # 确保所有问题都有答案
        required_keys = [
            "q1_main_content", "q2_problem", "q3_related_work",
            "q4_solution", "q5_experiments", "q6_future_work"
        ]
        
        for key in required_keys:
            if key not in result:
                result[key] = "无法解析答案"
        
        return result
        
    except Exception as e:
        logging.error(f"文本解析失败: {e}")
        return {
            "q1_main_content": "解析失败",
            "q2_problem": "解析失败",
            "q3_related_work": "解析失败",
            "q4_solution": "解析失败",
            "q5_experiments": "解析失败",
            "q6_future_work": "解析失败"
        }

# ==================== 论文相关性分析 ====================
def analyze_paper_relevance(paper_title: str, paper_abstract: str, research_areas: Dict[str, str]) -> Dict:
    """
    使用LLM分析论文与研究领域的相关性
    
    Args:
        paper_title: 论文标题
        paper_abstract: 论文摘要
        research_areas: 研究领域定义
    
    Returns:
        Dict: 包含相关性分析结果的字典
    """
    try:
        # 根据配置选择客户端
        config = get_config()
        provider = config.get("llm", {}).get("provider", "deepseek")
        
        if provider == "deepseek":
            client = get_deepseek_client()
        elif provider == "kimi":
            client = get_kimi_client()
        elif provider == "openai":
            client = get_openai_client()
        else:
            logging.error(f"不支持的LLM提供商: {provider}")
            return {}
        
        if not client:
            logging.error("无法获取LLM客户端")
            return {}
        
        # 构建研究领域描述
        areas_description = "\n".join([f"- {area}: {desc}" for area, desc in research_areas.items()])
        
        prompt = f"""
请分析以下论文与我们关注的研究领域的相关性。

论文标题: {paper_title}
论文摘要: {paper_abstract}

我们关注的研究领域:
{areas_description}

请分析这篇论文是否与我们的研究领域相关，并给出相关性评分（0-10分，10分表示高度相关）。

请按以下JSON格式输出:
{{
    "relevance_score": 相关性评分(0-10),
    "relevance_reasoning": "相关性分析推理过程",
    "best_match_area": "最匹配的研究领域",
    "is_relevant": true/false,
    "summary": "论文内容简要总结"
}}

注意:
1. 必须严格按照JSON格式输出
2. 相关性评分要客观准确
3. 推理过程要详细说明判断依据
4. 如果论文涉及硬件、芯片设计、电路等非AI算法内容，请给出较低评分
"""
        
        # 根据提供商构建不同的API调用参数
        if provider == "deepseek":
            # DeepSeek R1特殊处理
            api_params = {
                "model": get_api_config_with_scenario("paper_relevance")["model"],
                "messages": [
                    {"role": "system", "content": "你是一个专业的AI研究论文分析专家，擅长判断论文与研究领域的相关性。请严格按照要求的JSON格式输出。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": get_api_config_with_scenario("paper_relevance").get("max_tokens", 32000)
                # 注意：DeepSeek R1不支持temperature、top_p等参数
            }
        else:
            # 其他提供商使用标准参数
            api_params = {
                "model": get_api_config_with_scenario("paper_relevance")["model"],
                "messages": [
                    {"role": "system", "content": "你是一个专业的AI研究论文分析专家，擅长判断论文与研究领域的相关性。请严格按照要求的JSON格式输出。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": get_temperature_for_scenario("paper_relevance"),
                "max_tokens": get_api_config_with_scenario("paper_relevance").get("max_tokens", 4000)
            }
        
        # 调用LLM
        response = client.chat.completions.create(**api_params)
        
        # 记录token使用量
        if hasattr(response, 'usage') and response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            model_name = get_api_config_with_scenario("paper_relevance")["model"] if get_api_config_with_scenario("paper_relevance") else "unknown"
            token_tracker.add_usage(input_tokens, output_tokens, model_name)
        
        # 解析响应
        if provider == "deepseek":
            # DeepSeek R1特殊处理：同时获取reasoning_content和content
            reasoning_content = getattr(response.choices[0].message, 'reasoning_content', None)
            content = response.choices[0].message.content.strip()
            
            if reasoning_content:
                logging.info(f"DeepSeek R1推理过程: {reasoning_content[:200]}...")
        else:
            content = response.choices[0].message.content.strip()
        
        # 提取JSON部分
        try:
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
                
                # 验证必要字段
                required_keys = ["relevance_score", "relevance_reasoning", "best_match_area", "is_relevant", "summary"]
                for key in required_keys:
                    if key not in result:
                        result[key] = "未提供"
                
                # 如果是DeepSeek R1，添加推理过程
                if provider == "deepseek" and reasoning_content:
                    result["reasoning_process"] = reasoning_content
                
                return result
            else:
                logging.warning("未找到JSON格式，尝试解析文本")
                return _parse_relevance_text_response(content)
                
        except json.JSONDecodeError as e:
            logging.warning(f"JSON解析失败: {e}，尝试解析文本")
            return _parse_relevance_text_response(content)
            
    except Exception as e:
        logging.error(f"LLM分析论文相关性失败: {e}")
        return {}

def _parse_relevance_text_response(content: str) -> Dict:
    """从LLM的文本响应中提取相关性信息"""
    try:
        # 尝试找到相关性分数
        import re
        score_match = re.search(r'相关性.*?(\d+\.?\d*)', content)
        relevance_score = float(score_match.group(1)) if score_match else 0.5
        
        # 尝试找到最佳匹配领域
        best_area = "未知"
        for area in research_areas.keys():
            if area in content:
                best_area = area
                break
        
        # 提取推理过程
        reasoning = content.split('\n')[-1] if content else "无法提取推理过程"
        
        return {
            "relevance_score": relevance_score,
            "relevance_reasoning": reasoning,
            "best_match_area": best_area,
            "is_relevant": relevance_score > 5, # 假设分数大于5表示相关
            "summary": content.split('\n')[-1] if content else "无法提取摘要"
        }
        
    except Exception as e:
        logging.warning(f"从文本提取相关性信息失败: {e}")
        return {
            "relevance_score": 0.5,
            "relevance_reasoning": "无法提取信息",
            "best_match_area": "未知",
            "is_relevant": False,
            "summary": "无法提取摘要"
        }

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

def save_analysis_result(result: Dict, paper_id: str):
    """
    保存分析结果到文件
    
    Args:
        result: 分析结果字典
        paper_id: 论文ID
    """
    try:
        # 创建保存目录
        today = datetime.now().strftime("%y%m%d")
        save_dir = os.path.join(PAPER_DATA_DIR, today, "analysis_results")
        os.makedirs(save_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"analysis_{paper_id}_{timestamp}.json"
        filepath = os.path.join(save_dir, filename)
        
        # 保存结果
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logging.info(f"分析结果已保存: {filepath}")
        
        # 同时保存到汇总文件（追加模式）
        summary_file = os.path.join(save_dir, f"analysis_summary_{today}.json")
        save_to_summary_file(result, summary_file)
        
    except Exception as e:
        logging.error(f"保存分析结果失败: {e}")

def save_to_summary_file(result: Dict, summary_file: str):
    """
    将分析结果追加到汇总文件
    
    Args:
        result: 分析结果字典
        summary_file: 汇总文件路径
    """
    try:
        # 读取现有汇总文件
        existing_results = []
        if os.path.exists(summary_file):
            try:
                with open(summary_file, 'r', encoding='utf-8') as f:
                    existing_results = json.load(f)
                if not isinstance(existing_results, list):
                    existing_results = []
            except Exception as e:
                logging.warning(f"读取汇总文件失败: {e}，将创建新文件")
                existing_results = []
        
        # 检查是否已存在相同论文ID的结果
        paper_id = result.get('paper_id')
        if paper_id:
            # 移除旧的结果
            existing_results = [r for r in existing_results if r.get('paper_id') != paper_id]
        
        # 添加新结果
        existing_results.append(result)
        
        # 保存汇总文件
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(existing_results, f, ensure_ascii=False, indent=2)
        
        logging.info(f"分析结果已追加到汇总文件: {summary_file} (总计: {len(existing_results)} 篇)")
        
    except Exception as e:
        logging.error(f"保存到汇总文件失败: {e}")

def load_analysis_results(date_str: str = None) -> List[Dict]:
    """
    加载指定日期的分析结果
    
    Args:
        date_str: 日期字符串（格式：YYMMDD），如果为None则使用今天
    
    Returns:
        List[Dict]: 分析结果列表
    """
    try:
        if not date_str:
            date_str = datetime.now().strftime("%y%m%d")
        
        summary_file = os.path.join(PAPER_DATA_DIR, date_str, "analysis_results", f"analysis_summary_{date_str}.json")
        
        if not os.path.exists(summary_file):
            logging.info(f"汇总文件不存在: {summary_file}")
            return []
        
        with open(summary_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        logging.info(f"成功加载分析结果: {summary_file} (总计: {len(results)} 篇)")
        return results
        
    except Exception as e:
        logging.error(f"加载分析结果失败: {e}")
        return []

def main_paper_analysis():
    """
    主要的论文分析函数 - 优化版本，减少token消耗
    """
    try:
        # 加载论文数据
        papers = load_paper_data()
        if not papers:
            logging.warning("没有找到论文数据")
            return
        
        logging.info(f"开始分析 {len(papers)} 篇论文")
        
        # 获取当前日期
        date_str = datetime.now().strftime("%y%m%d")
        
        # 创建分析结果目录
        analysis_dir = f"./{date_str}/paper_analysis"
        os.makedirs(analysis_dir, exist_ok=True)
        
        all_analysis_results = []
        
        for i, paper in enumerate(papers, 1):
            try:
                logging.info(f"分析论文 {i}/{len(papers)}: {paper.get('title', 'Unknown')[:50]}...")
                
                # 使用优化的分析方法，一次性回答所有问题
                analysis_result = analyze_paper_with_questions(
                    paper_title=paper.get('title', ''),
                    paper_abstract=paper.get('abstract', ''),
                    paper_url=paper.get('url'), # 传递URL
                    paper_id=paper.get('id'), # 传递ID
                    save_results=True # 保存结果
                )
                
                if analysis_result:
                    # 添加论文基本信息
                    analysis_result.update({
                        'paper_id': paper.get('id', ''),
                        'paper_title': paper.get('title', ''),
                        'paper_url': paper.get('url', ''),
                        'analysis_time': datetime.now().isoformat(),
                        'llm_provider': get_api_config_with_scenario("paper_analysis")["model"] if get_api_config_with_scenario("paper_analysis") else "unknown"
                    })
                    
                    all_analysis_results.append(analysis_result)
                    
                    # 保存单篇论文的分析结果
                    paper_filename = f"paper_analysis_{paper.get('id', f'paper_{i}')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    paper_filepath = os.path.join(analysis_dir, paper_filename)
                    
                    with open(paper_filepath, 'w', encoding='utf-8') as f:
                        json.dump(analysis_result, f, ensure_ascii=False, indent=2)
                    
                    logging.info(f"论文分析完成: {paper_filename}")
                    
                    # 添加延迟避免API限制
                    time.sleep(2)
                else:
                    logging.warning(f"论文 {i} 分析失败")
                
            except Exception as e:
                logging.error(f"分析论文 {i} 时出错: {e}")
                continue
        
        # 保存所有分析结果
        if all_analysis_results:
            all_results_filename = f"all_paper_analysis_{date_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            all_results_filepath = os.path.join(analysis_dir, all_results_filename)
            
            with open(all_results_filepath, 'w', encoding='utf-8') as f:
                json.dump(all_analysis_results, f, ensure_ascii=False, indent=2)
            
            logging.info(f"所有论文分析完成，结果保存到: {all_results_filepath}")
            logging.info(f"成功分析 {len(all_analysis_results)} 篇论文")
        else:
            logging.warning("没有成功分析的论文")
        
        # 显示和保存token使用量统计
        token_tracker.print_summary()
        token_usage_filename = os.path.join(analysis_dir, f"token_usage_{date_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        token_tracker.save_summary(token_usage_filename)
            
    except Exception as e:
        logging.error(f"论文分析过程中出错: {e}")
        # 即使出错也要显示token统计
        token_tracker.print_summary()
        raise

# ==================== Token统计相关函数 ====================
def get_token_usage_summary() -> Dict:
    """获取当前token使用量摘要"""
    return token_tracker.get_summary()

def print_token_usage_summary():
    """打印当前token使用量摘要"""
    token_tracker.print_summary()

def save_token_usage_summary(filename: str = None):
    """保存当前token使用量摘要到文件"""
    token_tracker.save_summary(filename)

def reset_token_tracker():
    """重置token跟踪器"""
    global token_tracker
    token_tracker = TokenUsageTracker()
    logging.info("Token跟踪器已重置")

# ==================== PDF处理函数 ====================
def download_pdf(url: str, paper_id: str, pdf_dir: str = None) -> Optional[str]:
    """
    下载PDF文件
    
    Args:
        url: 论文URL
        paper_id: 论文ID
        pdf_dir: PDF保存目录，如果为None则使用默认目录
    
    Returns:
        str: PDF文件路径，如果下载失败返回None
    """
    try:
        if not pdf_dir:
            # 使用默认目录
            today = datetime.now().strftime("%y%m%d")
            pdf_dir = os.path.join(PAPER_DATA_DIR, today, "pdf_downloads")
        
        # 确保目录存在
        os.makedirs(pdf_dir, exist_ok=True)
        
        pdf_path = os.path.join(pdf_dir, f"{paper_id}.pdf")
        
        # 如果文件已存在，直接返回路径
        if os.path.exists(pdf_path):
            logging.info(f"PDF文件已存在: {pdf_path}")
            return pdf_path
        
        # 将abs链接转换为pdf链接
        pdf_url = url.replace('/abs/', '/pdf/') + '.pdf'
        logging.info(f"正在下载PDF: {pdf_url}")
        
        # 设置请求头，模拟浏览器
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(pdf_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 检查内容类型
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not response.content.startswith(b'%PDF'):
            logging.warning(f"下载的文件可能不是PDF: {content_type}")
        
        with open(pdf_path, 'wb') as f:
            f.write(response.content)
        
        logging.info(f"PDF下载成功: {pdf_path} (大小: {len(response.content)} bytes)")
        return pdf_path
        
    except Exception as e:
        logging.error(f"下载PDF失败 {paper_id}: {e}")
        return None

def encode_pdf_to_base64(pdf_path: str) -> Optional[str]:
    """
    将PDF文件编码为base64字符串
    
    Args:
        pdf_path: PDF文件路径
    
    Returns:
        str: base64编码的PDF内容，如果失败返回None
    """
    try:
        if not os.path.exists(pdf_path):
            logging.error(f"PDF文件不存在: {pdf_path}")
            return None
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        # 检查文件大小
        file_size_mb = len(pdf_content) / (1024 * 1024)
        if file_size_mb > 10:  # 如果PDF大于10MB，给出警告
            logging.warning(f"PDF文件较大 ({file_size_mb:.1f}MB)，可能影响API调用")
        
        # 编码为base64
        base64_content = base64.b64encode(pdf_content).decode('utf-8')
        logging.info(f"PDF编码成功: {pdf_path} -> base64 (长度: {len(base64_content)} 字符)")
        
        return base64_content
        
    except Exception as e:
        logging.error(f"PDF编码失败 {pdf_path}: {e}")
        return None

def create_file_upload_message(pdf_path: str, filename: str = None) -> Dict:
    """
    创建文件上传消息（用于支持文件上传的API）
    
    Args:
        pdf_path: PDF文件路径
        filename: 文件名，如果为None则使用原文件名
    
    Returns:
        Dict: 文件上传消息
    """
    try:
        if not filename:
            filename = os.path.basename(pdf_path)
        
        # 读取文件内容
        with open(pdf_path, 'rb') as f:
            file_content = f.read()
        
        # 创建文件上传消息
        file_message = {
            "type": "file",
            "file": {
                "name": filename,
                "content": file_content,
                "mime_type": "application/pdf"
            }
        }
        
        logging.info(f"文件上传消息创建成功: {filename}")
        return file_message
        
    except Exception as e:
        logging.error(f"创建文件上传消息失败 {pdf_path}: {e}")
        return {}

# ==================== 主执行流程 ====================
if __name__ == '__main__':
    main_paper_analysis()