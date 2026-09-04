import os


# ============================================================
# GRAM AI SMS CONFIGURATION
# ============================================================

SMS_MODE = os.environ.get(
    "GRAMAI_SMS_MODE",
    "demo"
)


# ============================================================
# SEND LOGIN OTP
# ============================================================

def send_otp_sms(
    phone: str,
    otp: str
):

    # ========================================================
    # DEMO MODE
    # ========================================================
    #
    # For local testing:
    #
    # OTP will appear in the VS Code terminal.
    #
    # Later we can connect a real SMS provider.
    # ========================================================

    if SMS_MODE == "demo":

        print()
        print("==========================================")
        print("GRAM AI LOGIN OTP")
        print("==========================================")
        print(f"Phone : +{phone}")
        print(f"OTP   : {otp}")
        print("Valid : 5 minutes")
        print("==========================================")
        print()

        return {
            "sent": True,
            "provider": "DEMO",
            "demo_otp": otp
        }


    # ========================================================
    # PRODUCTION SMS PROVIDER
    # ========================================================
    #
    # We will later connect:
    #
    # MSG91
    # Twilio
    # AWS SNS
    # Firebase Phone Authentication
    #
    # Keep API keys in environment variables.
    # ========================================================

    return {
        "sent": False,
        "provider": SMS_MODE,
        "message": (
            "Production SMS provider "
            "is not configured"
        )
    }