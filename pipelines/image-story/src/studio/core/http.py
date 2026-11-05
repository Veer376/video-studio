"""Verified TLS with a portable CA bundle and an explicit custom-CA override."""
import os
import ssl

import certifi


def tls_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or certifi.where())
