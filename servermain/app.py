import base64
import json
import logging
import traceback
import uuid
from collections import Counter
from datetime import datetime
import pandas as pd

import bcrypt
import numpy as np
from dotenv.parser import Reader
from flask import Flask , jsonify , request , send_file
import os
import psycopg2
from dotenv import load_dotenv
import sys
import re  # import the regex library

from oauthlib.common import generate_token
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from send_email import sendemainandcodeoutput

load_dotenv ( )

app = Flask ( __name__ )

log_formatter = logging.Formatter ( '%(asctime)s - %(levelname)s - %(message)s' )
log_handler = logging.StreamHandler ( sys.stderr )
log_handler.setFormatter ( log_formatter )

log = logging.getLogger ( __name__ )
log.setLevel ( logging.DEBUG )
log.addHandler ( log_handler )


def get_db_connection ( ) :
	log.info ( "Attempting to connect to the database..." )
	conn = None
	try :
		conn = psycopg2.connect (
			host = os.environ.get ( 'POSTGRES_HOST' , '192.168.3.190' ) ,
			port = os.environ.get ( 'POSTGRES_PORT' , 5956 ) ,
			database = os.environ.get ( 'POSTGRES_DB' , 'MusicDBcource' ) ,
			user = os.environ.get ( 'POSTGRES_USER' , 'jeived7' ) ,
			password = os.environ.get ( 'POSTGRES_PASSWORD' , 'rafaelov1234' ) ,
			options = "-c search_path=Soundmusicconnect" ,
			)
		log.info ( "Successfully connected to the database." )
		return conn
	except psycopg2.Error as e :
		log.error ( f"Database connection error: {e}" )
		return None


def set_search_path ( conn , schema_name ) :
	return True


@app.route ( '/' )
def hello ( ) :
	log.info ( "GET /" )
	return "<h1>СЕРВЕР БЛЯТЬ</h1>"


@app.route ( '/send_email' , methods = [ 'POST' ] )
def sendemain ( ) :
	try :
		log.info ( "Entering /send_email endpoint..." )
		emailadress = request.get_json ( )
		log.debug ( f"Received {emailadress}" )
		emailsend = emailadress.get ( 'email' )  # Corrected line: Use lowercase 'email'
		
		if not emailsend :
			return jsonify ( { "emailsending" : False , "error" : "Email is required" } ) , 400
		code , error = sendemainandcodeoutput ( emailsend )  # Changed emailsend to tosend_email for consistency
		if error :
			return jsonify ( { "emailsending" : False , "error" : error } ) , 300
		
		return jsonify ( { "emailsending" : True , "code" : code } ) , 200
	except Exception as e :
		log.error ( f"An unexpected error occurred in /send_email endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal Server Error" } ) , 500


