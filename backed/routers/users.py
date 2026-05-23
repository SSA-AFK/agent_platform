from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status


from backed.crud import users

from backed.crud.db_config import get_db
from backed.models.users import User
from backed.schema.users import UserAuthResponse, UserInfoResponse, UserRequest, UserUpdateRequest, \
    UserChangePasswordRequest
from backed.utils.auth import get_current_user
from backed.utils.response import success_response

user_router = APIRouter(prefix="/api/user", tags=["users"])


@user_router.post("/register")
async def register(user_data: UserRequest, db: AsyncSession = Depends(get_db)):
    existing_user = await users.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已存在")
    user = await users.create_user(db, user_data)
    token = await users.create_token(db, user.id)
    response_data = UserAuthResponse(token=token, user_info=UserInfoResponse.model_validate(user))
    return success_response(message="注册成功", data=response_data, by_alias=True)


@user_router.post("/login")
async def login(user_data: UserRequest, db: AsyncSession = Depends(get_db)):
    user = await users.authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = await users.create_token(db, user.id)
    response_data = UserAuthResponse(token=token, user_info=UserInfoResponse.model_validate(user))
    return success_response(message="登录成功啦", data=response_data, by_alias=True)


# 查Token查用户 → 封装crud → 功能整合成一个工具函数 → 路由导入使用: 依赖注入
@user_router.get("/info")
async def get_user_info(user: User = Depends(get_current_user)):
    return success_response(message="获取用户信息成功", data=UserInfoResponse.model_validate(user))


# 修改用户信息：验证Token → 更新（用户输入数据 put 提交 → 请求体参数 → 定义Pydantic模型类） → 响应结果
# 参数：用户输入的 + 验证Token的 + db（调用更新的方法）
@user_router.put("/update")
async def update_user_info(user_data: UserUpdateRequest, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    user = await users.update_user(db, user.username, user_data)
    return success_response(message="更新用户信息成功", data=UserInfoResponse.model_validate(user))


@user_router.put("/password")
async def update_password(
        password_data: UserChangePasswordRequest,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    res_change_pwd = await users.change_password(db, user, password_data.old_password, password_data.new_password)
    if not res_change_pwd:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="旧密码不正确")
    return success_response(message="修改密码成功")
