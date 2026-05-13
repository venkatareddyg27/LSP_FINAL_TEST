import uuid

import cloudinary
import cloudinary.uploader

from core.config import settings


# =========================================================
# CLOUDINARY CONFIG
# =========================================================
cloudinary.config(

    cloud_name=(
        settings
        .CLOUDINARY_CLOUD_NAME
    ),

    api_key=(
        settings
        .CLOUDINARY_API_KEY
    ),

    api_secret=(
        settings
        .CLOUDINARY_API_SECRET
    ),

    secure=True,
)


# =========================================================
# GENERATE PUBLIC ID
# =========================================================
def generate_cloudinary_public_id(
    user_id: int,
    document_type: str
) -> str:

    unique = uuid.uuid4().hex[:10]

    return (

        f"{user_id}_"

        f"{document_type}_"

        f"{unique}"
    )