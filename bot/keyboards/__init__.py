from .menus import (
    main_menu,
    edit_profile_keyboard,
    policy_keyboard,
    back_to_menu_button
)
from .builders import (
    build_main_menu,
    build_yes_no_keyboard,
    build_gender_select,
    build_photos_upload
)

# Для удобного импорта всех клавиатур
__all__ = [
    'main_menu',
    'edit_profile_keyboard',
    'policy_keyboard',
    'back_to_menu_button',
    'build_main_menu',
    'build_yes_no_keyboard',
    'build_gender_select',
    'build_photos_upload'
]