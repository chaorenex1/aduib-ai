import logging
from multiprocessing.spawn import freeze_support

from .app_factory import create_app

app=create_app()
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    freeze_support()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=app.config.APP_PORT)