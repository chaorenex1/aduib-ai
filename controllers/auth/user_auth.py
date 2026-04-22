from fastapi import APIRouter

from controllers.common.base import api_endpoint
from controllers.params import ChangePasswordRequest, LoginRequest, RefreshTokenRequest, RegisterRequest
from libs.deps import CurrentUserDep
from service.user_service import UserService

router = APIRouter(tags=["auth"], prefix="/auth")


@router.post("/register")
@api_endpoint()
async def register(payload: RegisterRequest):
    user = UserService.register(payload.username, payload.password, payload.email)
    return {"user_id": user.id, "username": user.username}


@router.post("/login")
@api_endpoint()
async def login(payload: LoginRequest):
    result = UserService.login(payload.username, payload.password)
    return result


@router.post("/refresh")
@api_endpoint()
async def refresh_token(payload: RefreshTokenRequest):
    result = UserService.refresh_access_token(payload.refresh_token)
    return result


@router.get("/me")
@api_endpoint()
async def get_current_user(current_user: CurrentUserDep):
    user = UserService.get_user_by_id(current_user["user_id"])
    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "status": user.status,
    }


@router.put("/password")
@api_endpoint()
async def change_password(payload: ChangePasswordRequest, current_user: CurrentUserDep):
    UserService.update_password(current_user["user_id"], payload.old_password, payload.new_password)
    return {"message": "Password updated successfully"}
