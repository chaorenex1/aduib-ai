from fastapi import APIRouter

from controllers.common.base import BaseResponse, catch_exceptions
from controllers.params import ChangePasswordRequest, LoginRequest, RefreshTokenRequest, RegisterRequest
from libs.deps import CurrentUserDep
from service.user_service import UserService

router = APIRouter(tags=["auth"], prefix="/auth")


@router.post("/register")
@catch_exceptions
async def register(payload: RegisterRequest):
    user = UserService.register(payload.username, payload.password, payload.email)
    return BaseResponse.ok({"user_id": user.id, "username": user.username})


@router.post("/login")
@catch_exceptions
async def login(payload: LoginRequest):
    result = UserService.login(payload.username, payload.password)
    return BaseResponse.ok(result)


@router.post("/refresh")
@catch_exceptions
async def refresh_token(payload: RefreshTokenRequest):
    result = UserService.refresh_access_token(payload.refresh_token)
    return BaseResponse.ok(result)


@router.get("/me")
@catch_exceptions
async def get_current_user(current_user: CurrentUserDep):
    user = UserService.get_user_by_id(current_user["user_id"])
    return BaseResponse.ok(
        {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": user.status,
        }
    )


@router.put("/password")
@catch_exceptions
async def change_password(payload: ChangePasswordRequest, current_user: CurrentUserDep):
    UserService.update_password(current_user["user_id"], payload.old_password, payload.new_password)
    return BaseResponse.ok({"message": "Password updated successfully"})
