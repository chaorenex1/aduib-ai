from typing import Any, Optional

from models.api_key import ApiKey
from models.auth_user import User
from models.engine import get_db
from utils.api_key import generate_api_key, hash_api_key, verify_api_key

from .error.error import ApiKeyNotFound


class ApiKeyService:
    """
    Api Key Service
    """

    @staticmethod
    def validate_api_key(api_hash_key: str) -> Optional[dict[str, Any]]:
        """
        validate the api key
        """
        with get_db() as session:
            api_Key_model = session.query(ApiKey).filter(ApiKey.hash_key == api_hash_key).first()
            if not api_Key_model:
                raise ApiKeyNotFound("Api Key not correct")
            if api_Key_model.hash_key != api_hash_key:
                raise ApiKeyNotFound("Api Key not correct")
            if verify_api_key(api_Key_model.api_key, api_hash_key):
                user: User = session.query(User).filter(User.id == api_Key_model.user_id).first()
                if not user:
                    raise ApiKeyNotFound("Api Key not correct")
                else:
                    return {
                        "user_id": str(user.id),
                        "username": user.username,
                        "user_type": user.user_type,
                    }
            else:
                raise ApiKeyNotFound("Api Key not correct")

    @staticmethod
    def create_api_key(name: str, description: Optional[str]) -> ApiKey:
        """
        create the api key
        """
        with get_db() as session:
            key = generate_api_key()
            hash_key = hash_api_key(key)
            api_key = ApiKey(api_key=key, hash_key=hash_key[0], salt=hash_key[1], name=name, description=description)
            session.add(api_key)
            session.commit()
        return api_key

    @staticmethod
    def get_by_api_key(api_key: str) -> Optional[ApiKey]:
        """
        get the api key by hash key
        """
        with get_db() as session:
            return session.query(ApiKey).filter(ApiKey.api_key == api_key).first()

    @staticmethod
    def get_by_hash_key(api_hash_key: str) -> Optional[ApiKey]:
        """
        get the api key by hash key
        """
        with get_db() as session:
            return session.query(ApiKey).filter(ApiKey.hash_key == api_hash_key).first()

    @staticmethod
    def delete_by_apy_key(api_key: str):
        """
        delete the api key
        """
        with get_db() as session:
            session.delete(session.query(ApiKey).filter(ApiKey.api_key == api_key).first())
            session.commit()

    @staticmethod
    def delete_by_hash_key(api_hash_key: str):
        """
        delete the api key
        """
        with get_db() as session:
            session.delete(session.query(ApiKey).filter(ApiKey.hash_key == api_hash_key).first())
            session.commit()
