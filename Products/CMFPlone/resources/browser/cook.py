# -*- coding: utf-8 -*-
from cssmin import cssmin
from datetime import datetime
from plone.protect.interfaces import IDisableCSRFProtection
from plone.registry.interfaces import IRegistry
from plone.subrequest import subrequest
from Products.CMFPlone.interfaces.resources import IBundleRegistry
from Products.CMFPlone.interfaces.resources import IResourceRegistry
from Products.CMFPlone.resources.browser.combine import combine_bundles
from Products.CMFPlone.resources.browser.combine import get_override_directory
from slimit import minify
from StringIO import StringIO
from zExceptions import NotFound
from zope.component import getUtility
from zope.component.hooks import getSite
from zope.globalrequest import getRequest
from zope.interface import alsoProvides

import logging


logger = logging.getLogger('Products.CMFPlone')

REQUIREJS_RESET_PREFIX = """
/* reset requirejs definitions so that people who
   put requirejs in legacy compilation do not get errors */
var _old_define = define;
var _old_require = require;
define = undefined;
require = undefined;
try{
"""
REQUIREJS_RESET_POSTFIX = """
}catch(e){
    // log it
    if (typeof console !== "undefined"){
        console.log('Error loading javascripts!' + e);
    }
}finally{
    define = _old_define;
    require = _old_require;
}
"""


def cookWhenChangingSettings(context, bundle=None):
    """When our settings are changed, re-cook the not compilable bundles
    """
    registry = getUtility(IRegistry)
    resources = registry.collectionOfInterface(
        IResourceRegistry,
        prefix='plone.resources',
        check=False
    )
    if bundle is None:
        # default to cooking legacy bundle
        bundles = registry.collectionOfInterface(
            IBundleRegistry,
            prefix='plone.bundles',
            check=False
        )
        if 'plone-legacy' in bundles:
            bundle = bundles['plone-legacy']
        else:
            bundle = bundles.setdefault('plone-legacy')
            bundle.resources = []

    if not bundle.resources:
        # you can have a bundle without any resources defined and it's just
        # shipped as a legacy compiled js file
        return

    # Let's join all css and js
    css_file = ''
    cooked_js = REQUIREJS_RESET_PREFIX
    siteUrl = getSite().absolute_url()
    request = getRequest()
    for package in bundle.resources or []:
        if package not in resources:
            continue
        resource = resources[package]
        for css in resource.css:
            url = siteUrl + '/' + css
            response = subrequest(url)
            if response.status == 200:
                css_file += response.getBody()
                css_file += '\n'
            else:
                css_file += '\n/* Could not find resource: %s */\n\n' % url
        if not resource.js:
            continue
        url = siteUrl + '/' + resource.js
        response = subrequest(url)
        if response.status == 200:
            js = response.getBody()
            try:
                cooked_js += '\n/* resource: %s */\n%s' % (
                    resource.js,
                    minify(js, mangle=False, mangle_toplevel=False)
                )
            except SyntaxError:
                cooked_js += '\n/* resource(error cooking): %s */\n%s' % (
                    resource.js, js)
        else:
            cooked_js += '\n/* Could not find resource: %s */\n\n' % url

    cooked_js += REQUIREJS_RESET_POSTFIX
    cooked_css = cssmin(css_file)

    js_path = bundle.jscompilation
    css_path = bundle.csscompilation

    if not js_path:
        logger.warn('Could not compile js/css for bundle as there is '
                    'no jscompilation setting')
        return

    # Storing js
    resource_path = js_path.split('++plone++')[-1]
    resource_name, resource_filepath = resource_path.split('/', 1)
    container = get_override_directory()
    if resource_name not in container:
        container.makeDirectory(resource_name)
    try:
        folder = container[resource_name]
        fi = StringIO(cooked_js)
        folder.writeFile(resource_filepath, fi)

        if css_path:
            # Storing css if defined
            resource_path = css_path.split('++plone++')[-1]
            resource_name, resource_filepath = resource_path.split('/', 1)
            if resource_name not in container:
                container.makeDirectory(resource_name)
            folder = container[resource_name]
            fi = StringIO(cooked_css)
            folder.writeFile(resource_filepath, fi)
        bundle.last_compilation = datetime.now()
        # setRequest(original_request)
    except NotFound:
        logger.info('Error compiling js/css for the bundle')

    # refresh production meta bundles
    combine_bundles(context)

    # Disable CSRF protection on this request
    alsoProvides(request, IDisableCSRFProtection)
