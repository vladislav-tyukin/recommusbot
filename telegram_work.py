import asyncio
import database
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
import pandas as pd
from token_tg import token_teleg
from sklearn.preprocessing import MinMaxScaler
import model_db  
from model_db import clean_genre, clean_artist, get_recommended_track_for_user

database.init_db()

def load_dataset():
    return pd.read_csv("SpotifyFeatures.csv")

dataset = load_dataset()
dataset2 = load_dataset()

columns_to_drop = ['energy', 'danceability', 'explicit', 'duration_ms']
dataset = dataset.drop(columns=columns_to_drop)

dataset = dataset.drop_duplicates(subset='track_id')
dataset2 = dataset2.drop_duplicates(subset='track_id')

dataset['genre'] = dataset['genre'].apply(clean_genre)
dataset = dataset.dropna(subset=['genre'])

dataset['artist_name'] = dataset['artist_name'].apply(clean_artist)
dataset = dataset.dropna(subset=['artist_name'])

# нормализация популярности
scaler = MinMaxScaler(feature_range=(0, 1))
dataset['normalized_popularity'] = scaler.fit_transform(dataset[['popularity']])
dataset = dataset[dataset['normalized_popularity'] > 0]

# формирование маппингов для артистов, жанров и треков
genre_popularity = dataset.groupby('genre')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')
artist_popularity = dataset.groupby('artist_name')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')
track_popularity = dataset.groupby('track_name')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')

artist_numeric_mapping = {artist: idx + 1 for idx, artist in enumerate(artist_popularity['artist_name'])}
genre_numeric_mapping = {genre: idx + 1 for idx, genre in enumerate(genre_popularity['genre'])}
track_numeric_mapping = {track: idx + 1 for idx, track in enumerate(track_popularity['track_name'])}



current_input_type = None

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    username = user.username

    if database.is_new_user(user_id):
        await update.message.reply_text(f"Привет {username}! Вы новый пользователь. Давайте начнем!")
        await main_menu(update, context)
    else:
        await update.message.reply_text(f"С возвращением, {username}! Продолжим с рекомендациями.")
        await main_menu(update, context)

async def start_genre_survey(update: Update, context: CallbackContext):
    global current_input_type
    current_input_type = "genre" 

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

async def start_artist_survey(update: Update, context: CallbackContext):
    global current_input_type
    current_input_type = "artist"

    artists = dataset["artist_name"].unique().tolist()
    artists_display = artists[:50]
    artists_text = "\n".join([f"{artist}" for artist in artists_display])
    if update.callback_query:
        query = update.callback_query
        await query.answer() 
        await query.message.reply_text(
            f"Оцените исполнителей(в формате 'Автор - оценка'). Пример:\nEminem - 5\n\nИсполнители:\n{artists_text}"
        )
    else:
        await update.message.reply_text(
            f"Оцените исполнителей(в формате 'Автор - оценка'). Пример:\nEminem - 5\n\nИсполнители:\n{artists_text}"
        )

