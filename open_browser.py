
# Browser opening is handled by start.bat after the Uvicorn health check.
# Kept for compatibility with previous versions.
import webbrowser
webbrowser.open("http://127.0.0.1:8000")
