
import threading
import time
import webbrowser
import uvicorn

URL = "http://127.0.0.1:8000"


def open_browser():
    time.sleep(1.5)
    webbrowser.open(URL)


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "webapp.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
