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

'''The app module, containing the app factory function.'''
from flask import Flask

from gluuapi.settings import ProdConfig
from gluuapi.extensions import (
    restapi,
)
from gluuapi.resource.node import Node
from gluuapi.resource.node import NodeList
from gluuapi.resource.cluster import Cluster
from gluuapi.resource.cluster import ClusterList
from gluuapi.resource import ProviderResource
from gluuapi.resource import ProviderListResource
from gluuapi.database import db


def create_app(config_object=ProdConfig):
    '''An application factory, as explained here:
        http://flask.pocoo.org/docs/patterns/appfactories/

    :param config_object: The configuration object to use.
    '''
    app = Flask(__name__)
    app.config.from_object(config_object)
    register_resources()
    register_extensions(app)
    return app


def register_extensions(app):
    restapi.init_app(app)
    db.init_app(app)


def register_resources():
    restapi.add_resource(NodeList, '/node')
    restapi.add_resource(Node, '/node/<string:node_id>')
    restapi.add_resource(ClusterList, '/cluster')
    restapi.add_resource(Cluster, '/cluster/<string:cluster_id>')
    restapi.add_resource(ProviderResource, "/provider/<string:provider_id>", endpoint="provider")
    restapi.add_resource(ProviderListResource, "/provider", endpoint="providerlist")
