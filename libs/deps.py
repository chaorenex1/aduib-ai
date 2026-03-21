from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from models import get_db

from .context import verify_api_key_in_db, verify_jwt_in_request

SessionDep = Annotated[Session, Depends(get_db)]

CurrentApiKeyDep = Annotated[None, Depends(verify_api_key_in_db)]
CurrentUserDep = Annotated[dict, Depends(verify_jwt_in_request)]
