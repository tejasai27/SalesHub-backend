"""
Gemini AI client for the sales chatbot.
Provides conversation context, sales-focused prompts, and retry logic.
"""
import google.generativeai as genai
from config import Config
import logging
import time


# Sales-focused system prompt
SALES_SYSTEM_PROMPT = """You are SalesHub AI, a professional sales assistant for a sales team. Your role is to:

1. **Help craft compelling communications**: Assist with emails, follow-up messages, LinkedIn outreach, and proposals
2. **Provide sales strategies**: Suggest objection handling techniques, closing strategies, and negotiation tips
3. **Answer product/service questions**: Help explain features, benefits, and value propositions
4. **Lead qualification**: Help with discovery questions and qualifying leads
5. **Research assistance**: Help analyze prospects, industries, and competitive landscape

Guidelines:
- Be professional, helpful, and action-oriented
- Provide specific, actionable advice (not generic tips)
- Use a confident but friendly tone
- Keep responses concise but comprehensive
- When writing emails or messages, make them ready to send
- Focus on value and outcomes, not just features
"""


class GeminiClient:
    """
    Enhanced Gemini AI client with conversation context, 
    sales prompts, and retry logic.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        # Check if API key is configured
        if not Config.GEMINI_API_KEY or Config.GEMINI_API_KEY == 'your_actual_gemini_api_key_here':
            self.gemini_available = False
            self.logger.error("❌ Gemini API key is not configured!")
            return
        
        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
            self.gemini_available = True
            self.logger.info("✅ Gemini AI client initialized successfully")
        except Exception as e:
            self.gemini_available = False
            self.logger.error(f"❌ Gemini AI initialization failed: {str(e)}")
    
    def _build_context_prompt(self, prompt, conversation_history=None, context=None):
        """
        Build the full prompt with system instructions and conversation context.
        
        Args:
            prompt (str): Current user message
            conversation_history (list): Recent messages [(role, text), ...]
            context (str): Additional context
            
        Returns:
            str: Full prompt with context
        """
        parts = [SALES_SYSTEM_PROMPT]
        
        # Add conversation history for context
        if conversation_history and len(conversation_history) > 0:
            parts.append("\n--- Recent Conversation ---")
            for role, text in conversation_history[-10:]:  # Last 10 messages
                if role == 'user':
                    parts.append(f"User: {text}")
                else:
                    parts.append(f"Assistant: {text}")
            parts.append("--- End of History ---\n")
        
        # Add additional context if provided
        if context:
            parts.append(f"Additional Context: {context}\n")
        
        # Add current message
        parts.append(f"Current User Message: {prompt}")
        parts.append("\nProvide a helpful, sales-focused response:")
        
        return "\n".join(parts)
    
    def _call_api_with_retry(self, prompt, max_tokens):
        """
        Call the Gemini API with exponential backoff retry logic.
        
        Args:
            prompt (str): The prompt to send
            max_tokens (int): Maximum tokens in response
            
        Returns:
            str: API response text
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        "max_output_tokens": max_tokens,
                        "temperature": 0.7,
                        "top_p": 0.8,
                        "top_k": 40,
                    },
                    safety_settings=[
                        {
                            "category": "HARM_CATEGORY_HARASSMENT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_HATE_SPEECH",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        },
                        {
                            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                        }
                    ]
                )
                
                return response.text
                
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Check if it's a rate limit error (429)
                if "429" in error_str or "quota" in error_str.lower():
                    wait_time = self.retry_delay * (2 ** attempt)
                    self.logger.warning(
                        f"Rate limit hit, retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                
                # For other errors, don't retry
                self.logger.error(f"Gemini API error: {error_str}")
                break
        
        raise last_exception
    
    def generate_response(self, prompt, context=None, conversation_history=None, max_tokens=800):
        """
        Generate AI response using Gemini with conversation context.
        
        Args:
            prompt (str): User's message
            context (str, optional): Additional context
            conversation_history (list, optional): Recent messages [(role, text), ...]
            max_tokens (int): Maximum tokens in response
            
        Returns:
            dict: {
                'text': str - AI generated response,
                'tokens_used': int - Token count (if available),
                'response_obj': object - Full API response
            }
        """
        # Check if Gemini is available
        if not self.gemini_available:
            fallback_text = ("Hello! I'm SalesHub AI, your sales assistant. "
                   "To enable AI chat features, please configure the Gemini API key. "
                   "Get a free API key from https://ai.google.dev/")
            return {
                'text': fallback_text,
                'tokens_used': None,
                'response_obj': None
            }
        
        try:
            # Build the full prompt with context
            full_prompt = self._build_context_prompt(prompt, conversation_history, context)
            
            # Call API with retry logic
            response_text = self._call_api_with_retry(full_prompt, max_tokens)
            
            # Try to extract token usage if available
            # Note: Gemini API may not always provide token counts in the free tier
            tokens_used = None
            try:
                # This is a placeholder - Gemini SDK structure may vary
                # You might need to check the actual response object structure
                tokens_used = None  # Will be None if not available
            except:
                pass
            
            return {
                'text': response_text,
                'tokens_used': tokens_used,
                'response_obj': None
            }
            
        except Exception as e:
            error_str = str(e)
            self.logger.error(f"Gemini API error: {error_str}")
            
            # Provide helpful error messages
            if "429" in error_str or "quota" in error_str.lower():
                error_text = ("I'm currently experiencing high demand. Please wait a moment and try again. "
                       "If this persists, your daily API quota may have been reached.")
            elif "safety" in error_str.lower():
                error_text = ("I couldn't process that request due to content safety filters. "
                       "Please rephrase your question.")
            else:
                error_text = ("I apologize, but I'm having trouble processing your request. "
                       "Please try again in a moment.")
            
            return {
                'text': error_text,
                'tokens_used': None,
                'response_obj': None
            }
    
    def get_chat_context(self, user_id, session_id):
        """
        Retrieve recent conversation context for AI response.
        This method is called by the chat routes to build context.
        
        Args:
            user_id (str): User identifier
            session_id (str): Session identifier
            
        Returns:
            str: Context string (placeholder for future enhancement)
        """
        # Future enhancement: Integrate with CRM, Google Docs, etc.
        return f"Sales team member using SalesHub AI assistant. Session: {session_id}"
    
    def get_conversation_history(self, user_id, session_id, limit=10):
        """
        Retrieve recent conversation history from database.
        
        Args:
            user_id (str): User identifier
            session_id (str): Session identifier
            limit (int): Maximum messages to retrieve
            
        Returns:
            list: List of (role, text) tuples
        """
        try:
            from database.models import ChatSession
            
            messages = ChatSession.query.filter_by(
                user_id=user_id,
                session_id=session_id
            ).order_by(
                ChatSession.timestamp.desc()
            ).limit(limit).all()
            
            # Reverse to get chronological order
            messages = list(reversed(messages))
            
            return [(msg.message_type, msg.message_text) for msg in messages]
            
        except Exception as e:
            self.logger.error(f"Error fetching conversation history: {e}")
            return []