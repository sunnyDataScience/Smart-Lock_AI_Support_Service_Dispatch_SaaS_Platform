"""Message bus module for decoupled channel-agent communication."""

from lockcore.bus.events import InboundMessage, OutboundMessage
from lockcore.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
