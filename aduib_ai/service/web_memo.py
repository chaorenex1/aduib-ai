from typing import Optional

from aduib_rpc.utils.net_utils import NetUtils

from models import get_db, ApiKey
from models.browser import BrowserHistory
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
            from configs import config
            from rpc.client import CrawlService
            host,port = NetUtils.get_ip_and_free_port()
            notify_url = f"http://{host}:{config.APP_PORT}/v1/web_memo/notify?api_key={api_key.hash_key}"
            crawl_service = CrawlService()
            resp = await crawl_service.crawl([url], notify_url)
            task_id = resp.get('task_id', '')

            history = BrowserHistory(url=url,ua=ua,crawl_task_id=task_id,crawl_status=False)
            session.add(history)
            session.commit()
        except Exception as e:
            raise RuntimeError(f"Error fetching web memo: {e}")