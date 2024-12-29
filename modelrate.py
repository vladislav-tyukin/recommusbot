import pandas as pd
import numpy as np
import ast
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error

import database  # 



df = pd.read_csv("SpotifyFeatures.csv")
dataset2 = pd.read_csv("SpotifyFeatures.csv")


columns_to_drop = ['energy', 'danceability', 'explicit', 'duration_ms']
df = df.drop(columns=columns_to_drop)

df = df.drop_duplicates(subset='track_id')
dataset2 = dataset2.drop_duplicates(subset='track_id')





def clean_genre(value):
    try:
        genre_list = ast.literal_eval(value)
        if isinstance(genre_list, list) and len(genre_list) > 0:
            return genre_list[0]
        else:
            return value
    except (ValueError, SyntaxError):
        return value

def clean_artist(value):
    try:
        artist_list = ast.literal_eval(value)
        if isinstance(artist_list, list) and len(artist_list) > 0:
            return artist_list[0]
        else:
            return value
    except (ValueError, SyntaxError):
        return value

df['genre'] = df['genre'].apply(clean_genre)
df = df.dropna(subset=['genre'])

df['artist_name'] = df['artist_name'].apply(clean_artist)
df = df.dropna(subset=['artist_name'])


scaler = MinMaxScaler(feature_range=(0, 1))
df['normalized_popularity'] = scaler.fit_transform(df[['popularity']])
dataset2['normalized_popularity'] = scaler.fit_transform(dataset2[['popularity']])

df = (
    df
    .sort_values('normalized_popularity', ascending=False) 
    .drop_duplicates(subset=['track_name', 'artist_name'], keep='first')
    .reset_index(drop=True)
)

dataset2 = (
    dataset2
    .sort_values('normalized_popularity', ascending=False) 
    .drop_duplicates(subset=['track_name', 'artist_name'], keep='first')
    .reset_index(drop=True)
)

df = df[df['normalized_popularity'] > 0]

genre_popularity = df.groupby('genre')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')
artist_popularity = df.groupby('artist_name')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')
track_popularity = df.groupby('track_name')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')

artist_numeric_mapping = {artist: idx + 1 for idx, artist in enumerate(artist_popularity['artist_name'])}
genre_numeric_mapping = {genre: idx + 1 for idx, genre in enumerate(genre_popularity['genre'])}
track_numeric_mapping = {track: idx + 1 for idx, track in enumerate(track_popularity['track_name'])}


def get_user_ratings_df_from_db(user_id, df, artist_numeric_mapping, genre_numeric_mapping, track_numeric_mapping):

    """
    Читаем из базы все оценки пользователя: (track_id, track_genre, rating), 
    а также оценки жанров и артистов, если нужно.
    
    Возвращаем DataFrame в формате:
      track_name | artist_name | track_genre | user_artist_rating | user_genre_rating | user_track_rating
    где track_name, artist_name, track_genre и т.д. восстанавливаем на основе исходного DataFrame `df`.
    """

    user_track_ratings = database.get_user_ratings(user_id) 
    user_genre_ratings = database.get_genre_rating(user_id) 
    user_artist_ratings = database.get_artist_rating(user_id)



    columns = ["track_name", "artist_name", "genre",
               "user_artist_rating", "user_genre_rating", "user_track_rating"]
    user_ratings_df = pd.DataFrame(columns=columns)

    for (t_id, t_genre, t_rating) in user_track_ratings:
      
        row_df = df[df["track_id"] == str(t_id)]
        if row_df.empty:
           
            continue
        row_first = row_df.iloc[0]
       
        new_row = {
            "track_name": row_first["track_name"],
            "artist_name": row_first["artist_name"],
            "genre": row_first["genre"],
            "user_artist_rating": None,
            "user_genre_rating": None,
            "user_track_rating": t_rating
        }
        user_ratings_df = pd.concat([user_ratings_df, pd.DataFrame([new_row])], ignore_index=True)

    
    for (g, g_rating) in user_genre_ratings:
        genre_df = df[df["genre"] == g].copy()
        if len(genre_df) == 0:
           
            continue
        
     
        if genre_df["normalized_popularity"].isna().all():
            continue

        best_idx = genre_df["normalized_popularity"].idxmax()
        best_row = genre_df.loc[best_idx]

        new_row = {
            "track_name": best_row["track_name"],
            "artist_name": best_row["artist_name"],
            "genre": best_row["genre"],
            "user_artist_rating": None,
            "user_genre_rating": g_rating,
            "user_track_rating": None
        }
        user_ratings_df = pd.concat([user_ratings_df, pd.DataFrame([new_row])], ignore_index=True)



    for (a, a_rating) in user_artist_ratings:
        artist_df = df[df["artist_name"] == a]
        if len(artist_df) == 0:
            continue
        
        if artist_df["normalized_popularity"].isna().all():
            continue

        best_idx = artist_df["normalized_popularity"].idxmax()
        best_row = artist_df.loc[best_idx]
        
        new_row = {
            "track_name": best_row["track_name"],
            "artist_name": best_row["artist_name"], 
            "genre": best_row["genre"],
            "user_artist_rating": a_rating,
            "user_genre_rating": None,
            "user_track_rating": None
        }
        user_ratings_df = pd.concat([user_ratings_df, pd.DataFrame([new_row])], ignore_index=True)

    return user_ratings_df




