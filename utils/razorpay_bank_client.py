import httpx
from fastapi import HTTPException
from core.config import settings

_BASE = settings.RAZORPAY_BASE_URL
_TIMEOUT = httpx.Timeout(30.0)


# ============================================================
# AUTH
# ============================================================
def _auth() -> tuple[str, str]:
    return (
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET,
    )


# ============================================================
# CHECK MOCK MODE
# ============================================================
def _is_mock_mode() -> bool:
    """
    Mock mode enabled if:
    - USE_MOCK_PAYOUT=True
    OR
    - Razorpay keys missing
    """

    return bool(
        settings.USE_MOCK_PAYOUT
        or not settings.RAZORPAY_KEY_ID
        or not settings.RAZORPAY_KEY_SECRET
    )


# ============================================================
# CHECK TEST MODE
# ============================================================
def _is_test_mode() -> bool:

    return bool(
        settings.RAZORPAY_KEY_ID
        and settings.RAZORPAY_KEY_ID.startswith("rzp_test")
    )


# ============================================================
# COMMON POST METHOD
# ============================================================
def _post(endpoint: str, payload: dict) -> dict:

    # ========================================================
    # MOCK MODE
    # ========================================================
    if _is_mock_mode():

        # CONTACT
        if endpoint == "/contacts":
            return {
                "id": "cont_mock_123456",
                "entity": "contact",
                "name": payload.get("name"),
                "email": payload.get("email"),
                "contact": payload.get("contact"),
            }

        # FUND ACCOUNT
        elif endpoint == "/fund_accounts":
            return {
                "id": "fa_mock_123456",
                "entity": "fund_account",
                "contact_id": payload.get("contact_id"),
                "account_type": "bank_account",
            }

        # VALIDATION
        elif endpoint == "/fund_accounts/validations":
            return {
                "id": "fav_mock_123456",
                "status": "completed",
                "results": {
                    "account_status": "active",
                    "registered_name": "Mock User",
                }
            }

        raise HTTPException(
            status_code=400,
            detail=f"Mock endpoint not implemented: {endpoint}"
        )

    # ========================================================
    # LIVE / TEST MODE
    # ========================================================
    try:

        resp = httpx.post(
            f"{_BASE}{endpoint}",
            json=payload,
            auth=_auth(),
            timeout=_TIMEOUT,
        )

        resp.raise_for_status()

        return resp.json()

    except httpx.TimeoutException:

        raise HTTPException(
            status_code=504,
            detail="Razorpay service timed out. Please try again.",
        )

    except httpx.HTTPStatusError as e:

        try:
            desc = (
                e.response.json()
                .get("error", {})
                .get(
                    "description",
                    "Razorpay request failed"
                )
            )

        except Exception:
            desc = "Razorpay request failed"

        raise HTTPException(
            status_code=400,
            detail=desc,
        )

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach Razorpay: {str(e)}"
        )


# ============================================================
# STEP 1 — CREATE CONTACT
# ============================================================
def create_contact(
    name: str,
    email: str,
    contact: str,
) -> str:

    data = _post(
        "/contacts",
        {
            "name": name,
            "email": email,
            "contact": contact,
            "type": "customer",
        },
    )

    contact_id = data.get("id")

    if not contact_id:

        raise HTTPException(
            status_code=502,
            detail="Razorpay did not return contact ID.",
        )

    return contact_id


# ============================================================
# STEP 2 — CREATE FUND ACCOUNT
# ============================================================
def create_fund_account(
    contact_id: str,
    name: str,
    account_number: str,
    ifsc: str,
) -> str:

    data = _post(
        "/fund_accounts",
        {
            "contact_id": contact_id,
            "account_type": "bank_account",
            "bank_account": {
                "name": name,
                "ifsc": ifsc,
                "account_number": account_number,
            },
        },
    )

    fund_account_id = data.get("id")

    if not fund_account_id:

        raise HTTPException(
            status_code=502,
            detail="Razorpay did not return fund account ID.",
        )

    return fund_account_id


# ============================================================
# STEP 3 — VALIDATE FUND ACCOUNT
# ============================================================
def validate_fund_account(
    fund_account_id: str,
    account_holder_name: str,
) -> dict:

    mock_mode = _is_mock_mode()
    test_mode = _is_test_mode()

    payload = {
        "fund_account": {
            "id": fund_account_id,
        },
        "amount": 100,
        "currency": "INR",
    }

    # ========================================================
    # LIVE MODE ONLY
    # ========================================================
    if not mock_mode and not test_mode:

        if not settings.RAZORPAYX_ACCOUNT_NUMBER:

            raise HTTPException(
                status_code=500,
                detail=(
                    "RAZORPAYX_ACCOUNT_NUMBER "
                    "missing for live mode."
                )
            )

        payload["account_number"] = (
            settings.RAZORPAYX_ACCOUNT_NUMBER
        )

    data = _post(
        "/fund_accounts/validations",
        payload,
    )

    status = data.get("status", "")
    results = data.get("results", {})
    validation_id = data.get("id", "")

    # ========================================================
    # MOCK MODE
    # ========================================================
    if mock_mode:

        return {
            "razorpay_status": "completed",
            "account_status": "active",
            "registered_name": account_holder_name,
            "validation_id": validation_id,
        }

    # ========================================================
    # TEST MODE
    # ========================================================
    if test_mode:

        is_success = status in (
            "created",
            "completed",
        )

        return {
            "razorpay_status": (
                "completed"
                if is_success
                else "failed"
            ),
            "account_status": "active",
            "registered_name": account_holder_name,
            "validation_id": validation_id,
        }

    # ========================================================
    # LIVE MODE
    # ========================================================
    account_status = results.get(
        "account_status",
        "inactive",
    )

    registered_name = results.get(
        "registered_name",
        "",
    )

    is_success = status == "completed"

    return {
        "razorpay_status": (
            "completed"
            if is_success
            else "failed"
        ),
        "account_status": account_status,
        "registered_name": registered_name,
        "validation_id": validation_id,
    }