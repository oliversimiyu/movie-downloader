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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
CORS(app)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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

class Download(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='completed')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_sample_movies():
    return [
        {
            'id': 'night-of-the-living-dead',
            'title': 'Night of the Living Dead (1968)',
            'overview': 'A classic horror film directed by George A. Romero. A group of people hide from bloodthirsty zombies in a farmhouse.',
            'poster_path': 'https://archive.org/download/night_of_the_living_dead/format=Thumbnail',
            'release_date': '1968',
            'vote_average': 4.5,
            'download_url': 'https://archive.org/details/night_of_the_living_dead'
        },
        {
            'id': 'metropolis',
            'title': 'Metropolis (1927)',
            'overview': 'In a futuristic city sharply divided between the working class and the city planners, the son of the city\'s mastermind falls in love with a working class prophet.',
            'poster_path': 'https://archive.org/download/metropolis1927germanversion/format=Thumbnail',
            'release_date': '1927',
            'vote_average': 4.8,
            'download_url': 'https://archive.org/details/metropolis1927germanversion'
        },
        {
            'id': 'nosferatu',
            'title': 'Nosferatu (1922)',
            'overview': 'Vampire Count Orlok expresses interest in a new residence and real estate agent Hutter\'s wife. Silent horror film by F. W. Murnau.',
            'poster_path': 'https://archive.org/download/Nosferatu_201604/format=Thumbnail',
            'release_date': '1922',
            'vote_average': 4.7,
            'download_url': 'https://archive.org/details/Nosferatu_201604'
        },
        {
            'id': 'the-general',
            'title': 'The General (1926)',
            'overview': 'When Union spies steal an engineer\'s beloved locomotive, he pursues it single-handedly and straight through enemy lines. Starring Buster Keaton.',
            'poster_path': 'https://archive.org/download/TheGeneral_981/format=Thumbnail',
            'release_date': '1926',
            'vote_average': 4.6,
            'download_url': 'https://archive.org/details/TheGeneral_981'
        },
        {
            'id': 'plan-9-from-outer-space',
            'title': 'Plan 9 from Outer Space (1959)',
            'overview': 'Aliens resurrect dead humans as zombies and vampires to stop humanity from creating the Solaranite (a sort of sun-driven bomb).',
            'poster_path': 'https://archive.org/download/Plan9FromOuterSpace_657/format=Thumbnail',
            'release_date': '1959',
            'vote_average': 3.5,
            'download_url': 'https://archive.org/details/Plan9FromOuterSpace_657'
        },
        {
            'id': 'little-shop-of-horrors',
            'title': 'The Little Shop of Horrors (1960)',
            'overview': 'A clumsy young man nurtures a plant and discovers it\'s carnivorous, forcing him to kill to feed it.',
            'poster_path': 'https://archive.org/download/little_shop_of_horrors/format=Thumbnail',
            'release_date': '1960',
            'vote_average': 4.2,
            'download_url': 'https://archive.org/details/little_shop_of_horrors'
        },
        {
            'id': 'his-girl-friday',
            'title': 'His Girl Friday (1940)',
            'overview': 'A newspaper editor uses every trick in the book to keep his ace reporter ex-wife from remarrying.',
            'poster_path': 'https://archive.org/download/his_girl_friday/format=Thumbnail',
            'release_date': '1940',
            'vote_average': 4.6,
            'download_url': 'https://archive.org/details/his_girl_friday'
        },
        {
            'id': 'charade',
            'title': 'Charade (1963)',
            'overview': 'Romance and suspense ensue in Paris as a woman is pursued by several men who want a fortune her murdered husband had stolen. Starring Audrey Hepburn and Cary Grant.',
            'poster_path': 'https://archive.org/download/charade_202006/format=Thumbnail',
            'release_date': '1963',
            'vote_average': 4.7,
            'download_url': 'https://archive.org/details/charade_202006'
        },
        {
            'id': 'carnival-of-souls',
            'title': 'Carnival of Souls (1962)',
            'overview': 'After a traumatic accident, a woman becomes drawn to a mysterious abandoned carnival.',
            'poster_path': 'https://archive.org/download/carnival_of_souls/format=Thumbnail',
            'release_date': '1962',
            'vote_average': 4.3,
            'download_url': 'https://archive.org/details/carnival_of_souls'
        },
        {
            'id': 'the-kid',
            'title': 'The Kid (1921)',
            'overview': 'The Tramp cares for an abandoned child, but events put their relationship in jeopardy. Charlie Chaplin\'s first full-length film.',
            'poster_path': 'https://archive.org/download/the_kid_chaplin/format=Thumbnail',
            'release_date': '1921',
            'vote_average': 4.8,
            'download_url': 'https://archive.org/details/the_kid_chaplin'
        },
        {
            'id': 'the-phantom-of-the-opera',
            'title': 'The Phantom of the Opera (1925)',
            'overview': 'A mad, disfigured composer seeks love with a lovely young opera singer.',
            'poster_path': 'https://archive.org/download/phantom_of_the_opera/format=Thumbnail',
            'release_date': '1925',
            'vote_average': 4.5,
            'download_url': 'https://archive.org/details/phantom_of_the_opera'
        },
        {
            'id': 'dementia-13',
            'title': 'Dementia 13 (1963)',
            'overview': 'A widow deceives her late husband\'s family about his death, but then a series of brutal axe murders begins. Francis Ford Coppola\'s directorial debut.',
            'poster_path': 'https://archive.org/download/dementia_13/format=Thumbnail',
            'release_date': '1963',
            'vote_average': 4.0,
            'download_url': 'https://archive.org/details/dementia_13'
        }
    ]

