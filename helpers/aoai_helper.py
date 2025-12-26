import os
import logging
from openai import AsyncAzureOpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")


class AOAIError(Exception):
    """Custom exception for Azure OpenAI errors."""
    pass


class AOAIHelper:
    """Helper class for Azure OpenAI API calls."""
    
    def __init__(self):
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            raise AOAIError("Azure OpenAI configuration is missing. Please check your .env file.")
        
        self.client = AsyncAzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        self.model = AZURE_OPENAI_DEPLOYMENT
    
    async def get_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0
    ) -> str:
        """
        Make a call to Azure OpenAI and get the response.
        
        Args:
            system_prompt: The system message for context.
            user_prompt: The user instruction prompt.
            max_tokens: Maximum tokens in response.
            temperature: Temperature for response generation.
        
        Returns:
            The response content from Azure OpenAI.
        
        Raises:
            AOAIError: If the API call fails.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
        except AuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            raise AOAIError("Azure OpenAI authentication failed. Please check your API key.")
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise AOAIError("Azure OpenAI rate limit exceeded. Please try again later.")
        except APIConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise AOAIError("Failed to connect to Azure OpenAI. Please check your endpoint URL.")
        except APIError as e:
            logger.error(f"API error: {e}")
            raise AOAIError(f"Azure OpenAI API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during API call: {e}")
            raise AOAIError(f"Failed to call Azure OpenAI: {str(e)}")
        
        result = response.choices[0].message.content
        
        if not result:
            raise AOAIError("Empty response from Azure OpenAI")
        
        return result
