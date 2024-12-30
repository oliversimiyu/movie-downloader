# Movie Downloader Web Application

A simple and modern web application for downloading movies and videos using yt-dlp.

Last updated: 2024-12-30 10:25:10 UTC+03:00

## Features

- Clean and responsive user interface
- Support for multiple video platforms
- Real-time download status updates
- Error handling and user feedback
- Secure download management

## Installation

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the Flask application:
   ```
   python app.py
   ```
2. Open your web browser and navigate to `http://localhost:5000`
3. Enter the URL of the video you want to download
4. Click the "Download Video" button
5. Wait for the download to complete

## Dependencies

- Flask
- yt-dlp
- requests
- python-dotenv
- flask-cors

## Notes

- Downloaded files are saved in the `downloads` folder
- Supports various video platforms compatible with yt-dlp
- Built with security and performance in mind
- Regular updates and maintenance
