import logging

logger = logging.getLogger(__name__)

class SMSService:
    @staticmethod
    def send_sms_fallback(phone_number: str, message: str):
        # Stub for SMS Gateway
        logger.info(f"[SMS FALLBACK] To: {phone_number} - MESSAGE: {message}")
        print(f"[SMS FALLBACK] To: {phone_number} - MESSAGE: {message}")
