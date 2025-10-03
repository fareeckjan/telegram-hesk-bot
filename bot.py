#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import string
import random
import mysql.connector
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    PicklePersistence
)


BOT_TOKEN = "TOKEN"


DB_CONFIG = {
    'host': 'localhost',
    'user': 'HESKADMINUSER',
    'password': 'PASSWORD',
    'database': 'heskdb',
    'port': 3306
}


DEFAULT_CATEGORY = 1
DEFAULT_PRIORITY = '1'
DEFAULT_IP = '0.0.0.0'
DEFAULT_STATUS = 0
DEFAULT_OPENEDBY = 0
DEFAULT_OWNER = 0


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


(
    STATE_NAME,
    STATE_EMAIL,
    STATE_SUBJECT,
    STATE_MESSAGE,
    STATE_CONFIRM
) = range(5)


def generate_trackid(length=10) -> str:
    """
    Генерируем псевдослучайный trackid (буквы + цифры) нужной длины.
    У HESK в поле trackid max ~ 13 символов.
    """
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def insert_ticket(
    user_name: str,
    user_email: str,
    subject: str,
    message: str,
    ip_address: str = DEFAULT_IP,
    category: int = DEFAULT_CATEGORY,
    priority: str = DEFAULT_PRIORITY,
    status: int = DEFAULT_STATUS,
    openedby: int = DEFAULT_OPENEDBY,
    owner: int = DEFAULT_OWNER
) -> str:
    """
    Вставляем новую заявку (ticket) в hesk_tickets.
    Заполняем все поля, чтобы HESK точно видел u_name и u_email как значения по умолчанию.
    Информация о пользователе включается в поле message.
    Возвращаем trackid (код отслеживания).
    """

    trackid = generate_trackid(10)  #

    
    full_message = (
        f"**Имя:** {user_name}\n"
        f"**E-mail:** {user_email}\n\n"
        f"**Сообщение:**\n{message}"
    )
    html_version = (
        f"<p><strong>Имя:</strong> {user_name}<br>"
        f"<strong>E-mail:</strong> {user_email}</p>"
        f"<p><strong>Сообщение:</strong><br>{message}</p>"
    )

    
    base_columns = [
        "trackid",
        "u_name",
        "u_email",          'client@domain.com'
        "category",
        "priority",
        "subject",
        "message",
        "message_html",
        "dt",
        "ip",
        "status",
        "openedby",
        "owner",
        "lastchange"
    ]

    base_values = [
        trackid,
        "Client",
        "client@domain.com",
        category,
        priority,
        subject,
        full_message,
        html_version,
        None,
        ip_address,
        status,
        openedby,
        owner,
        None
    ]

    
    extra_fields = ["attachments", "merged", "history"]
    for i in range(1, 101):
        extra_fields.append(f"custom{i}")

    
    extra_values = ['' for _ in extra_fields]


    columns = base_columns + extra_fields
    values = base_values + extra_values

    
    placeholders = []
    final_data = []
    for col, val in zip(columns, values):
        if col in ["dt", "lastchange"]:
           
            placeholders.append("NOW()")
        else:
            placeholders.append("%s")
            final_data.append(val)

    column_list = ", ".join(columns)
    placeholder_list = ", ".join(placeholders)

    sql = f"""
    INSERT INTO hesk_tickets
    ({column_list})
    VALUES
    ({placeholder_list})
    """

    
    cnx = mysql.connector.connect(**DB_CONFIG)
    cursor = cnx.cursor()
    cursor.execute(sql, final_data)
    cnx.commit()
    cursor.close()
    cnx.close()

    return trackid


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start — приветственное сообщение.
    """
    await update.message.reply_text(
        "Привет! Я бот поддержки.\n"
        "Помогу создать заявку в HESK.\n\n"
        "Сначала представьтесь: как вас зовут?"
    )
    return STATE_NAME

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cancel — отмена диалога
    """
    await update.message.reply_text("Вы отменили создание заявки.")
    return ConversationHandler.END


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    context.user_data["user_name"] = user_name

    await update.message.reply_text(
        f"Отлично, {user_name}!\nТеперь введите ваш E-mail для связи."
    )
    return STATE_EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_email = update.message.text.strip()
    context.user_data["user_email"] = user_email

    await update.message.reply_text(
        "Спасибо! Теперь введите тему (кратко суть запроса):"
    )
    return STATE_SUBJECT

async def get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subject = update.message.text.strip()
    context.user_data["subject"] = subject

    await update.message.reply_text(
        "Принято. Теперь опишите проблему подробнее:"
    )
    return STATE_MESSAGE

async def get_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.strip()
    context.user_data["message"] = user_message

    summary = (
        f"**Проверим введённые данные:**\n\n"
        f"Имя: {context.user_data['user_name']}\n"
        f"E-mail: {context.user_data['user_email']}\n"
        f"Тема: {context.user_data['subject']}\n"
        f"Сообщение: {user_message}\n\n"
        f"Отправить заявку в HESK?"
    )

    keyboard = [
        [
            InlineKeyboardButton("Отправить", callback_data="confirm_yes"),
            InlineKeyboardButton("Отмена", callback_data="confirm_no")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=summary,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    return STATE_CONFIRM

# ------------------ ОБРАБОТЧИК INLINE-КНОПОК ------------------
async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_yes":
        user_name = context.user_data["user_name"]
        user_email = context.user_data["user_email"]
        subject = context.user_data["subject"]
        message = context.user_data["message"]

        try:
            trackid = insert_ticket(
                user_name=user_name,
                user_email=user_email,
                subject=subject,
                message=message
            )
            text = (
                "✅ Заявка успешно отправлена!\n\n"
                f"Ваш трек-ID: `{trackid}`\n"
                "Вы можете отследить её в системе HESK."
            )
        except Exception as e:
            logging.error(f"Ошибка при вставке тикета: {e}")
            text = "Произошла ошибка при создании заявки. Попробуйте позже."

        await query.edit_message_text(text=text, parse_mode="Markdown")
        return ConversationHandler.END

    else:
        await query.edit_message_text("Отправка заявки отменена!")
        return ConversationHandler.END


def main():
    persistence = PicklePersistence(filepath="bot_state.pkl")

    app = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            STATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            STATE_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            STATE_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subject)],
            STATE_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_message)],
            STATE_CONFIRM: [CallbackQueryHandler(confirm_callback, pattern="^confirm_")]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )

    app.add_handler(conv_handler)

    logging.info("Бот запущен. Нажмите Ctrl+C, чтобы остановить.")
    app.run_polling()

if __name__ == "__main__":
    main()