async def handle_rating(update: Update, context: CallbackContext):
    global current_input_type
    text = update.message.text
    
    try:
        name, rating = text.split(" - ")
        rating = int(rating)
        name = name.strip()

        if rating < 1 or rating > 5:
            await update.message.reply_text("Оценка должна быть от 1 до 5.")
            return

        user = update.message.from_user
        user_id = user.id

        if current_input_type == "genre":
            genres = dataset["genre"].unique().tolist()
            if name not in genres:
                await update.message.reply_text(f"Жанра '{name}' нет в базе. Пожалуйста, выберите жанр из списка.")
                return

            rated_genres_count = database.get_rated_genres_count(user_id)
            if rated_genres_count >= 5:
                await update.message.reply_text("Вы уже оценили 5 жанров. Больше оценивать нельзя.")
                return

            if database.check_genre_rating(user_id, name):
                await update.message.reply_text(f"Вы уже оценили жанр '{name}'.")
                return

            database.add_genre_rating(user_id, user.username, name, rating)
            await update.message.reply_text(f"Вы оценили жанр '{name}' на {rating}/5.")

            rated_genres_count += 1
            if rated_genres_count >= 5:
                await update.message.reply_text("Вы оценили 5 жанров. Ура!")
                await main_menu(update, context)
            else:
                await update.message.reply_text(f"Оцените ещё {5 - rated_genres_count} жанров.")

        elif current_input_type == "artist":
            artists = dataset["artist_name"].unique().tolist()
            if name not in artists:
                await update.message.reply_text(f"Исполнителя '{name}' нет в базе. Пожалуйста, выберите из списка.")
                return

            rated_artist_count = database.get_rated_artists_count(user_id)
            if rated_artist_count >= 5:
                await update.message.reply_text("Вы уже оценили 5 исполнителей. Больше оценивать нельзя.")
                return

            if database.check_artist_rating(user_id, name):
                await update.message.reply_text(f"Вы уже оценили исполнителя '{name}'.")
                return

            database.add_artist_rating(user_id, user.username, name, rating)
            await update.message.reply_text(f"Вы оценили исполнителя '{name}' на {rating}/5.")

            rated_artist_count += 1
            if rated_artist_count >= 5:
                await update.message.reply_text("Вы оценили 5 исполнителей. Ура!")
           
                await main_menu(update, context)
            else:
                await update.message.reply_text(f"Оцените ещё {5 - rated_artist_count} исполнителей.")

    except ValueError:
        await update.message.reply_text("Ошибка формата. Используйте формат 'Жанр/Исполнитель - Оценка'. Пример: 'Eminem - 5'")


async def main_menu(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user = query.from_user 
    else:
        user = update.message.from_user 
    
    rated_genres_count = database.get_rated_genres_count(user.id)
    rated_artists_count = database.get_rated_artists_count(user.id)

    keyboard = [
        [InlineKeyboardButton("Получить рекомендацию", callback_data="get_recommendation")],
        [InlineKeyboardButton("Посмотреть все оценки", callback_data="view_ratings")],
    ]

    if rated_genres_count < 5:
        keyboard.append([InlineKeyboardButton("Оценить жанры", callback_data="start_genre_survey")])

    if rated_artists_count < 5:
        keyboard.append([InlineKeyboardButton("Оценить исполнителей", callback_data="start_artist_survey")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await query.edit_message_text("Выберите действие:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

def get_track_info(track_name):
    track = dataset2[dataset2["track_name"] == track_name]
    if track.empty:
        return None
    track = track.iloc[0]
    return {
        "id": track["track_id"],
        "name": track["track_name"],
        "artist": track["artist_name"],
        "genre": track["genre"],
        "link": f"https://open.spotify.com/track/{track['track_id']}",
    }

async def send_recommendation(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id

    track = get_recommended_track_for_user(user_id, dataset, artist_numeric_mapping=artist_numeric_mapping,
                                           genre_numeric_mapping=genre_numeric_mapping, track_numeric_mapping=track_numeric_mapping)

    print(track['id'])
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

    track = dataset2[dataset2["track_id"] == track_id].iloc[0]  
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
        track = dataset2[dataset2["track_id"] == track_id] 
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

def main():
    application = Application.builder().token(token_teleg).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(rate_callback, pattern="^rate_"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(view_ratings, pattern="^view_ratings$"))
    application.add_handler(CallbackQueryHandler(send_recommendation, pattern="^get_recommendation$"))
    application.add_handler(MessageHandler(filters.TEXT, handle_rating))
    application.add_handler(CallbackQueryHandler(start_genre_survey, pattern="^start_genre_survey$")) 
    application.add_handler(CallbackQueryHandler(start_artist_survey, pattern="^start_artist_survey$")) 

   
    application.run_polling()

if __name__ == "__main__":
    main()
