from fastapi import APIRouter

from controllers.common.base import api_endpoint
from controllers.params import ChangePasswordRequest, LoginRequest, LogoutRequest, RefreshTokenRequest, RegisterRequest
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
    result = UserService.login(
        payload.username,
        payload.password,
        client_type=payload.client_type,
        device_label=payload.device_label,
    )
    return result


@router.post("/refresh")
@api_endpoint()
async def refresh_token(payload: RefreshTokenRequest):
    result = UserService.refresh_access_token(payload.refresh_token)
    return result


@router.post("/logout")
@api_endpoint()
async def logout(payload: LogoutRequest, current_user: CurrentUserDep):
    UserService.logout(payload.refresh_token, current_user["user_id"])
    return {"message": "Logged out successfully"}


@router.get("/me")
@api_endpoint()
async def get_current_user(current_user: CurrentUserDep):
    return UserService.get_user_auth_profile(current_user["user_id"])


@router.put("/password")
@api_endpoint()
async def change_password(payload: ChangePasswordRequest, current_user: CurrentUserDep):
    UserService.update_password(current_user["user_id"], payload.old_password, payload.new_password)
    return {"message": "Password updated successfully"}
