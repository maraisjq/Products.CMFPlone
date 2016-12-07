# -*- coding: utf-8 -*-
from Acquisition import aq_base
from datetime import datetime
from plone.registry.interfaces import IRegistry
from plone.resource.file import FilesystemFile
from plone.resource.interfaces import IResourceDirectory
from Products.CMFPlone.interfaces import IBundleRegistry
from Products.CMFPlone.interfaces.resources import OVERRIDE_RESOURCE_DIRECTORY_NAME  # noqa
from StringIO import StringIO
from zExceptions import NotFound
from zope.component import getUtility
from zope.component import queryUtility

import logging
import re


PRODUCTION_RESOURCE_DIRECTORY = 'production'
logger = logging.getLogger(__name__)


def get_production_resource_directory():
    """the directory, where the current production resources are located
    """
    persistent_directory = queryUtility(IResourceDirectory, name='persistent')
    if persistent_directory is None:
        return ''
    container = persistent_directory[OVERRIDE_RESOURCE_DIRECTORY_NAME]
    try:
        production_folder = container[PRODUCTION_RESOURCE_DIRECTORY]
    except NotFound:
        return '{0}/++unique++1'.format(PRODUCTION_RESOURCE_DIRECTORY)
    if 'timestamp.txt' not in production_folder:
        return '{0}/++unique++1'.format(PRODUCTION_RESOURCE_DIRECTORY)
    timestamp = production_folder.readFile('timestamp.txt')
    return '{0}/++unique++{1}'.format(PRODUCTION_RESOURCE_DIRECTORY, timestamp)


def get_resource(context, path):
    """fetch resource content from a given path
    """
    if path.startswith('++plone++'):
        # ++plone++ resources can be customized, we return their override
        # value if any
        overrides = get_override_directory(context)
        filepath = path[9:]
        if overrides.isFile(filepath):
            return overrides.readFile(filepath)

    try:
        resource = context.unrestrictedTraverse(path)
    except NotFound:
        logger.warn(
            u'Could not find resource {0}. '
            u'You may have to create it first.'.format(path)
        )
        return

    if isinstance(resource, FilesystemFile):
        directory, sep, filename = path.rpartition('/')
        return context.unrestrictedTraverse(directory).readFile(filename)
    elif hasattr(aq_base(resource), 'GET'):
        # for FileResource
        return resource.GET()
    else:
        # any BrowserView
        return resource()


def write_js(context, folder, meta_bundle):
    sio = StringIO()
    registry = getUtility(IRegistry)

    # default resources
    if (
        meta_bundle == 'default' and
        registry.records.get('plone.resources/jquery.js')
    ):
        sio.write(
            get_resource(
                context,
                registry.records['plone.resources/jquery.js'].value
            )
        )
        sio.write('\n')
        sio.write(
            get_resource(
                context,
                registry.records['plone.resources.requirejs'].value
            )
        )
        sio.write('\n')
        sio.write(
            get_resource(
                context,
                registry.records['plone.resources.configjs'].value
            )
        )

    # bundles
    bundles = registry.collectionOfInterface(
        IBundleRegistry,
        prefix='plone.bundles',
        check=False
    )
    for bundle in bundles.values():
        if bundle.merge_with == meta_bundle and bundle.jscompilation:
            resource = get_resource(context, bundle.jscompilation)
            if resource:
                sio.write(resource)
                sio.write('\n')

    folder.writeFile(meta_bundle + '.js', sio)


def write_css(context, folder, meta_bundle):
    sio = StringIO()
    registry = getUtility(IRegistry)

    bundles = registry.collectionOfInterface(
        IBundleRegistry,
        prefix='plone.bundles',
        check=False
    )
    for bundle in bundles.values():
        if bundle.merge_with == meta_bundle and bundle.csscompilation:
            css = get_resource(context, bundle.csscompilation)
            if not css:
                continue
            (path, sep, filename) = bundle.csscompilation.rpartition('/')
            # Process relative urls:
            # we prefix with current resource path any url not starting with
            # '/' or http: or data:
            css = re.sub(
                r"""(url\(['"]?(?!['"]?([a-z]+:|\/)))""",
                r'\1{0}/'.format(path),
                css)
            sio.write(css + '\n')

    folder.writeFile(meta_bundle + '.css', sio)


def get_override_directory(context):
    """the zodb directory.

    used for
    - overriding FileSystem resources and
    - storing combined production merge-bundle
    """
    persistent_directory = queryUtility(IResourceDirectory, name='persistent')
    if persistent_directory is None:
        return
    if OVERRIDE_RESOURCE_DIRECTORY_NAME not in persistent_directory:
        persistent_directory.makeDirectory(OVERRIDE_RESOURCE_DIRECTORY_NAME)
    return persistent_directory[OVERRIDE_RESOURCE_DIRECTORY_NAME]


def combine_bundles(context):
    container = get_override_directory(context)
    if PRODUCTION_RESOURCE_DIRECTORY not in container:
        container.makeDirectory(PRODUCTION_RESOURCE_DIRECTORY)
    production_folder = container[PRODUCTION_RESOURCE_DIRECTORY]

    # store timestamp
    fi = StringIO()
    fi.write(datetime.now().isoformat())
    production_folder.writeFile('timestamp.txt', fi)

    # generate new combined bundles
    write_js(context, production_folder, 'default')
    write_js(context, production_folder, 'logged-in')
    write_css(context, production_folder, 'default')
    write_css(context, production_folder, 'logged-in')
