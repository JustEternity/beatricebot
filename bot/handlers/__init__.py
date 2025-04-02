from .common import router as common_router
from .registration import router as registration_router
from .profile_edit import router as profile_edit_router
from .testing import router as testing_router
from bot.handlers.algorithm import router as compatibility_router
from .subscription import router as sub_router
from aiogram import Router
from .services import router as services_router

# Все роутеры для удобного импорта
routers = [
    registration_router,
    profile_edit_router,
    testing_router,
    common_router,
    compatibility_router,
    sub_router,
    services_router
]
