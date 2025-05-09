from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from bot.models.states import RegistrationStates
from bot.services.database import Database
from bot.services.utils import delete_previous_messages
from bot.keyboards.menus import reports_menu, back_to_reports_menu, back_to_admin_menu_button, feedback_categories, complaint_decisions, verify_decisions, moder_decisions
from bot.handlers.common import get_user_profile
from bot.services.encryption import CryptoService
from bot.services.s3storage import S3Service

import datetime
import logging
logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "admin_reports")
async def admin_reports_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await delete_previous_messages(callback.message, state)
    #await state.clear()
    msg = await callback.message.answer(
        "Выберите отчет:",
        reply_markup=reports_menu()
    )
    await state.update_data(edit_message_id=msg.message_id)
    await state.set_state(RegistrationStates.WATCH_REPORTS)
    reports = await db.get_reports()
    if not reports:
        await callback.answer("⚠️ Отчеты не найдены!", show_alert=True)
        return
    await state.update_data(reports=reports)
    await state.update_data(message_ids=[msg.message_id])
    await callback.answer()

@router.callback_query(F.data == "get_active_users")
async def get_active_users_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await delete_previous_messages(callback.message, state)
    data = await state.get_data()
    reports = data.get('reports')
    res = await db.exec_report(admin_id=callback.from_user.id, report_id=1, query=reports[1])
    message_text = '📊 Отчет по активным пользователям:\n\n'
    message_text = f'Активных пользователей за последний месяц: {res[0].get("active_users_count", 0)}'

    msg = await callback.message.answer(message_text, reply_markup=back_to_reports_menu())

    await callback.answer()

@router.callback_query(F.data == "get_count_of_regs")
async def get_count_of_regs_handler(callback: CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback.message, state)
    msg = await callback.message.answer("📅 Введите год:")
    await state.update_data(request_message_id=msg.message_id)
    await state.set_state(RegistrationStates.AWAIT_YEAR)
    await callback.answer()

@router.message(RegistrationStates.AWAIT_YEAR)
async def input_year_for_count_of_regs_report(message: Message, state: FSMContext, db: Database):
    try:
        data = await state.get_data()
        reports = data.get('reports')
        await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data.get('request_message_id'))
        await message.delete()

        try:
            year = int(message.text)
            if not (2000 <= year <= datetime.datetime.now().year):
                raise ValueError
        except (ValueError, TypeError):
            error_msg = await message.answer("⚠ Некорректный год! Введите 4 цифры, например: 2023")
            await state.update_data(request_message_id=error_msg.message_id)
            return

        month_names = [
                "Январь", "Февраль", "Март", "Апрель",
                "Май", "Июнь", "Июль", "Август",
                "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
            ]

        res = await db.exec_report(message.from_user.id, 3, reports[3], year)
        message_text = f'📊 Отчет по активным пользователям за {year} год:\n\n'
        total = 0
        for entry in res:
            month_number = entry.get('month_number')
            count = entry.get('registrations_count', 0)
            message_text += f'{month_names[month_number-1]}: {count}\n'
            total += count
        message_text += f'Всего регистраций за год: {total}'

        await message.answer(message_text, reply_markup=back_to_reports_menu())
        #await state.clear()

    except Exception as e:
        logger.error(f"Error in process_year_handler: {str(e)}")
        logger.exception(e)
        await message.answer("❌ Произошла ошибка при обработке отчета", reply_markup=back_to_reports_menu())
        await state.clear()

@router.callback_query(F.data == "admin_results")
async def admin_results_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await delete_previous_messages(callback.message, state)
    data = await state.get_data()
    reports = data.get('reports')
    res = await db.exec_report(callback.from_user.id, 4, reports[4], callback.from_user.id)
    message_text = '📊 Отчет по работе администратора за текущий месяц:\n\n'

    message_text += f'Обработано жалоб: {res[0].get("processed_complaints", 0)}\n'
    message_text += f'Обработано обратной связи: {res[0].get("processed_feedback", 0)}\n'
    message_text += f'Проведено модераций: {res[0].get("processed_moderations", 0)}\n'
    message_text += f'Проведено верификаций: {res[0].get("processed_verifications", 0)}\n'

    msg = await callback.message.answer(message_text, reply_markup=back_to_reports_menu())

    await callback.answer()

