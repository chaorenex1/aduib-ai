"""
deepseek r2 nlp module
"""
from backend.core.util.factory import auto_register
from backend.model.llm.nlp.base_nlp import AbstractNlp, TaskType, PromptTaskType
from backend.core.serving.ollama import OllamaServing
import logging as log


@auto_register('ds_r2_nlp')
class DsR2Nlp(AbstractNlp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path'] if 'model_path' in kwargs else None

    def generate(self, task: TaskType,text:str, **kwargs):
        """
        :param task:
        :param text:
        :param kwargs:
        :return: result
        """
        text = PromptTaskType.create_task(task, text=text, **kwargs)
        kwargs['messages'] = [{'role': 'user', 'content': text},{'role': 'system', 'content': '您是一个nlp助手，请执行以下 {NLP任务}，并提供准确的结果：\n任务类型：{文本分类 / 关键词抽取 / 摘要生成 / 标题生成 / 评价对象抽取 / 机器翻译 / 情感分析 / 问题生成} \n输入文本：{待处理的文本} \n输出格式：仅返回关键结果，不包含额外解释'}]
        if kwargs.get('model') is None:
            kwargs['model'] = 'deepseek-r1:14b'
        #模型参数
        kwargs['options'] = {
            'temperature': 0.7,
            'top_p': 0.5,
            # 'top_k': 50,
        }
        params={
            'model':kwargs['model'],
            'messages': kwargs['messages'],
            'options': kwargs['options']
        }
        res = OllamaServing(**kwargs).chat(**params)
        """
        关键词提取结果：
            - 中文分词
            - Jieba库
            - 深度学习
            - BPE
            - SentencePiece
            - LLM（大语言模型）
            - 性能
            - 准确性
            - 资源需求
            - 无空格语言
        """
        content = res.message.content
        #取出</think>标签后的内容
        if '</think>' in content:
            content = content.split('</think>')[1]
        log.info(f"task:{task},text:{content}")
        return {'text': content}