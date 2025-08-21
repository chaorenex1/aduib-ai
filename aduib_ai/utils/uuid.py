def random_uuid() -> str:
    """Generate a random UUID."""
    import uuid
    return str(uuid.uuid4())


def message_uuid() -> str:
    """Generate a UUID for a message."""
    import uuid
    return f"chatcmpl-{str(uuid.uuid4().hex)}"