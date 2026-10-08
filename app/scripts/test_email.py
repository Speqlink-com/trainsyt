"""Send a harmless SMTP smoke-test message without creating a user."""

import argparse
import asyncio

from app.core.core import settings
from app.services.email_service import email_service


async def run(recipient: str | None) -> None:
    destination = recipient or settings.ZOHO_EMAIL
    if settings.EMAIL_DELIVERY_MODE != "smtp":
        raise SystemExit("EMAIL_DELIVERY_MODE must be smtp for a real delivery test")
    if not settings.smtp_configured or not destination:
        raise SystemExit("Zoho SMTP credentials and a recipient must be configured")

    sent = await email_service.send(
        destination,
        "TrainSyt email delivery test",
        "<p>TrainSyt successfully delivered this message through Zoho SMTP.</p>",
        "TrainSyt successfully delivered this message through Zoho SMTP.",
    )
    if not sent:
        raise SystemExit("Zoho SMTP rejected the test message; inspect the API logs")
    print(f"Zoho SMTP accepted the TrainSyt test message for {destination}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "recipient",
        nargs="?",
        help="Destination address; defaults to the configured Zoho mailbox",
    )
    args = parser.parse_args()
    asyncio.run(run(args.recipient))


if __name__ == "__main__":
    main()
