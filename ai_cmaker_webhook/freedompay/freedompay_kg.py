import requests
import httpx
import random
import string
import sys
import os

sys.path.append("E:/Work/AI Agents/freedompay kg module")  # Add the module directory to sys.path
from freedompay.jws_freedompay import generate_init_payment_signature, generate_get_status_signature, generate_signature

def parse_pg_xml(xml_str):
    result = {}

    # Remove the XML declaration
    if xml_str.startswith("<?xml"):
        xml_str = xml_str.split("?>", 1)[-1]

    while "<pg_" in xml_str:
        start_tag_index = xml_str.find("<pg_")
        end_tag_index = xml_str.find(">", start_tag_index)
        start_tag = xml_str[start_tag_index + 1:end_tag_index]  # e.g., pg_status

        closing_tag = f"</{start_tag}>"
        closing_tag_index = xml_str.find(closing_tag)

        value = xml_str[end_tag_index + 1:closing_tag_index]
        key = start_tag.replace("pg_", "")
        value = value.replace("&amp;", "&").strip()

        result[key] = value

        # Skip processed part
        xml_str = xml_str[closing_tag_index + len(closing_tag):]

    return result

class FreedomPayClient:
    def __init__(self, merchant_id: str, receive_key: str, webhook_url: str, base_url: str = "https://api.freedompay.kg", test_mode: bool = False):
        """
        Initialize the FreedomPayClient with merchant details.
        
        :param merchant_id: Your merchant ID
        :param secret_key: Secret key for signing requests
        :param webhook_url: Your public webhook URL (e.g., ngrok URL)
        :param base_url: Base API URL (default: FreedomPay API)
        :param test_mode: If True, enables testing mode (default: True)
        """
        self.merchant_id = merchant_id
        self.receive_key = receive_key
        self.webhook_url = webhook_url.rstrip("/")  # Ensure no trailing slash
        self.base_url = base_url.rstrip("/")
        self.test_mode = "1" if test_mode else "0"

        # Predefined list of salts
        self.salt_list = [
            "XkL9a7B3cD2E5F1G6H8J0K", "P9Q2R4S7T8U1V5W6X3Y0Z", 
            "A1B2C3D4E5F6G7H8J9K0L", "M2N3P4Q5R6S7T8U9V0W", 
            "Y8X7W6V5U4T3S2R1Q0P9", "Z3Y4X5W6V7U8T9S0R1", 
            "N5M4L3K2J1H0G9F8E7D6", "B7C8D9E0F1G2H3J4K5L", 
            "P0Q9R8S7T6U5V4W3X2Y1", "A3B4C5D6E7F8G9H0J1K"
        ]

    def _get_random_salt(self):
        """Selects a random salt from the predefined list."""
        return random.choice(self.salt_list)

    async def init_payment(self, order_id: str, amount: float, description: str, user_phone: str, user_email: str):
        """
        Initialize a payment request asynchronously.

        :param order_id: Unique order ID
        :param amount: Payment amount
        :param description: Payment description
        :param user_phone: Customer phone number
        :param user_email: Customer email
        :return: JSON response from FreedomPay API
        """
        url = f"{self.base_url}/init_payment.php"
        salt = self._get_random_salt()  # Automatically select salt

        params = {
            "pg_order_id": order_id,
            "pg_merchant_id": self.merchant_id,
            "pg_amount": amount,
            "pg_currency": "KGS",
            "pg_description": description,
            "pg_salt": salt,
            "pg_check_url": f"{self.webhook_url}/check",
            "pg_result_url": f"{self.webhook_url}/result",
            "pg_request_method": "POST",
            "pg_success_url": f"{self.webhook_url}/success",
            "pg_failure_url": f"{self.webhook_url}/failure",
            "pg_payment_system": "EPAYWEBKGS",
            "pg_lifetime": "86400",
            "pg_user_phone": user_phone,
            "pg_user_contact_email": user_email,
            "pg_user_ip": "127.0.0.1",
            "pg_language": "ru",
            "pg_testing_mode": self.test_mode,
            "pg_user_id": "1",
        }

        # Generate signature
        params["pg_sig"] = generate_init_payment_signature(params, self.receive_key)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=params)

        cleansed_response = parse_pg_xml(response.text)

        return cleansed_response

    async def get_payment_status(self, payment_id: int = None, order_id: str = None):
        """
        Get the status of a payment from FreedomPay asynchronously.

        :param payment_id: The unique FreedomPay payment ID
        :param order_id: The order ID used when initiating the payment
        :return: JSON response containing payment status
        """
        if not payment_id and not order_id:
            raise ValueError("Either 'payment_id' or 'order_id' must be provided.")

        url = f"{self.base_url}/get_status3.php"
        salt = self._get_random_salt()  # Automatically select salt

        params = {
            "pg_merchant_id": self.merchant_id,
            "pg_salt": salt,
        }

        if payment_id:
            params["pg_payment_id"] = payment_id
        else:
            params["pg_order_id"] = order_id

        # Generate signature
        params["pg_sig"] = generate_get_status_signature(params, self.receive_key)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=params)

        cleansed_response = parse_pg_xml(response.text)

        if cleansed_response['payment_status'] == 'success' and cleansed_response['can_reject'] == '1' and cleansed_response['amount'] == cleansed_response['clearing_amount']:
            return 1
        else:
            return 0
    
    
    # async def capture_payment(self, payment_id: int, clearing_amount: float):
    #     """
    #     Request clearing (capture) for a previously authorized payment.

    #     :param payment_id: FreedomPay payment ID
    #     :param clearing_amount: Amount to be cleared
    #     :return: JSON or text response
    #     """
    #     url = f"{self.base_url}/do_capture.php"
    #     salt = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

    #     params = {
    #         "pg_merchant_id": self.merchant_id,
    #         "pg_payment_id": payment_id,
    #         "pg_clearing_amount": clearing_amount,
    #         "pg_salt": salt,
    #     }

    #     params["pg_sig"] = generate_signature("do_capture.php", params, self.receive_key)

    #     async with httpx.AsyncClient() as client:
    #         response = await client.post(url, data=params)

    #     return response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text


    async def cancel_payment(self, payment_id: int, receipt_positions: list = None, idempotency_key: str = None):
        """
        Cancel a pending payment that has not been completed.

        :param payment_id: FreedomPay payment ID
        :param receipt_positions: Optional receipt positions (list of dicts)
        :param idempotency_key: Optional unique key for safety
        :return: JSON or text response
        """
        url = f"{self.base_url}/cancel.php"
        salt = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        idempotency_key = idempotency_key or ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        params = {
            "pg_merchant_id": self.merchant_id,
            "pg_payment_id": payment_id,
            "pg_salt": salt,
            "pg_idempotency_key": idempotency_key,
        }

        if receipt_positions:
            for i, item in enumerate(receipt_positions):
                params[f"pg_receipt_positions[{i}][count]"] = item["count"]
                params[f"pg_receipt_positions[{i}][name]"] = item["name"]
                params[f"pg_receipt_positions[{i}][tax_type]"] = item["tax_type"]
                params[f"pg_receipt_positions[{i}][price]"] = item["price"]

        params["pg_sig"] = generate_signature("cancel.php", params, self.receive_key)

        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=params)
        
        cleansed_response = parse_pg_xml(response.text)

        return cleansed_response


    # async def refund_payment(self, payment_id: int, refund_amount: float = 0, receipt_positions: list = None, idempotency_key: str = None):
    #     """
    #     Refund a successfully completed payment, fully or partially.

    #     :param payment_id: FreedomPay payment ID
    #     :param refund_amount: Amount to refund (0 for full refund)
    #     :param receipt_positions: Optional list of receipt positions
    #     :param idempotency_key: Optional unique key to avoid duplicate refunds
    #     :return: JSON or text response
    #     """
    #     url = f"{self.base_url}/revoke.php"
    #     salt = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    #     idempotency_key = idempotency_key or ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    #     params = {
    #         "pg_merchant_id": self.merchant_id,
    #         "pg_payment_id": payment_id,
    #         "pg_salt": salt,
    #         "pg_idempotency_key": idempotency_key,
    #     }

    #     if refund_amount:
    #         params["pg_refund_amount"] = refund_amount

    #     if receipt_positions:
    #         for i, item in enumerate(receipt_positions):
    #             params[f"pg_receipt_positions[{i}][count]"] = item["count"]
    #             params[f"pg_receipt_positions[{i}][name]"] = item["name"]
    #             params[f"pg_receipt_positions[{i}][tax_type]"] = item["tax_type"]
    #             params[f"pg_receipt_positions[{i}][price]"] = item["price"]

    #     params["pg_sig"] = generate_signature("revoke.php", params, self.receive_key)

    #     async with httpx.AsyncClient() as client:
    #         response = await client.post(url, data=params)

    #     return response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text
