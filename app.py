from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, flash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import yt_dlp
import os
from werkzeug.utils import secure_filename
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
CORS(app)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# TMDB API Configuration
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_ACCESS_TOKEN = os.getenv('TMDB_ACCESS_TOKEN')

if not TMDB_API_KEY or not TMDB_ACCESS_TOKEN:
    raise ValueError("TMDB_API_KEY and TMDB_ACCESS_TOKEN must be set in .env file")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"
TMDB_HEADERS = {
    'Authorization': f'Bearer {TMDB_ACCESS_TOKEN}',
    'Content-Type': 'application/json;charset=utf-8'
}

# Configure download directory
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Base URL for movie scraping (using a public domain movies website)
BASE_URL = "https://archive.org/details/movies"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    downloads = db.relationship('Download', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='completed')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_movie_details(movie_id):
    try:
        # Get movie details
        url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        params = {
            'append_to_response': 'videos,watch/providers',
            'language': 'en-US'
        }
        headers = {
            'Authorization': f'Bearer {TMDB_ACCESS_TOKEN}',
            'accept': 'application/json'
        }
        
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        movie_data = response.json()
        
        # Get watch providers
        providers_data = movie_data.get('watch/providers', {}).get('results', {}).get('US', {})
        streaming = providers_data.get('flatrate', [])
        rent = providers_data.get('rent', [])
        buy = providers_data.get('buy', [])
        
        # Format provider data
        all_providers = []
        if streaming:
            all_providers.extend([{'name': p['provider_name'], 'type': 'stream'} for p in streaming])
        if rent:
            all_providers.extend([{'name': p['provider_name'], 'type': 'rent'} for p in rent])
        if buy:
            all_providers.extend([{'name': p['provider_name'], 'type': 'buy'} for p in buy])
        
        # Get trailer
        trailers = []
        if 'videos' in movie_data and movie_data['videos']['results']:
            for video in movie_data['videos']['results']:
                if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                    trailers.append({
                        'name': video['name'],
                        'key': video['key'],
                        'site': video['site']
                    })
        
        # Format the response
        formatted_data = {
            'id': movie_data['id'],
            'title': movie_data['title'],
            'original_title': movie_data['original_title'],
            'overview': movie_data['overview'],
            'poster_path': f"https://image.tmdb.org/t/p/w500{movie_data['poster_path']}" if movie_data['poster_path'] else None,
            'backdrop_path': f"https://image.tmdb.org/t/p/original{movie_data['backdrop_path']}" if movie_data['backdrop_path'] else None,
            'release_date': movie_data['release_date'],
            'vote_average': movie_data['vote_average'],
            'vote_count': movie_data['vote_count'],
            'runtime': movie_data['runtime'],
            'status': movie_data['status'],
            'tagline': movie_data['tagline'],
            'genres': [genre['name'] for genre in movie_data['genres']],
            'production_companies': [company['name'] for company in movie_data['production_companies']],
            'videos': trailers,
            'providers': all_providers
        }
        
        return formatted_data
    except Exception as e:
        print(f"Error fetching movie details: {str(e)}")
        return None

@app.route('/')
@login_required
def index():
    query = request.args.get('query', '')
    page = request.args.get('page', 1, type=int)
    search_results = search_movies(query, page)
    return render_template('index.html', 
                         movies=search_results['results'], 
                         query=query,
                         current_page=search_results['page'],
                         total_pages=search_results['total_pages'])

