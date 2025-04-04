from .common import router as common_router
from .registration import router as registration_router
from .profile_edit import router as profile_edit_router
from .testing import router as testing_router
from bot.handlers.algorithm import router as compatibility_router
from aiogram import Router
from .services import router as services_router
from .admin_funcs import router as admin_router
from .action_likes import router as likes_router
from .view_likes import router as likes_menu_router

routers = [
    registration_router,
    profile_edit_router,
    testing_router,
    services_router,
    compatibility_router,
    admin_router,
    likes_router,
    likes_menu_router,
    common_router
]