@router.callback_query(F.data == "get_purchased_services")
async def get_purchased_services_handler(callback: CallbackQuery, state: FSMContext):
    await delete_previous_messages(callback.message, state)
    msg = await callback.message.answer("📅 Введите год:")
    await state.update_data(request_message_id=msg.message_id)
    await state.set_state(RegistrationStates.AWAIT_YEAR_FOR_SERV)
    await callback.answer()

@router.message(RegistrationStates.AWAIT_YEAR_FOR_SERV)
async def input_year_for_purchased_services_report(message: Message, state: FSMContext, db: Database):
    try:
        data = await state.get_data()
        reports = data.get('reports')
        await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data.get('request_message_id'))
        await message.delete()

        try:
            year = int(message.text)
            if not (2000 <= year <= datetime.datetime.now().year):
                raise ValueError
        except (ValueError, TypeError):
            error_msg = await message.answer("⚠ Некорректный год! Введите 4 цифры, например: 2023")
            await state.update_data(request_message_id=error_msg.message_id)
            return

        month_names = [
                "Январь", "Февраль", "Март", "Апрель",
                "Май", "Июнь", "Июль", "Август",
                "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
            ]

        res = await db.exec_report(message.from_user.id, 5, reports[5], year)
        message_text = f'📊 Отчет по купленным услугам за {year} год:\n\n'
        total = 0
        for entry in res:
            month_number = entry.get('month_number')
            count = entry.get('purchases_count', 0)
            message_text += f'{month_names[month_number-1]}: {count}\n'
            total += count
        message_text += f'Всего куплено услуг за год: {total}'

        await message.answer(message_text, reply_markup=back_to_reports_menu())
        await state.clear()

    except Exception as e:
        logger.error(f"Error in process_year_handler: {str(e)}")
        logger.exception(e)
        await message.answer("❌ Произошла ошибка при обработке отчета", reply_markup=back_to_reports_menu())
        #await state.clear()

@router.callback_query(F.data == "admin_feedback")
async def admin_feedback_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await delete_previous_messages(callback.message, state)
    #await state.clear()
    await state.set_state(RegistrationStates.WATCH_FEEDBACK)
    feedbacks = await db.get_feedback()
    await state.update_data(feedbacks=feedbacks)
    if feedbacks == None or feedbacks == {}:
        error_msg = await callback.message.answer("📭 Необработанных сообщений обратной связи нет :)",
                                                  reply_markup=back_to_admin_menu_button())
        await state.update_data(request_message_id=error_msg.message_id)
        return

    feedback_list = list(feedbacks.items())
    await state.update_data(
        feedback_list=feedback_list,
        current_fb_index=0
    )

    await show_next_feedback(callback.message, state, db)
    await callback.answer()

