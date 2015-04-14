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
import codecs
import json
import os.path
import time

from api.database import db
from api.helper.common_helper import run
from api.setup.base import BaseSetup
from api.setup.oxauth_setup import OxAuthSetup
from api.setup.oxtrust_setup import OxTrustSetup


class ldapSetup(BaseSetup):
    def write_ldap_pw(self):
        self.logger.info("writing temporary LDAP password")

        try:
            local_dest = os.path.join(self.build_dir, ".pw")
            with codecs.open(local_dest, "w", encoding="utf-8") as fp:
                fp.write(self.cluster.decrypted_admin_pw)

            self.saltlocal.cmd(
                self.node.id, "cmd.run", ["mkdir -p {}".format(os.path.dirname(self.node.ldapPassFn))],
            )
            run("salt-cp {} {} {}".format(self.node.id, local_dest, self.node.ldapPassFn))
        except Exception as exc:
            self.logger.error(exc)
        finally:
            os.unlink(local_dest)

    def delete_ldap_pw(self):
        self.logger.info("deleting temporary LDAP password")
        self.saltlocal.cmd(
            self.node.id,
            'cmd.run',
            ['rm -f {}'.format(self.node.ldapPassFn)],
        )

    def add_ldap_schema(self):
        ctx = {
            "inumOrgFN": self.cluster.inumOrgFN,
        }

        for schema_file in self.node.schemaFiles:
            # render templates
            rendered_content = ""

            try:
                with codecs.open(schema_file, "r", encoding="utf-8") as fp:
                    rendered_content = fp.read() % ctx
            except Exception as exc:
                self.logger.error(exc)

            try:
                file_basename = os.path.basename(schema_file)

                # save to temporary file
                local_dest = os.path.join(self.build_dir, file_basename)
                with codecs.open(local_dest, "w", encoding="utf-8") as fp:
                    fp.write(rendered_content)

                # copy to minion
                remote_dest = os.path.join(self.node.schemaFolder,
                                           file_basename)
                self.logger.info("copying {}".format(local_dest))
                run("salt-cp {} {} {}".format(self.node.id, local_dest,
                                              remote_dest))
            except Exception as exc:
                self.logger.error(exc)
            finally:
                os.unlink(local_dest)

    def setup_opendj(self):
        self.add_ldap_schema()

        # opendj-setup.properties template destination
        setupPropsFN = os.path.join(self.node.ldapBaseFolder,
                                    'opendj-setup.properties')

        try:
            with open(self.node.ldap_setup_properties, "r") as fp:
                content = fp.read().format(
                    ldap_hostname=self.node.local_hostname,
                    ldap_port=self.node.ldap_port,
                    ldaps_port=self.node.ldaps_port,
                    ldap_jmx_port=self.node.ldap_jmx_port,
                    ldap_admin_port=self.node.ldap_admin_port,
                    ldap_binddn=self.node.ldap_binddn,
                    ldapPassFn=self.node.ldapPassFn,
                )

            # Copy opendj-setup.properties so user ldap can find it
            # in /opt/opendj
            self.logger.info("copying opendj-setup.properties")
            self.saltlocal.cmd(
                self.node.id,
                "cmd.run",
                ["echo '{}' > {}".format(content, setupPropsFN)],
            )
        except Exception as exc:
            self.logger.error(exc)

        try:
            setupCmd = " ".join([self.node.ldapSetupCommand,
                                 '--no-prompt',
                                 '--cli',
                                 '--acceptLicense',
                                 '--propertiesFilePath',
                                 setupPropsFN,
                                 ])

            self.logger.info("running opendj setup")
            self.saltlocal.cmd(
                self.node.id,
                'cmd.run',
                ["{}".format(setupCmd)],
            )
            self.logger.debug("{}".format(setupCmd))
        except Exception as exc:
            self.logger.error("error running LDAP setup script: %s" % exc)

        try:
            self.logger.info("running dsjavaproperties")
            self.saltlocal.cmd(
                self.node.id,
                'cmd.run',
                [self.node.ldapDsJavaPropCommand],
            )
            self.logger.debug("{}".format(self.node.ldapDsJavaPropCommand))
        except Exception as exc:
            self.logger.error("error running dsjavaproperties: %s" % exc)

        # wait for opendj being started before proceeding to next step
        try:
            self.logger.info(
                "warming up opendj server; "
                "sleeping for {} seconds".format(self.node.ldapStartTimeOut))
            time.sleep(self.node.ldapStartTimeOut)
        except Exception as exc:
            self.logger.error(exc)

    def configure_opendj(self):
        config_changes = [
            ['set-global-configuration-prop', '--set', 'single-structural-objectclass-behavior:accept'],
            ['set-attribute-syntax-prop', '--syntax-name', '"Directory String"', '--set', 'allow-zero-length-values:true'],
            ['set-password-policy-prop', '--policy-name', '"Default Password Policy"', '--set', 'allow-pre-encoded-passwords:true'],
            ['set-log-publisher-prop', '--publisher-name', '"File-Based Audit Logger"', '--set', 'enabled:true'],
            ['create-backend', '--backend-name', 'site', '--set', 'base-dn:o=site', '--type local-db', '--set', 'enabled:true'],
        ]

        try:
            for changes in config_changes:
                dsconfigCmd = " ".join([self.node.ldapDsconfigCommand,
                                        '--trustAll',
                                        '--no-prompt',
                                        '--hostname',
                                        self.node.local_hostname,
                                        '--port',
                                        self.node.ldap_admin_port,
                                        '--bindDN',
                                        '"%s"' % self.node.ldap_binddn,
                                        '--bindPasswordFile',
                                        self.node.ldapPassFn] + changes)
                self.logger.info("configuring opendj config changes: {}".format(dsconfigCmd))
                # self.logger.debug("{}".format(dsconfigCmd))
                self.saltlocal.cmd(self.node.id, 'cmd.run', [dsconfigCmd])
                time.sleep(1)
        except Exception as exc:
            self.logger.error("error executing config changes: %s" % exc)

    def index_opendj(self):
        try:
            try:
                with open(self.node.indexJson, 'r') as fp:
                    index_json = json.load(fp)
            except Exception as exc:
                self.logger.error(exc)
                index_json = []

            if index_json:
                for attrDict in index_json:
                    attr_name = attrDict['attribute']
                    index_types = attrDict['index']

                    for index_type in index_types:
                        self.logger.info("creating %s index for attribute %s" % (index_type, attr_name))
                        indexCmd = " ".join([self.node.ldapDsconfigCommand,
                                             'create-local-db-index',
                                             '--backend-name',
                                             'userRoot',
                                             '--type',
                                             'generic',
                                             '--index-name',
                                             attr_name,
                                             '--set',
                                             'index-type:%s' % index_type,
                                             '--set',
                                             'index-entry-limit:4000',
                                             '--hostName',
                                             self.node.local_hostname,
                                             '--port',
                                             self.node.ldap_admin_port,
                                             '--bindDN',
                                             '"%s"' % self.node.ldap_binddn,
                                             '-j', self.node.ldapPassFn,
                                             '--trustAll',
                                             '--noPropertiesFile',
                                             '--no-prompt'])
                        self.saltlocal.cmd(self.node.id, 'cmd.run', [indexCmd])
                        self.logger.debug("{}".format(indexCmd))
            else:
                self.logger.warn("no indexes found %s" % self.node.indexJson)
        except Exception as exc:
            self.logger.error("error occured during LDAP indexing: %s" % exc)

    def import_ldif(self):
        # template's context
        ctx = {
            "oxauth_client_id": self.cluster.oxauth_client_id,
            "oxauthClient_encoded_pw": self.cluster.oxauth_client_encoded_pw,
            "encoded_ldap_pw": self.cluster.encoded_ldap_pw,
            "encoded_ox_ldap_pw": self.cluster.encoded_ox_ldap_pw,
            "inumAppliance": self.cluster.inumAppliance,
            "hostname": self.node.local_hostname,
            "hostname_oxauth_cluster": self.cluster.hostname_oxauth_cluster,
            "hostname_oxtrust_cluster": self.cluster.hostname_oxtrust_cluster,
            "ldaps_port": self.node.ldaps_port,
            "ldap_binddn": self.node.ldap_binddn,
            "inumOrg": self.cluster.inumOrg,
            "inumOrgFN": self.cluster.inumOrgFN,
            "orgName": self.cluster.orgName,
        }

        ldifFolder = '%s/ldif' % self.node.ldapBaseFolder
        self.saltlocal.cmd(
            self.node.id,
            "cmd.run",
            ["mkdir -p {}".format(ldifFolder)]
        )

        for ldif_file in self.node.ldif_files:
            # render templates
            rendered_content = ""
            try:
                with codecs.open(ldif_file, "r", encoding="utf-8") as fp:
                    rendered_content = fp.read() % ctx
            except Exception as exc:
                self.logger.error(exc)

            try:
                file_basename = os.path.basename(ldif_file)

                # save to temporary file
                local_dest = os.path.join(self.build_dir, file_basename)
                with codecs.open(local_dest, "w", encoding="utf-8") as fp:
                    fp.write(rendered_content)

                # copy to minion
                remote_dest = os.path.join(ldifFolder, file_basename)
                self.logger.info("copying {}".format(local_dest))
                run("salt-cp {} {} {}".format(self.node.id, local_dest,
                                              remote_dest))

                if file_basename == "o_site.ldif":
                    backend_id = "site"
                else:
                    backend_id = "userRoot"
                importCmd = " ".join([
                    self.node.importLdifCommand,
                    '--ldifFile',
                    remote_dest,
                    '--backendID',
                    backend_id,
                    '--hostname',
                    self.node.local_hostname,
                    '--port',
                    self.node.ldap_admin_port,
                    '--bindDN',
                    '"%s"' % self.node.ldap_binddn,
                    '-j',
                    self.node.ldapPassFn,
                    '--append',
                    '--trustAll',
                ])
                self.saltlocal.cmd(self.node.id, 'cmd.run', [importCmd])
                self.logger.debug("{}".format(importCmd))
                time.sleep(1)
            except Exception as exc:
                self.logger.error(exc)
            finally:
                # remove temporary file
                os.unlink(local_dest)

    def export_opendj_public_cert(self):
        # Load password to acces OpenDJ truststore
        openDjPinFn = '%s/config/keystore.pin' % self.node.ldapBaseFolder
        openDjTruststoreFn = '%s/config/truststore' % self.node.ldapBaseFolder
        openDjPin = "`cat {}`".format(openDjPinFn)

        self.saltlocal.cmd(
            self.node.id,
            ["cmd.run", "cmd.run"],
            [
                ["mkdir -p {}".format(os.path.dirname(self.node.openDjCertFn))],
                ["touch {}".format(self.node.openDjCertFn)],
            ],
        )

        # Export public OpenDJ certificate
        self.logger.info("exporting OpenDJ certificate")
        cmdsrt = ' '.join([self.node.keytoolCommand,
                           '-exportcert',
                           '-keystore',
                           openDjTruststoreFn,
                           '-storepass',
                           openDjPin,
                           '-file',
                           self.node.openDjCertFn,
                           '-alias',
                           'server-cert',
                           '-rfc'])
        self.saltlocal.cmd(self.node.id, 'cmd.run', [cmdsrt])
        self.logger.debug("{}".format(cmdsrt))

        # Import OpenDJ certificate into java truststore
        cmdstr = ' '.join([
            "/usr/bin/keytool", "-import", "-trustcacerts", "-alias",
            "{}_opendj".format(self.node.local_hostname),
            "-file", self.node.openDjCertFn,
            "-keystore", self.node.defaultTrustStoreFN,
            "-storepass", "changeit", "-noprompt",
        ])
        self.logger.info("importing OpenDJ certificate into Java truststore")
        self.saltlocal.cmd(self.node.id, 'cmd.run', [cmdstr])
        self.logger.debug("{}".format(cmdsrt))

    def get_existing_node(self, node_id):
        try:
            self.logger.info("getting existing node {}".format(node_id))
            node = db.get(node_id, "nodes")
            return node
        except IndexError as exc:
            self.logger.warn(exc)

    def replicate_from(self, existing_node):
        base_dns = ("o=gluu", "o=site",)
        for base_dn in base_dns:
            setup_obj = ldapSetup(existing_node, self.cluster, logger=self.logger)

            # creates temporary password file
            setup_obj.write_ldap_pw()

            try:
                enable_cmd = " ".join([
                    "/opt/opendj/bin/dsreplication", "enable",
                    "--host1", existing_node.local_hostname,
                    "--port1", existing_node.ldap_admin_port,
                    "--bindDN1", "'{}'".format(existing_node.ldap_binddn),
                    "--bindPasswordFile1", self.node.ldapPassFn,
                    "--replicationPort1", existing_node.ldap_replication_port,
                    "--host2", self.node.local_hostname,
                    "--port2", self.node.ldap_admin_port,
                    "--bindDN2", "'{}'".format(self.node.ldap_binddn),
                    "--bindPasswordFile2", self.node.ldapPassFn,
                    "--replicationPort2", self.node.ldap_replication_port,
                    "--adminUID", "admin",
                    "--adminPasswordFile", self.node.ldapPassFn,
                    "--baseDN", "'{}'".format(base_dn),
                    "--secureReplication1", "--secureReplication2",
                    "-X", "-n",
                ])
                self.logger.info("enabling {!r} replication between {} and {}".format(
                    base_dn, existing_node.local_hostname, self.node.local_hostname,
                ))
                self.saltlocal.cmd(self.node.id, "cmd.run", [enable_cmd])

                # wait before initializing the replication to ensure it
                # has been enabled
                time.sleep(10)
            except Exception as exc:
                self.logger.error("error enabling {!r} replication: {}".format(base_dn, exc))

            try:
                init_cmd = " ".join([
                    "/opt/opendj/bin/dsreplication", "initialize",
                    "--baseDN", "'{}'".format(base_dn),
                    "--adminUID", "admin",
                    "--adminPasswordFile", self.node.ldapPassFn,
                    "--hostSource", existing_node.local_hostname,
                    "--portSource", existing_node.ldap_admin_port,
                    "--hostDestination", self.node.local_hostname,
                    "--portDestination", self.node.ldap_admin_port,
                    "-X", "-n"
                ])
                self.logger.info("initializing {!r} replication between {} and {}".format(
                    base_dn, existing_node.local_hostname, self.node.local_hostname,
                ))
                self.saltlocal.cmd(self.node.id, "cmd.run", [init_cmd])
                time.sleep(5)
            except Exception as exc:
                self.logger.error("error initializing {!r} replication: {}".format(base_dn, exc))

            # cleanups temporary password file
            setup_obj.delete_ldap_pw()

    def setup(self):
        self.logger.info("LDAP setup is started")
        start = time.time()

        self.write_ldap_pw()
        self.setup_opendj()
        self.configure_opendj()
        self.index_opendj()

        if self.cluster.ldap_nodes:
            # Initialize data from existing ldap node.
            # To create fully meshed replication, update the other ldap
            # nodes to use this new ldap node as a master.
            for node_id in self.cluster.ldap_nodes:
                existing_node = self.get_existing_node(node_id)
                if existing_node:
                    self.replicate_from(existing_node)
        else:
            # If no ldap nodes exist, import auto-generated base ldif data
            self.import_ldif()

        self.export_opendj_public_cert()

        # TODO: 2-way password encryption so we can delete LDAP password file
        self.delete_ldap_pw()

        elapsed = time.time() - start
        self.logger.info("LDAP setup is finished ({} seconds)".format(elapsed))
        return True

    def after_setup(self):
        """Runs post-setup.
        """
        # Currently, we need to update oxAuth and oxTrust LDAP properties
        # TODO: use signals?
        for node_id in self.cluster.oxauth_nodes:
            node = db.get(node_id, "nodes")
            if not node:
                continue

            setup_obj = OxAuthSetup(node, self.cluster, logger=self.logger)
            setup_obj.render_ldap_props_template()

        for node_id in self.cluster.oxtrust_nodes:
            node = db.get(node_id, "nodes")
            if not node:
                continue

            setup_obj = OxTrustSetup(node, self.cluster, logger=self.logger)
            setup_obj.render_ldap_props_template()
