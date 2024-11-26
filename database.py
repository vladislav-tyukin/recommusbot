import sqlite3

DB_PATH = "bot.db"

def init_db():
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS track_ratings (
                rating_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                track_id INTEGER NOT NULL,
                track_genre INTEGER NOT NULL,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                UNIQUE(user_id, track_id)
            )
        ''')
        
       
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genre_ratings (
                rating_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                track_genre INTEGER NOT NULL,
                genre_rating INTEGER CHECK(genre_rating >= 1 AND genre_rating <= 5),
                UNIQUE(user_id, track_genre)
            )
        ''')
        

def add_rating(user_id, username, track_id, track_genre, rating):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute('INSERT INTO track_ratings (user_id, username, track_id, track_genre, rating) VALUES (?, ?, ?, ?, ?)', 
                           (user_id, username, track_id, track_genre, rating))
            connection.commit()
        except sqlite3.IntegrityError:
            raise ValueError('Rating already exists for this user and track')



def get_user_ratings(user_id):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT track_id, track_genre, rating FROM track_ratings WHERE user_id = ?', (user_id,))
        return cursor.fetchall()



def update_rating(user_id, track_id, new_rating):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('UPDATE track_ratings SET rating = ? WHERE user_id = ? AND track_id = ?', 
                       (new_rating, user_id, track_id))
        connection.commit()
        if cursor.rowcount == 0:
            raise ValueError('Update rating error')



def check_rating(user_id, track_id):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM track_ratings WHERE user_id = ? AND track_id = ?', 
                       (user_id, track_id))
        return cursor.fetchone()[0] > 0


def is_new_user(user_id):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM track_ratings WHERE user_id = ?', (user_id,))
        user_in_users_table = cursor.fetchone()[0] > 0

        cursor.execute('SELECT COUNT(*) FROM genre_ratings WHERE user_id = ?', (user_id,))
        user_in_genre_ratings = cursor.fetchone()[0] > 0

        return not (user_in_users_table or user_in_genre_ratings)





def get_all_ratings():
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM track_ratings')
        return cursor.fetchall()



def add_genre_rating(user_id, username, track_genre, genre_rating):
    with sqlite3.connect(DB_PATH) as connection:
        try:
            cursor = connection.cursor()
            cursor.execute('INSERT INTO genre_ratings (user_id, username, track_genre, genre_rating) VALUES (?, ?, ?, ?)', (user_id, username, track_genre, genre_rating))
            connection.commit()
        except sqlite3.IntegrityError:
            raise ValueError('Add genre rating error')
        

def get_all_genre_ratings():
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM genre_ratings')
        return cursor.fetchall()



def get_genre_rating(user_id):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT track_genre, genre_rating FROM genre_ratings WHERE user_id = ?', (user_id))
        connection.commit()
        return cursor.fetchall()


def check_genre_rating(user_id, track_genre):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT 1 FROM genre_ratings WHERE user_id = ? AND track_genre = ? LIMIT 1', (user_id, track_genre))
        connection.commit()
        return cursor.fetchone()

def get_rated_genres_count(user_id):
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT COUNT(DISTINCT track_genre) FROM genre_ratings WHERE user_id = ?', (user_id,))
        connection.commit()
        return cursor.fetchone()[0]