@app.route ( '/connect_db' , methods = [ 'GET' ] )
def connect_db ( ) :
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "message" : "Failed to connect to the database." } ) , 500
		return jsonify ( { "message" : "Connection established" } ) , 200
	except Exception as e :
		log.exception ( f"Error in connect_db endpoint: {e}" )
		return jsonify ( { "error" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/check_auth' , methods = [ 'POST' ] )
def check_auth ( ) :
	data = request.get_json ( )
	login = data.get ( 'login' )
	password = data.get ( 'password' )
	
	if not login or not password :
		return jsonify ( { "authorized" : False , "message" : "Login and password are required" } ) , 400
	
	conn = get_db_connection ( )
	if not conn :
		return jsonify ( { "authorized" : False , "message" : "Database connection failed" } ) , 500
	
	cur = conn.cursor ( )
	cur.execute (
		'SELECT id, login, password, status, image FROM "Soundmusicconnect"."users" WHERE login = %s;' , (login ,)
		)
	user = cur.fetchone ( )
	conn.close ( )
	
	if user and bcrypt.checkpw ( password.encode ( 'utf-8' ) , user [ 2 ].encode ( 'utf-8' ) ) :
		token = str ( uuid.uuid4 ( ) )
		# Convert bytea image to base64 if it exists
		image_base64 = base64.b64encode ( user [ 4 ] ).decode ( 'utf-8' ) if user [ 4 ] else None
		return jsonify (
			{
				"authorized" : True ,
				"token" : token ,
				"message" : "Login successful" ,
				"login" : user [ 1 ] ,
				"status" : user [ 3 ] ,
				"image" : image_base64  # Add image field
				}
			)
	else :
		return jsonify ( { "authorized" : False , "message" : "Invalid login or password" } ) , 401


user_data = { }


@app.route ( '/check_login' , methods = [ 'POST' ] )
def check_login ( ) :
	conn = None
	try :
		log.info ( "Entering /check_login endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received {data}" )
		login = data.get ( 'login' )
		
		if not login :
			log.warning ( "Error: Login is required." )
			return jsonify ( { "error" : "Login is required" } ) , 400
		
		if not re.match ( r"^[a-zA-Z0-9]*$" , login ) :  # check for non-cyrillic
			log.warning ( "Error: Login can only contain alphanumeric characters." )
			return jsonify (
				{ "login_available" : False , "error" : "Login can only contain alphanumeric characters" }
				) , 200
		if not (5 <= len ( login ) < 30) :
			log.warning ( "Error: Login must contain between 5 and 30 characters." )
			return jsonify (
				{ "login_available" : False , "error" : "Login must contain between 5 and 30 characters" }
				) , 200
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		cur.execute ( 'SELECT COUNT(*) FROM "Soundmusicconnect"."users" WHERE login = %s;' , (login ,) )
		count = cur.fetchone ( ) [ 0 ]  # Fetch and extract count
		
		if count > 0 :
			log.warning ( f"Login '{login}' already in use." )
			return jsonify ( { "login_available" : False , "error" : "This login is already in use" } ) , 200
		else :
			log.info ( f"Login '{login}' is available." )
			return jsonify ( { "login_available" : True } ) , 200
	
	except Exception as e :
		log.error ( f"An unexpected error occurred in /check_login endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/loginuser' , methods = [ 'POST' ] )
def LoginAutorization ( ) :
	conn = None
	try :
		log.info ( "Entering /loginuser endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received {data}" )
		stored_login = data.get ( 'login' )
		stored_password = data.get ( 'password' )
		
		if not stored_login or not stored_password :
			log.warning ( "Error: Login and password are required." )
			return jsonify ( { "error" : "Login and password are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		
		if "@" in stored_login :  # Check if the user is logging in using email or login.
			cur.execute (
				'SELECT id, password FROM "Soundmusicconnect"."users" WHERE email = %s;' , (stored_login ,)
				)
		else :
			cur.execute (
				'SELECT id, password FROM "Soundmusicconnect"."users" WHERE login = %s;' , (stored_login ,)
				)
		
		user = cur.fetchone ( )
		log.debug ( f"Executed SQL query, user found: {user}" )
		
		if user :
			user_id , hashed_password_from_db = user
			if isinstance ( hashed_password_from_db , str ) and hashed_password_from_db.startswith ( "$2b$" ) :
				if bcrypt.checkpw (
						stored_password.encode ( 'utf-8' ) , hashed_password_from_db.encode ( 'utf-8' )
						) :
					response_data = { "loginuserstatus" : True }
					log.info ( f"Response data for /loginuser (authorized): {response_data}" )
					return jsonify ( response_data ) , 200
				else :
					log.warning ( "User not authorized due to password mismatch." )
					return jsonify (
						{ "loginuserstatus" : False , "error" : "Invalid username or password." }
						) , 200
			else :
				log.error ( "Invalid hashed password format." )
				return jsonify ( { "loginuserstatus" : False , "error" : "Invalid username or password." } ) , 200
		else :
			log.warning ( "User not found." )
			return jsonify ( { "loginuserstatus" : False , "error" : "Invalid username or password." } ) , 200
	
	except Exception as e :
		log.error ( f"An unexpected error occurred in /loginuser endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/check_email' , methods = [ 'POST' ] )
def check_email ( ) :
	conn = None
	try :
		log.info ( "Entering /check_email endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received {data}" )
		stored_email = data.get ( 'email' )
		
		if not stored_email :
			log.warning ( "Error: email is required." )
			return jsonify ( { "error" : "email is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		# *Crucial Fix:* The `users` table must be accessed using the `schema.tablename` format:
		cur.execute ( 'SELECT id FROM "Soundmusicconnect"."users" WHERE email = %s;' , (stored_email ,) )
		user = cur.fetchone ( )
		log.debug ( f"Executed SQL query, user found: {user}" )
		
		if user :
			# User exists, return False
			response_data = { "email_exists" : False }
			log.info ( f"Response data for /check_email (email_exists): {response_data}" )
			return jsonify ( response_data ) , 200
		else :
			# User does not exist, return True
			response_data = { "email_exists" : True }
			log.info ( f"Response data for /check_email (email_exists): {response_data}" )
			return jsonify ( response_data ) , 200
	except Exception as e :
		log.error ( f"An unexpected error occurred in /check_email endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/registationuser' , methods = [ 'POST' ] )
def registationuser ( ) :
	conn = None
	try :
		log.info ( "Entering /registationuser endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received {data}" )
		login = data.get ( 'login' )
		password = data.get ( 'password' )
		email = data.get ( 'email' )
		
		if not login or not password or not email :
			log.warning ( "Error: Login, password and email are required." )
			return jsonify ( { "error" : "Login, password and email are required" } ) , 400
		
		# Хеширование пароля
		hashed_password = bcrypt.hashpw ( password.encode ( 'utf-8' ) , bcrypt.gensalt ( ) ).decode ( 'utf-8' )
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'INSERT INTO "Soundmusicconnect"."users" (login, password, email, status) VALUES (%s, %s, %s, %s);' ,
			(login , hashed_password , email , "user")
			)
		conn.commit ( )
		log.info ( "User registered successfully." )
		return jsonify ( { "registationuserstatus" : True } ) , 200
	
	except Exception as e :
		log.error ( f"An unexpected error occurred in /registationuser endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


script_dir = os.path.dirname ( os.path.abspath ( __file__ ) )
music_dir_path = os.path.join ( script_dir , "musicfile" )


@app.route ( '/play_music' , methods = [ 'POST' ] )
def play_music ( ) :
	conn = None
	try :
		data = request.get_json ( )
		idtrack = data.get ( 'idTrack' )
		user_login = data.get ( 'userLogin' )
		
		if not idtrack or not user_login :
			log.error ( f"Missing parameters. idTrack: {idtrack}, userLogin: {user_login}" )
			return jsonify ( { "error" : "idTrack and userLogin parameters are required" } ) , 400
		
		log.debug ( f"Received request for music file with idtrack: {idtrack}, userLogin: {user_login}" )
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			log.error ( f"User not found for login: {user_login}" )
			return jsonify ( { "error" : "User not found" } ) , 404
		user_id = user_result [ 0 ]
		
		# Adjusted query to handle grouping and favorite check correctly
		cur.execute (
			"""
			SELECT s.songname, STRING_AGG(p.fullname, ', ') AS performers, s.imagesong, s.filepath,
				   CASE WHEN fs.user_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_favorite
			FROM "Soundmusicconnect".songs s
			LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
			LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
			LEFT JOIN "Soundmusicconnect".favorite_songs fs ON s.idtrack = fs.song_id AND fs.user_id = %s
			WHERE s.idtrack = %s
			GROUP BY s.songname, s.imagesong, s.filepath, fs.user_id;
			""" , (user_id , idtrack)
			)
		
		result = cur.fetchone ( )
		if not result :
			log.error ( f"Song data not found in the database for idtrack: {idtrack}" )
			return jsonify ( { "error" : f"Song data not found in the database for idtrack: {idtrack}" } ) , 404
		
		song_name , performer_names , image_data , filepath , is_favorite = result
		
		song_path = os.path.join ( music_dir_path , filepath )
		log.debug ( f"Attempting to access: {song_path}" )
		
		if os.path.isfile ( song_path ) :
			log.debug ( f"Serving song from: {song_path}" )
			with open ( song_path , 'rb' ) as f :
				song_data = f.read ( )
			
			image_base64 = base64.b64encode ( image_data ).decode ( 'utf-8' ) if image_data else None
			
			current_time = datetime.now ( ).isoformat ( )
			cur.execute (
				'''
				INSERT INTO "Soundmusicconnect".listening_history (user_id, song_id, listened_at)
				VALUES (%s, %s, %s)
				''' , (user_id , idtrack , current_time)
				)
			conn.commit ( )
			log.info ( f"Listening history recorded for user {user_login}, song {idtrack} at {current_time}" )
			
			return jsonify (
				{
					"data" : base64.b64encode ( song_data ).decode ( 'utf-8' ) ,
					"songName" : song_name ,
					"performer" : performer_names or "Unknown Artist" ,
					"imageBase64" : image_base64 ,
					"isFavorite" : is_favorite ,
					"listenedAt" : current_time
					}
				) , 200
		else :
			log.error ( f"Song file not found on server: {song_path}" )
			return jsonify ( { "error" : f"Song file not found on server: {song_path}" } ) , 404
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.exception ( f"Server error: {str ( e )}" )
		return jsonify ( { "error" : f"Server error: {str ( e )}" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/popular_content' , methods = [ 'GET' ] )
def popular_content ( ) :
	conn = None
	try :
		user_login = request.args.get ( 'login' )
		if not user_login :
			return jsonify ( { "error" : "Login parameter is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		
		# Get user ID
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			return jsonify ( { "error" : "User not found" } ) , 404
		user_id = user_result [ 0 ]
		
		# Popular Artists
		cur.execute (
			'''
			SELECT p.id, p.fullname, encode(p."Photo", 'base64') AS photo_base64,
				   COUNT(DISTINCT a.idalbum) AS album_count,
				   COUNT(DISTINCT fp.user_id) AS follower_count,
				   EXISTS (
					   SELECT 1 FROM "Soundmusicconnect".favorite_performers f
					   WHERE f.performer_id = p.id AND f.user_id = %s
				   ) AS is_favorite
			FROM "Soundmusicconnect".performers p
			LEFT JOIN "Soundmusicconnect".albums a ON p.id = a.performer_id
			LEFT JOIN "Soundmusicconnect".favorite_performers fp ON p.id = fp.performer_id
			GROUP BY p.id, p.fullname, p."Photo"
			ORDER BY follower_count DESC
			LIMIT 4;
			''' , (user_id ,)
			)
		performer_rows = cur.fetchall ( )
		popular_artists = [
			{
				"id" : row [ 0 ] ,
				"name" : row [ 1 ] ,
				"imageBase64" : row [ 2 ] ,
				"albumCount" : row [ 3 ] ,
				"followerCount" : row [ 4 ] ,
				"isFavorite" : row [ 5 ]
				}
			for row in performer_rows
			]
		
		# Trending Tracks
		cur.execute (
			'''
			SELECT s.idtrack, s.songname, STRING_AGG(DISTINCT p.fullname, ', ') AS artists,
				   COUNT(lh.id) AS play_count,
				   EXISTS (
					   SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
					   WHERE fs.user_id = %s AND fs.song_id = s.idtrack
				   ) AS is_favorite,
				   encode(s.imagesong, 'base64') AS imagesong_base64, s.duration
			FROM "Soundmusicconnect".songs s
			LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
			LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
			LEFT JOIN "Soundmusicconnect".listening_history lh ON s.idtrack = lh.song_id
			GROUP BY s.idtrack, s.songname, s.imagesong, s.duration
			ORDER BY play_count DESC
			LIMIT 15;
			''' , (user_id ,)
			)
		track_rows = cur.fetchall ( )
		trending_tracks = [ ]
		for index , row in enumerate ( track_rows , start = 1 ) :
			total_seconds = convert_duration_to_seconds ( row [ 6 ] )
			minutes = total_seconds//60
			seconds = total_seconds%60
			duration_str = f"{minutes:02d}:{seconds:02d}"
			trending_tracks.append (
				{
					"rank" : index ,
					"songId" : row [ 0 ] ,
					"title" : row [ 1 ] ,
					"artist" : row [ 2 ] or "Unknown Artist" ,
					"duration" : duration_str ,
					"isFavorite" : row [ 4 ] ,
					"imageBase64" : row [ 5 ]
					}
				)
		
		# Popular Playlists
		cur.execute (
			'''
			SELECT p.idplay, p.nameplay, encode(p.image, 'base64') AS image_base64,
				   COUNT(DISTINCT fp.user_id) AS follower_count,
				   EXISTS (
					   SELECT 1 FROM "Soundmusicconnect".favorite_playlists f
					   WHERE f.playlist_id = p.idplay AND f.user_id = %s
				   ) AS is_favorite
			FROM "Soundmusicconnect".playlists p
			LEFT JOIN "Soundmusicconnect".favorite_playlists fp ON p.idplay = fp.playlist_id
			GROUP BY p.idplay, p.nameplay, p.image
			ORDER BY follower_count DESC
			LIMIT 5;
			''' , (user_id ,)
			)
		playlist_rows = cur.fetchall ( )
		popular_playlists = [
			{
				"id" : row [ 0 ] ,
				"name" : row [ 1 ] ,
				"imageBase64" : row [ 2 ] ,
				"followerCount" : row [ 3 ] ,
				"isFavorite" : row [ 4 ]
				}
			for row in playlist_rows
			]
		
		response = {
			"popularArtists" : popular_artists ,
			"trendingTracks" : trending_tracks ,
			"popularPlaylists" : popular_playlists ,
			"error" : None
			}
		log.info ( f"Successfully fetched popular content for user {user_login}" )
		return jsonify ( response ) , 200
	
	except Exception as e :
		log.error ( f"Error fetching popular content: {str ( e )}" )
		return jsonify (
			{
				"popularArtists" : [ ] ,
				"trendingTracks" : [ ] ,
				"popularPlaylists" : [ ] ,
				"error" : f"Database error: {str ( e )}"
				}
			) , 500
	finally :
		if conn :
			conn.close ( )


def convert_duration_to_seconds ( duration ) :
	if duration is None :
		return 0
	if isinstance ( duration , str ) and re.match ( r'^\d{2}:\d{2}$' , duration ) :
		minutes , seconds = map ( int , duration.split ( ':' ) )
		return (minutes*60) + seconds
	try :
		return int ( duration )
	except ValueError :
		log.warning ( f"Invalid duration format: {duration}. Defaulting to 0." )
		return 0


@app.route ( '/insertimageplaylist' , methods = [ 'POST' ] )
def insertimageplaylist ( ) :
	data = request.get_json ( )
	imageinsert = data.get ( 'imageinsert' )
	login = data.get ( 'login' )
	playlistId = data.get ( 'playlistId' )
	conn = None  # Initialize conn to None for proper handling in finally block
	try :
		conn = get_db_connection ( )
		if not conn :
			print ( "Failed to connect to the database." )
			return jsonify (
				{ "error" : "Failed to connect to the database." , "playlists" : [ ] }
				) , 500  # Added empty playlist array
		
		cur = conn.cursor ( )
		cur.execute (
			"""
				SELECT u.id
				FROM "Soundmusicconnect".users u
				WHERE u.login = %s
				""" , (login ,)
			)
		user_result = cur.fetchone ( )
		if not user_result :
			cur.close ( )
			conn.close ( )
			return jsonify ( { "error" : "User not found." } ) , 404
		
		if not imageinsert :
			cur.close ( )
			conn.close ( )
			return jsonify ( { "error" : "No image provided." } ) , 400  # Changed message and status code
		
		update = conn.cursor ( )
		
		update.execute (
			"""
				SELECT idplay
				FROM "Soundmusicconnect".playlists
				WHERE idplay = %s
				""" , (playlistId ,)
			)  # Use playlists table
		result = update.fetchone ( )
		if not result :
			update.close ( )
			cur.close ( )
			conn.close ( )
			return jsonify ( { "error" : "Playlist not found for the given ID." } ) , 404  # Fixed message
		
		updatephoto = conn.cursor ( )
		updatephoto.execute (
			"""
				UPDATE "Soundmusicconnect".playlists
				SET image = decode(%s, 'base64')
				WHERE idplay = %s;
				""" , (imageinsert , playlistId)
			)  # Corrected SQL syntax and table name
		conn.commit ( )
		
		updatephoto.close ( )
		cur.close ( )
		return jsonify ( { "message" : "Image updated successfully." } ) , 200  # Success
	
	except Exception as e :
		if conn :
			conn.rollback ( )  # Rollback in case of an error during database operations
		print ( f"Database error: {e}" )  # Log the exception for debugging
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	
	finally :
		if conn :
			conn.close ( )


def get_user_preferences ( user_id , conn ) :
	"""Получение избранных элементов пользователя"""
	cur = conn.cursor ( )
	try :
		cur.execute (
			"""
				SELECT fs.song_id, s.imagesong
				FROM "Soundmusicconnect".favorite_songs fs
				LEFT JOIN "Soundmusicconnect".songs s ON fs.song_id = s.idtrack
				WHERE fs.user_id = %s
			""" , (user_id ,)
			)
		favorite_songs_data = cur.fetchall ( )
		favorite_songs = [ {
			'id' : row [ 0 ] ,
			'image' : base64.b64encode ( row [ 1 ] ).decode ( 'utf-8' ) if row [ 1 ] else None
			}
			for row in favorite_songs_data ]
		
		cur.execute (
			"""
				SELECT p.idplay, ps.song_id, p.image
				FROM "Soundmusicconnect".favorite_playlists fp
				JOIN "Soundmusicconnect".playlists p ON fp.playlist_id = p.idplay
				JOIN "Soundmusicconnect".playlist_songs ps ON ps.playlist_id = p.idplay
				WHERE fp.user_id = %s
			""" , (user_id ,)
			)
		playlist_data = [ {
			'playlist_id' : row [ 0 ] , 'song_id' : row [ 1 ] ,
			'image' : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None
			}
			for row in cur.fetchall ( ) ]
		
		cur.execute (
			"""
				SELECT p.id, p."Photo"
				FROM "Soundmusicconnect".favorite_performers fp
				JOIN "Soundmusicconnect".performers p ON fp.performer_id = p.id
				WHERE fp.user_id = %s
			""" , (user_id ,)
			)
		favorite_performers_data = cur.fetchall ( )
		favorite_performers = [ {
			'id' : row [ 0 ] ,
			'image' : base64.b64encode ( row [ 1 ] ).decode ( 'utf-8' ) if row [
				1 ] else None
			}
			for row in favorite_performers_data ]
		
		return favorite_songs , playlist_data , favorite_performers
	except Exception as e :
		logging.error ( f"Ошибка в get_user_preferences: {e}" )
		raise


def get_top_genres ( user_id , conn , limit = 6 ) :
	"""Получение топ-6 жанров для пользователя или популярных жанров для новых пользователей"""
	cur = conn.cursor ( )
	try :
		cur.execute (
			"""
					SELECT COUNT(*) FROM "Soundmusicconnect".favorite_songs WHERE user_id = %s
				""" , (user_id ,)
			)
		has_preferences = cur.fetchone ( ) [ 0 ] > 0
		
		genre_ids = [ ]
		if has_preferences :
			cur.execute (
				"""
						SELECT s.genre_id
						FROM "Soundmusicconnect".favorite_songs fs
						JOIN "Soundmusicconnect".songs s ON fs.song_id = s.idtrack
						WHERE fs.user_id = %s
						UNION
						SELECT s.genre_id
						FROM "Soundmusicconnect".favorite_playlists fp
						JOIN "Soundmusicconnect".playlist_songs ps ON fp.playlist_id = ps.playlist_id
						JOIN "Soundmusicconnect".songs s ON ps.song_id = s.idtrack
						WHERE fp.user_id = %s
					""" , (user_id , user_id)
				)
			genre_ids = [ row [ 0 ] for row in cur.fetchall ( ) ]
		else :
			cur.execute (
				"""
						SELECT s.genre_id
						FROM "Soundmusicconnect".favorite_songs fs
						JOIN "Soundmusicconnect".songs s ON fs.song_id = s.idtrack
						GROUP BY s.genre_id
						ORDER BY COUNT(*) DESC
						LIMIT %s
					""" , (limit ,)
				)
			genre_ids = [ row [ 0 ] for row in cur.fetchall ( ) ]
		
		if not genre_ids :
			return [ ]
		
		genre_counts = Counter ( genre_ids )
		top_genre_ids = [ genre for genre , _ in genre_counts.most_common ( limit ) ]
		
		cur.execute (
			"""
					SELECT idgenr, name, phototrack
					FROM "Soundmusicconnect".genres
					WHERE idgenr = ANY(%s)
				""" , (top_genre_ids ,)
			)
		return [
			{
				"id" : row [ 0 ] , "name" : row [ 1 ] ,
				"image" : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None
				}
			for row in cur.fetchall ( ) ]
	except Exception as e :
		logging.error ( f"Ошибка в get_top_genres: {e}" )
		raise


def fetch_interaction_data ( ) :
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database in fetch_interaction_data" )
			return pd.DataFrame ( columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
		
		cur = conn.cursor ( )
		query = """
        SELECT lh.user_id, lh.song_id, COUNT(*) as interaction_count
        FROM "Soundmusicconnect".listening_history lh
        GROUP BY lh.user_id, lh.song_id
        """
		cur.execute ( query )
		rows = cur.fetchall ( )
		
		df = pd.DataFrame ( rows , columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
		log.info (
			f"Successfully fetched interaction data. Shape: {df.shape}, Unique users: {df [ 'user_id' ].nunique ( )}, Unique songs: {df [ 'song_id' ].nunique ( )}"
			)
		log.debug ( f"Sample data:\n{df.head ( ).to_string ( )}" )
		return df
	
	except psycopg2.Error as e :
		log.error ( f"Database error in fetch_interaction_data: {e}" )
		return pd.DataFrame ( columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
	except Exception as e :
		log.error ( f"Unexpected error in fetch_interaction_data: {e}" )
		log.error ( traceback.format_exc ( ) )
		return pd.DataFrame ( columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
	finally :
		if conn :
			conn.close ( )


def get_popular_genres ( conn , limit ) :
	pass


@app.route ( '/favorite_albums' , methods = [ 'GET' ] )
def get_favorite_albums ( ) :
	conn = None
	try :
		log.info ( "Entering /favorite_albums endpoint..." )
		login = request.args.get ( 'login' )
		if not login :
			log.warning ( "Error: Login parameter is required." )
			return jsonify ( { "error" : "Login parameter is required" , "favorite_albums" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "favorite_albums" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT a.idalbum, a.albumname, a.year_release, p.fullname, a.imagealbum
            FROM "Soundmusicconnect".favorite_albums fa
            JOIN "Soundmusicconnect".albums a ON fa.album_id = a.idalbum
            JOIN "Soundmusicconnect".performers p ON a.performer_id = p.id
            WHERE fa.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
            ''' , (login ,)
			)
		rows = cur.fetchall ( )
		
		favorite_albums = [
			{
				"id" : row [ 0 ] ,
				"albumName" : row [ 1 ] ,
				"yearRelease" : row [ 2 ].isoformat ( ) if row [ 2 ] else None ,
				"performerName" : row [ 3 ] ,
				"imageBase64" : base64.b64encode ( row [ 4 ] ).decode ( 'utf-8' ) if row [ 4 ] else None
				}
			for row in rows
			]
		
		log.info ( f"Successfully retrieved {len ( favorite_albums )} favorite albums for user {login}" )
		return jsonify ( { "favorite_albums" : favorite_albums , "error" : None } ) , 200
	
	except Exception as e :
		log.error ( f"Error fetching favorite albums: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : str ( e ) , "favorite_albums" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/favorite_playlists' , methods = [ 'GET' ] )
def get_favorite_playlists ( ) :
	conn = None
	try :
		log.info ( "Entering /favorite_playlists endpoint..." )
		login = request.args.get ( 'login' )
		if not login :
			log.warning ( "Error: Login parameter is required." )
			return jsonify ( { "error" : "Login parameter is required" , "favorite_playlists" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "favorite_playlists" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT p.idplay, p.nameplay, p.image, p.madeinuser
            FROM "Soundmusicconnect".favorite_playlists fp
            JOIN "Soundmusicconnect".playlists p ON fp.playlist_id = p.idplay
            WHERE fp.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
            ''' , (login ,)
			)
		rows = cur.fetchall ( )
		
		favorite_playlists = [
			{
				"id" : row [ 0 ] ,
				"name" : row [ 1 ] ,
				"imageBase64" : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None ,
				"madeInUser" : row [ 3 ]
				}
			for row in rows
			]
		
		log.info ( f"Successfully retrieved {len ( favorite_playlists )} favorite playlists for user {login}" )
		return jsonify ( { "favorite_playlists" : favorite_playlists , "error" : None } ) , 200
	
	except Exception as e :
		log.error ( f"Error fetching favorite playlists: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : str ( e ) , "favorite_playlists" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/favorite_performers' , methods = [ 'GET' ] )
def get_favorite_performers ( ) :
	conn = None
	try :
		log.info ( "Entering /favorite_performers endpoint..." )
		login = request.args.get ( 'login' )
		if not login :
			log.warning ( "Error: Login parameter is required." )
			return jsonify ( { "error" : "Login parameter is required" , "favorite_performers" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "favorite_performers" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT p.id, p.fullname, p.information, p."Photo"
            FROM "Soundmusicconnect".favorite_performers fp
            JOIN "Soundmusicconnect".performers p ON fp.performer_id = p.id
            WHERE fp.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
            ''' , (login ,)
			)
		rows = cur.fetchall ( )
		
		favorite_performers = [
			{
				"id" : row [ 0 ] ,
				"fullName" : row [ 1 ] ,
				"information" : row [ 2 ] ,
				"photoBase64" : base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None
				}
			for row in rows
			]
		
		log.info ( f"Successfully retrieved {len ( favorite_performers )} favorite performers for user {login}" )
		return jsonify ( { "favorite_performers" : favorite_performers , "error" : None } ) , 200
	
	except Exception as e :
		log.error ( f"Error fetching favorite performers: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : str ( e ) , "favorite_performers" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/favorite_tracks' , methods = [ 'GET' ] )
def get_favorite_tracks ( ) :
	conn = None
	try :
		log.info ( "Entering /favorite_tracks endpoint..." )
		login = request.args.get ( 'login' )
		if not login :
			log.warning ( "Error: Login parameter is required." )
			return jsonify ( { "error" : "Login parameter is required" , "favorite_tracks" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "favorite_tracks" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performer_name, s.imagesong,
                   s.yearcreate, s.duration, g.name AS genre_name
            FROM "Soundmusicconnect".favorite_songs fs
            JOIN "Soundmusicconnect".songs s ON fs.song_id = s.idtrack
            LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
            LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
            LEFT JOIN "Soundmusicconnect".genres g ON s.genre_id = g.idgenr
            WHERE fs.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
            GROUP BY s.idtrack, s.songname, s.imagesong, s.yearcreate, s.duration, g.name
            ''' , (login ,)
			)
		rows = cur.fetchall ( )
		
		favorite_tracks = [
			{
				"id" : row [ 0 ] ,
				"songName" : row [ 1 ] ,
				"performerName" : row [ 2 ] or "Unknown Artist" ,
				"imageBase64" : base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None ,
				"yearCreate" : str ( row [ 4 ] ) if row [ 4 ] is not None else None ,
				"duration" : row [ 5 ] ,
				"genreName" : row [ 6 ]
				}
			for row in rows
			]
		
		log.info ( f"Successfully retrieved {len ( favorite_tracks )} favorite tracks for user {login}" )
		return jsonify ( { "favorite_tracks" : favorite_tracks , "error" : None } ) , 200
	
	except Exception as e :
		log.error ( f"Error fetching favorite tracks: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : str ( e ) , "favorite_tracks" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


def recommend_content ( user_id , conn ) :
	try :
		# Get user preferences (favorite songs, playlists, performers)
		favorite_songs , playlist_data , favorite_performers = get_user_preferences ( user_id , conn )
		all_song_ids = [ song [ 'id' ] for song in favorite_songs ] + [ row [ 'song_id' ] for row in playlist_data ]
		
		# Fetch all genres and performers for feature matrix
		cur = conn.cursor ( )
		cur.execute ( 'SELECT idgenr FROM "Soundmusicconnect".genres' )
		all_genres = [ row [ 0 ] for row in cur.fetchall ( ) ]
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".performers' )
		all_performers = [ row [ 0 ] for row in cur.fetchall ( ) ]
		
		MIN_SONG_THRESHOLD = 3
		
		# Case 1: New user with insufficient data
		if len ( all_song_ids ) < MIN_SONG_THRESHOLD and not favorite_performers :
			log.info ( f"User {user_id} has insufficient data, using enhanced fallback" )
			
			# Get listened songs from history (even for new users)
			cur.execute (
				'''
				SELECT song_id FROM "Soundmusicconnect".listening_history
				WHERE user_id = %s LIMIT %s
				''' , (user_id , MIN_SONG_THRESHOLD)
				)
			listened_song_ids = [ row [ 0 ] for row in cur.fetchall ( ) ]
			all_song_ids.extend ( listened_song_ids )
			
			# Fetch popular genres as a fallback
			popular_genres = get_popular_genres ( conn , limit = 3 )
			genre_ids = [ g [ 'id' ] for g in popular_genres ]
			
			# Recommended Songs (blend popular songs and genre-based)
			cur.execute (
				'''
				SELECT s.idtrack, COALESCE(s.songname, 'Unnamed Song') AS songname, s.genre_id,
					   COALESCE(STRING_AGG(p.fullname, ', '), 'Unknown Artist') AS performers,
					   s.imagesong, COALESCE(s.duration, '00:00') AS duration,
					   EXISTS (
						   SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
						   WHERE fs.user_id = %s AND fs.song_id = s.idtrack
					   ) AS is_liked
				FROM "Soundmusicconnect".songs s
				LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
				LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
				WHERE (s.genre_id = ANY(%s) OR s.idtrack NOT IN %s)
				GROUP BY s.idtrack, s.songname, s.genre_id, s.imagesong, s.duration
				ORDER BY COUNT(lh.song_id) DESC NULLS LAST, RANDOM()
				LIMIT 10
				''' , (user_id , genre_ids , tuple ( all_song_ids ) if all_song_ids else (0 ,))
				)
			rows = cur.fetchall ( )
			recommended_songs = [
				{
					"id" : row [ 0 ] ,
					"name" : row [ 1 ] ,
					"genre_id" : row [ 2 ] ,
					"performers" : row [ 3 ] ,
					"image" : base64.b64encode ( row [ 4 ] ).decode ( 'utf-8' ) if row [ 4 ] else None ,
					"duration" : row [ 5 ] ,
					"is_liked" : row [ 6 ]
					} for row in rows
				]
			
			# Recommended Playlists (favor popular ones with songs in popular genres)
			cur.execute (
				'''
				SELECT p.idplay, p.nameplay, p.image, p.madeinuser,
					   EXISTS (
						   SELECT 1 FROM "Soundmusicconnect".favorite_playlists fp
						   WHERE fp.user_id = %s AND fp.playlist_id = p.idplay
					   ) AS is_liked
				FROM "Soundmusicconnect".playlists p
				JOIN "Soundmusicconnect".playlist_songs ps ON p.idplay = ps.playlist_id
				JOIN "Soundmusicconnect".songs s ON ps.song_id = s.idtrack
				WHERE s.genre_id = ANY(%s)
				GROUP BY p.idplay, p.nameplay, p.image, p.madeinuser
				ORDER BY COUNT(fp.playlist_id) DESC NULLS LAST, RANDOM()
				LIMIT 5
				''' , (user_id , genre_ids)
				)
			recommended_playlists = [
				{
					"id" : row [ 0 ] ,
					"name" : row [ 1 ] ,
					"image" : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None ,
					"madeinuser" : row [ 3 ] ,
					"is_liked" : row [ 4 ]
					} for row in cur.fetchall ( )
				]
			
			# Recommended Performers (based on popular songs)
			cur.execute (
				'''
				SELECT p.id, p.fullname, p."Photo",
					   EXISTS (
						   SELECT 1 FROM "Soundmusicconnect".favorite_performers fp
						   WHERE fp.user_id = %s AND fp.performer_id = p.id
					   ) AS is_liked
				FROM "Soundmusicconnect".performers p
				JOIN "Soundmusicconnect".song_performers sp ON p.id = sp.performer_id
				JOIN "Soundmusicconnect".songs s ON sp.song_id = s.idtrack
				WHERE s.genre_id = ANY(%s)
				GROUP BY p.id, p.fullname, p."Photo"
				ORDER BY COUNT(lh.song_id) DESC NULLS LAST, RANDOM()
				LIMIT 5
				''' , (user_id , genre_ids)
				)
			recommended_performers = [
				{
					"id" : row [ 0 ] ,
					"name" : row [ 1 ] ,
					"image" : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None ,
					"is_liked" : row [ 3 ]
					} for row in cur.fetchall ( )
				]
		
		# Case 2: User with sufficient data (existing logic)
		else :
			# Feature matrix and similarity-based recommendations (unchanged)
			cur.execute (
				'''
				SELECT s.idtrack, s.genre_id,
					   STRING_AGG(sp.performer_id::text, ',') AS performer_ids
				FROM "Soundmusicconnect".songs s
				LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
				WHERE s.idtrack = ANY(%s)
				GROUP BY s.idtrack, s.genre_id
				''' , (all_song_ids ,)
				)
			song_features = cur.fetchall ( )
			feature_matrix_list = [ ]
			song_ids = [ ]
			for song_id , genre_id , performer_ids in song_features :
				genre_vector = [ 1 if g == genre_id else 0 for g in all_genres ]
				performer_ids_list = [ int ( pid ) for pid in (performer_ids.split ( ',' ) if performer_ids else [ ]) ]
				performer_vector = [ 1 if p in performer_ids_list else 0 for p in all_performers ]
				feature_matrix_list.append ( genre_vector + performer_vector )
				song_ids.append ( song_id )
			feature_matrix = np.array ( feature_matrix_list ) if feature_matrix_list else np.array ( [ ] )
			similarity_matrix = cosine_similarity ( feature_matrix ) if feature_matrix.size else np.array ( [ ] )
			
			cur.execute (
				'''
				SELECT s.idtrack, COALESCE(s.songname, 'Unnamed Song') AS songname, s.genre_id,
					   COALESCE(STRING_AGG(p.fullname, ', '), 'Unknown Artist') AS performers,
					   s.imagesong, COALESCE(s.duration, '00:00') AS duration,
					   EXISTS (
						   SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
						   WHERE fs.user_id = %s AND fs.song_id = s.idtrack
					   ) AS is_liked
				FROM "Soundmusicconnect".songs s
				LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
				LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
				WHERE s.idtrack NOT IN %s
				GROUP BY s.idtrack, s.songname, s.genre_id, s.imagesong, s.duration
				LIMIT 100
				''' , (user_id , tuple ( all_song_ids ) if all_song_ids else (0 ,))
				)
			all_songs = cur.fetchall ( )
			recommended_songs = [ ]
			recommended_performers_ids = set ( )
			for song_id , song_name , genre_id , performers , image , duration , is_liked in all_songs :
				if feature_matrix.size :
					genre_vector = [ 1 if g == genre_id else 0 for g in all_genres ]
					cur.execute (
						'SELECT performer_id FROM "Soundmusicconnect".song_performers WHERE song_id = %s' ,
						(song_id ,)
						)
					performer_ids = [ row [ 0 ] for row in cur.fetchall ( ) ]
					performer_vector = [ 1 if p in performer_ids else 0 for p in all_performers ]
					song_vector = genre_vector + performer_vector
					similarities = cosine_similarity ( [ song_vector ] , feature_matrix ) [ 0 ]
					if max ( similarities ) > 0.7 :
						recommended_songs.append (
							{
								"id" : song_id ,
								"name" : song_name ,
								"genre_id" : genre_id ,
								"performers" : performers ,
								"image" : base64.b64encode ( image ).decode ( 'utf-8' ) if image else None ,
								"duration" : duration ,
								"is_liked" : is_liked
								}
							)
						recommended_performers_ids.update ( performer_ids )
				if len ( recommended_songs ) >= 10 :
					break
			
			cur.execute (
				'''
				SELECT DISTINCT p.idplay, p.nameplay, p.image, p.madeinuser,
					   EXISTS (
						   SELECT 1 FROM "Soundmusicconnect".favorite_playlists fp
						   WHERE fp.user_id = %s AND fp.playlist_id = p.idplay
					   ) AS is_liked
				FROM "Soundmusicconnect".playlists p
				WHERE p.idplay NOT IN (
					SELECT playlist_id FROM "Soundmusicconnect".favorite_playlists WHERE user_id = %s
				)
				LIMIT 5
				''' , (user_id , user_id)
				)
			recommended_playlists = [
				{
					"id" : row [ 0 ] ,
					"name" : row [ 1 ] ,
					"image" : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None ,
					"madeinuser" : row [ 3 ] ,
					"is_liked" : row [ 4 ]
					} for row in cur.fetchall ( )
				]
			
			recommended_performers_ids = list ( recommended_performers_ids ) [ :5 ]
			cur.execute (
				'''
				SELECT p.id, p.fullname, p."Photo",
					   EXISTS (
						   SELECT 1 FROM "Soundmusicconnect".favorite_performers fp
						   WHERE fp.user_id = %s AND fp.performer_id = p.id
					   ) AS is_liked
				FROM "Soundmusicconnect".performers p
				WHERE p.id = ANY(%s)
				''' , (user_id , recommended_performers_ids if recommended_performers_ids else [ 0 ])
				)
			recommended_performers = [
				{
					"id" : row [ 0 ] ,
					"name" : row [ 1 ] ,
					"image" : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None ,
					"is_liked" : row [ 3 ]
					} for row in cur.fetchall ( )
				]
		
		return recommended_songs , recommended_playlists , recommended_performers
	except Exception as e :
		log.error ( f"Error in recommend_content: {e}" )
		raise


verification_codes = { }


@app.route ( '/change_email' , methods = [ 'POST' ] )
def change_email ( ) :
	conn = None
	try :
		log.info ( "Entering /change_email endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received raw data: {data}" )
		
		# Use case-insensitive key lookup
		login = data.get ( 'Login' ) or data.get ( 'login' )
		password = data.get ( 'Password' ) or data.get ( 'password' )
		new_email = data.get ( 'NewEmail' ) or data.get ( 'newEmail' )
		code = data.get ( 'Code' ) or data.get ( 'code' )
		
		log.debug ( f"Parsed: login={login}, password={password}, new_email={new_email}, code={code}" )
		
		if not login :
			log.warning ( "Error: Login is required." )
			return jsonify ( { "Success" : False , "ErrorMessage" : "Login is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "ErrorMessage" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		
		# Step 1: Send verification code
		if not new_email and not code :
			if not password :
				log.warning ( "Error: Password is required for verification." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "Password is required" } ) , 400
			
			cur.execute ( 'SELECT id, password, email FROM "Soundmusicconnect"."users" WHERE login = %s;' , (login ,) )
			user = cur.fetchone ( )
			
			if not user :
				log.warning ( f"User with login {login} not found." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "User not found" } ) , 404
			
			user_id , stored_password_hash , current_email = user
			
			if not bcrypt.checkpw ( password.encode ( 'utf-8' ) , stored_password_hash.encode ( 'utf-8' ) ) :
				log.warning ( f"Invalid password for user {login}." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "Invalid password" } ) , 401
			
			code , error = sendemainandcodeoutput ( current_email )
			if error :
				log.error ( f"Failed to send verification code: {error}" )
				return jsonify ( { "Success" : False , "ErrorMessage" : f"Failed to send code: {error}" } ) , 500
			
			verification_codes [ user_id ] = code
			log.info ( f"Verification code {code} sent to {current_email} for user {login}" )
			return jsonify (
				{ "Success" : True , "CodeSent" : True , "Message" : "Verification code sent to your current email" }
				) , 200
		
		# Step 2: Verify code and change email
		if new_email and code :
			cur.execute ( 'SELECT id FROM "Soundmusicconnect"."users" WHERE login = %s;' , (login ,) )
			user = cur.fetchone ( )
			
			if not user :
				log.warning ( f"User with login {login} not found." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "User not found" } ) , 404
			
			user_id = user [ 0 ]
			
			stored_code = verification_codes.get ( user_id )
			if not stored_code or stored_code != code :
				log.warning ( f"Invalid or expired code for user {login}." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "Invalid or expired verification code" } ) , 401
			
			cur.execute (
				'UPDATE "Soundmusicconnect"."users" SET email = %s WHERE id = %s;' ,
				(new_email , user_id)
				)
			conn.commit ( )
			
			verification_codes.pop ( user_id , None )
			log.info ( f"Email for user {login} updated to {new_email}" )
			return jsonify ( { "Success" : True , "Message" : "Email changed successfully" } ) , 200
		
		log.warning ( "Error: Either password or both newEmail and code are required." )
		return jsonify (
			{ "Success" : False , "ErrorMessage" : "Either password or both newEmail and code are required" }
			) , 400
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"An unexpected error occurred in /change_email endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "Success" : False , "ErrorMessage" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/change_password_with_code' , methods = [ 'POST' ] )
def change_password_with_code ( ) :
	conn = None
	try :
		log.info ( "Entering /change_password_with_code endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received {data}" )
		
		login = data.get ( 'Login' )
		current_password = data.get ( 'CurrentPassword' )  # Текущий пароль
		new_password = data.get ( 'NewPassword' )  # Новый пароль
		code = data.get ( 'Code' )  # Код подтверждения
		
		if not login :
			log.warning ( "Error: Login is required." )
			return jsonify ( { "Success" : False , "ErrorMessage" : "Login is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "ErrorMessage" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		
		# Шаг 1: Проверка текущего пароля и отправка кода
		if not new_password and not code :
			if not current_password :
				log.warning ( "Error: Current password is required for verification." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "Current password is required" } ) , 400
			
			# Проверяем существование пользователя и получаем текущий пароль и email
			cur.execute ( 'SELECT id, password, email FROM "Soundmusicconnect"."users" WHERE login = %s;' , (login ,) )
			user = cur.fetchone ( )
			
			if not user :
				log.warning ( f"User with login {login} not found." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "User not found" } ) , 404
			
			user_id , stored_password_hash , current_email = user
			
			# Проверяем текущий пароль
			if not bcrypt.checkpw ( current_password.encode ( 'utf-8' ) , stored_password_hash.encode ( 'utf-8' ) ) :
				log.warning ( f"Invalid current password for user {login}." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "Invalid current password" } ) , 401
			
			# Отправляем код подтверждения на текущий email
			code , error = sendemainandcodeoutput ( current_email )
			if error :
				log.error ( f"Failed to send verification code: {error}" )
				return jsonify ( { "Success" : False , "ErrorMessage" : f"Failed to send code: {error}" } ) , 500
			
			# Сохраняем код во временное хранилище и возвращаем его в ответе
			verification_codes [ user_id ] = code
			log.info ( f"Verification code {code} sent to {current_email} for user {login}" )
			return jsonify (
				{
					"Success" : True , "CodeSent" : True , "Code" : code ,
					"Message" : "Verification code sent to your email"
					}
				) , 200
		
		# Шаг 2: Проверка кода и смена пароля
		if new_password and code :
			# Получаем пользователя
			cur.execute ( 'SELECT id, password FROM "Soundmusicconnect"."users" WHERE login = %s;' , (login ,) )
			user = cur.fetchone ( )
			
			if not user :
				log.warning ( f"User with login {login} not found." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "User not found" } ) , 404
			
			user_id , stored_password_hash = user
			
			# Проверяем код
			stored_code = verification_codes.get ( user_id )
			if not stored_code or stored_code != code :
				log.warning ( f"Invalid or expired code for user {login}." )
				return jsonify ( { "Success" : False , "ErrorMessage" : "Invalid or expired verification code" } ) , 401
			
			# Проверяем, что новый пароль отличается от старого
			if bcrypt.checkpw ( new_password.encode ( 'utf-8' ) , stored_password_hash.encode ( 'utf-8' ) ) :
				log.warning ( f"New password is the same as the old password for user {login}." )
				return jsonify (
					{ "Success" : False , "ErrorMessage" : "New password cannot be the same as the old password" }
					) , 400
			
			# Хэшируем новый пароль
			hashed_new_password = bcrypt.hashpw ( new_password.encode ( 'utf-8' ) , bcrypt.gensalt ( ) ).decode (
				'utf-8'
				)
			
			# Обновляем пароль
			cur.execute (
				'UPDATE "Soundmusicconnect"."users" SET password = %s WHERE id = %s;' ,
				(hashed_new_password , user_id)
				)
			conn.commit ( )
			
			# Удаляем использованный код
			verification_codes.pop ( user_id , None )
			
			log.info ( f"Password for user {login} updated successfully" )
			return jsonify ( { "Success" : True , "Message" : "Password changed successfully" } ) , 200
		
		log.warning ( "Error: Either currentPassword or both newPassword and code are required." )
		return jsonify (
			{ "Success" : False , "ErrorMessage" : "Either currentPassword or both newPassword and code are required" }
			) , 400
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"An unexpected error occurred in /change_password_with_code endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "Success" : False , "ErrorMessage" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


def fetch_interaction_data ( ) :
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database in fetch_interaction_data" )
			return pd.DataFrame ( columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
		
		cur = conn.cursor ( )
		query = """
        SELECT lh.user_id, lh.song_id, COUNT(*) as interaction_count
        FROM "Soundmusicconnect".listening_history lh
        GROUP BY lh.user_id, lh.song_id
        """
		cur.execute ( query )
		rows = cur.fetchall ( )
		
		df = pd.DataFrame ( rows , columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
		log.info (
			f"Successfully fetched interaction data. Shape: {df.shape}, Unique users: {df [ 'user_id' ].nunique ( )}, Unique songs: {df [ 'song_id' ].nunique ( )}"
			)
		log.debug ( f"Sample data:\n{df.head ( ).to_string ( )}" )
		return df
	
	except psycopg2.Error as e :
		log.error ( f"Database error in fetch_interaction_data: {e}" )
		return pd.DataFrame ( columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
	except Exception as e :
		log.error ( f"Unexpected error in fetch_interaction_data: {e}" )
		log.error ( traceback.format_exc ( ) )
		return pd.DataFrame ( columns = [ 'user_id' , 'song_id' , 'interaction_count' ] )
	finally :
		if conn :
			conn.close ( )


# Train the recommendation model using TruncatedSVD
def train_model ( ) :
	data = fetch_interaction_data ( )
	if data is None or data.empty :
		log.warning ( "No interaction data available for training" )
		return None
	
	try :
		pivot_table = data.pivot_table (
			index = 'user_id' ,
			columns = 'song_id' ,
			values = 'interaction_count' ,
			fill_value = 0
			)
		svd = TruncatedSVD ( n_components = 20 )
		matrix = svd.fit_transform ( pivot_table )
		
		log.info ( "Model training completed successfully" )
		return {
			'svd' : svd ,
			'matrix' : matrix ,
			'user_ids' : pivot_table.index.tolist ( ) ,
			'song_ids' : pivot_table.columns.tolist ( )
			}
	except Exception as e :
		log.error ( f"Error training model: {e}" )
		return None


def train_recommendation_model ( ) :
	try :
		interaction_df = fetch_interaction_data ( )
		if interaction_df.empty :
			log.warning ( "No interaction data available for training." )
			return None
		
		interaction_matrix = interaction_df.pivot_table (
			index = 'user_id' ,
			columns = 'song_id' ,
			values = 'interaction_count' ,
			fill_value = 0
			)
		log.info ( f"Interaction matrix shape: {interaction_matrix.shape}" )
		
		interaction_matrix_np = interaction_matrix.to_numpy ( )
		scaler = StandardScaler ( )
		interaction_matrix_scaled = scaler.fit_transform ( interaction_matrix_np )
		log.info ( f"Scaled interaction matrix shape: {interaction_matrix_scaled.shape}" )
		
		n_features = interaction_matrix_scaled.shape [ 1 ]
		n_components = min ( 20 , n_features )
		log.info ( f"Training TruncatedSVD with n_features={n_features}, n_components={n_components}" )
		
		svd = TruncatedSVD ( n_components = n_components )
		reduced_matrix = svd.fit_transform ( interaction_matrix_scaled )
		log.info ( f"Reduced matrix shape: {reduced_matrix.shape}" )
		
		return svd , reduced_matrix , interaction_matrix.index
	
	except Exception as e :
		log.error ( f"Error training model: {e}" )
		log.error ( traceback.format_exc ( ) )
		raise


# Global model data (trained at startup)
model_data = None


def initialize_model ( ) :
	global model_data
	try :
		svd , reduced_matrix , user_ids = train_recommendation_model ( )
		model_data = { 'svd' : svd , 'reduced_matrix' : reduced_matrix , 'user_ids' : user_ids }
		log.info ( "Recommendation model initialized successfully." )
	except Exception as e :
		log.error ( f"Failed to initialize model: {e}" )


# Generate song recommendations
def get_song_recommendations ( user_login , top_n = 5 ) :
	conn = get_db_connection ( )
	if not conn :
		return [ ]
	cur = conn.cursor ( )
	
	try :
		# Get user_id from login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			log.warning ( f"User {user_login} not found" )
			return [ ]
		user_id = user_result [ 0 ]
		
		if not model_data :
			log.warning ( "Model not trained, falling back to popular songs" )
		elif user_id not in model_data [ 'user_ids' ] :
			log.warning ( f"User {user_id} not in training data, falling back to popular songs" )
		else :
			# Use trained model for recommendations
			user_idx = model_data [ 'user_ids' ].index ( user_id )
			user_vector = model_data [ 'matrix' ] [ user_idx ]
			predicted_ratings = np.dot ( user_vector , model_data [ 'svd' ].components_.T )
			
			# Get unrated songs
			data = fetch_interaction_data ( )
			user_interacted_songs = data [ data [ 'user_id' ] == user_id ] [ 'song_id' ].tolist ( )
			all_song_ids = model_data [ 'song_ids' ]
			unrated_song_ids = [ sid for sid in all_song_ids if sid not in user_interacted_songs ]
			unrated_ratings = [ predicted_ratings [ model_data [ 'song_ids' ].index ( sid ) ] for sid in
			                    unrated_song_ids ]
			
			# Sort and select top N
			top_indices = np.argsort ( unrated_ratings ) [ : :-1 ] [ :top_n ]
			recommended_song_ids = [ unrated_song_ids [ i ] for i in top_indices ]
		# Fallback to popular songs if no model or user not in model
		if not model_data or user_id not in model_data [ 'user_ids' ] :
			cur.execute (
				"""
				SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performers,
					   encode(s.imagesong, 'base64') AS image, s.duration,
					   COUNT(lh.id) AS listen_count,
					   EXISTS (SELECT 1 FROM "Soundmusicconnect".favorite_songs fs WHERE fs.song_id = s.idtrack AND fs.user_id = %s) AS is_liked
				FROM "Soundmusicconnect".songs s
				LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
				LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
				LEFT JOIN "Soundmusicconnect".listening_history lh ON s.idtrack = lh.song_id
				GROUP BY s.idtrack, s.songname, s.imagesong, s.duration
				ORDER BY listen_count DESC
				LIMIT %s
			""" , (user_id , top_n)
				)
			rows = cur.fetchall ( )
			recommended_song_ids = [ row [ 0 ] for row in rows ]
		else :
			# Fetch details for recommended songs
			placeholders = ','.join ( [ '%s' ]*len ( recommended_song_ids ) )
			cur.execute (
				f"""
                SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performers,
                       encode(s.imagesong, 'base64') AS image, s.duration,
                       EXISTS (SELECT 1 FROM "Soundmusicconnect".favorite_songs fs WHERE fs.song_id = s.idtrack AND fs.user_id = %s) AS is_liked
                FROM "Soundmusicconnect".songs s
                LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
                LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
                WHERE s.idtrack IN ({placeholders})
                GROUP BY s.idtrack, s.songname, s.imagesong, s.duration
            """ , [ user_id ] + recommended_song_ids
				)
			rows = cur.fetchall ( )
		
		recommendations = [
			{
				"Id" : row [ 0 ] ,
				"Name" : row [ 1 ] ,
				"Performers" : row [ 2 ] or "Unknown Artist" ,
				"Image" : row [ 3 ] ,
				"Duration" : row [ 4 ] ,
				"IsLiked" : row [ 5 ]
				} for row in rows
			]
		log.info ( f"Generated {len ( recommendations )} song recommendations for user {user_login}" )
		return recommendations
	
	except Exception as e :
		log.error ( f"Error generating song recommendations: {e}" )
		return [ ]
	finally :
		conn.close ( )


# Generate genre recommendations
def get_genre_recommendations ( user_login , top_n = 3 ) :
	conn = get_db_connection ( )
	if not conn :
		return [ ]
	cur = conn.cursor ( )
	
	try :
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_id = cur.fetchone ( )
		if not user_id :
			log.warning ( f"User {user_login} not found" )
			return [ ]
		user_id = user_id [ 0 ]
		
		# Aggregate user preferences by genre
		query = """
        SELECT g.idgenr, g.name, encode(g.phototrack, 'base64') AS image, COUNT(*) as interaction_count
        FROM "Soundmusicconnect".listening_history lh
        JOIN "Soundmusicconnect".songs s ON lh.song_id = s.idtrack
        JOIN "Soundmusicconnect".genres g ON s.genre_id = g.idgenr
        WHERE lh.user_id = %s
        GROUP BY g.idgenr, g.name, g.phototrack
        ORDER BY interaction_count DESC
        LIMIT %s
        """
		cur.execute ( query , (user_id , top_n) )
		rows = cur.fetchall ( )
		
		if not rows :  # Fallback to popular genres
			cur.execute (
				"""
				SELECT g.idgenr, g.name, encode(g.phototrack, 'base64') AS image
				FROM "Soundmusicconnect".genres g
				JOIN "Soundmusicconnect".songs s ON s.genre_id = g.idgenr
				JOIN "Soundmusicconnect".listening_history lh ON s.idtrack = lh.song_id
				GROUP BY g.idgenr, g.name, g.phototrack
				ORDER BY COUNT(lh.id) DESC
				LIMIT %s
			""" , (top_n ,)
				)
			rows = cur.fetchall ( )
		
		genres = [
			{
				"Id" : row [ 0 ] ,
				"Name" : row [ 1 ] ,
				"Image" : row [ 2 ]
				} for row in rows
			]
		return genres
	
	except Exception as e :
		log.error ( f"Error in get_genre_recommendations: {e}" )
		return [ ]
	finally :
		conn.close ( )


# Generate playlist recommendations
def get_playlist_recommendations ( user_login , top_n = 5 ) :
	conn = get_db_connection ( )
	if not conn :
		return [ ]
	cur = conn.cursor ( )
	
	try :
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_id = cur.fetchone ( )
		if not user_id :
			log.warning ( f"User {user_login} not found" )
			return [ ]
		user_id = user_id [ 0 ]
		
		# Recommend playlists based on user listening history genres
		cur.execute (
			"""
			SELECT p.idplay, p.nameplay, encode(p.image, 'base64') AS image, p.madeinuser,
				   EXISTS (SELECT 1 FROM "Soundmusicconnect".favorite_playlists fp WHERE fp.playlist_id = p.idplay AND fp.user_id = %s) AS is_liked,
				   COUNT(*) as genre_overlap
			FROM "Soundmusicconnect".playlists p
			JOIN "Soundmusicconnect".playlist_songs ps ON p.idplay = ps.playlist_id
			JOIN "Soundmusicconnect".songs s ON ps.song_id = s.idtrack
			JOIN "Soundmusicconnect".genres g ON s.genre_id = g.idgenr
			WHERE g.idgenr IN (
				SELECT s2.genre_id
				FROM "Soundmusicconnect".listening_history lh
				JOIN "Soundmusicconnect".songs s2 ON lh.song_id = s2.idtrack
				WHERE lh.user_id = %s
				GROUP BY s2.genre_id
				ORDER BY COUNT(*) DESC
				LIMIT 5
			)
			GROUP BY p.idplay, p.nameplay, p.image, p.madeinuser
			ORDER BY genre_overlap DESC, COUNT(*) DESC
			LIMIT %s
		""" , (user_id , user_id , top_n)
			)
		rows = cur.fetchall ( )
		
		if not rows :  # Fallback to popular playlists
			cur.execute (
				"""
				SELECT p.idplay, p.nameplay, encode(p.image, 'base64') AS image, p.madeinuser,
					   EXISTS (SELECT 1 FROM "Soundmusicconnect".favorite_playlists fp WHERE fp.playlist_id = p.idplay AND fp.user_id = %s) AS is_liked
				FROM "Soundmusicconnect".playlists p
				JOIN "Soundmusicconnect".playlist_songs ps ON p.idplay = ps.playlist_id
				JOIN "Soundmusicconnect".listening_history lh ON ps.song_id = lh.song_id
				GROUP BY p.idplay, p.nameplay, p.image, p.madeinuser
				ORDER BY COUNT(lh.id) DESC
				LIMIT %s
			""" , (user_id , top_n)
				)
			rows = cur.fetchall ( )
		
		playlists = [
			{
				"Id" : row [ 0 ] ,
				"Name" : row [ 1 ] ,
				"Image" : row [ 2 ] ,
				"MadeInUser" : row [ 3 ] ,
				"IsLiked" : row [ 4 ]
				} for row in rows
			]
		return playlists
	
	except Exception as e :
		log.error ( f"Error in get_playlist_recommendations: {e}" )
		return [ ]
	finally :
		conn.close ( )


@app.route ( '/homepage' , methods = [ 'POST' ] )
def homepage ( ) :
	conn = None
	try :
		log.info ( "Entering /homepage endpoint..." )
		data = request.get_json ( )
		login = data.get ( 'login' )
		user_data_date = data.get ( 'userData' )  # Expected format: "YYYY-MM-DD"
		
		if not login :
			log.warning ( "Error: Login is required." )
			return jsonify (
				{
					"error" : "Login is required" , "recommend_songs" : [ ] , "recommend_playlists" : [ ] ,
					"recommend_performers" : [ ] , "top_genres" : [ ] , "date" : None
					}
				) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database." )
			return jsonify (
				{
					"error" : "Failed to connect to the database" , "recommend_songs" : [ ] ,
					"recommend_playlists" : [ ] , "recommend_performers" : [ ] , "top_genres" : [ ] , "date" : None
					}
				) , 500
		
		cur = conn.cursor ( )
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			log.warning ( f"User not found for login: {login}" )
			return jsonify (
				{
					"error" : "User not found" , "recommend_songs" : [ ] , "recommend_playlists" : [ ] ,
					"recommend_performers" : [ ] , "top_genres" : [ ] , "date" : None
					}
				) , 404
		user_id = user_result [ 0 ]
		
		# Get recommendations and top genres
		recommended_songs , recommended_playlists , recommended_performers = recommend_content ( user_id , conn )
		top_genres = get_top_genres ( user_id , conn )
		
		# Prepare data without images for logging
		log_songs = [ {
			              "id" : song [ "id" ] , "name" : song [ "name" ] , "genre_id" : song [ "genre_id" ] ,
			              "performers" : song [ "performers" ] , "duration" : song [ "duration" ] ,
			              "is_liked" : song [ "is_liked" ]
			              } for song in recommended_songs ]
		log_playlists = [ {
			                  "id" : playlist [ "id" ] , "name" : playlist [ "name" ] ,
			                  "madeinuser" : playlist [ "madeinuser" ] , "is_liked" : playlist [ "is_liked" ]
			                  } for playlist in recommended_playlists ]
		log_performers = [
			{ "id" : performer [ "id" ] , "name" : performer [ "name" ] , "is_liked" : performer [ "is_liked" ] } for
			performer in recommended_performers ]
		log_genres = [ { "id" : genre [ "id" ] , "name" : genre [ "name" ] } for genre in top_genres ]
		
		# Log the data without images
		log.info ( f"Recommended songs for user {login}: {json.dumps ( log_songs , ensure_ascii = False )}" )
		log.info ( f"Recommended playlists for user {login}: {json.dumps ( log_playlists , ensure_ascii = False )}" )
		log.info ( f"Recommended performers for user {login}: {json.dumps ( log_performers , ensure_ascii = False )}" )
		log.info ( f"Top genres for user {login}: {json.dumps ( log_genres , ensure_ascii = False )}" )
		
		# Prepare response with all data (including images)
		response = {
			"recommend_songs" : recommended_songs ,
			"recommend_playlists" : recommended_playlists ,
			"recommend_performers" : recommended_performers ,
			"top_genres" : top_genres ,
			"date" : datetime.now ( ).strftime ( "%Y-%m-%d" ) ,
			"error" : None
			}
		
		log.info ( f"Successfully generated homepage data for user {login}" )
		return jsonify ( response ) , 200
	
	except Exception as e :
		log.error ( f"Error in /homepage endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify (
			{
				"error" : f"Server error: {str ( e )}" , "recommend_songs" : [ ] , "recommend_playlists" : [ ] ,
				"recommend_performers" : [ ] , "top_genres" : [ ] , "date" : None
				}
			) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/change_avatar' , methods = [ 'POST' ] )
def change_avatar ( ) :
	conn = None
	try :
		data = request.get_json ( )
		login = data.get ( 'login' )
		avatar_base64 = data.get ( 'avatarBase64' )
		
		if not login or not avatar_base64 :
			return jsonify ( { "Success" : False , "Error" : "Login and avatar are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Database connection failed" } ) , 500
		
		cur = conn.cursor ( )
		avatar_bytes = base64.b64decode ( avatar_base64 )  # Potential point of failure
		cur.execute (
			'UPDATE "Soundmusicconnect"."users" SET image = %s WHERE login = %s;' ,
			(psycopg2.Binary ( avatar_bytes ) , login)
			)
		if cur.rowcount == 0 :
			return jsonify ( { "Success" : False , "Error" : "User not found" } ) , 404
		
		conn.commit ( )
		return jsonify ( { "Success" : True , "Message" : "Avatar updated" } ) , 200
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error in change_avatar: {e}" )
		return jsonify ( { "Success" : False , "Error" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/favorite_items' , methods = [ 'POST' ] )
def get_favorite_items ( ) :
	data = request.get_json ( )
	if not data or 'login' not in data :
		return jsonify ( { "error" : "Login parameter is required in the request body" } ) , 400
	login = data.get ( "login" )
	
	print ( f"Received login: {login}" )
	
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		
		cur.execute ( "SELECT id FROM \"Soundmusicconnect\".users WHERE login = %s" , (login ,) )
		user = cur.fetchone ( )
		
		if not user :
			return jsonify ( { "error" : "User not found." } ) , 404
		
		user_id = user [ 0 ]
		print ( f"User ID found: {user_id}" )
		
		# Fetch favorite songs
		cur.execute (
			'''
			SELECT s.idtrack, s.songname, g."name" AS genre_name,
				   STRING_AGG(p.fullname, ', ') AS performer_name, s.imagesong,
				   MAX(fs.added_at) AS added_at, s.duration
			FROM "Soundmusicconnect".favorite_songs fs
			JOIN "Soundmusicconnect".songs s ON fs.song_id = s.idtrack
			LEFT JOIN "Soundmusicconnect".genres g ON s.genre_id = g.idgenr
			LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
			LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
			WHERE fs.user_id = %s
			GROUP BY s.idtrack, s.songname, g."name", s.imagesong, s.duration
			ORDER BY added_at DESC
			;
			''' , (user_id ,)
			)
		favorite_songs_rows = cur.fetchall ( )
		favorite_songs = [ ]
		for row in favorite_songs_rows :
			imagesong_data = row [ 4 ]
			imagesong = base64.b64encode ( imagesong_data ).decode ( 'utf-8' ) if imagesong_data else None
			favorite_songs.append (
				{
					"idtrack" : row [ 0 ] ,
					"songname" : row [ 1 ] ,
					"performer_name" : row [ 3 ] or "Unknown Artist" ,
					"imagesong" : imagesong ,
					"duration" : row [ 6 ] or "00:00"
					}
				)
		
		# Fetch favorite playlists
		cur.execute (
			'''
			SELECT pl.idplay, pl.nameplay, pl.image, u.login AS creator_name
			FROM "Soundmusicconnect".favorite_playlists fp
			JOIN "Soundmusicconnect".playlists pl ON fp.playlist_id = pl.idplay
			JOIN "Soundmusicconnect".users u ON pl.madeinuser = u.id
			WHERE fp.user_id = %s
			;
			''' , (user_id ,)
			)
		favorite_playlists_rows = cur.fetchall ( )
		favorite_playlists = [ ]
		for row in favorite_playlists_rows :
			playlist_image_data = row [ 2 ]
			playlist_image = base64.b64encode ( playlist_image_data ).decode (
				'utf-8'
				) if playlist_image_data else None
			favorite_playlists.append (
				{
					"idplay" : row [ 0 ] ,
					"nameplay" : row [ 1 ] ,
					"image" : playlist_image ,
					"creators" : row [ 3 ]
					}
				)
		
		# Fetch favorite performers
		cur.execute (
			'''
			SELECT p.id, p.fullname, p."Photo"
			FROM "Soundmusicconnect".favorite_performers fp
			JOIN "Soundmusicconnect".performers p ON fp.performer_id = p.id
			WHERE fp.user_id = %s
			ORDER BY fp.added_at DESC
			;
			''' , (user_id ,)
			)
		favorite_performers_rows = cur.fetchall ( )
		favorite_performers = [ ]
		for row in favorite_performers_rows :
			performer_photo_data = row [ 2 ]
			performer_photo = base64.b64encode ( performer_photo_data ).decode (
				'utf-8'
				) if performer_photo_data else None
			favorite_performers.append (
				{
					"id" : row [ 0 ] ,
					"fullname" : row [ 1 ] ,
					"Photo" : performer_photo
					}
				)
		
		# Fetch favorite albums (new addition)
		cur.execute (
			'''
			SELECT a.idalbum, a.albumname, a.imagealbum, p.fullname AS performer_name, a.yearrelease
			FROM "Soundmusicconnect".favorite_albums fa
			JOIN "Soundmusicconnect".albums a ON fa.album_id = a.idalbum
			JOIN "Soundmusicconnect".performers p ON a.performer_id = p.id
			WHERE fa.user_id = %s
			ORDER BY fa.added_at DESC
			;
			''' , (user_id ,)
			)
		favorite_albums_rows = cur.fetchall ( )
		favorite_albums = [ ]
		for row in favorite_albums_rows :
			album_image_data = row [ 2 ]
			album_image = base64.b64encode ( album_image_data ).decode ( 'utf-8' ) if album_image_data else None
			favorite_albums.append (
				{
					"idalbum" : row [ 0 ] ,
					"albumname" : row [ 1 ] ,
					"imagealbum" : album_image ,
					"performer_name" : row [ 3 ] or "Unknown Artist" ,
					"year_release" : row [ 4 ].strftime ( '%Y' ) if row [ 4 ] else None  # Convert date to year string
					}
				)
		
		response = {
			"favorite_songs" : favorite_songs ,
			"favorite_playlists" : favorite_playlists ,
			"favorite_performers" : favorite_performers ,
			"favorite_albums" : favorite_albums  # Added albums to response
			}
		print ( f"Response prepared: {response}" )
		return jsonify ( response ) , 200
	
	except Exception as e :
		print ( f"Database error: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/tracks_by_genre' , methods = [ 'POST' ] )
def tracks_by_genre ( ) :
	conn = None
	try :
		data = request.get_json ( )
		if not data or 'genreId' not in data or 'login' not in data :
			return jsonify ( { "error" : "genreId and login parameters are required." , "tracks" : [ ] } ) , 400
		
		genre_id = data.get ( 'genreId' )
		login = data.get ( 'login' )
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "tracks" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			return jsonify ( { "error" : "User not found." , "tracks" : [ ] } ) , 404
		user_id = user_result [ 0 ]
		
		# Fetch tracks for the given genre with multiple performers
		cur.execute (
			'''
			SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performer_name, s.imagesong,
				   EXISTS (
					   SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
					   WHERE fs.user_id = %s AND fs.song_id = s.idtrack
				   ) AS is_favorite
			FROM "Soundmusicconnect".songs s
			LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
			LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
			WHERE s.genre_id = %s
			GROUP BY s.idtrack, s.songname, s.imagesong
			LIMIT 50;
			''' , (user_id , genre_id)
			)
		
		tracks = [ ]
		for row in cur.fetchall ( ) :
			track = {
				"idtrack" : row [ 0 ] ,
				"songname" : row [ 1 ] ,
				"performer_name" : row [ 2 ] or "Unknown Artist" ,
				"imagesong" : base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None ,
				"is_favorite" : row [ 4 ]
				}
			tracks.append ( track )
		
		return jsonify ( { "tracks" : tracks , "error" : None } ) , 200
	
	except Exception as e :
		logging.error ( f"Error in /tracks_by_genre endpoint: {e}" )
		return jsonify ( { "error" : str ( e ) , "tracks" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/toggle_favorite_track' , methods = [ 'POST' ] )
def toggle_favorite_track ( ) :
	"""Adds or removes a song from a user's favorites based on its current status."""
	conn = None
	try :
		data = request.get_json ( )
		track_id = data.get ( 'track_id' )
		user_login = data.get ( 'user_login' )
		
		if not track_id or not user_login :
			return jsonify ( { "error" : "Track ID and user login are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		cur = conn.cursor ( )
		
		# Get user ID by login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_data = cur.fetchone ( )
		if not user_data :
			return jsonify ( { "error" : "User not found." } ) , 404
		user_id = user_data [ 0 ]
		
		# Check if the track is already favorited by the user
		cur.execute (
			'SELECT 1 FROM "Soundmusicconnect".favorite_songs WHERE user_id = %s AND song_id = %s' ,
			(user_id , track_id)
			)
		if cur.fetchone ( ) :
			# Remove track from favorites
			cur.execute (
				'DELETE FROM "Soundmusicconnect".favorite_songs WHERE user_id = %s AND song_id = %s' ,
				(user_id , track_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Track removed from favorites." } ) , 200
		else :
			# Add track to favorites
			cur.execute (
				'INSERT INTO "Soundmusicconnect".favorite_songs (user_id, song_id) VALUES (%s, %s)' ,
				(user_id , track_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Track added to favorites." } ) , 201
	
	except Exception as e :
		if conn :
			conn.rollback ( )  # If there was a problem, rollback changes
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/toggle_favorite_playlist' , methods = [ 'POST' ] )
def toggle_favorite_playlist ( ) :
	conn = None
	try :
		data = request.get_json ( )
		playlist_id = data.get ( 'playlist_id' )
		user_login = data.get ( 'user_login' )
		logging.debug ( f"Received {data}" )
		
		if not playlist_id or not user_login :
			return jsonify ( { "error" : "Playlist ID and user login are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		cur = conn.cursor ( )
		
		# Get user ID by login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_data = cur.fetchone ( )
		if not user_data :
			return jsonify ( { "error" : "User not found." } ) , 404
		user_id = user_data [ 0 ]
		
		cur.execute (
			'SELECT 1 FROM "Soundmusicconnect".favorite_playlists WHERE user_id = %s AND playlist_id = %s' ,
			(user_id , playlist_id)
			)
		is_favorited = cur.fetchone ( )
		
		if is_favorited :
			# Remove playlist from favorites
			cur.execute (
				'DELETE FROM "Soundmusicconnect".favorite_playlists WHERE user_id = %s AND playlist_id = %s' ,
				(user_id , playlist_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Playlist removed from favorites successfully." } ) , 200
		else :
			# Add playlist to favorites
			cur.execute (
				'INSERT INTO "Soundmusicconnect".favorite_playlists (user_id, playlist_id) VALUES (%s, %s)' ,
				(user_id , playlist_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Playlist added to favorites successfully." } ) , 201
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/performer_details' , methods = [ 'POST' ] )
def performer_details ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		performer_id = data.get ( 'perfomerid' )  # Typo in client: 'perfomerid'
		user_login = data.get ( 'login' )
		
		if not performer_id or not user_login :
			log.warning ( "Missing performer ID or login" )
			return jsonify (
				{
					"error" : "Performer ID and login are required" , "performer" : None , "new_releases" : [ ] ,
					"songs" : [ ]
					}
				) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify (
				{
					"error" : "Failed to connect to the database" , "performer" : None , "new_releases" : [ ] ,
					"songs" : [ ]
					}
				) , 500
		
		cur = conn.cursor ( )
		
		# Fetch performer info
		cur.execute (
			'''
            SELECT id, fullname, information, "Photo"
            FROM "Soundmusicconnect".performers
            WHERE id = %s
            ''' , (performer_id ,)
			)
		performer_row = cur.fetchone ( )
		if not performer_row :
			log.warning ( f"No performer found with id {performer_id}" )
			return jsonify (
				{ "error" : "Performer not found" , "performer" : None , "new_releases" : [ ] , "songs" : [ ] }
				) , 404
		
		# Check if performer is favorited by the user
		cur.execute (
			'''
            SELECT EXISTS (
                SELECT 1 FROM "Soundmusicconnect".favorite_performers
                WHERE user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                AND performer_id = %s
            )
            ''' , (user_login , performer_id)
			)
		is_favorite = cur.fetchone ( ) [ 0 ]
		
		performer = {
			"id" : performer_row [ 0 ] ,
			"fullname" : performer_row [ 1 ] ,
			"information" : performer_row [ 2 ] ,
			"photoBase64" : base64.b64encode ( performer_row [ 3 ] ).decode ( 'utf-8' ) if performer_row [
				3 ] else None ,
			"is_favorite" : is_favorite
			}
		
		# Fetch all songs and their performers using a CTE
		cur.execute (
			'''
            WITH performer_songs AS (
                SELECT song_id
                FROM "Soundmusicconnect".song_performers
                WHERE performer_id = %s
            )
            SELECT s.idtrack, s.songname, s.yearcreate, s.imagesong, s.duration,
                   COUNT(fs.user_id) AS like_count,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
                       WHERE fs.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fs.song_id = s.idtrack
                   ) AS is_favorite
            FROM "Soundmusicconnect".songs s
            JOIN performer_songs ps ON s.idtrack = ps.song_id
            LEFT JOIN "Soundmusicconnect".favorite_songs fs ON s.idtrack = fs.song_id
            GROUP BY s.idtrack, s.songname, s.yearcreate, s.imagesong, s.duration
            ''' , (performer_id , user_login)
			)
		song_rows = cur.fetchall ( )
		
		songs = [ ]
		for row in song_rows :
			# Fetch all performers for this song
			cur.execute (
				'''
                SELECT p.id, p.fullname, p."Photo",
                       EXISTS (
                           SELECT 1 FROM "Soundmusicconnect".favorite_performers fp
                           WHERE fp.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                           AND fp.performer_id = p.id
                       ) AS is_favorite
                FROM "Soundmusicconnect".song_performers sp
                JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
                WHERE sp.song_id = %s
                ''' , (user_login , row [ 0 ])
				)
			performer_rows = cur.fetchall ( )
			
			performers = [
				{
					"id" : p_row [ 0 ] ,
					"fullname" : p_row [ 1 ] ,
					"photoBase64" : base64.b64encode ( p_row [ 2 ] ).decode ( 'utf-8' ) if p_row [ 2 ] else None ,
					"is_favorite" : p_row [ 3 ]
					}
				for p_row in performer_rows
				]
			
			year_create = row [ 2 ]  # int4
			year_create_str = str ( year_create ) if year_create is not None else None
			
			song = {
				"song_id" : row [ 0 ] ,
				"song_name" : row [ 1 ] ,
				"yearcreate" : year_create_str ,
				"song_imageBase64" : base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None ,
				"duration" : row [ 4 ] ,
				"performers" : performers ,
				"like_count" : row [ 5 ] ,
				"is_favorite" : row [ 6 ]
				}
			songs.append ( song )
		
		# Define new releases (songs from the last year)
		current_year = datetime.now ( ).year
		new_releases = [
			song for song in songs
			if song [ "yearcreate" ] and int ( song [ "yearcreate" ] ) >= current_year - 1
			]
		
		response = {
			"error" : None ,
			"performer" : performer ,
			"new_releases" : new_releases ,
			"songs" : songs
			}
		log.info ( f"Successfully fetched details for performer {performer_id}" )
		return jsonify ( response ) , 200
	
	except Exception as e :
		log.error ( f"Database error: {e}" )
		return jsonify (
			{ "error" : f"Database error: {e}" , "performer" : None , "new_releases" : [ ] , "songs" : [ ] }
			) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/toggle_favorite_performer' , methods = [ 'POST' ] )
def toggle_favorite_performer ( ) :
	conn = None
	try :
		data = request.get_json ( )
		logging.debug ( f"Received {data}" )  # added logging
		performer_id = data.get ( 'performer_id' )
		user_login = data.get ( 'user_login' )
		
		if not performer_id or not user_login :
			return jsonify ( { "error" : "Performer ID and user login are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		cur = conn.cursor ( )
		
		# Get user ID by login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_data = cur.fetchone ( )
		logging.debug ( f"User {user_data}" )  # added logging
		if not user_data :
			return jsonify ( { "error" : "User not found." } ) , 404
		user_id = user_data [ 0 ]
		
		# Check if performer is already favorited by the user
		cur.execute (
			'SELECT 1 FROM "Soundmusicconnect".favorite_performers WHERE user_id = %s AND performer_id = %s' ,
			(user_id , performer_id)
			)
		is_favorited = cur.fetchone ( )
		logging.debug ( f"Is favorited: {is_favorited}" )  # added logging
		
		if is_favorited :
			# Remove performer from favorites
			cur.execute (
				'DELETE FROM "Soundmusicconnect".favorite_performers WHERE user_id = %s AND performer_id = %s' ,
				(user_id , performer_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Performer removed from favorites successfully." } ) , 200
		else :
			# Add performer to favorites
			cur.execute (
				'INSERT INTO "Soundmusicconnect".favorite_performers (user_id, performer_id) VALUES (%s, %s)' ,
				(user_id , performer_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Performer added to favorites successfully." } ) , 201
	
	except Exception as e :
		logging.exception ( f"Database error: {e}" )  # improved logging
		if conn :
			conn.rollback ( )
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	finally :
		if conn :
			conn.close ( )


def convert_duration_to_seconds ( duration ) :
	if duration is None :
		log.debug ( "Duration is None, defaulting to 0 seconds." )
		return 0
	if not isinstance ( duration , str ) :
		log.warning ( f"Duration is not a string: {duration}. Defaulting to 0." )
		return 0
	
	# Handle MM:SS format with flexible digit counts (e.g., "3:45" or "03:45")
	match = re.match ( r'^(\d{1,2}):(\d{2})$' , duration )
	if match :
		minutes = int ( match.group ( 1 ) )
		seconds = int ( match.group ( 2 ) )
		if 0 <= minutes <= 99 and 0 <= seconds < 60 :  # Reasonable bounds
			total_seconds = (minutes*60) + seconds
			log.debug ( f"Converted {duration} to {total_seconds} seconds." )
			return total_seconds
		else :
			log.warning (
				f"Invalid time values in {duration} (minutes: {minutes}, seconds: {seconds}). Defaulting to 0."
				)
			return 0
	
	# Fallback for pure seconds
	try :
		total_seconds = int ( duration )
		if 0 <= total_seconds <= 359999 :  # Max 99:59:59
			log.debug ( f"Interpreted {duration} as {total_seconds} seconds." )
			return total_seconds
		else :
			log.warning ( f"Duration {duration} out of valid range. Defaulting to 0." )
			return 0
	except ValueError :
		log.warning ( f"Invalid duration format: {duration}. Defaulting to 0." )
		return 0


@app.route ( '/album_details' , methods = [ 'POST' ] )
def album_details ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received request data: {data}" )
		performer_id = data.get ( 'performerid' )
		login = data.get ( 'login' )
		
		if not performer_id or not login :
			log.warning ( "Missing performerid or login in request" )
			return jsonify ( { "error" : "Missing performerid or login" , "albums" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify ( { "error" : "Failed to connect to the database" , "albums" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		
		# Get user ID from login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			log.warning ( f"User not found for login: {login}" )
			return jsonify ( { "error" : "User not found" , "albums" : [ ] } ) , 404
		user_id = user_result [ 0 ]
		
		# Fetch albums for the performer
		cur.execute (
			'''
            SELECT a.idalbum, a.albumname, a.yearrelease, p.fullname, a.imagealbum,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_albums fa
                       WHERE fa.album_id = a.idalbum AND fa.user_id = %s
                   ) AS is_favorite
            FROM "Soundmusicconnect".albums a
            JOIN "Soundmusicconnect".performers p ON a.performer_id = p.id
            WHERE a.performer_id = %s
            ''' ,
			(user_id , performer_id)
			)
		albums = cur.fetchall ( )
		
		if not albums :
			log.info ( f"No albums found for performer_id: {performer_id}" )
			return jsonify ( { "albums" : [ ] , "error" : None } ) , 200
		
		album_list = [
			{
				"id" : row [ 0 ] ,
				"albumname" : row [ 1 ] ,
				"year_release" : row [ 2 ].isoformat ( ) ,
				"performer_name" : row [ 3 ] ,
				"imageBase64" : base64.b64encode ( row [ 4 ] ).decode ( 'utf-8' ) if row [ 4 ] else None ,
				"is_favorite" : row [ 5 ]
				}
			for row in albums
			]
		
		log.info ( f"Returning {len ( album_list )} albums for performer_id: {performer_id}" )
		return jsonify ( { "albums" : album_list , "error" : None } ) , 200
	
	except psycopg2.Error as e :
		log.error ( f"Database error in /album_details: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" , "albums" : [ ] } ) , 500
	except Exception as e :
		log.error ( f"Unexpected error in /album_details: {e}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : f"Internal server error: {e}" , "albums" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )
			log.debug ( "Database connection closed" )


@app.route ( '/album_detail_by_id' , methods = [ 'POST' ] )
def album_detail_by_id ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_id = data.get ( 'albumId' )
		login = data.get ( 'login' )
		
		if not album_id or not login :
			return jsonify ( { "error" : "albumId and login are required" , "album" : None } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database" , "album" : None } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
			SELECT a.idalbum, a.albumname, a.yearrelease, p.fullname, encode(a.imagealbum, 'base64'),
				   EXISTS (
					   SELECT 1 FROM "Soundmusicconnect".favorite_albums fa
					   WHERE fa.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
					   AND fa.album_id = a.idalbum
				   ) AS is_favorite
			FROM "Soundmusicconnect".albums a
			JOIN "Soundmusicconnect".performers p ON a.performer_id = p.id
			WHERE a.idalbum = %s
			''' , (login , album_id)
			)
		row = cur.fetchone ( )
		if not row :
			return jsonify ( { "error" : "Album not found" , "album" : None } ) , 404
		
		album = {
			"id" : row [ 0 ] ,
			"albumname" : row [ 1 ] ,
			"year_release" : row [ 2 ].isoformat ( ) ,
			"performer_name" : row [ 3 ] ,
			"imageBase64" : row [ 4 ] ,
			"is_favorite" : row [ 5 ]
			}
		return jsonify ( { "album" : album , "error" : None } ) , 200
	except Exception as e :
		log.error ( f"Error fetching album details: {e}" )
		return jsonify ( { "error" : str ( e ) , "album" : None } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/popular_tracks' , methods = [ 'GET' ] )
def popular_tracks ( ) :
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "tracks" : [ ] } ) , 500
		cur = conn.cursor ( )
		cur.execute (
			'''
			SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performer_name,
				   s.imagesong, COUNT(fs.song_id) AS like_count
			FROM "Soundmusicconnect".songs s
			LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
			LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
			LEFT JOIN "Soundmusicconnect".favorite_songs fs ON s.idtrack = fs.song_id
			GROUP BY s.idtrack, s.songname, s.imagesong
			ORDER BY like_count DESC
			LIMIT 5;
			'''
			)
		track_rows = cur.fetchall ( )
		tracks_data = [ ]
		for row in track_rows :
			image_b64 = base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else ""
			tracks_data.append (
				{
					'song_id' : row [ 0 ] ,
					'song_name' : row [ 1 ] ,
					'performer_name' : row [ 2 ] or "Unknown Artist" ,
					'song_imageBase64' : image_b64 ,
					'like_count' : row [ 4 ]
					}
				)
		return jsonify ( { 'tracks' : tracks_data } )
	except Exception as e :
		log.error ( f"Database error: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" , "tracks" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/playlistdetail' , methods = [ 'POST' ] )
def playlist_detail ( ) :
	conn = None
	try :
		log.info ( "Entering /playlistdetail endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		playlist_id = data.get ( 'idplay' )  # Changed to 'idplay' to match client request
		user_login = data.get ( 'login' )
		
		if not playlist_id or not user_login :
			log.warning ( "Error: idplay and login are required." )
			return jsonify ( { "error" : "idplay and login are required" , "playlist" : None , "songs" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database." )
			return jsonify (
				{ "error" : "Failed to connect to the database" , "playlist" : None , "songs" : [ ] }
				) , 500
		
		cur = conn.cursor ( )
		
		# Get user ID from login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			log.warning ( f"User not found for login: {user_login}" )
			return jsonify ( { "error" : "User not found" , "playlist" : None , "songs" : [ ] } ) , 404
		user_id = user_result [ 0 ]
		
		# Fetch playlist metadata
		cur.execute (
			'''
            SELECT p.idplay, p.nameplay, p.image, p.madeinuser,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_playlists fp
                       WHERE fp.playlist_id = p.idplay AND fp.user_id = %s
                   ) AS is_favorite,
                   u.login AS creator_login
            FROM "Soundmusicconnect".playlists p
            LEFT JOIN "Soundmusicconnect".users u ON p.madeinuser = u.id
            WHERE p.idplay = %s
            ''' , (user_id , playlist_id)
			)
		playlist_result = cur.fetchone ( )
		if not playlist_result :
			log.warning ( f"Playlist not found for idplay: {playlist_id}" )
			return jsonify ( { "error" : "Playlist not found" , "playlist" : None , "songs" : [ ] } ) , 404
		
		playlist_id_db , nameplay , image , madeinuser , is_favorite , creator_login = playlist_result
		image_base64 = base64.b64encode ( image ).decode ( 'utf-8' ) if image else None
		
		playlist_data = {
			"id" : playlist_id_db ,
			"name" : nameplay ,
			"imageBase64" : image_base64 ,
			"madeinuser" : madeinuser ,
			"creatorLogin" : creator_login or "Unknown" ,
			"isFavorite" : is_favorite
			}
		
		# Fetch songs in the playlist
		cur.execute (
			'''
            SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performer_name,
                   s.imagesong, s.duration,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
                       WHERE fs.song_id = s.idtrack AND fs.user_id = %s
                   ) AS is_favorite
            FROM "Soundmusicconnect".songs s
            JOIN "Soundmusicconnect".playlist_songs ps ON s.idtrack = ps.song_id
            LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
            LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
            WHERE ps.playlist_id = %s
            GROUP BY s.idtrack, s.songname, s.imagesong, s.duration
            ''' , (user_id , playlist_id)
			)
		song_rows = cur.fetchall ( )
		
		songs_data = [
			{
				"songId" : row [ 0 ] ,
				"title" : row [ 1 ] ,
				"artist" : row [ 2 ] or "Unknown Artist" ,
				"imageBase64" : base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None ,
				"duration" : row [ 4 ] ,
				"isFavorite" : row [ 5 ]
				}
			for row in song_rows
			]
		
		response = {
			"playlist" : playlist_data ,
			"songs" : songs_data ,
			"error" : None
			}
		log.info ( f"Successfully fetched playlist details for playlist {playlist_id} and user {user_login}" )
		return jsonify ( response ) , 200
	
	except Exception as e :
		log.error ( f"Error in /playlistdetail endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : f"Server error: {str ( e )}" , "playlist" : None , "songs" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


def convert_duration_to_seconds ( duration ) :
	if duration is None :
		log.debug ( "Duration is None, defaulting to 0 seconds." )
		return 0
	if not isinstance ( duration , str ) :
		log.warning ( f"Duration is not a string: {duration}. Defaulting to 0." )
		return 0
	
	# Handle MM:SS format with flexible digit counts (e.g., "3:45" or "03:45")
	match = re.match ( r'^(\d{1,2}):(\d{2})$' , duration )
	if match :
		minutes = int ( match.group ( 1 ) )
		seconds = int ( match.group ( 2 ) )
		if 0 <= minutes <= 99 and 0 <= seconds < 60 :  # Reasonable bounds
			total_seconds = (minutes*60) + seconds
			log.debug ( f"Converted {duration} to {total_seconds} seconds." )
			return total_seconds
		else :
			log.warning (
				f"Invalid time values in {duration} (minutes: {minutes}, seconds: {seconds}). Defaulting to 0."
				)
			return 0
	
	# Fallback for pure seconds (unlikely in your schema, but included for robustness)
	try :
		total_seconds = int ( duration )
		if 0 <= total_seconds <= 359999 :  # Max 99:59:59
			log.debug ( f"Interpreted {duration} as {total_seconds} seconds." )
			return total_seconds
		else :
			log.warning ( f"Duration {duration} out of valid range. Defaulting to 0." )
			return 0
	except ValueError :
		log.warning ( f"Invalid duration format: {duration}. Defaulting to 0." )
		return 0


@app.route ( '/checkuserplaylists' , methods = [ 'POST' ] )
def checkuserplaylists ( ) :
	data = request.get_json ( )
	login = data [ 'login' ]
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			print ( "Failed to connect to the database." )
			return jsonify (
				{ "error" : "Failed to connect to the database." , "playlists" : [ ] }
				) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''SELECT
			p.idplay,
			p.nameplay
		FROM
			"Soundmusicconnect".playlists AS p
		JOIN
			"Soundmusicconnect".users AS u ON p.madeinuser = u.id
		WHERE
			u.login = %s;''' , (login ,)
			)  # Pass login as a tuple to prevent SQL injection
		
		playlists = [ ]
		for row in cur.fetchall ( ) :
			playlist_id , playlist_name = row
			playlists.append ( { "idplay" : playlist_id , "nameplay" : playlist_name } )
		print ( f"Playlists found for user {login}: {playlists}" )
		return jsonify ( { "playlists" : playlists } ) , 200
	
	
	except Exception as e :
		print ( f"An error occurred: {e}" )
		return jsonify ( { "error" : str ( e ) , "playlists" : [ ] } ) , 500
	finally :
		if conn :
			cur.close ( )
			conn.close ( )


@app.route ( '/createplaylist' , methods = [ 'POST' ] )
def create_playlist ( ) :
	"""Creates a new playlist for a user."""
	data = request.get_json ( )
	login = data.get ( 'login' )
	playlist_name = data.get ( 'playlistName' )
	image_data = data.get ( 'image' )  # Optional image data
	
	if not login or not playlist_name :
		return jsonify ( { "error" : "Login and playlistName are required." } ) , 400
	
	conn = get_db_connection ( )
	if not conn :
		return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
	
	try :
		cur = conn.cursor ( )
		
		# Get user ID based on login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (login ,) )
		user_row = cur.fetchone ( )
		if not user_row :
			conn.rollback ( )
			return jsonify ( { "error" : "User not found." } ) , 404
		
		user_id = user_row [ 0 ]
		
		# Create the playlist
		cur.execute (
			'INSERT INTO "Soundmusicconnect".playlists (nameplay, madeinuser, image) VALUES (%s, %s, %s) RETURNING '
			'idplay' ,
			(playlist_name , user_id , psycopg2.Binary ( image_data ) if image_data else None)
			)
		playlist_id = cur.fetchone ( ) [ 0 ]
		conn.commit ( )
		
		return jsonify ( { "message" : "Playlist created successfully!" , "playlistId" : playlist_id } ) , 201
	
	except Exception as e :
		conn.rollback ( )
		print ( f"Error creating playlist: {e}" )
		return jsonify ( { "error" : str ( e ) } ) , 500
	finally :
		if conn :
			cur.close ( )
			conn.close ( )


@app.route ( '/createplaylistandinsertsongs' , methods = [ 'POST' ] )
def create_playlistandinsertsongs ( ) :
	data = request.get_json ( )
	print ( "Received data:" , data )  # Print the received data
	login = data.get ( 'login' )
	song_ids = data.get ( 'songId' )  # Expecting a single song ID, or a list of song IDs
	playlist_name = "Новый плейлист"  # Default playlist name
	image_data = ""  # Placeholder for image data (optional)
	
	if not login :
		return jsonify ( { "error" : "Login is required." } ) , 400
	
	conn = get_db_connection ( )
	if not conn :
		return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
	
	try :
		cur = conn.cursor ( )
		
		# 1. Get user ID based on login
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (login ,) )
		user_row = cur.fetchone ( )
		if not user_row :
			conn.rollback ( )
			return jsonify ( { "error" : "User not found." } ) , 404
		user_id = user_row [ 0 ]
		
		# 2. Create the playlist
		cur.execute (
			'INSERT INTO "Soundmusicconnect".playlists (nameplay, madeinuser, image) VALUES (%s, %s, %s) RETURNING '
			'idplay' ,
			(playlist_name , user_id , psycopg2.Binary ( image_data ) if image_data else None)
			)
		playlist_id = cur.fetchone ( ) [ 0 ]  # Get the newly created playlist ID
		
		# 3. Insert songs into the playlist
		if isinstance ( song_ids , str ) or isinstance ( song_ids , int ) :  # Handle single song ID
			song_ids = [ song_ids ]  # Convert to list for consistent processing
		elif not isinstance ( song_ids , list ) or not all (
				isinstance ( song_id , (str , int) ) for song_id in song_ids
				) :
			conn.rollback ( )
			return jsonify ( { "error" : "Invalid songId format. Must be a single ID or a list of IDs." } ) , 400
		
		for song_id in song_ids :
			# Check if the song exists
			cur.execute ( 'SELECT 1 FROM "Soundmusicconnect".songs WHERE idtrack = %s' , (song_id ,) )
			if not cur.fetchone ( ) :
				conn.rollback ( )
				return jsonify ( { "error" : f"Song with ID {song_id} not found." } ) , 404
			
			# Add the song to the playlist
			cur.execute (
				'INSERT INTO "Soundmusicconnect".playlist_songs (playlist_id, song_id) VALUES (%s, %s)' ,
				(playlist_id , song_id)
				)
		print ( playlist_id , song_id )
		
		conn.commit ( )
		
		return jsonify ( { "playlistId" : playlist_id } ) , 201
	
	except Exception as e :
		conn.rollback ( )
		print ( f"Error creating playlist and adding songs: {e}" )
		return jsonify ( { "error" : str ( e ) } ) , 500
	finally :
		if conn :
			cur.close ( )
			conn.close ( )


@app.route ( '/deleteplaylist' , methods = [ 'POST' ] )
def delete_playlist ( ) :
	data = request.get_json ( )
	playlist_id = data.get ( 'playlistId' )  # Get playlist ID from query parameter
	
	if not playlist_id :
		return jsonify ( { "error" : "playlistId is required." } ) , 400
	
	conn = get_db_connection ( )
	if not conn :
		return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
	
	try :
		cur = conn.cursor ( )
		
		# Check if the playlist exists
		cur.execute ( 'SELECT 1 FROM "Soundmusicconnect".playlists WHERE idplay = %s' , (playlist_id ,) )
		if not cur.fetchone ( ) :
			conn.rollback ( )
			return jsonify ( { "error" : "Playlist not found." } ) , 404
		
		# Delete associated songs from the playlist_songs table first (cascade delete won't work across schemas)
		cur.execute ( 'DELETE FROM "Soundmusicconnect".playlist_songs WHERE playlist_id = %s' , (playlist_id ,) )
		
		# Delete favorite playlists:
		cur.execute ( 'DELETE FROM "Soundmusicconnect".favorite_playlists WHERE playlist_id = %s' , (playlist_id ,) )
		
		# Finally, delete the playlist itself
		cur.execute ( 'DELETE FROM "Soundmusicconnect".playlists WHERE idplay = %s' , (playlist_id ,) )
		
		conn.commit ( )
		return jsonify ( { "message" : "Playlist and associated songs deleted successfully!" } ) , 200
	
	except Exception as e :
		conn.rollback ( )
		print ( f"Error deleting playlist: {e}" )
		return jsonify ( { "error" : str ( e ) } ) , 500
	finally :
		if conn :
			cur.close ( )
			conn.close ( )


@app.route ( '/checkuserplaylists' , methods = [ 'GET' ] )
def check_user_playlists ( ) :
	user_login = request.args.get ( 'login' )
	track_id = request.args.get ( 'trackId' )
	
	if not user_login or not track_id :
		return jsonify ( { "error" : "login and trackId are required" , "playlists" : [ ] } ) , 400
	
	conn = get_db_connection ( )
	if not conn :
		return jsonify ( { "error" : "Failed to connect to the database" , "playlists" : [ ] } ) , 500
	
	try :
		cur = conn.cursor ( )
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			return jsonify ( { "error" : "User not found" , "playlists" : [ ] } ) , 404
		user_id = user_result [ 0 ]
		
		cur.execute (
			'''
            SELECT p.idplay, p.nameplay, p.image, p.madeinuser
            FROM "Soundmusicconnect".playlists p
            LEFT JOIN "Soundmusicconnect".favorite_playlists fp ON p.idplay = fp.playlist_id AND fp.user_id = %s
            WHERE (p.madeinuser = %s OR fp.user_id IS NOT NULL)
            AND p.idplay NOT IN (
                SELECT ps.playlist_id
                FROM "Soundmusicconnect".playlist_songs ps
                WHERE ps.song_id = %s
            )
            ORDER BY p.idplay
            ''' , (user_id , user_id , track_id)
			)
		playlists = cur.fetchall ( )
		
		playlist_data = [
			{
				"idplay" : row [ 0 ] , "nameplay" : row [ 1 ] ,
				"imageBase64" : base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None ,
				"madeinuser" : row [ 3 ]
				}
			for row in playlists
			]
		
		return jsonify ( { "playlists" : playlist_data , "error" : None } ) , 200
	
	except Exception as e :
		print ( f"Error: {e}" )
		return jsonify ( { "error" : str ( e ) , "playlists" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/addsongtoplaylist' , methods = [ 'POST' ] )
def add_song_to_playlist ( ) :
	"""Adds a song to a specific playlist."""
	data = request.get_json ( )
	playlist_id = data.get ( 'playlistId' )
	song_id = data.get ( 'songId' )
	
	if not playlist_id or not song_id :
		return jsonify ( { "error" : "playlistId and songId are required." } ) , 400
	
	conn = get_db_connection ( )
	if not conn :
		return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
	
	try :
		cur = conn.cursor ( )
		
		# Check if the playlist exists
		cur.execute ( 'SELECT 1 FROM "Soundmusicconnect".playlists WHERE idplay = %s' , (playlist_id ,) )
		if not cur.fetchone ( ) :
			conn.rollback ( )
			return jsonify ( { "error" : "Playlist not found." } ) , 404
		
		# Check if the song exists
		cur.execute ( 'SELECT 1 FROM "Soundmusicconnect".songs WHERE idtrack = %s' , (song_id ,) )
		if not cur.fetchone ( ) :
			conn.rollback ( )
			return jsonify ( { "error" : "Song not found." } ) , 404
		
		# Add the song to the playlist
		cur.execute (
			'INSERT INTO "Soundmusicconnect".playlist_songs (playlist_id, song_id) VALUES (%s, %s)' ,
			(playlist_id , song_id)
			)
		conn.commit ( )
		
		return jsonify ( { "message" : "Song added to playlist successfully!" } ) , 200
	
	except psycopg2.errors.UniqueViolation :
		conn.rollback ( )
		return jsonify ( { "error" : "Song already exists in the playlist." } ) , 409  # Conflict
	
	except Exception as e :
		conn.rollback ( )
		print ( f"Error adding song to playlist: {e}" )
		return jsonify ( { "error" : str ( e ) } ) , 500
	finally :
		if conn :
			cur.close ( )
			conn.close ( )


@app.route ( '/removesongfromplaylist' , methods = [ 'POST' ] )
def remove_song_from_playlist ( ) :
	"""Removes a song from a specific playlist."""
	data = request.get_json ( )
	logging.debug ( f"Received request with {data}" )  # Log the received data
	playlist_id = data.get ( 'playlistId' )
	song_id = data.get ( 'songId' )
	
	if not playlist_id or not song_id :
		logging.warning ( "Missing playlistId or songId" )  # Log missing parameters
		return jsonify ( { "error" : "playlistId and songId are required." } ) , 400
	
	conn = get_db_connection ( )
	if not conn :
		logging.error ( "Failed to connect to the database." )  # Log DB connection failure
		return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
	
	try :
		cur = conn.cursor ( )
		
		# Check if the playlist exists
		cur.execute ( 'SELECT 1 FROM "Soundmusicconnect".playlists WHERE idplay = %s' , (playlist_id ,) )
		playlist_exists = cur.fetchone ( )
		if not playlist_exists :
			conn.rollback ( )
			logging.warning ( f"Playlist with id {playlist_id} not found." )  # Log playlist not found
			return jsonify ( { "error" : "Playlist not found." } ) , 404
		
		# Check if the song exists
		cur.execute ( 'SELECT 1 FROM "Soundmusicconnect".songs WHERE idtrack = %s' , (song_id ,) )
		song_exists = cur.fetchone ( )
		if not song_exists :
			conn.rollback ( )
			logging.warning ( f"Song with id {song_id} not found." )  # Log song not found
			return jsonify ( { "error" : "Song not found." } ) , 404
		
		# Remove the song from the playlist
		cur.execute (
			'DELETE FROM "Soundmusicconnect".playlist_songs WHERE playlist_id = %s AND song_id = %s' ,
			(playlist_id , song_id)
			)
		
		if cur.rowcount == 0 :  # Check if any rows were actually deleted
			conn.rollback ( )
			logging.warning (
				f"Song with id {song_id} not found in playlist with id {playlist_id}."
				)  # Log song not in playlist
			return jsonify ( { "error" : "Song not found in the playlist." } ) , 404
		
		conn.commit ( )
		logging.info ( f"Song {song_id} removed from playlist {playlist_id} successfully!" )  # Log success
		
		return jsonify ( { "message" : "Song removed from playlist successfully!" } ) , 200
	
	except Exception as e :
		conn.rollback ( )
		logging.exception ( f"Error removing song from playlist: {e}" )  # Log the full exception traceback
		return jsonify ( { "error" : str ( e ) } ) , 500
	finally :
		if conn :
			cur.close ( )
			conn.close ( )


@app.route ( '/renameplaylist' , methods = [ 'POST' ] )  # Changed to POST as we're modifying data
def rename_playlist ( ) :
	data = request.get_json ( )
	logging.debug ( f"Received request with {data}" )
	playlist_id = data.get ( 'playlistId' )
	new_playlist_name = data.get ( 'newPlaylistName' )
	login = data.get ( 'login' )
	
	if not all ( [ playlist_id , new_playlist_name , login ] ) :
		return jsonify ( { "error" : "Missing required parameters" } ) , 400
	
	try :
		conn = get_db_connection ( )
		if not conn :
			print ( "Failed to connect to the database." )
			return jsonify (
				{ "error" : "Failed to connect to the database." , "playlists" : [ ] }
				) , 500  # Added empty playlist array
		
		cur = conn.cursor ( )
		
		# First, verify that the playlist belongs to the user.  Crucial for security.
		cur.execute (
			"""
				SELECT u.id
				FROM "Soundmusicconnect".users u
				WHERE u.login = %s
			""" , (login ,)
			)
		user_result = cur.fetchone ( )
		
		if not user_result :
			conn.rollback ( )
			cur.close ( )
			conn.close ( )
			return jsonify ( { "error" : "User not found." } ) , 404
		
		user_id = user_result [ 0 ]
		
		cur.execute (
			"""
				SELECT 1
				FROM "Soundmusicconnect".playlists p
				WHERE p.idplay = %s AND p.madeinuser = %s
			""" , (playlist_id , user_id)
			)
		playlist_ownership_result = cur.fetchone ( )
		
		if not playlist_ownership_result :
			conn.rollback ( )
			cur.close ( )
			conn.close ( )
			return jsonify ( { "error" : "Playlist not found or does not belong to this user." } ) , 403  # Forbidden
		
		# Now, rename the playlist.
		cur.execute (
			"""
				UPDATE "Soundmusicconnect".playlists
				SET nameplay = %s
				WHERE idplay = %s
			""" , (new_playlist_name , playlist_id)
			)
		
		conn.commit ( )
		cur.close ( )
		conn.close ( )
		
		return jsonify ( { "message" : "Playlist renamed successfully." } ) , 200
	
	except psycopg2.Error as e :
		print ( f"Database error: {e}" )
		if conn :
			conn.rollback ( )
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/playlists' , methods = [ 'GET' ] )
def playlists ( ) :
	conn = None
	try :
		print ( "Attempting to connect to the database..." )
		conn = get_db_connection ( )
		if not conn :
			print ( "Failed to connect to the database." )
			return jsonify (
				{ "error" : "Failed to connect to the database." , "playlists" : [ ] }
				) , 500  # Added empty playlist array
		
		cur = conn.cursor ( )
		print ( "Executing SQL query to fetch playlists..." )
		cur.execute (
			'''
				SELECT idplay, nameplay, image FROM "Soundmusicconnect".playlists;
			'''
			)
		rows = cur.fetchall ( )
		print ( f"Retrieved {len ( rows )} rows from the database." )
		print ( "Raw database rows:" , rows )
		
		playlist_data = [ ]
		for row in rows :
			try :
				image_b64 = ""
				if row [ 2 ] is not None :
					print ( f"Encoding imagedata for playlistid: {row [ 0 ]}" )
					image_b64 = base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' )
					print ( f"Encoded base64 data for image: {image_b64 [ :50 ]}...(showing first 50 chars)" )
				else :
					image_b64 = None
					print ( f"No image data for playlistid: {row [ 0 ]}" )
			except Exception as base64_error :
				print ( f"Error during base64 encoding for playlistid {row [ 0 ]}: {base64_error}" )
				image_b64 = None
			
			playlist_item = {
				'IdPlaylist' : row [ 0 ] ,
				'NamePlaylist' : row [ 1 ] ,
				'ImageBase64' : image_b64 if image_b64 is not None else ""
				}
			print ( f"Processed playlist item: {playlist_item}" )
			playlist_data.append ( playlist_item )
		
		print ( "Finished processing all playlists." )
		print ( "Final playlist data:" , playlist_data )
		return jsonify ( { "playlists" : playlist_data , "error" : None } )  # Return only 'playlists' array
	
	except Exception as e :
		print ( f"Database error: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" , "playlists" : [ ] } ) , 500  # Added empty playlist array
	finally :
		if conn :
			print ( "Closing database connection." )
			conn.close ( )


def base64_encode_image ( image_data ) :
	if image_data :
		return base64.b64encode ( image_data ).decode ( 'utf-8' )
	return None


@app.route ( '/search' , methods = [ 'POST' ] )
def search ( ) :
	conn = None
	try :
		data = request.get_json ( )
		searchinput = data.get ( 'searchinput' )
		login = data.get ( 'login' , '' )
		log.debug ( f"Received {data}" )
		
		if not searchinput :
			return jsonify ( { "error" : "Search input is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		results = [ ]
		
		# Search Tracks
		track_cursor = conn.cursor ( )
		track_cursor.execute (
			'''
            SELECT s.idtrack, s.songname, s.yearcreate, g.name AS genre_name,
                   STRING_AGG(p.fullname, ', ') AS performer_name, s.imagesong,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
                       WHERE fs.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fs.song_id = s.idtrack
                   ) AS is_favorite
            FROM "Soundmusicconnect".songs s
            LEFT JOIN "Soundmusicconnect".genres g ON s.genre_id = g.idgenr
            LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
            LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
            WHERE s.songname ILIKE %s
            GROUP BY s.idtrack, s.songname, s.yearcreate, g.name, s.imagesong
            LIMIT 10;
            ''' , (login , f"%{searchinput}%")
			)
		
		track_results = track_cursor.fetchall ( )
		for result in track_results :
			year_create = result [ 2 ]
			year_str = str ( year_create ) if year_create is not None else None  # Convert int to string
			results.append (
				{
					"id" : result [ 0 ] ,
					"name" : result [ 1 ] ,
					"year" : year_str ,
					"genre" : result [ 3 ] ,
					"performer" : result [ 4 ] or "Unknown Artist" ,
					"creator" : None ,
					"type" : "track" ,
					"image" : base64_encode_image ( result [ 5 ] ) if result [ 5 ] else None ,
					"is_favorite" : result [ 6 ]
					}
				)
		track_cursor.close ( )
		
		# Search Playlists
		playlist_cursor = conn.cursor ( )
		playlist_cursor.execute (
			'''
            SELECT p.idplay, p.nameplay, u.login, p.image,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_playlists fp
                       WHERE fp.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fp.playlist_id = p.idplay
                   ) AS is_favorite
            FROM "Soundmusicconnect".playlists p
            LEFT JOIN "Soundmusicconnect".users u ON p.madeinuser = u.id
            WHERE p.nameplay ILIKE %s
            LIMIT 10;
            ''' , (login , f"%{searchinput}%")
			)
		
		playlist_results = playlist_cursor.fetchall ( )
		for result in playlist_results :
			results.append (
				{
					"id" : result [ 0 ] ,
					"name" : result [ 1 ] ,
					"creator" : result [ 2 ] ,
					"type" : "playlist" ,
					"image" : base64_encode_image ( result [ 3 ] ) if result [ 3 ] else None ,
					"is_favorite" : result [ 4 ]
					}
				)
		playlist_cursor.close ( )
		
		# Search Performers
		performer_cursor = conn.cursor ( )
		performer_cursor.execute (
			'''
            SELECT p.id, p.fullname, p.information, p."Photo",
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_performers fper
                       WHERE fper.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fper.performer_id = p.id
                   ) AS is_favorite
            FROM "Soundmusicconnect".performers p
            WHERE p.fullname ILIKE %s
            LIMIT 10;
            ''' , (login , f"%{searchinput}%")
			)
		
		performer_results = performer_cursor.fetchall ( )
		for result in performer_results :
			results.append (
				{
					"id" : result [ 0 ] ,
					"name" : result [ 1 ] ,
					"type" : "performer" ,
					"information" : result [ 2 ] ,
					"image" : base64_encode_image ( result [ 3 ] ) if result [ 3 ] else None ,
					"is_favorite" : result [ 4 ]
					}
				)
		performer_cursor.close ( )
		
		# Search Albums
		album_cursor = conn.cursor ( )
		album_cursor.execute (
			'''
            SELECT a.idalbum, a.albumname, p.fullname, a.yearRelease, a.imagealbum,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_albums fa
                       WHERE fa.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fa.album_id = a.idalbum
                   ) AS is_favorite
            FROM "Soundmusicconnect".albums a
            JOIN "Soundmusicconnect".performers p ON a.performer_id = p.id
            WHERE a.albumname ILIKE %s
            LIMIT 10;
            ''' , (login , f"%{searchinput}%")
			)
		
		album_results = album_cursor.fetchall ( )
		for result in album_results :
			year_release = result [ 3 ]
			year_str = str ( year_release ) if year_release is not None else None  # Convert int to string
			results.append (
				{
					"id" : result [ 0 ] ,
					"name" : result [ 1 ] ,
					"performer" : result [ 2 ] ,
					"year" : year_str ,
					"type" : "album" ,
					"image" : base64_encode_image ( result [ 4 ] ) if result [ 4 ] else None ,
					"is_favorite" : result [ 5 ]
					}
				)
		album_cursor.close ( )
		
		conn.close ( )
		return jsonify ( results )
	
	except Exception as e :
		log.error ( f"An error occurred: {e}" )
		if conn :
			conn.close ( )
		return jsonify ( { "error" : "An internal error occurred." } ) , 500


@app.route ( '/toggle_favorite_album' , methods = [ 'POST' ] )
def toggle_favorite_album ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_id = data.get ( 'album_id' )
		user_login = data.get ( 'user_login' )
		
		if not album_id or not user_login :
			return jsonify ( { "error" : "Album ID and user login are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		cur = conn.cursor ( )
		
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_data = cur.fetchone ( )
		if not user_data :
			return jsonify ( { "error" : "User not found." } ) , 404
		user_id = user_data [ 0 ]
		
		cur.execute (
			'SELECT 1 FROM "Soundmusicconnect".favorite_albums WHERE user_id = %s AND album_id = %s' ,
			(user_id , album_id)
			)
		is_favorited = cur.fetchone ( )
		
		if is_favorited :
			cur.execute (
				'DELETE FROM "Soundmusicconnect".favorite_albums WHERE user_id = %s AND album_id = %s' ,
				(user_id , album_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Album removed from favorites successfully." } ) , 200
		else :
			cur.execute (
				'INSERT INTO "Soundmusicconnect".favorite_albums (user_id, album_id) VALUES (%s, %s)' ,
				(user_id , album_id)
				)
			conn.commit ( )
			return jsonify ( { "message" : "Album added to favorites successfully." } ) , 201
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error toggling favorite album: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/change_password3' , methods = [ 'POST' ] )
def change_password3 ( ) :
	conn = None
	try :
		log.info ( "Entering /change_password3 endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received {data}" )
		
		# Use lowercase keys to match client request
		login = data.get ( 'login' )  # Changed from 'Login'
		current_password = data.get ( 'currentPassword' )  # Changed from 'CurrentPassword'
		new_password = data.get ( 'newPassword' )  # Changed from 'NewPassword'
		
		if not login or not current_password or not new_password :
			log.warning ( "Error: login, currentPassword, and newPassword are required." )
			return jsonify (
				{ "Success" : False , "ErrorMessage" : "login, currentPassword, and newPassword are required" }
				) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "ErrorMessage" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		
		# Get the user's current hashed password
		cur.execute ( 'SELECT id, password FROM "Soundmusicconnect"."users" WHERE login = %s;' , (login ,) )
		user = cur.fetchone ( )
		
		if not user :
			log.warning ( f"User with login {login} not found." )
			return jsonify ( { "Success" : False , "ErrorMessage" : "User not found" } ) , 404
		
		user_id , stored_password_hash = user
		
		# Verify the current password
		if not bcrypt.checkpw ( current_password.encode ( 'utf-8' ) , stored_password_hash.encode ( 'utf-8' ) ) :
			log.warning ( f"Invalid current password for user: {login}" )
			return jsonify ( { "Success" : False , "ErrorMessage" : "Invalid current password" } ) , 401
		
		# Check if new password is different from the current one
		if bcrypt.checkpw ( new_password.encode ( 'utf-8' ) , stored_password_hash.encode ( 'utf-8' ) ) :
			log.warning ( f"New password is the same as the current password for user: {login}" )
			return jsonify (
				{ "Success" : False , "ErrorMessage" : "New password cannot be the same as the current password" }
				) , 400
		
		# Hash the new password
		hashed_new_password = bcrypt.hashpw ( new_password.encode ( 'utf-8' ) , bcrypt.gensalt ( ) ).decode ( 'utf-8' )
		
		# Update the password
		cur.execute (
			'UPDATE "Soundmusicconnect"."users" SET password = %s WHERE id = %s;' ,
			(hashed_new_password , user_id)
			)
		
		conn.commit ( )
		log.info ( f"Password for user {login} updated successfully." )
		return jsonify ( { "Success" : True , "Message" : "Password changed successfully" } ) , 200
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"An unexpected error occurred in /change_password3 endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "Success" : False , "ErrorMessage" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/passwordchangecode' , methods = [ 'POST' ] )
def change_password ( ) :
	data = request.get_json ( )
	log.debug ( f"Received {data}" )
	email = data.get ( 'email' )
	conn = None
	try :
		log.info ( "Entering /change_password endpoint..." )
		log.debug ( f"Received email: {email}" )
		if not email :
			log.warning ( "Error: Email is required." )
			return jsonify ( { "error" : "Email is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		cur = conn.cursor ( )
		cur.execute ( 'SELECT login FROM "Soundmusicconnect"."users" WHERE email = %s;' , (email ,) )
		login = cur.fetchone ( )
		log.debug ( f"Executed SQL query, user found: {login}" )
		
		if login :
			code , error = sendemainandcodeoutput ( email )
			if code :
				return jsonify ( { "code" : code , "login" : login [ 0 ] } ) , 200
			else :
				return jsonify ( { "error" : f"Failed to send email: {error}" } ) , 500
		else :
			log.info ( "Email not found." )
			return jsonify ( { "email_exists" : False } ) , 200
	except psycopg2.Error as e :
		log.error ( f"An unexpected error occurred in /change_password endpoint (database): {e}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : f"Database error: {e}" } ) , 500
	except Exception as e :
		log.error ( f"An unexpected error occurred in /change_password endpoint: {e}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal server error" } ) , 500
	finally :
		if conn :
			conn.close ( )


# Add these to your existing Flask app

@app.route ( '/update_performer' , methods = [ 'POST' ] )
def update_performer ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		performer_id = data.get ( 'id' )  # Match client’s 'id'
		fullname = data.get ( 'fullName' )  # Match client’s 'fullName'
		information = data.get ( 'information' )  # Match client’s 'information'
		photo_base64 = data.get ( 'photoBase64' )  # Match client’s 'photoBase64'
		
		if not performer_id or not fullname :
			log.warning ( "Missing required fields: id or fullName" )
			return jsonify ( { "Success" : False , "Error" : "Performer ID and FullName are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            UPDATE "Soundmusicconnect".performers
            SET fullname = %s, information = %s, "Photo" = decode(%s, 'base64')
            WHERE id = %s
            ''' ,
			(fullname , information , photo_base64 , performer_id)
			)
		if cur.rowcount == 0 :
			log.warning ( f"No performer found with id {performer_id}" )
			return jsonify ( { "Success" : False , "Error" : "Performer not found" } ) , 404
		
		conn.commit ( )
		log.info ( f"Performer with id {performer_id} updated successfully" )
		return jsonify ( { "Success" : True } ) , 200
	
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error updating performer: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/delete_performer' , methods = [ 'POST' ] )
def delete_performer ( ) :
	conn = None
	try :
		data = request.get_json ( )
		performer_id = data.get ( 'performerId' )
		
		if not performer_id :
			return jsonify ( { "Success" : False , "Error" : "Performer ID is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		cur.execute ( 'DELETE FROM "Soundmusicconnect".performers WHERE id = %s' , (performer_id ,) )
		conn.commit ( )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error deleting performer: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/create_performer' , methods = [ 'POST' ] )
def create_performer ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		fullname = data.get ( 'fullName' )
		information = data.get ( 'information' )
		photo_base64 = data.get ( 'photoBase64' )  # Base64 string
		
		if not fullname :
			log.warning ( "fullname is missing or empty in request" )
			return jsonify ( { "Success" : False , "Error" : "fullname is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		# Decode Base64 string to bytes if photo is provided
		photo_bytes = base64.b64decode ( photo_base64 ) if photo_base64 else None
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            INSERT INTO "Soundmusicconnect".performers (fullname, information, "Photo")
            VALUES (%s, %s, %s)
            ''' ,
			(fullname , information , psycopg2.Binary ( photo_bytes ) if photo_bytes else None)  # Wrap bytes in Binary
			)
		conn.commit ( )
		log.info ( f"Performer '{fullname}' created successfully" )
		return jsonify ( { "Success" : True } ) , 201
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error creating performer: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/genreslist' , methods = [ 'GET' ] )
def genreslist ( ) :
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "genres_data" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT idgenr, "name", phototrack
            FROM "Soundmusicconnect".genres;
            '''
			)
		rows = cur.fetchall ( )
		
		genre_data = [ ]
		for row in rows :
			image_b64 = base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None
			genre_item = {
				'Id' : row [ 0 ] ,
				'Name' : row [ 1 ] ,
				'PhotoBase64' : image_b64
				}
			genre_data.append ( genre_item )
		
		return jsonify ( { "genres_data" : genre_data , "error" : None } ) , 200
	except Exception as e :
		log.error ( f"Database error: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" , "genres_data" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


# Create a new genre
@app.route ( '/create_genre' , methods = [ 'POST' ] )
def create_genre ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		name = data.get ( 'name' )
		photo_base64 = data.get ( 'photoBase64' )
		
		if not name :
			log.warning ( "name is missing or empty in request" )
			return jsonify ( { "Success" : False , "Error" : "name is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		photo_bytes = base64.b64decode ( photo_base64 ) if photo_base64 else None
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            INSERT INTO "Soundmusicconnect".genres ("name", phototrack)
            VALUES (%s, %s)
            ''' ,
			(name , psycopg2.Binary ( photo_bytes ) if photo_bytes else None)
			)
		conn.commit ( )
		log.info ( f"Genre '{name}' created successfully" )
		return jsonify ( { "Success" : True } ) , 201
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error creating genre: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


# Update an existing genre
@app.route ( '/update_genre' , methods = [ 'POST' ] )
def update_genre ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		genre_id = data.get ( 'id' )
		name = data.get ( 'name' )
		photo_base64 = data.get ( 'photoBase64' )
		
		if not genre_id or not name :
			log.warning ( "Missing required fields: id or name" )
			return jsonify ( { "Success" : False , "Error" : "Genre ID and Name are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		photo_bytes = base64.b64decode ( photo_base64 ) if photo_base64 else None
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            UPDATE "Soundmusicconnect".genres
            SET "name" = %s, phototrack = %s
            WHERE idgenr = %s
            ''' ,
			(name , psycopg2.Binary ( photo_bytes ) if photo_bytes else None , genre_id)
			)
		if cur.rowcount == 0 :
			log.warning ( f"No genre found with id {genre_id}" )
			return jsonify ( { "Success" : False , "Error" : "Genre not found" } ) , 404
		
		conn.commit ( )
		log.info ( f"Genre with id {genre_id} updated successfully" )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error updating genre: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


# Delete a genre
@app.route ( '/delete_genre' , methods = [ 'POST' ] )
def delete_genre ( ) :
	conn = None
	try :
		data = request.get_json ( )
		genre_id = data.get ( 'genreId' )
		
		if not genre_id :
			return jsonify ( { "Success" : False , "Error" : "Genre ID is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'DELETE FROM "Soundmusicconnect".genres WHERE idgenr = %s' ,
			(genre_id ,)
			)
		if cur.rowcount == 0 :
			log.warning ( f"No genre found with id {genre_id}" )
			return jsonify ( { "Success" : False , "Error" : "Genre not found" } ) , 404
		
		conn.commit ( )
		log.info ( f"Genre with id {genre_id} deleted successfully" )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error deleting genre: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


# Add these endpoints to your Flask app after existing ones

@app.route ( '/albums_list' , methods = [ 'GET' ] )
def albums_list ( ) :
	conn = None
	try :
		login = request.args.get ( 'login' )
		if not login :
			return jsonify ( { "error" : "Login parameter is required" , "albums" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database" , "albums" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT a.idalbum, a.albumname, a.yearrelease, p.fullname, a.imagealbum,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_albums fa
                       WHERE fa.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fa.album_id = a.idalbum
                   ) AS is_favorite
            FROM "Soundmusicconnect".albums a
            JOIN "Soundmusicconnect".performers p ON a.performer_id = p.id
            ''' , (login ,)
			)
		rows = cur.fetchall ( )
		albums = [
			{
				"id" : row [ 0 ] ,
				"albumName" : row [ 1 ] ,
				"yearRelease" : row [ 2 ].isoformat ( ) ,
				"performerName" : row [ 3 ] ,
				"imageBase64" : base64.b64encode ( row [ 4 ] ).decode ( 'utf-8' ) if row [ 4 ] else None ,
				"isFavorite" : row [ 5 ]
				}
			for row in rows
			]
		return jsonify ( { "albums" : albums , "error" : None } ) , 200
	except Exception as e :
		log.error ( f"Error fetching albums: {e}" )
		return jsonify ( { "error" : str ( e ) , "albums" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/get_playlist_carousel' , methods = [ 'GET' ] )
def get_playlist_carousel ( ) :
	conn = None
	try :
		log.info ( "Entering /get_playlist_carousel endpoint..." )
		user_login = request.args.get ( 'login' )
		if not user_login :
			log.warning ( "Error: Login parameter is required." )
			return jsonify ( { "error" : "Login parameter is required" , "playlists" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "playlists" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute ( 'SELECT id FROM "Soundmusicconnect".users WHERE login = %s' , (user_login ,) )
		user_result = cur.fetchone ( )
		if not user_result :
			log.warning ( f"User not found for login: {user_login}" )
			return jsonify ( { "error" : "User not found" , "playlists" : [ ] } ) , 404
		user_id = user_result [ 0 ]
		
		# Fetch all playlists created by or favorited by the user
		cur.execute (
			'''
            SELECT p.idplay, p.nameplay, p.image, p.madeinuser
            FROM "Soundmusicconnect".playlists p
            LEFT JOIN "Soundmusicconnect".favorite_playlists fp ON p.idplay = fp.playlist_id AND fp.user_id = %s
            WHERE p.madeinuser = %s OR fp.user_id IS NOT NULL
            ORDER BY p.idplay
            ''' , (user_id , user_id)
			)
		playlists = cur.fetchall ( )
		
		if not playlists :
			log.info ( f"No playlists found for user {user_login}" )
			return jsonify ( { "playlists" : [ ] , "error" : None } ) , 200
		
		playlist_data = [ ]
		for row in playlists :
			image_base64 = base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' ) if row [ 2 ] else None
			playlist_item = {
				"idplay" : row [ 0 ] ,
				"nameplay" : row [ 1 ] ,
				"imageBase64" : image_base64 ,
				"madeinuser" : row [ 3 ]
				}
			playlist_data.append ( playlist_item )
		
		return jsonify ( { "playlists" : playlist_data , "error" : None } ) , 200
	
	except Exception as e :
		log.error ( f"An unexpected error occurred in /get_playlist_carousel endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal Server Error" , "playlists" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/album_tracks' , methods = [ 'POST' ] )
def album_tracks ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_id = data.get ( 'albumId' )
		login = data.get ( 'login' )
		
		if not album_id :
			return jsonify ( { "error" : "Album ID is required" , "tracks" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database" , "tracks" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performer_name, s.imagesong,
                   s.yearcreate, s.duration,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
                       WHERE fs.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fs.song_id = s.idtrack
                   ) AS is_favorite
            FROM "Soundmusicconnect".songs s
            JOIN "Soundmusicconnect".album_songs als ON s.idtrack = als.song_id
            LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
            LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
            WHERE als.album_id = %s
            GROUP BY s.idtrack, s.songname, s.imagesong, s.yearcreate, s.duration
            ''' , (login , album_id)
			)
		tracks = [
			{
				"id" : row [ 0 ] ,
				"songName" : row [ 1 ] ,
				"performerName" : row [ 2 ] or "Unknown Artist" ,
				"imageBase64" : base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None ,
				"yearCreate" : str ( row [ 4 ] ) if row [ 4 ] is not None else None ,  # Convert integer to string
				"duration" : row [ 5 ] ,
				"isFavorite" : row [ 6 ]
				}
			for row in cur.fetchall ( )
			]
		return jsonify ( { "tracks" : tracks , "error" : None } ) , 200
	except Exception as e :
		log.error ( f"Error fetching album tracks: {e}" )
		return jsonify ( { "error" : str ( e ) , "tracks" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/create_album' , methods = [ 'POST' ] )
def create_album ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_name = data.get ( 'albumName' )
		performer_id = data.get ( 'performerId' )
		year_release = data.get ( 'yearRelease' )
		image_base64 = data.get ( 'imageBase64' )
		
		if not all ( [ album_name , performer_id , year_release ] ) :
			return jsonify (
				{ "Success" : False , "Error" : "Album name, performer ID, and year release are required" }
				) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		image_bytes = base64.b64decode ( image_base64 ) if image_base64 else None
		cur.execute (
			'''
            INSERT INTO "Soundmusicconnect".albums (albumname, performer_id, yearrelease, imagealbum)
            VALUES (%s, %s, %s, %s) RETURNING idalbum
            ''' ,
			(album_name , performer_id , year_release , psycopg2.Binary ( image_bytes ) if image_bytes else None)
			)
		album_id = cur.fetchone ( ) [ 0 ]
		conn.commit ( )
		return jsonify ( { "Success" : True , "AlbumId" : album_id } ) , 201
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error creating album: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/update_album' , methods = [ 'POST' ] )
def update_album ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_id = data.get ( 'albumId' )
		album_name = data.get ( 'albumName' )
		year_release = data.get ( 'yearRelease' )  # Matches client request
		image_base64 = data.get ( 'imageBase64' )
		
		if not album_id or not album_name :
			return jsonify ( { "Success" : False , "Error" : "Album ID and name are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		image_bytes = base64.b64decode ( image_base64 ) if image_base64 else None
		cur.execute (
			'''
            UPDATE "Soundmusicconnect".albums
            SET albumname = %s, yearrelease = %s, imagealbum = %s
            WHERE idalbum = %s
            ''' ,
			(album_name , year_release , psycopg2.Binary ( image_bytes ) if image_bytes else None , album_id)
			)
		if cur.rowcount == 0 :
			return jsonify ( { "Success" : False , "Error" : "Album not found" } ) , 404
		conn.commit ( )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error updating album: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/delete_album' , methods = [ 'POST' ] )
def delete_album ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_id = data.get ( 'albumId' )
		
		if not album_id :
			return jsonify ( { "Success" : False , "Error" : "Album ID is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		cur.execute ( 'DELETE FROM "Soundmusicconnect".albums WHERE idalbum = %s' , (album_id ,) )
		if cur.rowcount == 0 :
			return jsonify ( { "Success" : False , "Error" : "Album not found" } ) , 404
		conn.commit ( )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error deleting album: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/add_track_to_album' , methods = [ 'POST' ] )
def add_track_to_album ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_id = data.get ( 'albumId' )
		song_id = data.get ( 'songId' )
		
		if not album_id or not song_id :
			return jsonify ( { "Success" : False , "Error" : "Album ID and Song ID are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            INSERT INTO "Soundmusicconnect".album_songs (album_id, song_id)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
            ''' ,
			(album_id , song_id)
			)
		conn.commit ( )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error adding track to album: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/remove_track_from_album' , methods = [ 'POST' ] )
def remove_track_from_album ( ) :
	conn = None
	try :
		data = request.get_json ( )
		album_id = data.get ( 'albumId' )
		song_id = data.get ( 'songId' )
		
		if not album_id or not song_id :
			return jsonify ( { "Success" : False , "Error" : "Album ID and Song ID are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            DELETE FROM "Soundmusicconnect".album_songs
            WHERE album_id = %s AND song_id = %s
            ''' ,
			(album_id , song_id)
			)
		if cur.rowcount == 0 :
			return jsonify ( { "Success" : False , "Error" : "Track not found in album" } ) , 404
		conn.commit ( )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error removing track from album: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


# Already implemented /search enhanced for albums
@app.route ( '/performer_tracks' , methods = [ 'POST' ] )
def get_performer_tracks ( ) :
	conn = None
	try :
		data = request.get_json ( )
		performer_id = data.get ( 'performerId' )
		login = data.get ( 'login' )
		
		if not performer_id :
			return jsonify ( { "error" : "Performer ID is required" , "tracks" : [ ] } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database" , "tracks" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
            SELECT s.idtrack, s.songname, STRING_AGG(p.fullname, ', ') AS performer_name, s.imagesong,
                   s.yearcreate, s.duration,
                   EXISTS (
                       SELECT 1 FROM "Soundmusicconnect".favorite_songs fs
                       WHERE fs.user_id = (SELECT id FROM "Soundmusicconnect".users WHERE login = %s)
                       AND fs.song_id = s.idtrack
                   ) AS is_favorite
            FROM "Soundmusicconnect".songs s
            LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
            LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
            WHERE sp.performer_id = %s
            GROUP BY s.idtrack, s.songname, s.imagesong, s.yearcreate, s.duration
            ''' , (login , performer_id)
			)
		tracks = [
			{
				"id" : row [ 0 ] ,
				"songName" : row [ 1 ] ,
				"performerName" : row [ 2 ] or "Unknown Artist" ,
				"imageBase64" : base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None ,
				"yearCreate" : row [ 4 ].isoformat ( ) ,
				"duration" : row [ 5 ] ,
				"isFavorite" : row [ 6 ]
				}
			for row in cur.fetchall ( )
			]
		return jsonify ( { "tracks" : tracks , "error" : None } ) , 200
	except Exception as e :
		log.error ( f"Error fetching performer tracks: {e}" )
		return jsonify ( { "error" : str ( e ) , "tracks" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


# List all tracks
@app.route ( '/trackslist' , methods = [ 'GET' ] )
def trackslist ( ) :
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "tracks_data" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
			SELECT s.idtrack, s.songname, s.yearcreate, g.name AS genre_name,
				   STRING_AGG(p.fullname, ', ') AS performer_name, s.imagesong, s.filepath, s.duration
			FROM "Soundmusicconnect".songs s
			LEFT JOIN "Soundmusicconnect".genres g ON s.genre_id = g.idgenr
			LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
			LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
			GROUP BY s.idtrack, s.songname, s.yearcreate, g.name, s.imagesong, s.filepath, s.duration;
			'''
			)
		rows = cur.fetchall ( )
		
		tracks_data = [ ]
		for row in rows :
			image_b64 = base64.b64encode ( row [ 5 ] ).decode ( 'utf-8' ) if row [ 5 ] else None
			# Handle yearcreate based on its type
			year_create = row [ 2 ]
			if isinstance ( year_create , int ) :
				year_create_str = str ( year_create )  # Convert int to string (e.g., "2023")
			elif hasattr ( year_create , 'isoformat' ) :
				year_create_str = year_create.isoformat ( )  # Use isoformat for date objects
			else :
				year_create_str = None  # Fallback for unexpected types
			
			track_item = {
				'Id' : row [ 0 ] ,
				'SongName' : row [ 1 ] ,
				'YearCreate' : year_create_str ,
				'GenreName' : row [ 3 ] ,
				'PerformerName' : row [ 4 ] or "Unknown Artist" ,
				'ImageBase64' : image_b64 ,
				'FilePath' : row [ 6 ] ,
				'Duration' : row [ 7 ]
				}
			tracks_data.append ( track_item )
		
		return jsonify ( { "tracks_data" : tracks_data , "error" : None } ) , 200
	except Exception as e :
		log.error ( f"Database error: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" , "tracks_data" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/create_track' , methods = [ 'POST' ] )
def create_track ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		songname = data.get ( 'songName' )
		yearcreate = data.get ( 'yearCreate' )
		genre_id = data.get ( 'genreId' )
		performer_ids = data.get ( 'performerIds' )
		image_base64 = data.get ( 'imageBase64' )
		filepath = data.get ( 'filePath' )
		duration = data.get ( 'duration' )
		
		if not songname or not yearcreate or not filepath :
			log.warning ( "Missing required fields: songName, yearCreate, or filePath" )
			return jsonify (
				{ "Success" : False , "Error" : "Song name, year created, and file content are required" }
				) , 400
		
		# Validate yearcreate as an integer
		try :
			year = int ( yearcreate )
			if year < 1900 or year > 2100 :
				raise ValueError ( "Year must be between 1900 and 2100" )
		except ValueError as ve :
			log.error ( f"Invalid year format: {ve}" )
			return jsonify (
				{ "Success" : False , "Error" : "Year must be a valid number between 1900 and 2100" }
				) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		image_bytes = base64.b64decode ( image_base64 ) if image_base64 else None
		
		# Handle audio file
		try :
			audio_bytes = base64.b64decode ( filepath )
			file_extension = '.mp3'
			filename = f"{uuid.uuid4 ( )}{file_extension}"
			file_path = os.path.join ( music_dir_path , filename )
			with open ( file_path , 'wb' ) as f :
				f.write ( audio_bytes )
			filepath_to_store = filename
		except Exception as e :
			log.error ( f"Error processing audio file: {e}" )
			return jsonify ( { "Success" : False , "Error" : f"Invalid audio file data: {str ( e )}" } ) , 400
		
		cur = conn.cursor ( )
		# Use year directly as an integer
		cur.execute (
			'''
            INSERT INTO "Soundmusicconnect".songs (songname, yearcreate, genre_id, imagesong, filepath, duration)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING idtrack
            ''' ,
			(songname , year , genre_id , psycopg2.Binary ( image_bytes ) if image_bytes else None ,
			 filepath_to_store , duration or '00:00')
			)
		track_id = cur.fetchone ( ) [ 0 ]
		
		# Link performers
		if performer_ids and isinstance ( performer_ids , list ) :
			for performer_id in performer_ids :
				cur.execute (
					'''
                    INSERT INTO "Soundmusicconnect".song_performers (song_id, performer_id)
                    VALUES (%s, %s)
                    ''' ,
					(track_id , performer_id)
					)
		
		conn.commit ( )
		log.info ( f"Track '{songname}' created successfully with ID {track_id}" )
		return jsonify ( { "Success" : True , "TrackId" : track_id } ) , 201
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error creating track: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/update_track' , methods = [ 'POST' ] )
def update_track ( ) :
	conn = None
	try :
		data = request.get_json ( )
		log.debug ( f"Received data: {data}" )
		track_id = data.get ( 'id' )
		songname = data.get ( 'songName' )
		yearcreate = data.get ( 'yearCreate' )
		genre_id = data.get ( 'genreId' )
		performer_ids = data.get ( 'performerIds' )
		image_base64 = data.get ( 'imageBase64' )
		filepath = data.get ( 'filePath' )  # Base64-encoded audio (optional)
		duration = data.get ( 'duration' )
		
		if not track_id or not songname :
			log.warning ( "Missing required fields: id or songName" )
			return jsonify ( { "Success" : False , "Error" : "Track ID and Song Name are required" } ) , 400
		
		# Validate and format yearcreate
		try :
			yearcreate_formatted = None
			if '-' in yearcreate :
				date_obj = datetime.strptime ( yearcreate , '%Y-%m-%d' )
				yearcreate_formatted = date_obj.date ( ).isoformat ( )
				year = date_obj.year
				if year < 1900 or year > 2100 :
					raise ValueError ( "Year must be between 1900 and 2100" )
			else :
				year = int ( yearcreate )
				if year < 1900 or year > 2100 :
					raise ValueError ( "Year must be between 1900 and 2100" )
				yearcreate_formatted = f"{year}-01-01"
		except ValueError as ve :
			log.error ( f"Invalid year or date format: {ve}" )
			return jsonify (
				{
					"Success" : False ,
					"Error" : "Year must be a valid number between 1900 and 2100 or date (YYYY-MM-DD)"
					}
				) , 400
		
		conn = get_db_connection ( )
		if not conn :
			log.error ( "Failed to connect to the database" )
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		image_bytes = base64.b64decode ( image_base64 ) if image_base64 else None
		
		# Handle audio file update
		filepath_to_store = None
		cur = conn.cursor ( )
		
		# Get the existing filepath to delete it if a new file is provided
		cur.execute ( 'SELECT filepath FROM "Soundmusicconnect".songs WHERE idtrack = %s' , (track_id ,) )
		existing_filepath_result = cur.fetchone ( )
		if not existing_filepath_result :
			log.error ( f"No track found with id {track_id}" )
			return jsonify ( { "Success" : False , "Error" : "Track not found" } ) , 404
		existing_filepath = existing_filepath_result [ 0 ]
		
		if filepath :  # New audio file provided
			try :
				audio_bytes = base64.b64decode ( filepath )
				file_extension = '.mp3'  # Default; adjust if needed
				filename = f"{uuid.uuid4 ( )}{file_extension}"
				file_path = os.path.join ( music_dir_path , filename )
				
				# Save the new audio file
				with open ( file_path , 'wb' ) as f :
					f.write ( audio_bytes )
				
				filepath_to_store = filename
				
				# Delete the old audio file if it exists
				if existing_filepath :
					old_file_path = os.path.join ( music_dir_path , existing_filepath )
					if os.path.exists ( old_file_path ) :
						os.remove ( old_file_path )
						log.info ( f"Deleted old audio file: {old_file_path}" )
					else :
						log.warning ( f"Old audio file not found on server: {old_file_path}" )
			except Exception as e :
				log.error ( f"Error processing audio file: {e}" )
				return jsonify ( { "Success" : False , "Error" : f"Invalid audio file data: {str ( e )}" } ) , 400
		else :
			# Keep existing filepath if no new file is provided
			filepath_to_store = existing_filepath
		
		# Update the track
		cur.execute (
			'''
			UPDATE "Soundmusicconnect".songs
			SET songname = %s, yearcreate = %s, genre_id = %s, imagesong = %s, filepath = %s, duration = %s
			WHERE idtrack = %s
			''' ,
			(songname , yearcreate_formatted , genre_id , psycopg2.Binary ( image_bytes ) if image_bytes else None ,
			 filepath_to_store , duration or '00:00' , track_id)
			)
		if cur.rowcount == 0 :
			log.warning ( f"No track found with id {track_id}" )
			return jsonify ( { "Success" : False , "Error" : "Track not found" } ) , 404
		
		# Update performers
		cur.execute ( 'DELETE FROM "Soundmusicconnect".song_performers WHERE song_id = %s' , (track_id ,) )
		if performer_ids and isinstance ( performer_ids , list ) :
			for performer_id in performer_ids :
				cur.execute (
					'''
					INSERT INTO "Soundmusicconnect".song_performers (song_id, performer_id)
					VALUES (%s, %s)
					''' ,
					(track_id , performer_id)
					)
		
		conn.commit ( )
		log.info ( f"Track with id {track_id} updated successfully" )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error updating track: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


# Delete a track
@app.route ( '/delete_track' , methods = [ 'POST' ] )
def delete_track ( ) :
	conn = None
	try :
		data = request.get_json ( )
		track_id = data.get ( 'trackId' )
		
		if not track_id :
			return jsonify ( { "Success" : False , "Error" : "Track ID is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "Success" : False , "Error" : "Failed to connect to the database" } ) , 500
		
		cur = conn.cursor ( )
		
		# Get the filepath to delete the audio file
		cur.execute ( 'SELECT filepath FROM "Soundmusicconnect".songs WHERE idtrack = %s' , (track_id ,) )
		filepath_result = cur.fetchone ( )
		if not filepath_result :
			log.warning ( f"No track found with id {track_id}" )
			return jsonify ( { "Success" : False , "Error" : "Track not found" } ) , 404
		filepath = filepath_result [ 0 ]
		
		# Delete related records in listening_history first
		cur.execute ( 'DELETE FROM "Soundmusicconnect".listening_history WHERE song_id = %s' , (track_id ,) )
		
		# Delete related records in favorite_songs
		cur.execute ( 'DELETE FROM "Soundmusicconnect".favorite_songs WHERE song_id = %s' , (track_id ,) )
		
		# Delete related records in user_songs
		cur.execute ( 'DELETE FROM "Soundmusicconnect".user_songs WHERE song_id = %s' , (track_id ,) )
		
		# Delete related records in playlist_songs
		cur.execute ( 'DELETE FROM "Soundmusicconnect".playlist_songs WHERE song_id = %s' , (track_id ,) )
		
		# Delete the song from the songs table
		cur.execute ( 'DELETE FROM "Soundmusicconnect".songs WHERE idtrack = %s' , (track_id ,) )
		
		if cur.rowcount == 0 :
			log.warning ( f"No track found with id {track_id}" )
			return jsonify ( { "Success" : False , "Error" : "Track not found" } ) , 404
		
		# Delete the audio file from musicfile folder
		if filepath :
			file_path = os.path.join ( music_dir_path , filepath )
			if os.path.exists ( file_path ) :
				os.remove ( file_path )
				log.info ( f"Deleted audio file: {file_path}" )
			else :
				log.warning ( f"Audio file not found on server: {file_path}" )
		
		conn.commit ( )
		log.info ( f"Track with id {track_id} and related records deleted successfully" )
		return jsonify ( { "Success" : True } ) , 200
	except Exception as e :
		if conn :
			conn.rollback ( )
		log.error ( f"Error deleting track: {e}" )
		return jsonify ( { "Success" : False , "Error" : str ( e ) } ) , 500
	finally :
		if conn :
			conn.close ( )


# Update the existing /performerslist endpoint to include information
@app.route ( '/performerslist' , methods = [ 'GET' ] )
def performerslist ( ) :
	conn = None
	try :
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." , "perfomers_data" : [ ] } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			'''
			SELECT id, fullname, information, "Photo"
			FROM "Soundmusicconnect".performers;
			'''
			)
		rows = cur.fetchall ( )
		
		performer_data = [ ]
		for row in rows :
			image_b64 = base64.b64encode ( row [ 3 ] ).decode ( 'utf-8' ) if row [ 3 ] else None
			performer_item = {
				'Id' : str ( row [ 0 ] ) ,
				'FullName' : row [ 1 ] ,
				'information' : row [ 2 ] ,
				'PhotoBase64' : image_b64
				}
			performer_data.append ( performer_item )
		
		return jsonify ( { "perfomers_data" : performer_data , "error" : None } ) , 200
	except Exception as e :
		log.error ( f"Database error: {e}" )
		return jsonify ( { "error" : f"Database error: {e}" , "perfomers_data" : [ ] } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/change_password' , methods = [ 'POST' ] )
def change_password2 ( ) :
	conn = None
	try :
		log.info ( "Entering /change_password endpoint..." )
		data = request.get_json ( )
		log.debug ( f"Received {data}" )
		
		stored_login = data.get ( 'login' )
		new_password = data.get ( 'password' )
		
		if not stored_login or not new_password :
			log.warning ( "Error: Login and new password are required." )
			return jsonify ( { "error" : "Login and new password are required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		
		# 1. Получаем хэш старого пароля пользователя
		cur.execute ( 'SELECT password FROM "Soundmusicconnect"."users" WHERE login = %s;' , (stored_login ,) )
		user = cur.fetchone ( )
		
		if not user :
			log.warning ( f"User with login {stored_login} not found." )
			return jsonify ( { "error" : "User not found" } ) , 404
		
		stored_password_hash = user [ 0 ]
		
		log.debug ( f"User found, old password hash retrieved. User: {stored_login}" )
		
		# 2. Проверяем, что новый пароль не совпадает со старым (в незахэшированном виде),
		#    а затем хэшируем новый пароль
		if bcrypt.checkpw ( new_password.encode ( 'utf-8' ) , stored_password_hash.encode ( 'utf-8' ) ) :
			log.warning ( f"New password is the same as the old password for user: {stored_login}" )
			return jsonify ( { "error" : "New password cannot be the same as the old password." } ) , 400
		
		# Хэшируем новый пароль
		hashed_new_password = bcrypt.hashpw ( new_password.encode ( 'utf-8' ) , bcrypt.gensalt ( ) ).decode ( 'utf-8' )
		
		# 3. Обновляем пароль пользователя
		cur.execute (
			'UPDATE "Soundmusicconnect"."users" SET password = %s WHERE login = %s;' ,
			(hashed_new_password , stored_login)
			)
		
		conn.commit ( )
		log.info ( f"Password for user {stored_login} updated successfully." )
		return jsonify ( { "success" : "Password changed successfully" } ) , 200
	
	except Exception as e :
		log.error ( f"An unexpected error occurred in /change_password endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Internal Server Error" } ) , 500
	finally :
		if conn :
			conn.close ( )


@app.route ( '/likeusermusicandplayulist' , methods = [ 'GET' ] )
def likeusermusicandplaylist ( ) :
	conn = None
	try :
		log.info ( "Entering /likeusermusicandplaylist endpoint..." )
		usersid = request.args.get ( 'usersid' )
		if not usersid :
			log.warning ( "Error: Usersid is required." )
			return jsonify ( { "error" : "Usersid is required" } ) , 400
		
		conn = get_db_connection ( )
		if not conn :
			return jsonify ( { "error" : "Failed to connect to the database." } ) , 500
		
		cur = conn.cursor ( )
		cur.execute (
			"""
			SELECT s.imagesong AS song_image, s.songname AS song_name, g."name" AS genre_name,
				   STRING_AGG(p.fullname, ', ') AS performer_name,
				   EXTRACT(YEAR FROM s.yearcreate) AS song_year
			FROM "Soundmusicconnect".user_songs us
			JOIN "Soundmusicconnect".songs s ON us.song_id = s.idtrack
			JOIN "Soundmusicconnect".genres g ON s.genre_id = g.idgenr
			LEFT JOIN "Soundmusicconnect".song_performers sp ON s.idtrack = sp.song_id
			LEFT JOIN "Soundmusicconnect".performers p ON sp.performer_id = p.id
			WHERE us.user_id = %s
			GROUP BY s.imagesong, s.songname, g."name", s.yearcreate;
			""" , (usersid ,)
			)
		
		rows = cur.fetchall ( )
		results = [ ]
		for row in rows :
			song_image , song_name , genre_name , performer_name , song_year = row
			encoded_image = encode_image_to_base64 ( song_image )
			results.append (
				{
					"song_image" : encoded_image ,
					"song_name" : song_name ,
					"genre_name" : genre_name ,
					"performer_name" : performer_name or "Unknown Artist" ,
					"song_year" : song_year
					}
				)
		
		cur.execute (
			"""
			SELECT id, fullname, photo FROM "Soundmusicconnect".performers;
			"""
			)
		
		rows = cur.fetchall ( )
		performer_data = [ ]
		for row in rows :
			try :
				image_b64 = ""
				if row [ 2 ] is not None :
					print ( f"Encoding imagedata for performerid: {row [ 0 ]}" )
					image_b64 = base64.b64encode ( row [ 2 ] ).decode ( 'utf-8' )
					print ( f"Encoded base64 data for image: {image_b64 [ :50 ]}...(showing first 50 chars)" )
				else :
					image_b64 = None
					print ( f"No image data for performerid: {row [ 0 ]}" )
			except Exception as base64_error :
				print ( f"Error during base64 encoding for performerid {row [ 0 ]}: {base64_error}" )
				image_b64 = None
			
			performer_item = {
				'Id' : row [ 0 ] ,
				'FullName' : row [ 1 ] ,
				'PhotoBase64' : image_b64 if image_b64 is not None else ""
				}
			print ( f"Processed performer item: {performer_item}" )
			performer_data.append ( performer_item )
		
		log.info ( "Successfully retrieved liked songs and performers." )
		return jsonify ( { "liked_songs" : results , "performers" : performer_data } ) , 200
	
	except Exception as e :
		log.error ( f"An unexpected error occurred in /likeusermusicandplaylist endpoint: {str ( e )}" )
		log.error ( traceback.format_exc ( ) )
		return jsonify ( { "error" : "Error retrieving user songs" } ) , 500
	finally :
		if conn :
			conn.close ( )


def encode_image_to_base64 ( image_data ) :
	if image_data :
		try :
			encoded_image = base64.b64encode ( image_data ).decode ( 'utf-8' )
			return encoded_image
		except Exception as e :
			log.error ( f"Error during image encoding: {e}" )
			return None
	else :
		return None


if __name__ == '__main__' :
	print ( "Starting Flask server..." )
	app.run ( debug = True , host = '0.0.0.0' , port = 5000 )