def fill_none_in_row(row):
    """
    Заполняет None в оценках по следующему принципу:
    - Если нет известных оценок, ставим 3.
    - Если есть оценки, выбираем fill_value равный максимальной известной оценке.
    """
    ratings = [row['user_artist_rating'], row['user_genre_rating'], row['user_track_rating']]
    known_ratings = [r for r in ratings if pd.notnull(r)]

    if len(known_ratings) == 0:
        fill_value = 3
    else:
      
        fill_value = max(known_ratings)

    new_ratings = [fill_value if pd.isnull(r) else r for r in ratings]
    row['user_artist_rating'] = new_ratings[0]
    row['user_genre_rating'] = new_ratings[1]
    row['user_track_rating'] = new_ratings[2]
    return row



def train_model(df, user_ratings_df, artist_numeric_mapping, genre_numeric_mapping, track_numeric_mapping):
    """
    Обучение модели (RandomForestRegressor) для предсказания оценки трека.
    Используем только оценку трека как целевую переменную.
    """
    merged = pd.merge(
        user_ratings_df,
        df[['artist_name', 'genre', 'track_name', 'normalized_popularity']],
        on=['track_name', 'artist_name', 'genre'],
        how='left'
    )

    merged['artist_id'] = merged['artist_name'].map(artist_numeric_mapping)
    merged['genre_id'] = merged['genre'].map(genre_numeric_mapping)
    merged['track_id'] = merged['track_name'].map(track_numeric_mapping)
    
    merged = merged.dropna(subset=['normalized_popularity', 'artist_id', 'genre_id', 'track_id', 'user_track_rating'])
    X = merged[['normalized_popularity', 'artist_id', 'genre_id', 'track_id']].values
    Y_track = merged['user_track_rating'].values

    if len(X) == 0:
        model = RandomForestRegressor(random_state=42)
        return model
    
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, Y_track)
    return model



def not_in_user_tracks(row, user_tracks):
    return row['track_id'] not in user_tracks

def get_recommended_track_for_user(user_id, df,
                                  artist_numeric_mapping, 
                                  genre_numeric_mapping, 
                                  track_numeric_mapping):
    """
    1) Формируем DataFrame с оценками пользователя, используя базу (database.py)
    2) Вызываем train_model(...)
    3) Формируем список кандидатов
    4) Возвращаем (track_id, pred_rating)
    """

    user_ratings_df = get_user_ratings_df_from_db(
        user_id, df, artist_numeric_mapping, genre_numeric_mapping, track_numeric_mapping
    )
    

    user_ratings_df = user_ratings_df.apply(fill_none_in_row, axis=1)
    user_ratings_df = fill_missing_track_info(user_ratings_df, df)


    model = train_model(df, user_ratings_df, artist_numeric_mapping, genre_numeric_mapping, track_numeric_mapping)
    

    df['artist_id'] = df['artist_name'].map(artist_numeric_mapping)
    df['genre_id']  = df['genre'].map(genre_numeric_mapping)
    df['track_id']  = df['track_name'].map(track_numeric_mapping)

    valid_df = df.dropna(subset=['normalized_popularity','artist_id','genre_id','track_id'])
    X_all = valid_df[['normalized_popularity','artist_id','genre_id','track_id']].values
    predictions = model.predict(X_all)
    valid_df['pred_user_track_rating'] = predictions

  
    if 'track_id' in valid_df.columns:
        valid_df = valid_df.drop(columns=['track_id'])


    valid_df = pd.merge(
        valid_df,
        dataset2[['track_name', 'artist_name', 'track_id']], 
        on=['track_name', 'artist_name'],
        how='left',
        suffixes=('', '_ds2') 
    )

    user_tracks_rated = database.get_user_ratings(user_id)  


    user_track_ids = {str(tr[0]).strip() for tr in user_tracks_rated}
    print("Юзерские треки", "\n", user_track_ids)

    valid_df['track_id'] = valid_df['track_id'].astype(str).str.strip()


    mask = valid_df.apply(lambda r: not_in_user_tracks(r, user_track_ids), axis=1)
    candidates = valid_df[mask]

    
    if len(candidates) == 0:
        return None, None


    candidates = candidates.sort_values('pred_user_track_rating', ascending=False)
    print(candidates, '\n')
    best_candidate = candidates.iloc[0]
    print(best_candidate)
    recommended_track = best_candidate['track_name']
    recommended_artist = best_candidate['artist_name']

    track = dataset2[
        (dataset2['track_name'] == recommended_track) &
        (dataset2['artist_name'] == recommended_artist)
    ]

    if track.empty:
        return None, None  

    track = track.iloc[0]

    return {
        "id": track["track_id"],
        "name": track["track_name"],
        "artist": track["artist_name"],
        "genre": track["genre"],
        "link": f"https://open.spotify.com/track/{track['track_id']}",
    }




