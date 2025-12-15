from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from configs import config

engine = create_engine(
    config.DATABASE_URI,
    pool_size=config.POOL_SIZE,
    max_overflow=20,  # 允许超过 pool_size 的额外连接数
    pool_recycle=3600,  # 1小时后回收连接，避免使用过期连接
    pool_pre_ping=True,  # 每次从池中获取连接前先测试连接是否有效
    pool_timeout=30,  # 从池中获取连接的超时时间（秒）
    echo_pool=False,  # 生产环境关闭连接池日志
    connect_args={
        "connect_timeout": 10,  # 数据库连接超时（秒）
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency
def get_session() -> Session:
    """创建一个新的数据库会话。调用者负责关闭会话。"""
    return SessionLocal()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    提供数据库会话的上下文管理器。
    自动处理会话的创建、提交、回滚和关闭。
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()  # 如果没有异常，提交事务
    except Exception:
        session.rollback()  # 出现异常时回滚
        raise
    finally:
        session.close()  # 确保会话被关闭
