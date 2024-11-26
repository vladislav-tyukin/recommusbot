import asyncio
import database
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
import pandas as pd
import random
from token_tg import token_teleg

#update — объект, который содержит всю информацию о событии, пришедшем от пользователя (например, сообщение или callback-запрос).
#callback_query — это объект, который содержится в update и представляет собой запрос, возникший от нажатия пользователем кнопки inline.
#query — это сокращение для объекта callback_query, которое используется в коде для упрощения.

DATASET_PATH = "SpotifyFeatures.csv"
database.init_db()

def load_dataset():
    return pd.read_csv(DATASET_PATH)

dataset = load_dataset()

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    username = user.username

    
    if database.is_new_user(user_id):
        await update.message.reply_text(f"Привет {username}! Вы новый пользователь. Давайте начнем!")
        await send_main_menu_new_user(update)
    else:
        await update.message.reply_text(f"С возвращением, {username}! Продолжим с рекомендациями.")
        await send_main_menu(update)

    
async def send_main_menu_new_user(update: Update):
    keyboard = [
        [InlineKeyboardButton("Получить рекомендацию", callback_data="get_recommendation")],
        [InlineKeyboardButton("Оценить жанры", callback_data="start_genre_survey")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)


async def start_genre_survey(update: Update, context: CallbackContext):
    genres = dataset["genre"].unique().tolist()
    genres_text = "\n".join([f"{genre}" for genre in genres])

    if update.callback_query:
        query = update.callback_query
        await query.answer() 
        await query.message.reply_text(
            f"Оцените жанры (в формате: 'Жанр - оценка'). Пример:\nRock - 5\n\nЖанры:\n{genres_text}"
        )
    else:
        await update.message.reply_text(
            f"Оцените жанры (в формате: 'Жанр - оценка'). Пример:\nRock - 5\n\nЖанры:\n{genres_text}"
        )



async def handle_genre_rating(update: Update, context: CallbackContext):
    text = update.message.text
 

    try:
      
        track_genre, rating = text.split(" - ")
        rating = int(rating)
        track_genre = track_genre.strip() 

        if rating < 1 or rating > 5:
            await update.message.reply_text("Оценка должна быть от 1 до 5.")
            return

        
        genres = dataset["genre"].unique().tolist()
        if track_genre not in genres:
            await update.message.reply_text(f"Жанра '{track_genre}' нет в базе. Пожалуйста, выберите жанр из списка.")
            return

        user = update.message.from_user
        user_id = user.id
        user_username = user.username

       
        rated_genres_count = database.get_rated_genres_count(user_id)
        if rated_genres_count >= 5:
            await update.message.reply_text("Вы уже оценили 5 жанров. Больше оценивать нельзя.")
            return

        if database.check_genre_rating(user_id, track_genre):
            await update.message.reply_text(f"Вы уже оценили жанр '{track_genre}'.")
            return

        database.add_genre_rating(user_id, user_username, track_genre, rating)
        await update.message.reply_text(f"Вы оценили жанр '{track_genre}' на {rating}/5.")

        
        rated_genres_count += 1
        if rated_genres_count >= 5:
            await update.message.reply_text("Вы оценили 5 жанров. Переходим к рекомендациям!")
            await send_recommendation(update, context)
        else:
            await update.message.reply_text(f"Оцените ещё {5 - rated_genres_count} жанров.")

    except ValueError:
        await update.message.reply_text("Ошибка формата. Используйте формат 'Жанр - Оценка'. Пример: 'Rock - 5'")


async def send_main_menu(update: Update):
    keyboard = [
        [InlineKeyboardButton("Получить рекомендацию", callback_data="get_recommendation")],
        [InlineKeyboardButton("Посмотреть все оценки", callback_data="view_ratings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)




def get_random_track():
    random_index = random.randint(0, len(dataset) - 1)
    track = dataset.iloc[random_index]
    return {
        "id": track["track_id"],
        "name": track["track_name"],
        "artist": track["artist_name"],
        "genre": track["genre"],
        "link": f"https://open.spotify.com/track/{track['track_id']}",
    }





async def send_recommendation(update: Update, context: CallbackContext):
    track = get_random_track()

    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=f"rate_{track['id']}_{i}") for i in range(1, 6)],
        [InlineKeyboardButton("Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query: #nazhal knopku
        query = update.callback_query
        await query.message.reply_text(
            f"🎵 *{track['name']}* - {track['artist']}\nЖанр: {track['genre']}\n[Слушать трек]({track['link']})",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else: # net callback zaprosa
        await update.message.reply_text(
            f"🎵 *{track['name']}* - {track['artist']}\nЖанр: {track['genre']}\n[Слушать трек]({track['link']})",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )




async def rate_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()


    _, track_id, rating = query.data.split("_")
    rating = int(rating)

    user = query.from_user
    user_id = user.id

  
    track = dataset[dataset["track_id"] == track_id].iloc[0]
    track_name = track["track_name"]
    track_artist = track["artist_name"]
    track_genre = track["genre"]
    track_link = f"https://open.spotify.com/track/{track_id}"

  
    if database.check_rating(user_id, track_id):
        try:
            database.update_rating(user_id, track_id, rating)
        except ValueError as e:
            await query.edit_message_text(f"Ошибка: {e}")
    else:
        try:
            database.add_rating(user_id, user.username, track_id, track_genre, rating)
        except ValueError as e:
            await query.edit_message_text(f"Ошибка: {e}")

    
    rating_text = f"Ваша оценка для этого трека: {rating}/5"

    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=f"rate_{track_id}_{i}") for i in range(1, 6)],
        [InlineKeyboardButton("Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

   
    await query.edit_message_text(
        f"🎵 *{track_name}* - {track_artist}\nЖанр: {track_genre}\n[Слушать трек]({track_link})\n\n{rating_text}",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

   
    await asyncio.sleep(1)

    
    await send_recommendation(update, context)



async def show_next_step(query):
    keyboard = [
        [InlineKeyboardButton("Следующий трек", callback_data="get_recommendation")],
        [InlineKeyboardButton("Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("Что вы хотите сделать дальше?", reply_markup=reply_markup)




async def view_ratings(update: Update, context: CallbackContext):
    user = update.callback_query.from_user
    user_id = user.id
    query = update.callback_query

  
    ratings = database.get_user_ratings(user_id)

    if not ratings:
        await query.message.reply_text("У вас еще нет оценок.")
        return

    ratings_text = ""
    for track_id, track_genre, rating in ratings:
        
        track = dataset[dataset["track_id"] == track_id]
        if not track.empty:
            track_name = track.iloc[0]["track_name"]
            track_genre = track.iloc[0]["genre"]
            track_url = f"https://open.spotify.com/track/{track_id}"
            ratings_text += f"🎵 *{track_name}* - Жанр: {track_genre}, Ваша оценка: {rating}/5\n"
        else:
            ratings_text += f"❓ Трек ID: {track_id} (не найден в датасете), Ваша оценка: {rating}/5\n"


    await query.message.reply_text(
        f"Ваши оценки:\n{ratings_text}",
        parse_mode="Markdown"
    )

    
    keyboard = [[InlineKeyboardButton("Главное меню", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Что вы хотите сделать дальше?", reply_markup=reply_markup)


async def main_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Получить рекомендацию", callback_data="get_recommendation")],
        [InlineKeyboardButton("Посмотреть все оценки", callback_data="view_ratings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите действие:", reply_markup=reply_markup)




def main():
    application = Application.builder().token(token_teleg).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(rate_callback, pattern="^rate_"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(view_ratings, pattern="^view_ratings$"))
    application.add_handler(CallbackQueryHandler(send_recommendation, pattern="^get_recommendation$"))
    application.add_handler(MessageHandler(filters.TEXT, handle_genre_rating))
    application.add_handler(CallbackQueryHandler(start_genre_survey, pattern="^start_genre_survey$"))   


    application.run_polling()

if __name__ == "__main__":
    main()
