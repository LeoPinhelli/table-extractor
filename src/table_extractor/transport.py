"""Conexoes HTTPS com a cadeia de confianca do sistema, sem alterar o SSL global."""

import ssl

import requests
import truststore
from requests.adapters import HTTPAdapter


class SystemTrustAdapter(HTTPAdapter):
    def __init__(self):
        self.ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        super().__init__()

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        host, options = super().build_connection_pool_key_attributes(request, verify, cert)
        if verify is True:
            options["ssl_context"] = self.ssl_context
        # Um CA bundle informado explicitamente continua tendo prioridade.
        return host, options

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs.setdefault("proxy_ssl_context", self.ssl_context)
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def create_session() -> requests.Session:
    session = requests.Session()
    session.mount("https://", SystemTrustAdapter())
    return session
