import ssl

import requests

from table_extractor.transport import SystemTrustAdapter, create_session


def test_native_trust_keeps_certificate_and_hostname_verification():
    with create_session() as session:
        adapter = session.get_adapter("https://api.openai.com")
        assert isinstance(adapter, SystemTrustAdapter)
        assert session.verify is True
        assert adapter.ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert adapter.ssl_context.check_hostname is True
        request = requests.Request("GET", "https://example.com").prepare()
        _, options = adapter.build_connection_pool_key_attributes(request, True)
        assert options["ssl_context"] is adapter.ssl_context


def test_explicit_ca_bundle_takes_priority_over_native_trust(tmp_path):
    adapter = SystemTrustAdapter()
    bundle = str(tmp_path / "custom-ca.pem")
    request = requests.Request("GET", "https://example.com").prepare()
    _, options = adapter.build_connection_pool_key_attributes(request, bundle)
    assert options["ca_certs"] == bundle
    assert options.get("ssl_context") is not adapter.ssl_context


def test_https_proxy_uses_verified_native_context():
    adapter = SystemTrustAdapter()
    manager = adapter.proxy_manager_for("https://proxy.example:8080")
    assert manager.proxy_config.ssl_context is adapter.ssl_context
