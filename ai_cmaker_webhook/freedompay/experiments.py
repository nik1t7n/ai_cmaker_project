
import asyncio
import xml.dom.minidom
from freedompay_kg import FreedomPayClient

# Set FreedomPay API and your ngrok webhook URL
MERCHANT_ID = "560402"
SECRET_KEY = "HZHObNVZSc8oMxLQ"
NGROK_URL = "https://b0a9-176-64-5-221.ngrok-free.app"  # Your public webhook URL

client = FreedomPayClient(MERCHANT_ID, SECRET_KEY, NGROK_URL)

# Function to prettify XML response
def pretty_print_xml(xml_string):
    try:
        dom = xml.dom.minidom.parseString(xml_string)
        return dom.toprettyxml(indent="  ")  # Adds indentation for better readability
    except Exception:
        return xml_string  # Return as is if parsing fails

# Jupyter-compatible async call
async def test_payment():
    print("🔍 Initiating Payment...")
    payment_response = await client.init_payment(
        order_id="00102",
        amount=2500,
        description="Test Payment",
        user_phone="77777777777",
        user_email="customer@example.com"
    )

    print("\n🔗 Payment Response:\n", pretty_print_xml(payment_response))

    # print("\n🔍 Checking Payment Status...")
    # status_response = await client.get_payment_status(order_id="00102")

    # print("\n🔗 Payment Status:\n", pretty_print_xml(status_response))

# ✅ Properly run the async function in a Python script
if __name__ == "__main__":
    asyncio.run(test_payment())

















# import requests
# import hashlib

# def generate_signature(script_name, params, secret_key):
#     sorted_params = sorted(params.items())  # Ensure parameters are sorted
#     concatenated_string = ";".join([script_name] + [str(value) for _, value in sorted_params] + [secret_key])
    
#     print("\n🔍 Signature Debugging:")
#     print("Signature String:", concatenated_string)  # 🔍 Debugging Output
#     signature = hashlib.md5(concatenated_string.encode('utf-8')).hexdigest()
#     print("Generated Signature:", signature)  # 🔍 Debugging Output
#     return signature

# def init_payment(order_id, merchant_id, amount, description, salt, secret_key):
#     url = "https://api.freedompay.kg/init_payment.php"

#     params = {
#         "pg_order_id": order_id,
#         "pg_merchant_id": merchant_id,
#         "pg_amount": amount,
#         "pg_currency": "KGS",
#         "pg_description": description,
#         "pg_salt": salt,
#         "pg_check_url": "https://2797-176-64-15-6.ngrok-free.app/check",
#         "pg_result_url": "https://2797-176-64-15-6.ngrok-free.app/result",
#         "pg_request_method": "POST",
#         "pg_success_url": "https://2797-176-64-15-6.ngrok-free.app/success",
#         "pg_failure_url": "https://2797-176-64-15-6.ngrok-free.app/failure",
#         "pg_payment_system": "EPAYWEBKGS",
#         "pg_lifetime": "86400",
#         "pg_user_phone": "77777777777",
#         "pg_user_contact_email": "mail@customer.kz",
#         "pg_user_ip": "127.0.0.1",
#         "pg_language": "ru",
#         "pg_testing_mode": "1",
#         "pg_user_id": "1",
#     }

#     params["pg_sig"] = generate_signature("init_payment.php", params, secret_key)

#     response = requests.post(url, data=params)
    
#     print("\n🔍 API Response:")
#     print(response.text)  # 🔍 Debugging Output
    
#     return response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text

# # Replace with your actual secret key
# SECRET_KEY = "HZHObNVZSc8oMxLQ"

# # 🔥 Make API Call
# response = init_payment(22, "560402", 2500, "test", "molbulak", SECRET_KEY)

# print("\n🔗 Payment Link (if available):", response)