@app.route('/search_movies')
def search_movies_route():
    try:
        # Get the authorization token from the request headers
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'No authorization token provided'}), 401

        # Use the token from the request headers
        headers = {
            'Authorization': auth_header,
            'Content-Type': 'application/json;charset=utf-8'
        }

        query = request.args.get('query', '')
        page = request.args.get('page', 1, type=int)
        
        # Determine which endpoint to use
        if query:
            endpoint = f"{TMDB_BASE_URL}/search/movie"
            params = {
                'query': query,
                'page': page,
                'include_adult': False,
                'language': 'en-US'
            }
        else:
            endpoint = f"{TMDB_BASE_URL}/movie/popular"
            params = {
                'page': page,
                'language': 'en-US'
            }
        
        # Make the API request with the token from the request headers
        response = requests.get(endpoint, params=params, headers=headers)
        
        # Check for specific error responses
        if response.status_code == 401:
            print("Authentication failed. Check your API key and token.")
            return jsonify({'error': 'Authentication failed'}), 401
        elif response.status_code == 404:
            print("Resource not found.")
            return jsonify({'error': 'Resource not found'}), 404
        
        # Raise for other status codes
        response.raise_for_status()
        data = response.json()
        
        # Format the movies data
        movies = []
        for movie in data.get('results', []):
            poster_path = movie.get('poster_path')
            backdrop_path = movie.get('backdrop_path')
            
            movies.append({
                'id': movie['id'],
                'title': movie['title'],
                'overview': movie['overview'],
                'poster_path': f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
                'backdrop_path': f"https://image.tmdb.org/t/p/original{backdrop_path}" if backdrop_path else None,
                'release_date': movie.get('release_date'),
                'vote_average': movie.get('vote_average'),
                'vote_count': movie.get('vote_count')
            })
        
        return jsonify({
            'results': movies,
            'page': data.get('page', 1),
            'total_pages': data.get('total_pages', 1),
            'total_results': data.get('total_results', 0)
        })
        
    except requests.exceptions.RequestException as e:
        print(f"TMDB API error: {str(e)}")
        return jsonify({'error': 'Failed to fetch movies from TMDB'}), 500
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/movie/<movie_id>')
def movie_details(movie_id):
    try:
        movie_data = get_movie_details(movie_id)
        if movie_data:
            return jsonify(movie_data)
        return jsonify({'error': 'Movie not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_movie/<movie_id>', methods=['POST'])
@login_required
def download_movie(movie_id):
    try:
        # Get movie details from TMDB
        movie_details = get_movie_details(movie_id)
        if not movie_details:
            return jsonify({'status': 'error', 'message': 'Movie not found'}), 404

        # Check if movie has streaming providers
        if not movie_details.get('providers'):
            return jsonify({'status': 'error', 'message': 'No streaming providers available for this movie'}), 400

        # Get provider URLs and information
        providers = movie_details['providers']
        provider_info = []
        for provider in providers:
            provider_info.append({
                'name': provider['name'],
                'type': provider['type']
            })

        # Record the request in database
        download = Download(
            user_id=current_user.id,
            movie_title=movie_details['title'],
            status='pending'
        )
        db.session.add(download)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Movie information retrieved',
            'movie': {
                'title': movie_details['title'],
                'providers': provider_info,
                'release_date': movie_details['release_date'],
                'overview': movie_details['overview']
            }
        })

    except Exception as e:
        print(f"Error in download_movie: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('signup'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('signup'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Redirect if user is already logged in
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/download', methods=['POST'])
@login_required
def download_video():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Configure yt-dlp options
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }

        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        return jsonify({
            'success': True,
            'message': 'Download completed',
            'filename': os.path.basename(filename)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    message = None
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Verify current password
        if not current_password or not bcrypt.check_password_hash(current_user.password_hash, current_password):
            error = "Current password is incorrect"
        else:
            # Check if username is taken
            if username != current_user.username and User.query.filter_by(username=username).first():
                error = "Username is already taken"
            # Check if email is taken
            elif email != current_user.email and User.query.filter_by(email=email).first():
                error = "Email is already taken"
            # Check if new password matches confirmation
            elif new_password and new_password != confirm_password:
                error = "New passwords do not match"
            else:
                # Update user information
                current_user.username = username
                current_user.email = email
                if new_password:
                    current_user.set_password(new_password)
                
                db.session.commit()
                message = "Profile updated successfully"

    # Get download history
    download_history = Download.query.filter_by(user_id=current_user.id).order_by(Download.date.desc()).all()
    
    return render_template('profile.html', 
                         username=current_user.username,
                         current_user=current_user,
                         download_history=download_history,
                         message=message,
                         error=error)

def search_movies(query=None, page=1):
    """Search for movies or get popular movies if no query is provided."""
    if query:
        url = f"{TMDB_BASE_URL}/search/movie"
    else:
        url = f"{TMDB_BASE_URL}/movie/popular"
    
    params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'page': page,
        'include_adult': False  # Filter out adult content
    }
    
    if query:
        params['query'] = query
    
    try:
        response = requests.get(url, headers=TMDB_HEADERS)
        if response.status_code == 200:
            data = response.json()
            movies = []
            for movie in data['results']:
                movies.append({
                    'id': movie['id'],
                    'title': movie['title'],
                    'overview': movie['overview'],
                    'poster_path': f"{TMDB_IMAGE_BASE_URL}{movie['poster_path']}" if movie.get('poster_path') else None,
                    'backdrop_path': f"{TMDB_IMAGE_BASE_URL}{movie['backdrop_path']}" if movie.get('backdrop_path') else None,
                    'release_date': movie.get('release_date', 'N/A'),
                    'vote_average': movie.get('vote_average', 0),
                    'vote_count': movie.get('vote_count', 0),
                    'popularity': movie.get('popularity', 0),
                    'original_language': movie.get('original_language'),
                    'genre_ids': movie.get('genre_ids', [])
                })
            return {
                'results': movies,
                'page': data['page'],
                'total_pages': data['total_pages'],
                'total_results': data['total_results']
            }
        elif response.status_code == 401:
            print("Authentication failed. Please check your API key.")
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
        elif response.status_code == 429:
            print("Rate limit exceeded. Please wait before making more requests.")
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
        else:
            print(f"Error searching movies: {response.status_code}")
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
    except Exception as e:
        print(f"Error searching movies: {e}")
        return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}

@app.route('/download_status/<video_id>')
@login_required
def download_status(video_id):
    try:
        # Check if the download exists in the database
        download = Download.query.filter_by(
            user_id=current_user.id
        ).order_by(Download.date.desc()).first()

        if download:
            return jsonify({
                'status': download.status,
                'title': download.movie_title,
                'date': download.date.isoformat()
            })
        return jsonify({'status': 'not_found'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