async def show_next_feedback(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    feedback_list = data.get('feedback_list', [])
    current_idx = data.get('current_fb_index', 0)

    if current_idx >= len(feedback_list):
        await message.answer(
            "✅ Все обращения обработаны",
            reply_markup=back_to_admin_menu_button()
        )
        await state.clear()
        return

    feedback_id, messagetext = feedback_list[current_idx]

    # Отправляем сообщение с клавиатурой
    msg = await message.answer(
        f"📩 Обращение #{feedback_id}\n\n{messagetext}",
        reply_markup=feedback_categories()
    )

    await state.update_data(last_message_id=msg.message_id)

@router.callback_query(F.data.startswith("feedback_"))
async def process_feedback_category(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    feedback_list = data.get('feedback_list', [])
    current_idx = data.get('current_fb_index', 0)

    # Удаляем предыдущее сообщение
    try:
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

    # Обновляем статус в базе данных
    category = callback.data.split("_")[1]
    feedback_id, messagetext = feedback_list[current_idx]

    await db.update_feedback_status(
        feedback_id=feedback_id,
        category=category,
        status=True,
        admin_id=callback.from_user.id
    )

    # Переходим к следующему обращению
    await state.update_data(current_fb_index=current_idx + 1)
    await show_next_feedback(callback.message, state, db)
    await callback.answer()

@router.callback_query(F.data == "admin_complaints")
async def admin_complaints_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto, bot, s3):
    # Обратите внимание, что мы добавили параметры crypto, bot и s3
    await delete_previous_messages(callback.message, state)
    #await state.clear()
    await state.set_state(RegistrationStates.WATCH_COMPLAINTS)
    complaints = await db.get_complaints()
    if complaints == None or complaints == {}:
        error_msg = await callback.message.answer("📭 Необработанных жалоб нет :)",
                                              reply_markup=back_to_admin_menu_button())
        await state.update_data(request_message_id=error_msg.message_id)
        return
    complaints_list = list(complaints.items())
    await state.update_data(
        complaints_list=complaints_list,
        current_compl_index=0,
        crypto=crypto,  # Сохраняем экземпляр crypto в state
        bot=bot,        # Сохраняем экземпляр bot в state
        s3=s3           # Сохраняем экземпляр s3 в state
    )
    await show_next_complaint(callback.message, state, db)
    await callback.answer()

async def show_next_complaint(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    complaints_list = data.get('complaints_list', [])
    current_idx = data.get('current_compl_index', 0)

    if current_idx >= len(complaints_list):
        await message.answer(
            "✅ Все жалобы обработаны",
            reply_markup=back_to_admin_menu_button()
        )
        #await state.clear()
        return

    complaintid, complaint_data = complaints_list[current_idx]

    # Используем экземпляры из state
    profile = await get_user_profile(
        user_id=complaint_data[0],
        db=db,
        crypto=data.get('crypto'),
        bot=message.bot,
        s3=data.get('s3'),
        refresh_photos=False
    )

    # Формируем сообщение
    message_text = (
        f"🛑 Жалоба #_{complaintid}_\n"
        f"▪️ На пользователя: {complaint_data[0]}\n"
        f"▪️ Причина: {'некорректное фото' if complaint_data[1] == 'photo' else 'некорректное описание'}\n\n"
    )

    if profile:
        message_text += (
            f"{profile['text']}\n\n"
        )

        # Отправляем фотографии, если они есть
        photos = profile.get('photos', [])

        if photos:
            try:
                # Создаем медиагруппу со всеми фотографиями
                media_group = []

                # Первое фото с подписью
                media_group.append(InputMediaPhoto(
                    media=photos[0],
                    caption=message_text,
                    parse_mode="Markdown"
                ))

                # Добавляем остальные фото (если есть)
                for photo_id in photos[1:10]:  # Ограничиваем до 9 дополнительных фото
                    media_group.append(InputMediaPhoto(media=photo_id))

                # Отправляем всю медиагруппу
                sent_messages = await message.bot.send_media_group(
                    chat_id=message.chat.id,
                    media=media_group
                )
                sent_message_ids = [msg.message_id for msg in sent_messages]

                # Отправляем кнопки отдельным сообщением, так как медиагруппа не поддерживает reply_markup
                msg = await message.answer(
                    "Выберите действие:",
                    reply_markup=complaint_decisions()
                )

                # Сохраняем ID сообщения с кнопками
                await state.update_data(last_message_id=msg.message_id, current_user=complaint_data[0],last_message_ids=sent_message_ids)

            except Exception as e:
                logger.error(f"Error sending media group: {e}")
                # Если не удалось отправить медиагруппу, отправляем текст отдельно
                msg = await message.answer(
                    text=message_text + "⚠️ Ошибка при отправке фотографий",
                    reply_markup=complaint_decisions(),
                    parse_mode="Markdown"
                )
                await state.update_data(last_message_id=msg.message_id, current_user=complaint_data[0],last_message_ids=sent_message_ids)
        else:
            # Если фотографий нет
            msg = await message.answer(
                text=message_text + "⚠️ Фотографии отсутствуют",
                reply_markup=complaint_decisions(),
                parse_mode="Markdown"
            )
            await state.update_data(last_message_id=msg.message_id, current_user=complaint_data[0])
    else:
        # Если профиль не найден
        msg = await message.answer(
            text=message_text + "⚠️ Анкета пользователя не найдена",
            reply_markup=complaint_decisions(),
            parse_mode="Markdown"
        )
        await state.update_data(last_message_id=msg.message_id, current_user=complaint_data[0])

@router.callback_query(F.data.startswith("complaint_"))
async def process_complaint_category(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    user_id = data.get('current_user')
    complaints_list = data.get('complaints_list', [])
    current_idx = data.get('current_compl_index', 0)
    last_message_ids = data.get('last_message_ids', [])

    # Удаляем все сообщения из медиагруппы и кнопки
    for msg_id in last_message_ids:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=msg_id
            )
        except Exception as e:
            logger.error(f"Error deleting message {msg_id}: {e}")

    # Удаляем предыдущее сообщение
    try:
        await callback.message.delete()
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

    # Обновляем статус в базе данных
    category = callback.data.split("_")[1]
    complaint_id, messagetext = complaints_list[current_idx]

    await db.update_complaint_status(
        complaint_id=complaint_id,
        category=category,
        status=True,
        admin_id=callback.from_user.id,
        user=(user_id if category == 'block' else None)
    )

    if category == 'block':
        await callback.bot.send_message(chat_id=user_id, text="Ваш аккаунт заблокирован за нарушение правил составления анкеты!")

    # Переходим к следующему обращению
    await state.update_data(current_compl_index=current_idx + 1)
    await show_next_complaint(callback.message, state, db)
    await callback.answer()

@router.callback_query(F.data == "admin_verifications")
async def admin_verifications_handler(callback: CallbackQuery, state: FSMContext, db: Database):
    await delete_previous_messages(callback.message, state)
    #await state.clear()
    await state.set_state(RegistrationStates.WATCH_VERIFY)
    verifs = await db.get_verifications()
    if verifs == None or verifs == {}:
        error_msg = await callback.message.answer("📭 Заявок на верификацию нет :)",
                                                  reply_markup=back_to_admin_menu_button())
        await state.update_data(request_message_id=error_msg.message_id)
        return

    verifs_list = list(verifs.items())
    await state.update_data(
        verifs_list=verifs_list,
        current_ver_index=0
    )

    await show_next_verif(callback.message, state, db)
    await callback.answer()

async def show_next_verif(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    verifs_list = data.get('verifs_list', [])
    current_idx = data.get('current_ver_index', 0)
    last_msg_id = data.get('last_message_id')

    # Удаляем предыдущее сообщение
    if last_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, last_msg_id)
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")

    if current_idx >= len(verifs_list):
        await message.answer("✅ Все верификации обработаны",
                            reply_markup=back_to_admin_menu_button())
        #await state.clear()
        return

    verification_id, data = verifs_list[current_idx]

    try:
        # Отправляем видео
        msg = await message.answer_video(
            video=data[0],
            caption=f"Верификация #{verification_id}",
            reply_markup=verify_decisions()
        )

        # Обновляем индекс после отправки
        await state.update_data(
            current_verification_id=verification_id,
            last_message_id=msg.message_id,
            current_ver_index=current_idx + 1,
            current_user=data[1]
        )

    except Exception as e:
        logger.error(f"Ошибка отображения верификации: {e}")
        await message.answer("⚠ Ошибка при загрузке видео")
        await show_next_verif(message, state, db)

@router.callback_query(F.data == "verify_block")
async def handle_block(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Введите причину отклонения верификации:")
    await state.set_state(RegistrationStates.AWAIT_REJECT_REASON)
    await callback.answer()

@router.message(RegistrationStates.AWAIT_REJECT_REASON)
async def process_rejection_verify(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    reason = message.text

    # Обновляем верификацию
    await db.update_verification(
        admin_id=message.from_user.id,
        verification_id=data['current_verification_id'],
        status='rejected',
        rejection_reason=reason
    )
    user_id = data['current_user']
    if user_id:
        await message.bot.send_message(
            chat_id=user_id,
            text=f"❌ Верификация отклонена. Причина: {reason}"
        )

    await message.answer(f"❌ Верификация отклонена. Причина: {reason}")
    await show_next_verif(message, state, db)

@router.callback_query(F.data == "verify_skip")
async def handle_skip(callback: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    await db.update_verification(
        admin_id=callback.from_user.id,
        verification_id=data['current_verification_id'],
        status='approve'
    )
    user_id = data['current_user']
    if user_id:
        await callback.bot.send_message(
            chat_id=user_id,
            text=f"✅ Верификация пройдена."
        )

    await callback.answer(f"✅ Верификация пройдена")
    await show_next_verif(callback.message, state, db)


@router.callback_query(F.data == "admin_moderations")
async def admin_moderations_handler(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService, bot: Bot, s3: S3Service):
    await delete_previous_messages(callback.message, state)
    await state.set_state(RegistrationStates.WATCH_MODER)
    moders = await db.get_moderations()
    if moders == None or moders == {}:
        error_msg = await callback.message.answer("📭 Заявок на модерацию нет :)",
                                                  reply_markup=back_to_admin_menu_button())
        await state.update_data(request_message_id=error_msg.message_id)
        return

    moders_list = list(moders.items())
    await state.update_data(
        moders_list=moders_list,
        current_moder_index=0
    )

    await show_next_moder(callback.message, state, db, crypto, bot, s3)
    await callback.answer()

async def show_next_moder(message: Message, state: FSMContext, db: Database, crypto: CryptoService, bot: Bot, s3: S3Service):
    data = await state.get_data()
    moder_list = data.get('moders_list', [])
    current_idx = data.get('current_moder_index', 0)
    messages_to_delete = data.get('messages_to_delete', [])

    # Удаляем предыдущие сообщения
    for msg_id in messages_to_delete:
        try:
            await message.bot.delete_message(message.chat.id, msg_id)
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")

    if current_idx >= len(moder_list):
        await message.answer("✅ Все анкеты обработаны",
                            reply_markup=back_to_admin_menu_button())
        #await state.clear()
        return

    user_id = moder_list[current_idx][1]

    # Получаем данные анкеты
    profile = await get_user_profile(
        user_id=user_id,
        db=db,
        crypto=crypto,
        bot=bot,
        s3=s3
    )

    if not profile:
        await message.answer("❌ Ошибка загрузки анкеты")
        await show_next_moder(message, state, db, crypto, bot, s3)
        return

    # Отправляем фото
    media_group = []
    for i, photo_id in enumerate(profile['photos']):
        media_group.append(InputMediaPhoto(
            media=photo_id,
            caption=profile['text'] if i == 0 else None,
        ))

    sent_messages = await message.answer_media_group(media=media_group)
    messages_to_delete.extend([m.message_id for m in sent_messages])

    # Отправляем кнопки
    msg = await message.answer("Выберите действие:", reply_markup=moder_decisions())
    messages_to_delete.append(msg.message_id)

    await state.update_data(
        current_user_id=user_id,
        messages_to_delete=messages_to_delete
    )


@router.callback_query(F.data == "moder_skip")
async def handle_approve(callback: CallbackQuery, state: FSMContext, db: Database, crypto: CryptoService, bot: Bot, s3: S3Service):
    data = await state.get_data()
    user_id = data.get('current_user_id')
    moder_list = data.get('moders_list', [])
    current_idx = data.get('current_moder_index', 0)

    moderation_id, user_id = moder_list[current_idx]

    await db.update_moderation_status(
        moderationid=moderation_id,
        status='approved',
        admin_id=callback.from_user.id, user=user_id
    )

    await callback.answer("✅ Анкета одобрена")
    await state.update_data(current_moder_index=current_idx + 1)
    await show_next_moder(callback.message, state, db, crypto, bot, s3)

@router.callback_query(F.data == "moder_block")
async def handle_block(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Укажите причину блокировки:")
    await state.set_state(RegistrationStates.AWAIT_BLOCK_REASON)
    await callback.answer()

@router.message(RegistrationStates.AWAIT_BLOCK_REASON)
async def moder_block_reason(message: Message, state: FSMContext, db: Database, crypto: CryptoService, bot: Bot, s3: S3Service):
    data = await state.get_data()
    user_id = data.get('current_user_id')
    moder_list = data.get('moders_list', [])
    current_idx = data.get('current_moder_index', 0)
    reason = message.text

    moderation_id, user_id = moder_list[current_idx]

    await db.update_moderation_status(
        moderationid=moderation_id,
        status='blocked',
        admin_id=message.from_user.id,
        rejection_reason=reason
    )

    # Уведомляем пользователя
    await message.bot.send_message(
        chat_id=user_id,
        text=f"⛔ Ваша анкета заблокирована и услуги обнулены за нарушение правил. Причина: {reason}\nЧтобы заполнить анкету заново, нажмите /start"
    )

    await db.del_user(user_id)
    await s3.delete_user_photos(user_id)

    await message.answer(f"⛔ Анкета заблокирована")
    await state.update_data(current_moder_index=current_idx + 1)
    await show_next_moder(message, state, db, crypto, bot, s3)