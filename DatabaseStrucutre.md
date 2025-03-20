		CREATE TABLE "Soundmusicconnect".song_performers (
			song_id int4 NOT NULL,
			performer_id int4 NOT NULL,
			CONSTRAINT song_performers_pkey PRIMARY KEY (song_id, performer_id),
			CONSTRAINT song_performers_performer_id_fkey FOREIGN KEY (performer_id) REFERENCES "Soundmusicconnect".performers(id) ON DELETE CASCADE,
			CONSTRAINT song_performers_song_id_fkey FOREIGN KEY (song_id) REFERENCES "Soundmusicconnect".songs(idtrack) ON DELETE CASCADE
		);
		CREATE TABLE "Soundmusicconnect".albums (
			idalbum serial4 NOT NULL,
			albumname varchar(100) NOT NULL,
			performer_id int4 NOT NULL,
			yearrelease date NOT NULL,
			imagealbum bytea NULL,
			CONSTRAINT albums_pkey PRIMARY KEY (idalbum),
			CONSTRAINT albums_performer_id_fkey FOREIGN KEY (performer_id) REFERENCES "Soundmusicconnect".performers(id)
		);
		CREATE TABLE "Soundmusicconnect".listening_history (
			id serial4 NOT NULL,
			user_id int4 NOT NULL,
			song_id int4 NOT NULL,
			listened_at timestamp DEFAULT now() NOT NULL,
			CONSTRAINT listening_history_pkey PRIMARY KEY (id),
			CONSTRAINT listening_history_song_id_fkey FOREIGN KEY (song_id) REFERENCES "Soundmusicconnect".songs(idtrack),
			CONSTRAINT listening_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES "Soundmusicconnect".users(id)
		);
		CREATE TABLE "Soundmusicconnect".favorite_songs (
			user_id int4 NOT NULL,
			song_id int4 NOT NULL,
			added_at timestamp DEFAULT now() NULL,
			CONSTRAINT favorite_songs_pkey PRIMARY KEY (user_id, song_id),
			CONSTRAINT favorite_songs_song_id_fkey FOREIGN KEY (song_id) REFERENCES "Soundmusicconnect".songs(idtrack),
			CONSTRAINT favorite_songs_user_id_fkey FOREIGN KEY (user_id) REFERENCES "Soundmusicconnect".users(id)
		);
		CREATE TABLE "Soundmusicconnect".favorite_albums (
			user_id int4 NOT NULL,
			album_id int4 NOT NULL,
			added_at timestamp DEFAULT now() NULL,
			CONSTRAINT favorite_albums_pkey PRIMARY KEY (user_id, album_id),
			CONSTRAINT favorite_albums_album_id_fkey FOREIGN KEY (album_id) REFERENCES "Soundmusicconnect".albums(idalbum),
			CONSTRAINT favorite_albums_user_id_fkey FOREIGN KEY (user_id) REFERENCES "Soundmusicconnect".users(id)
		);

		CREATE TABLE "Soundmusicconnect".playlists (
			idplay serial4 NOT NULL,
			nameplay varchar NOT NULL,
			madeinuser int4 NULL,
			image bytea NULL,
			CONSTRAINT playlists_pkey PRIMARY KEY (idplay),
			CONSTRAINT playlists_madeinuser_fkey FOREIGN KEY (madeinuser) REFERENCES "Soundmusicconnect".users(id)
		);
		CREATE TABLE "Soundmusicconnect".favorite_performers (
			user_id int4 NOT NULL,
			performer_id int4 NOT NULL,
			added_at timestamp DEFAULT now() NULL,
			CONSTRAINT favorite_performers_pkey PRIMARY KEY (user_id, performer_id),
			CONSTRAINT favorite_performers_performer_id_fkey FOREIGN KEY (performer_id) REFERENCES "Soundmusicconnect".performers(id),
			CONSTRAINT favorite_performers_user_id_fkey FOREIGN KEY (user_id) REFERENCES "Soundmusicconnect".users(id)
		);
		CREATE TABLE "Soundmusicconnect".favorite_playlists (
			user_id int4 NOT NULL,
			playlist_id int4 NOT NULL,
			added_at timestamp DEFAULT now() NULL,
			CONSTRAINT favorite_playlists_pkey PRIMARY KEY (user_id, playlist_id),
			CONSTRAINT favorite_playlists_playlist_id_fkey FOREIGN KEY (playlist_id) REFERENCES "Soundmusicconnect".playlists(idplay),
			CONSTRAINT favorite_playlists_user_id_fkey FOREIGN KEY (user_id) REFERENCES "Soundmusicconnect".users(id)
		);
		CREATE TABLE "Soundmusicconnect".users (
	id serial4 NOT NULL,
	login varchar(30) NOT NULL,
	"password" varchar(60) NOT NULL,
	email varchar(50) NOT NULL,
	status varchar(10) NOT NULL,
	image bytea NULL,
	CONSTRAINT users_pkey PRIMARY KEY (id)
);
		CREATE TABLE "Soundmusicconnect".user_songs (
			user_id int4 NOT NULL,
			song_id int4 NOT NULL,
			CONSTRAINT user_songs_pkey PRIMARY KEY (user_id, song_id),
			CONSTRAINT user_songs_song_id_fkey FOREIGN KEY (song_id) REFERENCES "Soundmusicconnect".songs(idtrack),
			CONSTRAINT user_songs_user_id_fkey FOREIGN KEY (user_id) REFERENCES "Soundmusicconnect".users(id)
		);
		CREATE TABLE "Soundmusicconnect".playlist_songs (
			playlist_id int4 NOT NULL,
			song_id int4 NOT NULL,
			CONSTRAINT playlist_songs_pkey PRIMARY KEY (playlist_id, song_id),
			CONSTRAINT playlist_songs_playlist_id_fkey FOREIGN KEY (playlist_id) REFERENCES "Soundmusicconnect".playlists(idplay),
			CONSTRAINT playlist_songs_song_id_fkey FOREIGN KEY (song_id) REFERENCES "Soundmusicconnect".songs(idtrack)
		);
		CREATE TABLE "Soundmusicconnect".songs (
	idtrack serial4 NOT NULL,
	songname varchar(100) NOT NULL,
	yearcreate int4 NOT NULL,
	genre_id int4 NULL,
	imagesong bytea NULL,
	filepath varchar NULL,
	duration varchar(5) DEFAULT '00:00'::character varying NOT NULL,
	CONSTRAINT songs_pkey PRIMARY KEY (idtrack),
	CONSTRAINT songs_genre_id_fkey FOREIGN KEY (genre_id) REFERENCES "Soundmusicconnect".genres(idgenr)
);
		CREATE TABLE "Soundmusicconnect".genres (
			idgenr serial4 NOT NULL,
			"name" varchar(255) NULL,
			phototrack bytea NULL,
			CONSTRAINT genres_pkey PRIMARY KEY (idgenr)
		);
		CREATE TABLE "Soundmusicconnect".album_songs (
			album_id int4 NOT NULL,
			song_id int4 NOT NULL,
			CONSTRAINT album_songs_pkey PRIMARY KEY (album_id, song_id),
			CONSTRAINT album_songs_album_id_fkey FOREIGN KEY (album_id) REFERENCES "Soundmusicconnect".albums(idalbum) ON DELETE CASCADE,
			CONSTRAINT album_songs_song_id_fkey FOREIGN KEY (song_id) REFERENCES "Soundmusicconnect".songs(idtrack) ON DELETE CASCADE
		); СТРУКТУРА БД
