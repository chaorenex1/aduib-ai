import datetime
import json
import logging
from typing import Optional, Any

from aduib_rpc.utils.net_utils import NetUtils

from models import get_db, ApiKey
from models.browser import BrowserHistory
from service import FileService
from service.error.error import ApiKeyNotFound
from utils import random_uuid

logger = logging.getLogger(__name__)


class WebMemoService:
    @classmethod
    async def handle_web_memo(cls, data: dict[str, str]):
        """
        Handle web memo by fetching and processing the content from the given URL.
        :param data: Dictionary containing the URL and other relevant information.
        :return: Processed content as a string.
        """
        url = data.get("url")
        ua = data.get("ua")
        with get_db() as session:
            api_key: Optional[ApiKey] = session.query(ApiKey).filter(ApiKey.source == "aduib_mcp_server").first()
            if not api_key:
                raise ApiKeyNotFound

        try:
            from configs import config
            from rpc.client import CrawlService

            host, port = NetUtils.get_ip_and_free_port()
            notify_url = f"http://{host}:{config.APP_PORT}/v1/web_memo/notify?api_key={api_key.hash_key}"
            crawl_service = CrawlService()
            resp = await crawl_service.crawl([url], notify_url)
            if resp:
                await cls.handle_web_memo_notify(resp, api_key.hash_key, ua)
        except Exception as e:
            raise RuntimeError(f"Error fetching web memo: {e}")

    @classmethod
    async def handle_web_memo_notify(cls, body: dict[str, Any], api_hash_key: str, ua: str = "") -> None:
        """
        Handle notification from the crawl service with the fetched content.
        :param body: Dictionary containing the notification data.
        :param api_hash_key: API hash key for validation.
        :param ua: User agent string.
        :return: None
        """
        with get_db() as session:
            api_key: Optional[ApiKey] = session.query(ApiKey).filter(ApiKey.source == "aduib_mcp_server").first()
            if not api_key or api_key.hash_key != api_hash_key:
                raise ApiKeyNotFound

            status = body.get("success", False)
            if not status:
                logger.warning("Web memo crawl failed or no results")
                return
            result = body.get("results", [])

            for item in result:
                url = item.get("url", "")
                crawl_text = item.get("crawl_text", "")
                hit_rule = item.get("hit_rule", "")
                logger.info(f"Web memo crawl result: url={url}, hit_rule={hit_rule}, length={len(crawl_text)}")
                if crawl_text != "\n" and crawl_text != "[]":
                    crawl_text = crawl_text.strip()
                    crawl_type = item.get("crawl_type", "")
                    crawl_media = item.get("crawl_media", {})
                    screenshot_png = ""
                    if item.get("screenshot", "") != "":
                        screenshot_png = "/his_screenshot/" + random_uuid() + ".png"
                        FileService.upload_base64(screenshot_png, item.get("screenshot", ""))
                    metadata = item.get("metadata", {})

                    history = BrowserHistory(url=url, ua=ua)
                    history.crawl_status = True
                    history.crawl_time = datetime.datetime.now()
                    history.crawl_screenshot = screenshot_png
                    history.crawl_content = crawl_text
                    history.crawl_type = crawl_type
                    history.crawl_media = json.dumps(crawl_media).encode("utf-8").decode("unicode-escape")
                    history.crawl_metadata = json.dumps(metadata).encode("utf-8").decode("unicode-escape")
                    session.add(history)
                    session.commit()
                    if hit_rule != "default" and crawl_text and len(crawl_text) > 0:
                        # from service import KnowledgeBaseService
                        # await KnowledgeBaseService.paragraph_rag_from_web_memo(crawl_text,crawl_type)
                        from runtime.rag_manager import RagManager

                        from event.event_manager import event_manager_context

                        event_manager = event_manager_context.get()
                        await event_manager.emit(
                            event="paragraph_rag_from_web_memo", crawl_text=crawl_text, crawl_type=crawl_type
                        )
