"""Concrete channel adapters.

V1.0:
    - ``line``: real adapter, wraps ``agent.core.line_bot``

V1.5+ stubs (return ``DeliveryResult(success=False, error="not configured")``):
    - ``sms``    — Twilio / AWS SNS / 國內供應商
    - ``email``  — AWS SES / SendGrid
    - ``fcm``    — Firebase Cloud Messaging (Android push)
"""
