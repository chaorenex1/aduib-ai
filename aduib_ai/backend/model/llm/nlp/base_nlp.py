"""
创建枚举类，用于定义任务类型
文本分类，抽取关键词，生成标题，生成摘要，评价对象抽取，翻译成英文，情感分析，根据给定的段落和答案生成对应的问题
"""
from abc import abstractmethod
from enum import Enum

from backend.base_model import BaseModel


class TaskType(Enum):
    TEXT_CLASSIFICATION = "文本分类"
    EXTRACT_KEYWORDS = "抽取关键词"
    GENERATE_TITLE = "生成标题"
    GENERATE_SUMMARY = "生成摘要"
    EXTRACT_OBJECT = "评价对象抽取"
    TRANSLATE = "翻译成"
    SENTIMENT_ANALYSIS = "情感分析"
    GENERATE_QUESTION = "根据给定的段落和答案生成对应的问题"

    def __str__(self):
        return self.value

    @staticmethod
    def get_task_type(task_type: str):
        for task in TaskType:
            if task.value == task_type:
                return task
        return None

    @staticmethod
    def get_task_types():
        return [task.value for task in TaskType]

    @staticmethod
    def get_task_type_by_index(index):
        return list(TaskType)[index]

    @staticmethod
    def create_task(task_type: Enum, **kwargs):
        if task_type == TaskType.TEXT_CLASSIFICATION:
            labels = ""
            for label in kwargs['labels']:
                labels += label + ","
            labels = labels[:-1]
            return task_type.value+ "：\n候选标签："+labels+ "\n文本内容："+kwargs['text']
        elif task_type == TaskType.EXTRACT_KEYWORDS:
            return task_type.value+ "：\n"+kwargs['text']
        elif task_type == TaskType.GENERATE_TITLE:
            return task_type.value+ "：\n"+kwargs['text']
        elif task_type == TaskType.GENERATE_SUMMARY:
            return task_type.value+ "：\n"+kwargs['text']
        elif task_type == TaskType.EXTRACT_OBJECT:
            return task_type.value+ "：\n"+kwargs['text']
        elif task_type == TaskType.TRANSLATE:
            return task_type.value+kwargs['lang']+ "：\n"+kwargs['text']
        elif task_type == TaskType.SENTIMENT_ANALYSIS:
            return task_type.value+ "：\n"+kwargs['text']
        elif task_type == TaskType.GENERATE_QUESTION:
            return task_type.value+ "：\n"+kwargs['text']
        return None

class PromptTaskType:

    @staticmethod
    def get_task_type(task_type: str):
        for task in TaskType:
            if task.value == task_type:
                return task
        return None

    @staticmethod
    def get_task_types():
        return [task.value for task in TaskType]

    @staticmethod
    def get_task_type_by_index(index):
        return list(TaskType)[index]

    @staticmethod
    def create_task(task_type: Enum, **kwargs):
        if task_type == TaskType.TEXT_CLASSIFICATION:
            labels = ""
            for label in kwargs['labels']:
                labels += label + ","
            labels = labels[:-1]
            return f"任务：文本分类  \n候选类别："+labels+f"  \n输入文本：{kwargs['text']}  \n"
        elif task_type == TaskType.EXTRACT_KEYWORDS:
            return f"任务：抽取关键词  \n输入文本：{kwargs['text']}  \n"
        elif task_type == TaskType.GENERATE_TITLE:
            return f"任务：生成标题  \n输入文本：{kwargs['text']}  \n"
        elif task_type == TaskType.GENERATE_SUMMARY:
            return f"任务：生成摘要  \n输入文本：{kwargs['text']}  \n"
        elif task_type == TaskType.EXTRACT_OBJECT:
            return f"任务：评价对象抽取  \n输入文本：{kwargs['text']}  \n"
        elif task_type == TaskType.TRANSLATE:
            return f"任务：翻译成{kwargs['lang']}  \n输入文本："+kwargs['text']+"  \n"
        elif task_type == TaskType.SENTIMENT_ANALYSIS:
            return f"任务：情感分析  \n输入文本：{kwargs['text']}  \n"
        elif task_type == TaskType.GENERATE_QUESTION:
            return f"任务：根据给定的段落和答案生成对应的问题  \n输入文本：{kwargs['text']}  \n"
        return None



"""
定义NLP基类
"""
class AbstractNlp(BaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path'] if 'model_path' in kwargs else None
        pass

    @abstractmethod
    def generate(self, task: TaskType,text:str, **kwargs):
        pass



