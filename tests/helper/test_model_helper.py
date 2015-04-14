import pytest


def test_base_model_helper_init(cluster):
    from api.helper.model_helper import BaseModelHelper

    # instantiating BaseModelHelper without overriding any
    # required attrs (e.g. ``setup_class``) raises AssertionError
    with pytest.raises(AssertionError):
        BaseModelHelper(cluster, "127.0.0.1")


def test_ldap_model_helper(monkeypatch, cluster):
    from api.helper.model_helper import LdapModelHelper
    from api.setup.ldap_setup import ldapSetup
    from api.model.ldap_node import ldapNode

    ipaddr = "172.17.0.4"
    monkeypatch.setattr(
        "docker.Client.inspect_container",
        lambda cls, container: {"NetworkSettings": {"IPAddress": ipaddr}},
    )
    helper = LdapModelHelper(cluster, "127.0.0.1")

    # some sanity checks
    assert helper.setup_class == ldapSetup
    assert helper.node_class == ldapNode
    assert helper.image == "gluuopendj"
    assert helper.dockerfile == "https://raw.githubusercontent.com" \
                                "/GluuFederation/gluu-docker/master" \
                                "/ubuntu/14.04/gluuopendj/Dockerfile"

    helper.prepare_node_attrs()
    assert helper.node.ip == ipaddr
    assert helper.node.local_hostname == ipaddr


def test_oxauth_model_helper(monkeypatch, cluster):
    from api.helper.model_helper import OxAuthModelHelper
    from api.setup.oxauth_setup import OxAuthSetup
    from api.model.oxauth_node import oxauthNode

    ipaddr = "172.17.0.4"
    monkeypatch.setattr(
        "docker.Client.inspect_container",
        lambda cls, container: {"NetworkSettings": {"IPAddress": ipaddr}},
    )
    helper = OxAuthModelHelper(cluster, "127.0.0.1")

    # some sanity checks
    assert helper.setup_class == OxAuthSetup
    assert helper.node_class == oxauthNode
    assert helper.image == "gluuoxauth"
    assert helper.dockerfile == "https://raw.githubusercontent.com" \
                                "/GluuFederation/gluu-docker/master" \
                                "/ubuntu/14.04/gluuoxauth/Dockerfile"

    helper.prepare_node_attrs()
    assert helper.node.ip == ipaddr


def test_oxtrust_model_helper(monkeypatch, cluster):
    from api.helper.model_helper import OxTrustModelHelper
    from api.setup.oxtrust_setup import OxTrustSetup
    from api.model.oxtrust_node import oxtrustNode

    ipaddr = "172.17.0.4"
    monkeypatch.setattr(
        "docker.Client.inspect_container",
        lambda cls, container: {"NetworkSettings": {"IPAddress": ipaddr}},
    )
    helper = OxTrustModelHelper(cluster, "127.0.0.1")

    # some sanity checks
    assert helper.setup_class == OxTrustSetup
    assert helper.node_class == oxtrustNode
    assert helper.image == "gluuoxtrust"
    assert helper.dockerfile == "https://raw.githubusercontent.com" \
                                "/GluuFederation/gluu-docker/master" \
                                "/ubuntu/14.04/gluuoxtrust/Dockerfile"

    helper.prepare_node_attrs()
    assert helper.node.ip == ipaddr
    assert helper.node.hostname == ipaddr