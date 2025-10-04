import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
import requests
from enum import Enum
from typing import Dict, Any, Optional
from parameter_validator import ParameterValidator

logging.basicConfig(
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8464723646:AAE5da7NBAFnjI2LRvUeR491CZBUKBZmjNI"
API_KEY = "Y2fZMA59MyAHI10MOxJlyGgfPohdvzAf"
API_SECRET = "G9PNgG384nNHbhLS"
TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"


class SessionState(Enum):
    """User session states"""
    IDLE = "idle"
    FILLING_REQUIRED_PARAMS = "filling_required"
    ADDING_CUSTOM_PARAM_NAME = "adding_custom_name"
    ADDING_CUSTOM_PARAM_VALUE = "adding_custom_value"
    READY_TO_EXECUTE = "ready_to_execute"

class AmadeusBot:
    """Main bot class handling API interactions"""

    def __init__(self):
        self.api_configs = {}
        self.user_sessions = {}
        self.validator = ParameterValidator()
        self.load_api_configs()

    def load_api_configs(self) -> None:
        """Load API configurations from params.json"""
        try:
            with open("params.json", "r") as file:
                self.api_configs = json.load(file)
        except FileNotFoundError:
            logger.error("params.json not found!")
            self.api_configs = {}

    def get_access_token(self) -> Optional[str]:
        """Get Amadeus API access token"""
        try: 
            response = requests.post(TOKEN_URL,
                headers = {"Content-Type": "application/x-www-form-urlencoded"},
                data = {
                    "grant_type": "client_credentials",
                    "client_id": API_KEY,
                    "client_secret": API_SECRET
                }
            )
            return response.json().get("access_token")
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None
        
    def call_api(self, access_token: str, params: dict, url: str) -> dict:
        """Call the Amadeus API"""
        try: 
            response = requests.get(url, 
                headers={"Authorization": f"Bearer {access_token}"},
                params={k: v for k, v in params.items() if v}
            )
            return {
                "success": response.status_code == 200,
                "data": response.json() if response.status_code == 200 else None,
                "error": None if response.status_code == 200 else f"API Error: {response.status_code}"
            }
        except Exception as e:
            return {"success": False, "error": f"Request failed: {str(e)}", "data": None}

    def create_user_session(self, user_id: int, api_name: str) -> None:
        """Initialize a new user session"""
        api_info = self.api_configs[api_name]
        self.user_sessions[user_id] = {
            "state": SessionState.FILLING_REQUIRED_PARAMS,
            "api_name": api_name,
            "api_info": api_info,
            "params": api_info["params"].copy(),
            "required_params": [k for k, v in api_info["params"].items() if not v],
            "current_param_index": 0,
            "custom_param_name": None
        }
    
    def get_current_required_param(self, user_id: int) -> Optional[str]:
        """Get the current required parameter to fill"""
        session = self.user_sessions.get(user_id)
        if not session or session["current_param_index"] >= len(session["required_params"]):
            return None
        return session["required_params"][session["current_param_index"]]
    
    def advance_to_next_param(self, user_id: int) -> None:
        """Move to next required parameter or ready state"""
        session = self.user_sessions[user_id]
        session["current_param_index"] += 1

        if session["current_param_index"] >= len(session["required_params"]):
            session["state"] = SessionState.READY_TO_EXECUTE
    
    def clear_session(self, user_id: int) -> None:
        """Clear user session"""
        self.user_sessions.pop(user_id, None)
    
bot = AmadeusBot()

class UserMessageHandler:
    """Handles different types of user messages based on session state"""

    @staticmethod
    async def handle_required_param(update: Update, user_id: int, message_text: str) -> None:
        session = bot.user_sessions[user_id]
        param_name = bot.get_current_required_param(user_id)
        if not param_name:
            session["state"] = SessionState.READY_TO_EXECUTE
            await UIHelper.show_ready_to_execute(update, user_id)
            return
        is_valid, error_msg, normalized_value = bot.validator.validate_parameter(param_name, message_text)
        if not is_valid:
            await UIHelper.show_validation_error(update, param_name, error_msg)
            return
        
        # Save parameter and advance
        session["params"][param_name] = normalized_value or message_text
        bot.advance_to_next_param(user_id)
        await update.message.reply_text(f"✅ Set {param_name}: `{normalized_value or message_text}`", parse_mode='Markdown')

        # Ask next parameter or show ready state
        next_param = bot.get_current_required_param(user_id)
        if next_param:
            await UIHelper.ask_parameter(update, next_param)
        else:
            session["state"] = SessionState.READY_TO_EXECUTE
            await UIHelper.show_ready_to_execute(update, user_id)

    @staticmethod
    async def handle_custom_param_name(update: Update, user_id: int, message_text: str) -> None:
        """Handle custom parameter name input"""
        session = bot.user_sessions[user_id]
        session["custom_param_name"] = message_text
        session["state"] = SessionState.ADDING_CUSTOM_PARAM_VALUE

        logger.info(f"Changed user {user_id} state to {session['state'].value}, custom_param_name: {message_text}")
        await update.message.reply_text(f"📝 Enter value for '{message_text}':")

    @staticmethod
    async def handle_custom_param_value(update: Update, user_id: int, message_text: str) -> None:
        """Handle custom parameter value input"""
        session = bot.user_sessions[user_id]
        param_name = session["custom_param_name"]

        logger.info(f"Processing custom param value. User: {user_id}, param_name: {param_name}, value: {message_text}")

        if not param_name:
            await update.message.reply_text("❌ Error: No parameter name found. Please start over with /apis")
            return

        # Validate if we have rules for this parameter
        is_valid, error_msg, normalized_value = bot.validator.validate_parameter(param_name, message_text)
        if not is_valid:
            await UIHelper.show_validation_error(update, param_name, error_msg)
            return
        
        #Save parameter and return to ready state
        session["params"][param_name] = normalized_value or message_text
        session["state"] = SessionState.READY_TO_EXECUTE
        session["custom_param_name"] = None

        logger.info(f"Successfully added custom param {param_name}={normalized_value or message_text}, changed state to {session['state'].value}")

        await update.message.reply_text(f"✅ Added {param_name}: `{normalized_value or message_text}`", parse_mode='Markdown')
        await UIHelper.show_ready_to_execute(update, user_id)

class UIHelper:
    """Helper class for UI interactions"""

    @staticmethod
    async def _send_message(update_or_query, text: str, reply_markup=None, parse_mode='Markdown'):
        """Helper to send message regardless of Update or CallbackQuery type"""
        if hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
            # This is an Update object with callback_query
            await update_or_query.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif hasattr(update_or_query, 'message') and update_or_query.message:
            # This is either an Update object with message, or a CallbackQuery
            await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            # This is likely a direct message object
            await update_or_query.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


    @staticmethod
    async def ask_parameter(update_or_query, param_name: str) -> None:
        """Ask user for a parameter with helpful hints"""
        hint = bot.validator.get_parameter_hint(param_name)
        message = f"📝 Please enter **{param_name}**:\n\n💡 {hint}"
        await UIHelper._send_message(update_or_query, message)
    
    @staticmethod
    async def show_validation_error(update: Update, param_name: str, error_msg: str) -> None:
        """Show validation error with hint"""
        hint = bot.validator.get_parameter_hint(param_name)
        message = f"❌ Invalid value: {error_msg}\n\n💡 {hint}\n\nPlease try again:"
        await update.message.reply_text(message, parse_mode='Markdown')
    
    @staticmethod
    async def show_ready_to_execute(update_or_query, user_id: int) -> None:
        """Show ready to execute UI with current parameters"""
        session = bot.user_sessions[user_id]
        keyboard = [
            [InlineKeyboardButton("🚀 Execute API Call", callback_data="execute")],
            [InlineKeyboardButton("➕ Add More Parameters", callback_data="add_more")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message = "✅ All required parameters filled!\n\n**Current parameters:**\n"
        for key, value in session["params"].items():
            if value:
                message += f"• {key}: `{value}`\n"
        await UIHelper._send_message(update_or_query, message, reply_markup)
    
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler"""
    welcome_message = """
🛫 Welcome to Amadeus API Bot! 🛫

I can help you search for flights, hotels, and more using Amadeus APIs.

Commands:
/start - Show this welcome message
/apis - List available APIs
/help - Show help information

Let's get started! Use /apis to see what's available.
"""
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command handler"""
    help_text = """
🆘 Help - How to use this bot:

1. Use /apis to see available APIs
2. Select an API from the list
3. Fill in the required parameters step by step
4. Get your results!

Example workflow:
1. /apis
2. Click on "Flight Offers Search"
3. Enter origin: NYC
4. Enter destination: LON
5. Enter departure date: 2024-01-15
6. Get flight results!
"""
    await update.message.reply_text(help_text)

async def list_apis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available APIs"""
    if not bot.api_configs:
        await update.message.reply_text("❌ No APIs configured. Please check params.json file.")
        return
        
    keyboard = [[InlineKeyboardButton(api_name, callback_data=f"api_{api_name}")] for api_name in bot.api_configs.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔍 Select an API:", reply_markup=reply_markup)

# Callback Handlers
async def api_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle API selection"""
    query = update.callback_query
    await query.answer()
    
    api_name = query.data.replace("api_", "")
    user_id = query.from_user.id
    
    if api_name not in bot.api_configs:
        await query.edit_message_text("❌ API not found!")
        return
    
    # Create new session
    bot.create_user_session(user_id, api_name)
    await query.edit_message_text(f"✅ Selected: {api_name}")
    
    # Start asking for parameters
    first_param = bot.get_current_required_param(user_id)
    if first_param:
        await UIHelper.ask_parameter(query, first_param)
    else:
        await UIHelper.show_ready_to_execute(query, user_id)

async def execute_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute API call"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    session = bot.user_sessions.get(user_id)
    if not session:
        await query.edit_message_text("❌ Session expired. Please start over with /apis")
        return
    
    await query.edit_message_text("🔄 Executing API call...")
    
    # Get access token and call API
    access_token = bot.get_access_token()
    if not access_token:
        await query.edit_message_text("❌ Failed to get access token. Please try again later.")
        return
    
    result = bot.call_api(access_token, session["params"], session["api_info"]["url"])
    
    if result["success"]:
        await handle_successful_api_response(query, session, result["data"], context, user_id)
    else:
        await query.edit_message_text(f"❌ API call failed:\n{result['error']}")
    
    bot.clear_session(user_id)

async def add_more_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle adding more parameters"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    session = bot.user_sessions.get(user_id)
    if not session:
        await query.edit_message_text("❌ Session expired. Please start over with /apis")
        return
    
    session["state"] = SessionState.ADDING_CUSTOM_PARAM_NAME
    await query.edit_message_text("📝 Enter parameter name:")

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current operation"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    bot.clear_session(user_id)
    await query.edit_message_text("❌ Operation cancelled. Use /apis to start over.")


# Helper Functions
async def handle_successful_api_response(query, session, data, context, user_id):
    """Handle successful API response"""
    response_text = f"✅ {session['api_name']} - Success!\n\n"
    
    # Create and send summary
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        response_text += f"📊 Found {len(data['data'])} results\n"
        
        # Show preview of first few results
        for i, item in enumerate(data["data"][:3]):
            response_text += f"\n🔸 Result {i+1}:\n"
            for key, value in list(item.items())[:3]:
                if isinstance(value, (str, int, float)):
                    response_text += f"  • {key}: {value}\n"
        
        if len(data["data"]) > 3:
            response_text += f"\n... and {len(data['data']) - 3} more results"
    
    await query.edit_message_text(response_text[:4000])
    
    # Save and send complete results
    filename = f"{session['api_name'].replace(' ', '_').lower()}_result.json"
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id=user_id,
                document=f,
                filename=filename,
                caption="📁 Complete API response"
            )
    except Exception as e:
        logger.error(f"Error sending file: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route messages based on user session state"""
    user_id = update.effective_user.id
    session = bot.user_sessions.get(user_id)
    
    if not session:
        await update.message.reply_text("👋 Please start by selecting an API with /apis")
        return
    
    message_text = update.message.text.strip()
    state = session["state"]

    logger.info(f"User {user_id} in state {state.value} sent message: {message_text}")
    
    # Route to appropriate handler based on state
    handlers = {
        SessionState.FILLING_REQUIRED_PARAMS: UserMessageHandler.handle_required_param,
        SessionState.ADDING_CUSTOM_PARAM_NAME: UserMessageHandler.handle_custom_param_name,
        SessionState.ADDING_CUSTOM_PARAM_VALUE: UserMessageHandler.handle_custom_param_value,
    }
    
    handler = handlers.get(state)
    if handler:
        await handler(update, user_id, message_text)
    else:
        await update.message.reply_text("❓ I'm not sure what you mean. Use /apis to start a new search.")


def main() -> None:
    """Start the bot"""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your Telegram Bot Token!")
        print("1. Create a bot with @BotFather on Telegram")
        print("2. Replace 'YOUR_BOT_TOKEN_HERE' with your actual token")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("apis", list_apis))
    
    application.add_handler(CallbackQueryHandler(api_callback, pattern="^api_"))
    application.add_handler(CallbackQueryHandler(execute_callback, pattern="^execute$"))
    application.add_handler(CallbackQueryHandler(add_more_callback, pattern="^add_more$"))
    application.add_handler(CallbackQueryHandler(cancel_callback, pattern="^cancel$"))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Starting Telegram Bot...")
    application.run_polling()


if __name__ == '__main__':
    main()