def fill_missing_track_info(user_ratings_df, df):
    """
    Если в user_ratings_df отсутствует track_name, но есть artist или genre,
    выбираем наиболее популярный трек этого артиста или жанра для заполнения.
    Если ни артист, ни жанр не известны, удаляем строку.
    """
    updated_rows = []
    for i, row in user_ratings_df.iterrows():
        track_name = row['track_name']
        artist_name = row['artist_name']
        genre_name = row['genre']

        if pd.isnull(track_name):
            if pd.notnull(artist_name):
                artist_tracks = df[df['artist_name'] == artist_name]
                if len(artist_tracks) > 0:
                    best_track = artist_tracks.loc[artist_tracks['normalized_popularity'].idxmax()]
                    row['track_name'] = best_track['track_name']
                    row['genre'] = best_track['genre']
                else:
                    continue
            elif pd.notnull(genre_name):
                genre_tracks = df[df['genre'] == genre_name]
                if len(genre_tracks) > 0:
                    best_track = genre_tracks.loc[genre_tracks['normalized_popularity'].idxmax()]
                    row['track_name'] = best_track['track_name']
                    row['artist_name'] = best_track['artist_name']
                else:
                    continue
            else:
              
                continue

        updated_rows.append(row)
    
    return pd.DataFrame(updated_rows, columns=user_ratings_df.columns)

# ============================================================
# Метрики качества
# ============================================================

def compute_rmse(actual, predicted):
    mse = mean_squared_error(actual, predicted)
    return np.sqrt(mse)

def compute_precision_recall_at_k(test_df, predicted_ratings, k=5, relevant_threshold=4):
    test_df = test_df.copy()
    test_df['pred_user_track_rating'] = predicted_ratings
    test_df['relevant'] = test_df['user_track_rating'] >= relevant_threshold
    test_df = test_df.sort_values('pred_user_track_rating', ascending=False)
    top_k = test_df.head(k)

    relevant_in_top_k = top_k['relevant'].sum()
    precision_at_k = relevant_in_top_k / k

    total_relevant = test_df['relevant'].sum()
    recall_at_k = relevant_in_top_k / total_relevant if total_relevant > 0 else 0.0

    return precision_at_k, recall_at_k

# ============================================================
# Цикл рекомендаций
# ============================================================
user_id = int(input("Введите id пользователя: "))

user_df = get_user_ratings_df_from_db(user_id, df, artist_numeric_mapping, genre_numeric_mapping, track_numeric_mapping)



train_df = user_df.sample(frac=0.7, random_state=42)
test_df = user_df.drop(train_df.index)

model = train_model(df, train_df, artist_numeric_mapping, genre_numeric_mapping, track_numeric_mapping)

merged_test = pd.merge(
    test_df,
    df[['artist_name', 'genre', 'track_name', 'normalized_popularity']],
    on=['artist_name', 'genre', 'track_name'],
    how='left'
)

merged_test['artist_id'] = merged_test['artist_name'].map(artist_numeric_mapping)
merged_test['genre_id'] = merged_test['genre'].map(genre_numeric_mapping)
merged_test['track_id'] = merged_test['track_name'].map(track_numeric_mapping)

X_test = merged_test[['normalized_popularity', 'artist_id', 'genre_id', 'track_id']].values
predicted_test_ratings = model.predict(X_test)
actual_test_ratings = merged_test['user_track_rating'].fillna(3).values

rmse = compute_rmse(actual_test_ratings, predicted_test_ratings)
precision, recall = compute_precision_recall_at_k(merged_test, predicted_test_ratings, k=5, relevant_threshold=4)

print("Результаты оценки модели:")
print("RMSE:", rmse)
print("Precision@5:", precision)
print("Recall@5:", recall)
print("Конец программы")