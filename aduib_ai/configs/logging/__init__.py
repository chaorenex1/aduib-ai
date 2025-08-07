from pydantic import Field
from pydantic_settings import BaseSettings

class LoggingConfig(BaseSettings):
    LOG_LEVEL:str = Field(default="INFO",description="Log level")
    LOG_FORMAT:str = Field(default="%(asctime)s.%(msecs)03d %(levelname)s [%(threadName)s] [%(filename)s:%(lineno)d] - %(message)s",description="Log format")
    LOG_TZ:str = Field(default="UTC",description="Log timezone")