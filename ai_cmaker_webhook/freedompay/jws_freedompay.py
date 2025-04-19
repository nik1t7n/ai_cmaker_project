# jws_freedompay.py

import hashlib

def generate_init_payment_signature(params: dict, secret_key: str) -> str:
    """Generate MD5 signature for the init_payment API."""
    script_name = "init_payment.php"
    sorted_params = sorted(params.items())
    concatenated_string = ";".join([script_name] + [str(value) for _, value in sorted_params] + [secret_key])

    signature = hashlib.md5(concatenated_string.encode("utf-8")).hexdigest()
    return signature

def generate_get_status_signature(params: dict, secret_key: str) -> str:
    """Generate MD5 signature for the get_status3 API."""
    script_name = "get_status3.php"
    sorted_params = sorted(params.items())
    concatenated_string = ";".join([script_name] + [str(value) for _, value in sorted_params] + [secret_key])

    signature = hashlib.md5(concatenated_string.encode("utf-8")).hexdigest()
    return signature

def generate_signature(script_name: str, params: dict, secret_key: str) -> str:
    """General-purpose signature generator for FreedomPay API."""
    sorted_params = sorted(params.items())  # Sort alphabetically by key
    concatenated_string = ";".join(
        [script_name] + [str(value) for _, value in sorted_params] + [secret_key]
    )
    return hashlib.md5(concatenated_string.encode("utf-8")).hexdigest()