def scrape_movies(query=None, page=1):
    try:
        if not query:
            # Return sample movies when no search query is provided
            return get_sample_movies()
            
        if query:
            url = f"{BASE_URL}?query={query}&page={page}"
        else:
            # For the initial page load, show movies from the featured section
            url = f"{BASE_URL}/movies?&sort=-downloads"
        
        print(f"Fetching movies from URL: {url}")  # Debug log
        response = requests.get(url, headers=HEADERS)
        print(f"Response status code: {response.status_code}")  # Debug log
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")  # Debug log
            return []
            
        soup = BeautifulSoup(response.text, 'lxml')
        movies = []
        items = soup.select('.C234')  # Updated selector for movie items
        print(f"Found {len(items)} movie items")  # Debug log
        
        for item in items[:20]:
            try:
                title_elem = item.select_one('.tile-title')
                if not title_elem:
                    continue
                    
                title = title_elem.text.strip()
                link = item.select_one('a')
                link_url = link['href'] if link else None
                full_url = urljoin(BASE_URL, link_url) if link_url else None
                
                # Get thumbnail
                thumbnail = item.select_one('img')
                thumbnail_url = thumbnail['src'] if thumbnail and 'src' in thumbnail.attrs else None
                
                # Get description
                description = item.select_one('.tile-description')
                overview = description.text.strip() if description else 'No description available'
                
                # Get year from title or metadata
                year_match = re.search(r'\b(19|20)\d{2}\b', title)
                year = year_match.group(0) if year_match else 'N/A'
                
                movie_data = {
                    'id': link_url.split('/')[-1] if link_url else '',
                    'title': title,
                    'overview': overview,
                    'poster_path': thumbnail_url,
                    'release_date': year,
                    'vote_average': 0,
                    'download_url': full_url
                }
                movies.append(movie_data)
                print(f"Added movie: {title}")  # Debug log
                
            except Exception as e:
                print(f"Error processing movie item: {str(e)}")  # Debug log
                continue
                
        return movies
    except Exception as e:
        print(f"Error in scrape_movies: {str(e)}")  # Debug log
        return []

@app.route('/search_movies')
@login_required
def search_movies():
    try:
        query = request.args.get('query', '')
        page = request.args.get('page', 1, type=int)
        movies = scrape_movies(query, page)
        print(f"Returning {len(movies)} movies")  # Debug log
        return jsonify(movies)
    except Exception as e:
        print(f"Error in search_movies route: {str(e)}")  # Debug log
        return jsonify({'error': str(e)}), 500

@app.route('/movie/<movie_id>')
@login_required
def get_movie_details(movie_id):
    try:
        url = f"{BASE_URL}/{movie_id}"
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.text, 'lxml')
        
        title = soup.select_one('h1').text.strip() if soup.select_one('h1') else 'Unknown Title'
        description = soup.select_one('.description')
        overview = description.text.strip() if description else 'No description available'
        
        # Get metadata
        metadata = soup.select('.metadata-definition')
        info = {}
        for meta in metadata:
            key = meta.select_one('.metadata-definition-label')
            value = meta.select_one('.metadata-definition-value')
            if key and value:
                info[key.text.strip()] = value.text.strip()
        
        return jsonify({
            'id': movie_id,
            'title': title,
            'overview': overview,
            'metadata': info,
            'download_url': f"{url}/download"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username)

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
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
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

@app.route('/download/<int:movie_id>', methods=['POST'])
@login_required
def download_movie(movie_id):
    try:
        # Add download record
        download = Download(
            user_id=current_user.id,
            movie_title=request.form.get('movie_title', 'Unknown Movie'),
            status='completed'
        )
        db.session.add(download)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Download started successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
