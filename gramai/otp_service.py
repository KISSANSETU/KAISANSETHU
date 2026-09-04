import os
import time
import secrets
import hashlib
import hmac


# ============================================================
# GRAM AI OTP CONFIGURATION
# ============================================================

OTP_SECRET = os.environ.get(
    "GRAMAI_OTP_SECRET",
    "GRAM-AI-DEVELOPMENT-OTP-SECRET-2026"
)

# OTP remains valid for 5 minutes
OTP_EXPIRY_SECONDS = 300

# Maximum incorrect attempts
OTP_MAX_ATTEMPTS = 5


# ============================================================
# DEVELOPMENT OTP STORE
# ============================================================
#
# For the prototype this is stored in memory.
#
# Later for production:
#
# Redis / database
#
# should be used instead.
# ============================================================

OTP_STORE = {}


# ============================================================
# NORMALIZE INDIAN PHONE NUMBER
# ============================================================

def normalize_phone(phone: str) -> str:

    if not phone:
        raise ValueError(
            "Phone number is required"
        )

    # Keep digits only
    digits = "".join(
        character
        for character in phone
        if character.isdigit()
    )

    # Example:
    #
    # 9876543210
    #
    # becomes
    #
    # 919876543210

    if len(digits) == 10:

        digits = (
            "91"
            +
            digits
        )

    # Already starts with 91
    elif (
        len(digits) == 12
        and
        digits.startswith("91")
    ):

        pass

    else:

        raise ValueError(
            "Enter a valid 10-digit Indian mobile number"
        )

    return digits


# ============================================================
# HASH OTP
# ============================================================

def hash_otp(
    phone: str,
    otp: str
) -> str:

    message = (
        f"{phone}:{otp}"
    ).encode()

    return hmac.new(

        OTP_SECRET.encode(),

        message,

        hashlib.sha256

    ).hexdigest()


# ============================================================
# GENERATE OTP
# ============================================================

def generate_otp(
    phone: str
):

    phone = normalize_phone(
        phone
    )

    # Secure random 6 digit OTP
    otp = str(
        secrets.randbelow(
            900000
        )
        +
        100000
    )

    OTP_STORE[
        phone
    ] = {

        "otp_hash":
            hash_otp(
                phone,
                otp
            ),

        "expires_at":
            time.time()
            +
            OTP_EXPIRY_SECONDS,

        "attempts":
            0,

        "verified":
            False
    }

    return {
        "phone":
            phone,

        "otp":
            otp,

        "expires_in":
            OTP_EXPIRY_SECONDS
    }


# ============================================================
# VERIFY OTP
# ============================================================

def verify_otp(
    phone: str,
    otp: str
):

    phone = normalize_phone(
        phone
    )

    record = OTP_STORE.get(
        phone
    )

    # ----------------------------------------
    # OTP DOES NOT EXIST
    # ----------------------------------------

    if not record:

        return {
            "success":
                False,

            "message":
                "OTP not requested"
        }

    # ----------------------------------------
    # CHECK EXPIRY
    # ----------------------------------------

    if (
        time.time()
        >
        record[
            "expires_at"
        ]
    ):

        OTP_STORE.pop(
            phone,
            None
        )

        return {
            "success":
                False,

            "message":
                "OTP expired. Request a new OTP."
        }

    # ----------------------------------------
    # CHECK ATTEMPT LIMIT
    # ----------------------------------------

    if (
        record[
            "attempts"
        ]
        >=
        OTP_MAX_ATTEMPTS
    ):

        OTP_STORE.pop(
            phone,
            None
        )

        return {
            "success":
                False,

            "message":
                "Too many incorrect OTP attempts"
        }

    # ----------------------------------------
    # COUNT ATTEMPT
    # ----------------------------------------

    record[
        "attempts"
    ] += 1

    # ----------------------------------------
    # HASH ENTERED OTP
    # ----------------------------------------

    entered_hash = (
        hash_otp(
            phone,
            otp
        )
    )

    # ----------------------------------------
    # COMPARE SECURELY
    # ----------------------------------------

    correct = (
        hmac.compare_digest(

            record[
                "otp_hash"
            ],

            entered_hash
        )
    )

    if not correct:

        remaining = (

            OTP_MAX_ATTEMPTS

            -

            record[
                "attempts"
            ]
        )

        return {

            "success":
                False,

            "message":
                "Incorrect OTP",

            "attempts_remaining":
                remaining
        }

    # ----------------------------------------
    # SUCCESS
    # ----------------------------------------

    OTP_STORE.pop(
        phone,
        None
    )

    return {

        "success":
            True,

        "message":
            "OTP verified successfully",

        "phone":
            phone
    }


# ============================================================
# RESEND OTP
# ============================================================

def resend_otp(
    phone: str
):

    phone = normalize_phone(
        phone
    )

    OTP_STORE.pop(
        phone,
        None
    )

    return generate_otp(
        phone
    )


# ============================================================
# CHECK IF OTP EXISTS
# ============================================================

def otp_exists(
    phone: str
):

    try:

        phone = normalize_phone(
            phone
        )

    except ValueError:

        return False

    record = OTP_STORE.get(
        phone
    )

    if not record:

        return False

    if (
        time.time()
        >
        record[
            "expires_at"
        ]
    ):

        OTP_STORE.pop(
            phone,
            None
        )

        return False

    return True