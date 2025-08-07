import jieba
import jieba.analyse
import jieba.posseg

from backend.core.util.factory import auto_register


@auto_register('jieba_tokenizer')
class JiebaTokenizer:
    #1. 分词
    def cut(self,text:str,search_enable=False)->list[str]:
        """
        使用 jieba 分词
        :param text: 文本
        :param search_enable: 是否支持搜索
        :return: 分词结果
        """
        if search_enable:
            return jieba.cut_for_search(text)
        return jieba.cut(text)

    #2. 关键字提取 TF-IDF
    def extract_tfidf(self,text:str,topK:int=5)->list[str]:
        """
        使用 jieba 提取关键字
        :param text: 文本
        :param topK: 返回关键字数量
        :return: 关键字
        """
        return jieba.analyse.extract_tags(text, topK=topK)


    #3. 关键字提取 TextRank
    def extract_textrank(self,text:str,topK:int=5)->list[str]:
        """
        使用 jieba 提取关键字
        :param text: 文本
        :param topK: 返回关键字数量
        :return: 关键字
        """
        return jieba.analyse.textrank(text, topK=topK)

    #4. 词性标注
    def posseg(self,text:str)->list[tuple[str,str]]:
        """
        使用 jieba 词性标注
        :param text: 文本
        :return: 词性标注结果
        """
        return jieba.posseg.lcut(text)