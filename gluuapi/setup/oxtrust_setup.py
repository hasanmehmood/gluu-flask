# -*- coding: utf-8 -*-
# The MIT License (MIT)
#
# Copyright (c) 2015 Gluu
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import os.path

from gluuapi.setup.oxauth_setup import OxauthSetup


class OxtrustSetup(OxauthSetup):
    @property
    def oxtrust_properties(self):  # pragma: no cover
        return self.get_template_path("salt/oxtrust/oxTrust.properties")

    @property
    def oxtrust_ldap_properties(self):  # pragma: no cover
        return self.get_template_path("salt/oxtrust/oxTrustLdap.properties")

    @property
    def oxtrust_log_rotation_configuration(self):  # pragma: no cover
        return self.get_template_path("salt/oxtrust/oxTrustLogRotationConfiguration.xml")

    @property
    def oxtrust_cache_refresh_properties(self):  # pragma: no cover
        return self.get_template_path("salt/oxtrust/oxTrustCacheRefresh-template.properties.vm")

    def import_httpd_cert(self):
        # imports httpd cert into oxtrust cacerts to avoid
        # "peer not authenticated" error
        cert_cmd = "echo -n | openssl s_client -connect {}:443 | " \
                   "sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p' " \
                   "> /tmp/ox.cert".format(self.cluster.ox_cluster_hostname)

        import_cmd = " ".join([
            "keytool -importcert -trustcacerts",
            "-alias '{}'".format(self.cluster.ox_cluster_hostname),
            "-file /tmp/ox.cert",
            "-keystore {}".format(self.node.truststore_fn),
            "-storepass changeit -noprompt",
        ])
        self.logger.info("importing httpd cert")
        self.salt.cmd(
            self.node.id,
            ["cmd.run", "cmd.run"],
            [[cert_cmd], [import_cmd]]
        )

    def delete_httpd_cert(self):
        delete_cmd = " ".join([
            "keytool -delete",
            "-alias {}".format(self.cluster.ox_cluster_hostname),
            "-keystore {}".format(self.node.truststore_fn),
            "-storepass changeit -noprompt",
        ])
        self.logger.info("deleting httpd cert")
        self.salt.cmd(self.node.id, "cmd.run", [delete_cmd])

    def add_host_entries(self, httpd):
        # currently we need to add httpd container hostname
        # to prevent "peer not authenticated" raised by oxTrust;
        # TODO: use a real DNS
        self.logger.info("updating oxTrust host entries in /etc/hosts")
        # add the entry only if line is not exist in /etc/hosts
        grep_cmd = "grep -q '^{0} {1}$' /etc/hosts " \
                   "|| echo '{0} {1}' >> /etc/hosts" \
                   .format(httpd.weave_ip,
                           self.cluster.ox_cluster_hostname)
        self.salt.cmd(self.node.id, "cmd.run", [grep_cmd])

    def render_cache_props_template(self):
        src = self.oxtrust_cache_refresh_properties
        dest_dir = os.path.join(self.node.tomcat_conf_dir, "template", "conf")
        dest = os.path.join(dest_dir, os.path.basename(src))
        self.salt.cmd(self.node.id, "cmd.run",
                      ["mkdir -p {}".format(dest_dir)])
        self.render_template(src, dest)

    def render_log_config_template(self):
        src = self.oxtrust_log_rotation_configuration
        dest = os.path.join(self.node.tomcat_conf_dir, os.path.basename(src))
        ctx = {
            "tomcat_log_folder": self.node.tomcat_log_folder,
        }
        self.render_template(src, dest, ctx)

    def render_props_template(self):
        src = self.oxtrust_properties
        dest = os.path.join(self.node.tomcat_conf_dir, os.path.basename(src))
        ctx = {
            "inumAppliance": self.cluster.inum_appliance,
            "inumOrg": self.cluster.inum_org,
            "orgName": self.cluster.org_name,
            "orgShortName": self.cluster.org_short_name,
            "admin_email": self.cluster.admin_email,
            "ox_cluster_hostname": self.cluster.ox_cluster_hostname,
            "shibJksFn": self.cluster.shib_jks_fn,
            "shibJksPass": self.cluster.decrypted_admin_pw,
            "inumOrgFN": self.cluster.inum_org_fn,
            "oxTrustConfigGeneration": self.node.oxtrust_config_generation,
            "encoded_shib_jks_pw": self.cluster.encoded_shib_jks_pw,
            "encoded_ox_ldap_pw": self.cluster.encoded_ox_ldap_pw,
            "oxauth_client_id": self.cluster.oxauth_client_id,
            "oxauthClient_encoded_pw": self.cluster.oxauth_client_encoded_pw,
            "inumApplianceFN": self.cluster.inum_appliance_fn,
            "truststore_fn": self.node.truststore_fn,
        }
        self.render_template(src, dest, ctx)

    def render_ldap_props_template(self):
        src = self.oxtrust_ldap_properties
        dest = os.path.join(self.node.tomcat_conf_dir, os.path.basename(src))

        ldap_hosts = ",".join([
            "{}:{}".format(ldap.weave_ip, ldap.ldaps_port)
            for ldap in self.cluster.get_ldap_objects()
        ])
        ctx = {
            "ldap_binddn": self.node.ldap_binddn,
            "encoded_ox_ldap_pw": self.cluster.encoded_ox_ldap_pw,
            "ldap_hosts": ldap_hosts,
            "inumAppliance": self.cluster.inum_appliance,
        }
        self.render_template(src, dest, ctx)

    def setup(self):
        hostname = self.cluster.ox_cluster_hostname.split(":")[0]
        self.create_cert_dir()

        # render config templates
        self.render_cache_props_template()
        self.render_log_config_template()
        self.render_props_template()
        self.render_ldap_props_template()
        self.render_server_xml_template()
        self.write_salt_file()

        self.gen_cert("shibIDP", self.cluster.decrypted_admin_pw,
                      "tomcat", "tomcat", hostname)

        # IDP keystore
        self.gen_keystore(
            "shibIDP",
            self.cluster.shib_jks_fn,
            self.cluster.decrypted_admin_pw,
            "{}/shibIDP.key".format(self.node.cert_folder),
            "{}/shibIDP.crt".format(self.node.cert_folder),
            "tomcat",
            "tomcat",
            hostname,
        )

        # Configure tomcat to run oxtrust war file
        # FIXME: cannot found "facter" and "check_ssl" commands
        self.start_tomcat()

        self.change_cert_access("tomcat", "tomcat")
        return True
