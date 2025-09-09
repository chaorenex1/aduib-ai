from typing import Optional

from models import get_db, ApiKey
from service.error.error import ApiKeyNotFound


class WebMemoService:

    @classmethod
    async def handle_web_memo(cls,data:dict[str,str]):
        """
        Handle web memo by fetching and processing the content from the given URL.
        :param data: Dictionary containing the URL and other relevant information.
        :return: Processed content as a string.
        """
        url = data.get("url")
        ua = data.get("user_agent")
        with get_db() as session:
            api_key:Optional[ApiKey] = session.query(ApiKey).filter(ApiKey.source == 'aduib_mcp_server').first()
            if not api_key:
                raise ApiKeyNotFound

        try:
            ...
        except Exception as e:
            raise RuntimeError(f"Error fetching web memo: {e}")