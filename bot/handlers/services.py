import logging
from typing import Dict, List, Any
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.services.database import Database
from aiogram.filters import Command

router = Router()
logger = logging.getLogger(__name__)

# Логирование загрузки модуля
logger.info("Services module loaded")

@router.message(Command("services"))
async def services_command(message: Message):
    """Команда для проверки работы модуля услуг"""
    logger.info(f"Services command called by user {message.from_user.id}")

    # Создаем клавиатуру с услугами
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Подписка на месяц", callback_data="service_1")],
            [InlineKeyboardButton(text="🚀 Буст видимости на 24 часа", callback_data="service_2")],
            [InlineKeyboardButton(text="🔥 Буст видимости на 7 дней", callback_data="service_3")],
            [InlineKeyboardButton(text="📋 Мои активные услуги", callback_data="my_services")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
        ]
    )

    await message.answer(
        text="📋 <b>Доступные услуги:</b>\n\n"
             "Выберите интересующую вас услугу для получения подробной информации:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Добавьте временный обработчик для проверки работы роутера
@router.message(Command("test_services"))
async def test_services_handler(message: Message):
    """Тестовый обработчик для проверки работы модуля услуг"""
    logger.info("Test services handler called")
    await message.answer(
        "Модуль услуг работает. Выберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Просмотр услуг", callback_data="view_services")],
            [InlineKeyboardButton(text="Мои услуги", callback_data="my_services")]
        ])
    )

