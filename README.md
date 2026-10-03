#  Universal File Conversion & AI Bot

An asynchronous Telegram bot built with Python that performs real-time file format conversions, multi-file PDF merging, and AI-powered Optical Character Recognition (OCR). 

Designed with a focus on non-blocking I/O, robust cross-request state management, and ephemeral file system handling to ensure high performance and zero memory leaks.

##  Features & Architecture

- **Interactive State Machine:** Replaces rigid slash-commands with dynamic Inline Keyboard menus. The bot utilizes an in-memory session router mapped to unique user IDs to handle complex, multi-step workflows (like accumulating multiple images over time before merging).
- **Asynchronous Processing:** Built on `python-telegram-bot` (v20+) and `asyncio`, enabling the bot to handle multiple concurrent users and non-blocking network requests to the Telegram and Google APIs.
- **Ephemeral Storage Management:** Implements Python's `tempfile` context managers to isolate concurrent user downloads. This guarantees that all heavy media files are securely wiped from the host server the millisecond a workflow completes or fails, preventing catastrophic disk-space leaks.
- **AI Vision Integration:** Utilizes Google's modern `google-genai` SDK and the `gemini-2.5-flash` model for high-speed, multimodal Optical Character Recognition (OCR) on user-uploaded documents.
- **Defensive Error Handling:** Features strict type-checking on incoming payloads, routing fallbacks for unexpected document types, and robust exception handling to ensure the event loop never crashes.

##  Tech Stack

- **Language:** Python 3.10+
- **Framework:** `python-telegram-bot` (Async API)
- **Image Processing:** `Pillow` (Format manipulation, RGB conversion)
- **PDF Manipulation:** `pypdf` (Stream merging and generation)
- **AI / LLM:** Google Gemini 2.5 Flash (`google-genai` SDK)

##  Core Workflows

1. **Image to PDF:** Converts raw images (PNG, JPG, WEBP) directly into a formatted PDF document.
2. **Image Format Swapping:** Intelligently detects image extensions and losslessly converts formats (e.g., stripping the Alpha channel from a PNG to create a valid JPG).
3. **Multi-File Accumulation (Merging):** 
   - Tracks a user's uploaded images over multiple discrete requests.
   - Merges multiple PDFs into a single, unified document.
4. **AI Text Extraction (OCR):** Analyzes high-resolution document uploads or compressed photos, extracts text seamlessly via Gemini Vision, and returns a cleanly formatted `.txt` file to bypass Telegram's character limits.

##  Installation & Local Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/nickos07/the-converter-bot.git](https://github.com/nickos07/the-converter-bot.git)
cd the-converter-bot

```

### 2. Set Up a Virtual Environment

Isolate the project dependencies:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate

```

### 3. Install Dependencies

```bash
pip install -r requirements.txt

```

### 4. Configure Environment Variables

You will need a Telegram Bot API Token from [BotFather](https://t.me/botfather) and a Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/).

Create a `.env` file in the root directory:

```env
BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_google_gemini_api_key_here

```

### 5. Run the Application

```bash
python bot.py

```

Send `/start` to your bot in Telegram to trigger the interactive menu and begin routing files.

##  Future Scalability

To transition this application from a single-node deployment to a highly available, horizontally scaled microservice, the following architectural upgrades are planned:

* **Redis Integration:** Migrate the in-memory Python `user_state` dictionary to a Redis cluster, allowing multiple bot instances to share user state concurrently.
* **Webhook Architecture:** Shift from `run_polling()` to a Webhook-based architecture behind an NGINX reverse proxy for improved payload delivery efficiency.
* **Systemd Service:** Package the application as a Linux `systemd` background service for 24/7 uptime and automatic crash restarts on a cloud VPS.
