"""
根据类型创建对象
"""
import importlib
import logging
import pkgutil


class Factory:
    _class_map = {}
    _instance_map = {}

    @classmethod
    def register_class(cls, name, class_ref):
        """注册类"""
        cls._class_map[name] = class_ref

    @classmethod
    def create_instance(cls, class_name, *args, **kwargs):
        """创建对象"""
        if class_name in cls._instance_map:
            return cls._instance_map[class_name]
        if class_name not in cls._class_map:
            raise ValueError(f"Class '{class_name}' not registered.")
        obj = cls._class_map[class_name](*args, **kwargs)
        cls._instance_map[class_name] = obj
        return obj

    @classmethod
    def get_instance(cls, class_name, *args, **kwargs):
        """获取对象"""
        if class_name in cls._instance_map:
            return cls._instance_map[class_name]
        if class_name not in cls._class_map:
            raise ValueError(f"Class '{class_name}' not registered.")
        obj = cls._class_map[class_name](*args, **kwargs)
        cls._instance_map[class_name] = obj
        return obj

    @classmethod
    def push_instance(cls, class_name, instance):
        """推送对象"""
        cls._instance_map[class_name] = instance

    @classmethod
    def check_exist(cls, class_name):
        """检查是否存在"""
        return class_name in cls._class_map

    #清空注册的类
    @classmethod
    def clear(cls):
        cls._class_map = {}
        cls._instance_map = {}


# **自动注册装饰器**
def auto_register(name):
    """自动注册装饰器"""
    logging.info(f"Auto registering {name}")
    def decorator(cls):
        Factory.register_class(name, cls)
        return cls  # 返回原始类，不影响类的使用
    return decorator

def auto_register_modules(package_name):
    """
    自动注册模块
    解析package_name下的所有目录，并自动注册带有auto_register的模块
    package_name: 包名
    格式1为: backend.core.serving 具体到包名
    格式2为: backend.core.serving.ollama 具体到模块名
    格式3为: backend.core.serving.ollama.OllamaServing 具体到类名
    格式4为: backend.core.serving.ollama.OllamaServing.chat 具体到方法名
    格式5为: backend.**.serving.**.** 规则为: **表示任意目录或文件名
    """

    package = importlib.import_module(package_name)
    for _, module_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        if is_pkg:
            auto_register_modules(module_name)
        else:
            module = importlib.import_module(module_name)
            # 遍历模块中的所有属性，找到带有auto_register的类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if hasattr(attr, '__class__') and attr.__class__.__name__ == 'type' and hasattr(attr, 'auto_register'):
                    if Factory.check_exist(attr_name):
                        logging.warning(f"Class '{attr_name}' already registered.")
                        continue
                    auto_register(attr_name)(attr)
                    logging.info(f"Auto registered {attr_name} from {module_name}")
            logging.info(f"Auto registered {module_name}")


