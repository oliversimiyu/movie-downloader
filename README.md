# Movie Downloader Web Application

A feature-rich web application for downloading movies and videos using yt-dlp, built with Flask and modern web technologies.

Last updated: 2024-12-30 10:26:08 UTC+03:00

## Features

### User Management
- User registration and authentication system
- Secure password hashing with bcrypt
- User profiles with download history
- Protected routes for authenticated users

### Movie Management
- Browse curated collection of classic movies
- Search functionality for finding specific movies
- Detailed movie information including:
  - Title and release date
  - Movie overview/description
  - Movie poster thumbnails
  - User ratings
- Support for multiple video platforms via yt-dlp
- Real-time download status updates
- Download history tracking
- Secure file handling

### Technical Features
- Clean and responsive user interface
- SQLite database for data persistence
- CORS support for cross-origin requests
- Error handling and user feedback
- Secure download management
- Built-in movie scraping from public domain sources
- Automatic download folder management

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/oliversimiyu/movie-downloader.git
   cd movie-downloader
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory (optional):
   ```
   SECRET_KEY=your-secret-key-here
   ```

## Usage

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your web browser and navigate to `http://localhost:5000`

3. Register a new account or log in if you already have one

4. Browse Movies:
   - View the curated collection on the home page
   - Use the search function to find specific movies
   - Click on a movie to view detailed information

5. Download Movies:
   - Click the "Download" button on any movie
   - Wait for the download to complete
   - Find downloaded files in the `downloads` folder

6. View Your Profile:
   - Check your download history
   - Manage your account settings

## Dependencies

- Flask - Web framework
- Flask-SQLAlchemy - Database ORM
- Flask-Login - User session management
- Flask-Bcrypt - Password hashing
- yt-dlp - Video downloading
- requests - HTTP client
- BeautifulSoup4 - Web scraping
- python-dotenv - Environment management
- flask-cors - Cross-origin resource sharing

## Project Structure
```
movie-downloader/
├── app.py              # Main application file
├── requirements.txt    # Python dependencies
├── downloads/          # Downloaded files directory
├── instance/          # SQLite database location
└── templates/         # HTML templates
    ├── base.html
    ├── index.html
    ├── login.html
    ├── profile.html
    └── signup.html
```

## Notes

- Downloaded files are automatically saved in the `downloads` folder
- Supports various video platforms compatible with yt-dlp
- Built with security and performance in mind
- Regular updates and maintenance
- Uses public domain movie sources for legal compliance

## Security

- Passwords are securely hashed using bcrypt
- Protected routes require authentication
- Secure file handling and validation
- Cross-Site Request Forgery (CSRF) protection
- Input validation and sanitization

## Contributing

Feel free to submit issues and enhancement requests!
