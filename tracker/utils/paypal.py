# tracker/utils/paypal.py

from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from paypalcheckoutsdk.orders import OrdersCreateRequest
from django.conf import settings
from django.urls import reverse
import json
import logging

logger = logging.getLogger(__name__)

class PayPalClient:
    def __init__(self):
        try:
            environment = SandboxEnvironment(
                client_id=settings.PAYPAL_CLIENT_ID,
                client_secret=settings.PAYPAL_CLIENT_SECRET
            )
            self.client = PayPalHttpClient(environment)
            logger.info("PayPal client initialized successfully")
        except Exception as e:
            logger.error(f"PayPal client initialization failed: {str(e)}")
            raise

    def create_subscription(self, user, tier, request):
        """Create a PayPal subscription for a user"""
        try:
            # Validate credentials before making request
            if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
                logger.error("PayPal credentials not configured")
                return None
            
            logger.info(f"Creating PayPal order for tier: {tier.name}, price: ${tier.price}")
            
            # Validate inputs
            if not tier.price or float(tier.price) <= 0:
                logger.error(f"Invalid tier price: {tier.price}")
                return None

            order_request = OrdersCreateRequest()
            order_request.prefer('return=representation')
            
            request_body = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": "USD",
                        "value": str(tier.price),
                        "breakdown": {
                            "item_total": {
                                "currency_code": "USD",
                                "value": str(tier.price)
                            }
                        }
                    },
                    "description": f"{tier.name} Plan Subscription",
                    "items": [{
                        "name": f"{tier.name} Plan",
                        "description": f"Monthly subscription to {tier.name} plan",
                        "quantity": "1",
                        "unit_amount": {
                            "currency_code": "USD",
                            "value": str(tier.price)
                        }
                    }]
                }],
                "application_context": {
                    "brand_name": "Link DNA",
                    "landing_page": "LOGIN",
                    "user_action": "PAY_NOW",
                    "return_url": request.build_absolute_uri(reverse('subscription_success')),
                    "cancel_url": request.build_absolute_uri(reverse('subscription_cancel'))
                }
            }
            
            logger.debug(f"PayPal request body: {json.dumps(request_body, indent=2)}")
            order_request.request_body(request_body)

            # Execute request
            response = self.client.execute(order_request)
            logger.info(f"PayPal response received: {json.dumps(response.result.dict(), indent=2)}")
            
            # Extract approval URL
            for link in response.result.links:
                if link.rel == "approve":
                    logger.info(f"Approval URL found: {link.href}")
                    return link.href
            
            logger.error("No approval URL found in PayPal response")
            return None

        except paypalhttp.http_error.HttpError as e:
            logger.error(f"PayPal authentication error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"PayPal order creation failed: {str(e)}", exc_info=True)
            return None

    def verify_webhook_signature(self, transmission_id, timestamp, webhook_id, event_body):
        """Verify that the webhook came from PayPal"""
        try:
            response = self.client.execute({
                "transmission_id": transmission_id,
                "transmission_time": timestamp,
                "cert_url": webhook_id,
                "webhook_event": event_body,
                "webhook_id": settings.PAYPAL_WEBHOOK_ID
            })
            return response.result.verification_status == "SUCCESS"
        except Exception as e:
            print(f'Webhook verification failed: {e}')
            return False

    def get_subscription_details(self, subscription_id):
        """Get details of a subscription"""
        try:
            response = self.client.execute({
                "subscription_id": subscription_id
            })
            return response.result
        except Exception as e:
            print(f'Failed to get subscription details: {e}')
            return None

    def cancel_subscription(self, subscription_id, reason=""):
        """Cancel a subscription"""
        try:
            response = self.client.execute({
                "subscription_id": subscription_id,
                "reason": reason
            })
            return True
        except Exception as e:
            print(f'Failed to cancel subscription: {e}')
            return False

    def suspend_subscription(self, subscription_id, reason=""):
        """Suspend a subscription"""
        try:
            response = self.client.execute({
                "subscription_id": subscription_id,
                "reason": reason
            })
            return True
        except Exception as e:
            print(f'Failed to suspend subscription: {e}')
            return False

    def activate_subscription(self, subscription_id):
        """Activate a suspended subscription"""
        try:
            response = self.client.execute({
                "subscription_id": subscription_id
            })
            return True
        except Exception as e:
            print(f'Failed to activate subscription: {e}')
            return False