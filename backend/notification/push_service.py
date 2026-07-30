import logging

logger = logging.getLogger(__name__)

class PushService:
    @staticmethod
    def send_urgent_push(user_id: str, message: str):
        # Stub for FCM integration
        logger.info(f"[FCM PUSH] To: {user_id} - MESSAGE: {message}")
        print(f"[FCM PUSH] To: {user_id} - MESSAGE: {message}")
