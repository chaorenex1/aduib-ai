from modelscope.pipelines import pipeline

from backend.core.util.factory import auto_register
import logging as log
#
# t2t_generator = pipeline("text2text-generation", "L:\\llmmodels\\nlp_mt5_zero-shot-augment_chinese-base", model_revision="v1.0.0")
#
# print(t2t_generator("文本分类。\n候选标签：故事,房产,娱乐,文化,游戏,国际,股票,科技,军事,教育。\n文本内容：他们的故事平静而闪光，一代人奠定沉默的基石，让中国走向繁荣。"))
# # {'text': '文化'}
#
# print(t2t_generator("抽取关键词：\n在分析无线Mesh网路由协议所面临挑战的基础上,结合无线Mesh网络的性能要求,以优化链路状态路由(OLSR)协议为原型,采用跨层设计理论,提出了一种基于链路状态良好程度的路由协议LR-OLSR.该协议引入了认知无线网络中的环境感知推理思想,通过时节点负载、链路投递率和链路可用性等信息进行感知,并以此为依据对链路质量进行推理,获得网络中源节点和目的节点对之间各路径状态良好程度的评价,将其作为路由选择的依据,实现对路由的优化选择,提高网络的吞吐量,达到负载均衡.通过与OLSR及其典型改进协议P-OLSR、SC-OLSR的对比仿真结果表明,LR-OLSB能够提高网络中分组的递交率,降低平均端到端时延,在一定程度上达到负载均衡."))
# # {'text': '无线Mesh网,路由协议,环境感知推理'}
#
# print(t2t_generator("为以下的文本生成标题：\n在分析无线Mesh网路由协议所面临挑战的基础上,结合无线Mesh网络的性能要求,以优化链路状态路由(OLSR)协议为原型,采用跨层设计理论,提出了一种基于链路状态良好程度的路由协议LR-OLSR.该协议引入了认知无线网络中的环境感知推理思想,通过时节点负载、链路投递率和链路可用性等信息进行感知,并以此为依据对链路质量进行推理,获得网络中源节点和目的节点对之间各路径状态良好程度的评价,将其作为路由选择的依据,实现对路由的优化选择,提高网络的吞吐量,达到负载均衡.通过与OLSR及其典型改进协议P-OLSR、SC-OLSR的对比仿真结果表明,LR-OLSB能够提高网络中分组的递交率,降低平均端到端时延,在一定程度上达到负载均衡."))
# # {'text': '基于链路状态良好程度的无线Mesh网路由协议'}
#
# print(t2t_generator("为下面的文章生成摘要：\n据统计，今年三季度大中华区共发生58宗IPO交易，融资总额为60亿美元，交易宗数和融资额分别占全球的35%和25%。报告显示，三季度融资额最高的三大证券交易所分别为东京证券交易所、深圳证券交易所和马来西亚证券交易所"))
# # {'text': '大中华区IPO融资额超60亿美元'}
#
# print(t2t_generator("评价对象抽取：颐和园还是挺不错的，作为皇家园林，有山有水，亭台楼阁，古色古香，见证着历史的变迁。"))
# # {'text': '颐和园'}
#
# print(t2t_generator("翻译成英文：如果日本沉没，中国会接收日本难民吗？"))
# # {'text': 'will China accept Japanese refugees if Japan sinks?'}
#
# print(t2t_generator("情感分析：外观漂亮，性能不错，屏幕很好。"))
# # {'text': '积极'}
#
# print(t2t_generator("根据给定的段落和答案生成对应的问题。\n段落：跑步后不能马上进食，运动与进食的时间要间隔30分钟以上。看你跑步的量有多大。不管怎么样，跑完步后要慢走一段时间，将呼吸心跳体温调整至正常状态才可进行正常饮食。血液在四肢还没有回流到内脏，不利于消化，加重肠胃的负担。如果口渴可以喝一点少量的水。洗澡的话看你运动量。如果跑步很剧烈，停下来以后，需要让身体恢复正常之后，再洗澡，能达到放松解乏的目的，建议15-20分钟后再洗澡；如果跑步不是很剧烈，只是慢跑，回来之后可以马上洗澡。 \n 答案：30分钟以上"))
# # {'text': '跑步后多久进食'}
from backend.model.llm.nlp.base_nlp import AbstractNlp, TaskType

@auto_register('mt5_nlp')
class MT5Nlp(AbstractNlp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path'] if 'model_path' in kwargs else None
        self.model = pipeline("text2text-generation", self.model_path, model_revision="v1.0.0")

    def generate(self,task, text, **kwargs):
        """
        :param task:
        :param text:
        :param kwargs:
        :return:
        """
        text = TaskType.create_task(task, text=text)
        res = self.model(text)
        log.info(f"task:{task},text:{res}")
        return res



# if __name__ == '__main__':
#     nlp = MT5Nlp("L:\\llmmodels\\nlp_mt5_zero-shot-augment_chinese-base")
#     print(nlp.generate(TaskType.TEXT_CLASSIFICATION,"文本内容：他们的故事平静而闪光，一代人奠定沉默的基石，让中国走向繁荣。",labels=["故事","房产","娱乐","文化","游戏","国际","股票","科技","军事","教育"]))
#     # {'text': '文化'}
#     print(nlp.generate(TaskType.EXTRACT_KEYWORDS,"在分析无线Mesh网路由协议所面临挑战的基础上,结合无线Mesh网络的性能要求,以优化链路状态路由(OLSR)协议为原型,采用跨层设计理论,提出了一种基于链路状态良好程度的路由协议LR-OLSR.该协议引入了认知无线网络中的环境感知推理思想,通过时节点负载、链路投递率和链路可用性等信息进行感知,并以此为依据对链路质量进行推理,获得网络中源节点和目的节点对之间各路径状态良好程度的评价,将其作为路由选择的依据,实现对路由的优化选择,提高网络的吞吐量,达到负载均衡.通过与OLSR及其典型改进协议P-OLSR、SC-OLSR的对比仿真结果表明,LR-OLSB能够提高网络中分组的递交率,降低平均端到端时延,在一定程度上达到负载均衡."))
#     # {'text': '无线Mesh网,路由协议,环境感知推理'}