@router.callback_query(F.data == "view_services")
async def view_services(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработчик для просмотра доступных услуг"""
    user_id = callback.from_user.id
    logger.info(f"Services: User {user_id} requested services list with callback data: {callback.data}")

    # Обновляем статус подписки и приоритет пользователя
    await db.update_subscription_status(user_id)
    await db.update_user_priority(user_id)

    # Создаем клавиатуру с услугами
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Подписка на месяц", callback_data="service_1")],
            [InlineKeyboardButton(text="🚀 Буст видимости на 24 часа", callback_data="service_2")],
            [InlineKeyboardButton(text="🔥 Буст видимости на 7 дней", callback_data="service_3")],
            [InlineKeyboardButton(text="📋 Мои активные услуги", callback_data="my_services")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
        ]
    )

    try:
        # Пробуем отредактировать текущее сообщение
        await callback.message.edit_text(
            text="📋 <b>Доступные услуги:</b>\n\n"
                 "Выберите интересующую вас услугу для получения подробной информации:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        # Если не получается отредактировать, отправляем новое сообщение
        await callback.message.answer(
            text="📋 <b>Доступные услуги:</b>\n\n"
                 "Выберите интересующую вас услугу для получения подробной информации:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    await callback.answer()

# Добавляем обработчик для кнопки "Услуги" в главном меню
@router.callback_query(F.data == "menu_services")
async def menu_services(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработчик для кнопки 'Услуги' в главном меню"""
    user_id = callback.from_user.id
    logger.info(f"User {user_id} clicked menu_services button")

    # Обновляем статус подписки и приоритет пользователя
    await db.update_subscription_status(user_id)
    await db.update_user_priority(user_id)

    # Создаем клавиатуру с услугами
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Подписка на месяц", callback_data="service_1")],
            [InlineKeyboardButton(text="🚀 Буст видимости на 24 часа", callback_data="service_2")],
            [InlineKeyboardButton(text="🔥 Буст видимости на 7 дней", callback_data="service_3")],
            [InlineKeyboardButton(text="📋 Мои активные услуги", callback_data="my_services")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
        ]
    )

    try:
        await callback.message.edit_text(
            text="📋 <b>Доступные услуги:</b>\n\n"
                 "Выберите интересующую вас услугу для получения подробной информации:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        await callback.message.answer(
            text="📋 <b>Доступные услуги:</b>\n\n"
                 "Выберите интересующую вас услугу для получения подробной информации:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    await callback.answer()

@router.callback_query(F.data.startswith("service_"))
async def service_details(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработчик для просмотра детальной информации об услуге с проверкой активных услуг"""
    try:
        service_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id

        # Исправляем коэффициент приоритета перед показом услуг
        await db.fix_priority_coefficient(user_id)

        # Информация об услугах
        service_info = {
            1: {
                "id": 1,
                "description": "💎 Подписка на месяц",
                "cost": 299,
                "serviceduration": "30 дней",
                "priorityboostvalue": 50,
                "availabilitystatus": True,
                "details": "Премиум подписка на месяц дает вам приоритет в поиске и доступ ко всем функциям приложения."
            },
            2: {
                "id": 2,
                "description": "🚀 Буст видимости на 24 часа",
                "cost": 99,
                "serviceduration": "24 часа",
                "priorityboostvalue": 100,
                "availabilitystatus": True,
                "details": "Максимальное повышение видимости вашего профиля в течение 24 часов."
            },
            3: {
                "id": 3,
                "description": "🔥 Буст видимости на 7 дней",
                "cost": 499,
                "serviceduration": "7 дней",
                "priorityboostvalue": 75,
                "availabilitystatus": True,
                "details": "Значительное повышение видимости вашего профиля в течение недели."
            }
        }

        if service_id not in service_info:
            logger.warning(f"Service {service_id} not found")
            await callback.answer("Услуга не найдена", show_alert=True)
            return

        service = service_info[service_id]

        # Проверяем, есть ли уже активная такая же услуга
        active_service = await db.pool.fetchrow(
            """
            SELECT * FROM purchasedservices
            WHERE usertelegramid = $1
            AND serviceid = $2
            AND serviceenddate > NOW()
            AND paymentstatus = TRUE
            """,
            user_id, service_id
        )

        # Формируем основное сообщение
        message_text = (
            f"<b>🔍 {service['description']}</b>\n\n"
            f"{service['details']}\n\n"
            f"💰 <b>Стоимость:</b> {service['cost']} руб.\n"
            f"⏱ <b>Длительность:</b> {service['serviceduration']}\n"
            f"🔝 <b>Повышение приоритета:</b> +{service['priorityboostvalue']}%\n"
        )

        # Добавляем информацию об активной услуге, если она есть
        if active_service:
            end_date = active_service['serviceenddate'].strftime("%d.%m.%Y %H:%M")
            message_text += (
                f"\n\n⚠️ <b>У вас уже активирована эта услуга!</b>\n"
                f"Действует до: {end_date}"
            )

        # Создаем клавиатуру в зависимости от статуса услуги
        if active_service:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Мои услуги", callback_data="my_services")],
                    [InlineKeyboardButton(text="◀️ К списку услуг", callback_data="view_services")],
                    [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
                ]
            )
        else:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Приобрести", callback_data=f"buy_service_{service_id}")],
                    [InlineKeyboardButton(text="📋 Мои услуги", callback_data="my_services")],
                    [InlineKeyboardButton(text="◀️ К списку услуг", callback_data="view_services")],
                    [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
                ]
            )

        try:
            await callback.message.edit_text(
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await callback.message.answer(
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        await callback.answer()
    except Exception as e:
        logger.error(f"Error in service_details handler: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке запроса", show_alert=True)


@router.callback_query(F.data.startswith("buy_service_"))
async def buy_service(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработчик для покупки услуги"""
    try:
        service_id = int(callback.data.split("_")[-1])
        user_id = callback.from_user.id

        # Пробуем активировать услугу
        success = await db.activate_service(user_id, service_id)
        if service_id == 1 and success:
            callback.answer("Ваша анкета отправлена на модерацию", show_alert=True)

        if success:
            # Получаем информацию об услуге для сообщения
            service = await db.get_service_by_id(service_id)
            service_name = service['description'] if service else "услуга"

            # Получаем обновленную информацию о пользователе
            user_data = await db.get_user(user_id)
            priority_coefficient = user_data['profileprioritycoefficient'] if user_data else 1.0
            subscription_status = user_data['subscriptionstatus'] if user_data else False

            # Формируем сообщение
            status_text = (
                f"✅ Услуга «{service_name}» успешно активирована!\n\n"
                f"📊 Ваш текущий приоритет: {priority_coefficient:.2f}\n"
                f"🔑 Статус подписки: {'Активна ✅' if subscription_status else 'Неактивна ❌'}"
            )

            await callback.answer("✅ Услуга успешно активирована!", show_alert=True)

            try:
                await callback.message.edit_text(
                    status_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📋 Мои услуги", callback_data="my_services")],
                        [InlineKeyboardButton(text="◀️ К списку услуг", callback_data="view_services")]
                    ])
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await callback.message.answer(
                    status_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📋 Мои услуги", callback_data="my_services")],
                        [InlineKeyboardButton(text="◀️ К списку услуг", callback_data="view_services")]
                    ])
                )
        else:
            # Получаем информацию об услуге для сообщения об ошибке
            service = await db.get_service_by_id(service_id)
            service_name = service['description'] if service else "эта услуга"

            # Проверяем, есть ли уже активная такая же услуга
            active_services = await db.pool.fetch(
                """
                SELECT * FROM purchasedservices
                WHERE usertelegramid = $1
                AND serviceid = $2
                AND serviceenddate > NOW()
                AND paymentstatus = TRUE
                """,
                user_id, service_id
            )

            if active_services:
                end_date = active_services[0]['serviceenddate'].strftime("%d.%m.%Y %H:%M")
                message = (
                    f"⚠️ У вас уже активирована услуга «{service_name}»\n\n"
                    f"Она действует до: {end_date}\n\n"
                    f"Вы сможете продлить её после истечения срока."
                )
            else:
                message = "⚠️ Не удалось активировать услугу. Попробуйте позже."

            await callback.answer(message, show_alert=True)

    except Exception as e:
        logger.error(f"Error in buy_service handler: {e}", exc_info=True)
        await callback.answer(
            "Произошла ошибка при активации услуги",
            show_alert=True
        )

@router.callback_query(F.data == "my_services")
async def view_my_services(callback: CallbackQuery, db: Database):
    """Показывает активные услуги пользователя"""
    try:
        # Добавим логирование для отладки
        logger.debug(f"Showing services for user {callback.from_user.id}")

        # Используем get_user_services вместо get_active_services
        services = await db.get_user_services(callback.from_user.id)

        logger.debug(f"Found {len(services)} services")

        if not services:
            text = "У вас нет активных услуг"
        else:
            text = "🎁 Ваши активные услуги:\n\n"
            for service in services:
                end_date = service['serviceenddate'].strftime("%d.%m.%Y %H:%M")
                text += (
                    f"🔹 {service['description']}\n"
                    f"   Приоритет: +{service['priorityboostvalue']}%\n"
                    f"   Действует до: {end_date}\n\n"
                )

        try:
            # Пробуем отредактировать текущее сообщение
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="view_services")]
                ])
            )
        except Exception as e:
            logger.error(f"Error editing message in view_my_services: {e}")
            # Если не получается отредактировать, отправляем новое сообщение
            await callback.message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="view_services")]
                ])
            )

        await callback.answer()
    except Exception as e:
        logger.error(f"Error showing services: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке услуг", show_alert=True)


