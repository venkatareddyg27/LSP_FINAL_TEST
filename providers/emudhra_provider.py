import uuid
import httpx

from core.config import settings


class EmudhraProvider:

    # =================================================
    # INITIATE
    # =================================================
    async def initiate_esign(
        self,
        payload: dict
    ):

        # =============================================
        # MOCK MODE
        # =============================================
        if settings.ESIGN_MOCK_MODE:

            return {

                "transaction_id": (
                    str(uuid.uuid4())
                ),

                "status": "OTP_SENT",

                "masked_aadhaar": (
                    "XXXX-XXXX-4587"
                ),

                "provider": "EMUDHRA",

                "message": (
                    "Mock OTP sent successfully"
                )
            }

        # =============================================
        # PROD API
        # =============================================
        request_payload = {

            "aadhaar_number": (
                payload["aadhaar_number"]
            ),

            "reference_id": (
                str(uuid.uuid4())
            ),

            "callback_url": (
                settings.EMUDHRA_CALLBACK_URL
            ),

            "redirect_url": (
                settings.EMUDHRA_REDIRECT_URL
            ),
        }

        headers = {

            "client_id": (
                settings.EMUDHRA_CLIENT_ID
            ),

            "client_secret": (
                settings.EMUDHRA_CLIENT_SECRET
            ),
        }

        async with httpx.AsyncClient(
            timeout=30
        ) as client:

            response = await client.post(

                f"{settings.EMUDHRA_BASE_URL}/initiate",

                json=request_payload,

                headers=headers
            )

        response.raise_for_status()

        return response.json()

    # =================================================
    # VERIFY OTP
    # =================================================
    async def verify_esign(
        self,
        payload: dict
    ):

        # =============================================
        # MOCK MODE
        # =============================================
        if settings.ESIGN_MOCK_MODE:

            if payload.get("otp") != "123456":

                return {
                    "status": "FAILED"
                }

            return {

                "status": "SIGNED",

                "provider": "EMUDHRA",

                "signed_pdf_url": (
                    "mock/signed_agreement.pdf"
                )
            }

        # =============================================
        # PROD API
        # =============================================
        request_payload = {

            "transaction_id": (
                payload["transaction_id"]
            ),

            "otp": payload["otp"]
        }

        headers = {

            "client_id": (
                settings.EMUDHRA_CLIENT_ID
            ),

            "client_secret": (
                settings.EMUDHRA_CLIENT_SECRET
            ),
        }

        async with httpx.AsyncClient(
            timeout=30
        ) as client:

            response = await client.post(

                f"{settings.EMUDHRA_BASE_URL}/verify",

                json=request_payload,

                headers=headers
            )

        response.raise_for_status()

        return response.json()