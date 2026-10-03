import os
import logging
from dotenv import load_dotenv
import tempfile
from google import genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from PIL import Image
from pypdf import PdfWriter

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# We'll hardcode the token for this first test, but remember: 
# in production, we use environment variables!
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

user_state = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: Shows the main menu."""
    keyboard = [
        [InlineKeyboardButton("🔄 Convert Files", callback_data="menu_convert")],
        [InlineKeyboardButton("📑 Merge Files", callback_data="menu_merge")],
        [InlineKeyboardButton("🧠 AI OCR (Extract Text)", callback_data="mode_ai_ocr")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the initial menu
    await update.message.reply_text("Welcome to The Converter Bot! What would you like to do?", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all button clicks and updates the user's state."""
    query = update.callback_query
    # Backend best practice: Always answer the callback query immediately to stop the loading spinner on the user's client
    await query.answer() 
    
    user_id = query.from_user.id
    data = query.data

    # --- MAIN MENU ROUTING ---
    if data == "menu_convert":
        keyboard = [
            [InlineKeyboardButton("Image ➡️ Image", callback_data="mode_convert_img_img")],
            [InlineKeyboardButton("Image ➡️ PDF", callback_data="mode_convert_img_pdf")],
            [InlineKeyboardButton("« Back", callback_data="menu_main")]
        ]
        await query.message.edit_text("Choose conversion type:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "menu_merge":
        keyboard = [
            [InlineKeyboardButton("Images ➡️ PDF", callback_data="mode_merge_img_pdf")],
            [InlineKeyboardButton("PDFs ➡️ PDF", callback_data="mode_merge_pdf_pdf")],
            [InlineKeyboardButton("« Back", callback_data="menu_main")]
        ]
        await query.message.edit_text("Choose merge type:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "menu_main":
        # Return to main menu
        keyboard = [
            [InlineKeyboardButton("🔄 Convert Files", callback_data="menu_convert")],
            [InlineKeyboardButton("📑 Merge Files", callback_data="menu_merge")],
            [InlineKeyboardButton("🧠 AI OCR (Extract Text)", callback_data="mode_ai_ocr")]
        ]
        await query.message.edit_text("What would you like to do?", reply_markup=InlineKeyboardMarkup(keyboard))
        
    # --- STATE ASSIGNMENT ---
    elif data.startswith("mode_"):
        # We now store a dictionary for the user state so we can track BOTH their chosen mode and their uploaded files
        user_state[user_id] = {
            "mode": data,
            "files": []
        }
        
        mode_names = {
            "mode_convert_img_img": "Image to Image",
            "mode_convert_img_pdf": "Image to PDF",
            "mode_merge_img_pdf": "Images to PDF",
            "mode_merge_pdf_pdf": "PDFs to PDF",
            "mode_ai_ocr": "AI Text Extraction (OCR)"
        }
        
        instructions = f"Mode set to: **{mode_names[data]}**.\n\nPlease upload your file(s). "
        if "merge" in data:
            instructions += "When you have uploaded all your files, type /done."
            
        await query.message.edit_text(instructions, parse_mode="Markdown")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes documents based on the user's current state."""
    user_id = update.message.from_user.id
    state_data = user_state.get(user_id)
    
    # 1. Strict State Validation
    if not state_data or not isinstance(state_data, dict):
        await update.message.reply_text("Please use /start to select a conversion mode first.")
        return

    mode = state_data.get("mode")
    document = update.message.document
    
    # Defensive check: ensure document actually exists before reading attributes
    if not document:
        await update.message.reply_text("Error: Expected a document, but received something else.")
        return
        
    file_name = document.file_name
    
    # 2. ROUTE: Image to PDF
    if mode == "mode_convert_img_pdf":
        await update.message.reply_text("Converting your image to a PDF...")
        telegram_file = await context.bot.get_file(document.file_id)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, file_name or "temp_img")
            await telegram_file.download_to_drive(local_path)
            
            output_path = os.path.join(temp_dir, "converted_image.pdf")
            with Image.open(local_path) as img:
                rgb_img = img.convert('RGB')
                rgb_img.save(output_path, 'PDF', resolution=100.0)
            
            with open(output_path, 'rb') as f:
                await update.message.reply_document(document=f, caption="Conversion complete! Here is your PDF.")
                
        del user_state[user_id]
        
    # 3. ROUTE: Image to Image
    elif mode == "mode_convert_img_img":
        await update.message.reply_text("Converting your image format...")
        telegram_file = await context.bot.get_file(document.file_id)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, file_name or "temp_img")
            await telegram_file.download_to_drive(local_path)
            
            ext = os.path.splitext(local_path)[1].lower()
            out_ext = ".jpg" if ext == ".png" else ".png"
            output_path = os.path.join(temp_dir, f"converted{out_ext}")
            
            with Image.open(local_path) as img:
                if out_ext == ".jpg":
                    img = img.convert('RGB')
                img.save(output_path)
            
            with open(output_path, 'rb') as f:
                await update.message.reply_document(document=f, caption=f"Converted to {out_ext.upper()}!")
                
        del user_state[user_id] 

    # 4. ROUTE: PDFs to PDF
    elif mode == "mode_merge_pdf_pdf":
        if not file_name or not file_name.lower().endswith('.pdf'):
            await update.message.reply_text("Please upload only PDF files for this mode.")
            return
            
        state_data["files"].append(document.file_id)
        await update.message.reply_text(f"PDF received! Total files: {len(state_data['files'])}. Upload more or type /done.")

    # 5. ROUTE: AI OCR (for uncompressed document uploads)
    elif mode == "mode_ai_ocr":
        safe_file_name = file_name or "unknown.jpg"
        file_ext = os.path.splitext(safe_file_name)[1].lower()
        
        if file_ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            await update.message.reply_text(f"Please upload an image file. Received: {file_ext}")
            return

        await update.message.reply_text("Extracting text from high-res document with AI. Please wait...")
        
        try:
            telegram_file = await context.bot.get_file(document.file_id)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = os.path.join(temp_dir, safe_file_name)
                await telegram_file.download_to_drive(local_path)
                
                img = Image.open(local_path)
                prompt = "Extract all text from this image perfectly. Preserve formatting. Return ONLY the text."
                
                # CRITICAL FIX: Use 'aio' for asynchronous API calls
                response = await ai_client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, img]
                )
                
                txt_path = os.path.join(temp_dir, "extracted_text.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                    
                with open(txt_path, "rb") as f:
                    await update.message.reply_document(document=f, caption="OCR complete!")
        except Exception as e:
            print(f"OCR Error: {e}")
            await update.message.reply_text("An error occurred while processing the AI request.")
        finally:
            if user_id in user_state:
                del user_state[user_id]

    # --- CRITICAL FIX: The missing fallback ---
    else:
        print(f"DEBUG: Unhandled mode in handle_document -> {mode}")
        await update.message.reply_text(f"System Error: Upload received, but the current mode '{mode}' does not support document files.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes standard photo uploads based on the active state."""
    user_id = update.message.from_user.id
    state_data = user_state.get(user_id)
    
    if not state_data or not isinstance(state_data, dict):
        await update.message.reply_text("Please use /start to select a mode first.")
        return

    mode = state_data.get("mode")
    
    # ROUTE 1: AI OCR 
    if mode == "mode_ai_ocr":
        await update.message.reply_text("Extracting text with AI. Please wait...")
        file_id = update.message.photo[-1].file_id
        
        try:
            telegram_file = await context.bot.get_file(file_id)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = os.path.join(temp_dir, "ocr_target.jpg")
                await telegram_file.download_to_drive(local_path)
                
                img = Image.open(local_path)
                prompt = "Extract all text from this image perfectly. Preserve formatting. Return ONLY the text."
                
                # CRITICAL FIX: Use 'aio' for asynchronous API calls
                response = await ai_client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt, img]
                )
                
                txt_path = os.path.join(temp_dir, "extracted_text.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
                    
                with open(txt_path, "rb") as f:
                    await update.message.reply_document(document=f, caption="OCR complete!")
        except Exception as e:
            print(f"OCR Error: {e}")
            await update.message.reply_text("An error occurred while processing the AI request.")
        finally:
            if user_id in user_state:
                del user_state[user_id]

    # ROUTE 2: Images to PDF
    elif mode == "mode_merge_img_pdf":
        file_id = update.message.photo[-1].file_id
        state_data["files"].append(file_id)
        await update.message.reply_text(f"Photo received! Total images: {len(state_data['files'])}. Upload more or type /done.")
        
    else:
        await update.message.reply_text(f"You sent a photo, but your current mode ('{mode}') requires a Document/File upload.")

async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Executes multi-file merges based on the active mode."""
    user_id = update.message.from_user.id
    state_data = user_state.get(user_id)
    
    if not state_data or not isinstance(state_data, dict) or not state_data.get("files"):
        await update.message.reply_text("You don't have any pending files to merge!")
        return
        
    mode = state_data["mode"]
    file_ids = state_data["files"]
    
    if mode == "mode_merge_pdf_pdf":
        await update.message.reply_text(f"Merging {len(file_ids)} PDFs. Please wait...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            merger = PdfWriter()
            
            # Download and append each PDF in order
            for idx, f_id in enumerate(file_ids):
                telegram_file = await context.bot.get_file(f_id)
                local_path = os.path.join(temp_dir, f"doc_{idx}.pdf")
                await telegram_file.download_to_drive(local_path)
                merger.append(local_path)
                
            output_pdf_path = os.path.join(temp_dir, "final_merged.pdf")
            merger.write(output_pdf_path)
            merger.close()
            
            with open(output_pdf_path, 'rb') as f:
                await update.message.reply_document(document=f, caption="Here is your merged PDF!")

    # --- NEW ELIF BLOCK: IMAGES TO PDF ---
    elif mode == "mode_merge_img_pdf":
        await update.message.reply_text(f"Merging {len(file_ids)} images into a PDF. Please wait...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            images = []
            
            # 1. Download all images
            for idx, f_id in enumerate(file_ids):
                telegram_file = await context.bot.get_file(f_id)
                local_path = os.path.join(temp_dir, f"image_{idx}.jpg")
                await telegram_file.download_to_drive(local_path)
                
                # Open with Pillow and convert to RGB (PDF requirement)
                img = Image.open(local_path).convert('RGB')
                images.append(img)
                
            output_pdf_path = os.path.join(temp_dir, "merged_output.pdf")
            
            # 2. Merge and save as PDF
            if images:
                images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
                
                # 3. Send the final product back
                with open(output_pdf_path, 'rb') as f:
                    await update.message.reply_document(document=f, caption="Here is your merged PDF!")
                
    # Clean up state to prevent memory leaks (runs for all modes)
    del user_state[user_id]

if __name__ == '__main__':
    print("Initializing bot...")
    
    # 1. Create the application instance
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 2. Register our handlers (routing)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # 3. Start polling Telegram for updates
    print("Bot is polling. Press Ctrl+C to stop.")
    app.run_polling()