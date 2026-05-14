from core.config import settings

from core.logger import logger

from providers.mock_provider import (
    MockESignProvider
)

from providers.emudhra_provider import (
    EmudhraProvider
)


def get_esign_provider():
    """
    Factory to load the correct
    eSign provider implementation.
    """

    env = (
        settings.ENV
        .strip()
        .upper()
    )

    provider = (
        settings.ESIGN_PROVIDER
        .strip()
        .lower()
    )

    mock_mode = getattr(
        settings,
        "ESIGN_MOCK_MODE",
        False
    )

    logger.info(
        f"[ESIGN FACTORY] "
        f"env={env}, "
        f"provider={provider}, "
        f"mock={mock_mode}"
    )

    # =================================================
    # FORCE MOCK MODE
    # =================================================
    if mock_mode:

        logger.warning(
            "[ESIGN] MOCK MODE ENABLED"
        )

        return MockESignProvider()

    # =================================================
    # DEVELOPMENT
    # =================================================
    if env in [

        "DEV",

        "LOCAL",

        "DEVELOPMENT"
    ]:

        logger.warning(
            "[ESIGN] DEV MODE MOCK PROVIDER"
        )

        return MockESignProvider()

    # =================================================
    # EMUDHRA
    # =================================================
    if provider == "emudhra":

        logger.info(
            "[ESIGN] USING EMUDHRA"
        )

        return EmudhraProvider()

    # =================================================
    # FUTURE PROVIDERS
    # =================================================
    # if provider == "nsdl":
    #     return NSDLProvider()

    # if provider == "digio":
    #     return DigioProvider()

    # =================================================
    # UNSUPPORTED
    # =================================================
    raise ValueError(
        f"Unsupported eSign provider: "
        f"{provider}"
    )