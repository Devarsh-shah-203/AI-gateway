DEBUG_URL = "http://127.0.0.1:9222"


def connect_to_chrome(playwright):
    """
    Connect to the Chrome instance that was
    launched with remote debugging enabled.
    """

    return playwright.chromium.connect_over_cdp(
        DEBUG_URL
    )