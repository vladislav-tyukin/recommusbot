# Отчет о разработке и обучении системы рекомендаций


## Этапы работы

1. **Формулировка задачи**
   - Целью проекта являлась разработка Telegram-бота для рекомендаций музыкальных треков на основе пользовательских предпочтений.
   - Предусматривалась возможность просмотра рекомендаций, оценивания треков и жанров, а также формирования новых рекомендаций на основе обученной модели.

2. **Сбор и подготовка данных**
   - Для работы использовался датасет музыкальных треков из библиотеки Spotify.
   - Библиотеки `pandas`, `sqlite` использовалась для обработки данных.
   - Выполнена предобработка данных:
   ```python
	    # Удаляем ненужные столбцы
		columns_to_drop = ['energy', 'danceability', 'explicit', 'duration_ms']
		df = df.drop(columns=columns_to_drop)

		# Очистка данных и удаление строк без жанра и артиста
		df['genre'] = df['genre'].apply(clean_genre)
		df = df.dropna(subset=['genre'])
		
		df['artist_name'] = df['artist_name'].apply(clean_artist)
		df = df.dropna(subset=['artist_name'])


		df = (
			df
		    .sort_values('normalized_popularity', ascending=False)
		    .drop_duplicates(subset=['track_name', 'artist_name'], keep='first')
			.reset_index(drop=True)
		)
	```
     - Очистка от дубликатов.
		```python
		df = df.drop_duplicates(subset='track_id')
		```
     - Нормализация числового признака (популярность).
	     ```python
	    scaler = MinMaxScaler(feature_range=(0, 1))
		df['normalized_popularity'] = scaler.fit_transform(df[['popularity']])
		df = df[df['normalized_popularity'] > 0]
		
	```
     - Кодирование категориальных признаков (жанры).
	     ```python
		genre_popularity = df.groupby('genre')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')

		artist_popularity = df.groupby('artist_name')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')

		track_popularity = df.groupby('track_name')['normalized_popularity'].mean().reset_index().sort_values('normalized_popularity')

  

		artist_numeric_mapping = {artist: idx + 1 for idx, artist in enumerate(artist_popularity['artist_name'])}
		
		genre_numeric_mapping = {genre: idx + 1 for idx, genre in enumerate(genre_popularity['genre'])}
		
		track_numeric_mapping = {track: idx + 1 for idx, track in enumerate(track_popularity['track_name'])}
		```
   
3. Реализация модели машинного обучения
	1. `RandomForestRegressor`
4. Оценка качества модели
	1. `RMSE, PRECISION@K, Recall@K`
5. Интерфейс
	1. `Telegram`

## Используемые методы

1. **Модель машинного обучения**
   - `RandomForestRegressor`  как ансамблевый метод.
	   - `n_estimators=100` - Модель строит **100 деревьев решений**, каждое из которых обучается на случайной подвыборке данных.
	   - `random_state = 42` - фиксированное начальное значение для генератора случайных чисел. Можно какое угодно число поставить.
   - Разделение данных на обучающую и тестовую выборки в соотношении 70/30.
	   ```python
	   # Например
	    train_df = user_df.sample(frac=0.7, random_state=42)
		test_df = user_df.drop(train_df.index)
		```

2. **Реализация рекомендаций**
   - Для пользователя формировался список рекомендаций на основе его предыдущих оценок.

## Интерфейс

- Интерфейс был реализован на основе TelegramBot с помощью библиотеки python-telegram-bot, которая обеспечила удобный интерфейс для работы с TelegramAPI. 
- С ее помощью был реализован функционал для обработки сообщений пользователей, создание меню с кнопками. 
- Асинхронная возможность и работа этой библиотеки поспособствовала высокой производительности, что сделало взаимодействие с ботом быстрым и удобным для пользователей.

## Данные & Библиотеки

- Библиотека `sqlite` использовалась для работы с локальной базой данных для хранения информации о пользователях, их оценках и результатах рекомендаций. Функциональность библиотеки позволяет выполнять операции удаления, добавления, обновления данных.
- Библиотека `pandas` использовалась для формирования пользовательского `dataframe`, который далее используется в обучении модели и выдачи наиболее рекомендуемого трека.
- Библиотека `ast` использовалась для парсинга строк, содержащие столбцы жанров и артистов в датасете
- Библиотека `sklearn` была основной библиотекой для создания и обучения модели.
## Результаты

- После обучения модель показала следующие результаты. Эксперимент производился на двух пользователях.
- Пользователь-1 ("Любитель")
		**RMSE** (1.086) - измеряет среднюю ошибку предсказания в тех же единицах, что и оценка пользователя (шкала от 1 до 5). Значение 1.086 указывает на то, что предсказания модели в среднем отклоняются от реальных оценок на ~1.1 балла.
		**Precision@5** (0.8) - показывает, какая доля треков из топ-5 рекомендаций оказалась релевантной (оценка пользователя ≥ 4). Значение 0.8 означает, что 80% из предложенных пользователю топ-5 треков соответствуют его вкусу.
		**Recall@5** (0.4) - измеряет, какую долю всех релевантных треков модель смогла включить в топ-5 рекомендаций. Значение 0.4 указывает, что модель захватывает только 40% релевантных треков.
- Пользователь-2 ("Эксперт")
		RMSE: 1.600960649110402 
		Precision@5: 0.4 
		Recall@5: 0.5
### Итоговый анализ

- **Достоинства**:
    - Модель хорошо справляется с точностью рекомендаций (Precision@5 = 80%).
    - RMSE указывает на адекватные предсказания (ошибка ~1.1 на шкале 1-5).
- **Проблемы**:
    - Recall@5 = 0.4 означает, что модель захватывает только 40% всех релевантных треков. Это указывает на необходимость работы над **разнообразием** рекомендаций и увеличением охвата.
- **Анализ двух пользователей**:
	- Эксперимент проводился на двух пользователях. Первый пользователь является любителем и не проводил долгие размышления о том какую оценку он поставит соответствующему треку.
	- Второй пользователь является экспертом, который на основе своих музыкальных знаний и предпочтений ставил полностью аргументированную оценку трекам.
	- Ниже приведены графики метрик двух пользователей (на основе `matplotlib`):
	
		
		![1](https://www.upload.ee/image/17570719/Pasted_image_20241229195346.png)
		![2](https://www.upload.ee/image/17570724/Pasted_image_20241229195353.png)
		![3](https://www.upload.ee/image/17570726/Pasted_image_20241229195406.png)
			
	  

## Заключение

- Telegram-бот успешно реализован, обеспечивает удобную навигацию и рекомендации высокого качества.
- Разработанная система продемонстрировала неплохие значения метрик, однако не покрывает все возможные предпочтения пользователя (см. Recall@5).
- В дальнейшем возможна доработка модели на большем числе пользователей, создании большого датасета, функционала для персонализации, включая использование нейронных сетей.
