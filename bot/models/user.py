from pydantic import BaseModel
from typing import List, Optional, Union
from datetime import datetime

class UserBase(BaseModel):
    """Базовая модель пользователя"""
    telegram_id: int
    name: bytes
    age: int
    gender: str
    city: bytes
    profile_description: bytes

class UserCreate(UserBase):
    """Модель для создания пользователя"""
    photos: List[str]

class UserDB(UserBase):
    """Модель пользователя из БД"""
    id: int
    subscription_status: bool = False
    moderation_status: bool = False
    verification_status: bool = False
    registration_date: datetime
    last_action_date: datetime
    profile_priority: float = 0.0
    account_status: str = "active"

    class Config:
        from_attributes = True

class UserPublic(BaseModel):
    """Публичное представление пользователя"""
    name: str
    age: int
    gender: str
    city: str
    profile_description: str
    photos: List[str]
    registration_date: datetime

class UserPhoto(BaseModel):
    """Модель для фотографий"""
    user_id: int
    photo_file_id: str
    display_order: int

User = UserDB