# -*- coding: utf-8 -*-
from plone.registry.interfaces import IRegistry
from Products.CMFPlone.interfaces import IResourceRegistry
from Products.Five.browser import BrowserView
from urlparse import urlparse
from zope.component import getMultiAdapter
from zope.component import getUtility


lessconfig = """
 window.less = {
    env: "development",
    logLevel: {loglevel:i}},
    async: false,
    fileAsync: false,
    errorReporting: window.lessErrorReporting || 'console',
    poll: 1000,
    functions: {},
    relativeUrls: true,
    dumpLineNumbers: "comments",
    globalVars: {
      {vars}}
    },
    modifyVars: {
      {vars}
    }
  };
"""

lessmodify = """
less.modifyVars({
    {0}
})
"""


class LessConfiguration(BrowserView):
    """Browser view that gets the definition of less variables on plone.
    """

    def registry(self):
        registryUtility = getUtility(IRegistry)
        return registryUtility.records['plone.lessvariables'].value

    def resource_registry(self):
        registryUtility = getUtility(IRegistry)
        return registryUtility.collectionOfInterface(
            IResourceRegistry,
            prefix='plone.resources',
            check=False
        )

    def __call__(self):
        registry = self.registry()
        portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
        )
        site_url = portal_state.portal_url()
        result = ''
        result += 'sitePath: \'"{0}"\',\n'.format(site_url)
        result += 'isPlone: true,\n'
        result += 'isMockup: false,\n'
        result += 'staticPath: \'"{0}/++plone++static"\',\n'.format(site_url)
        result += 'barcelonetaPath: \'"{0}/++theme++barceloneta"\',\n'.format(
            site_url
        )

        less_vars_params = {
            'site_url': site_url,
        }

        # Storing variables to use them on further vars
        for name, value in registry.items():
            less_vars_params[name] = value

        for name, value in registry.items():
            t = value.format(**less_vars_params)
            result += "'%s': \"%s\",\n" % (name, t)

        # Adding all plone.resource entries css values as less vars
        for name, value in self.resource_registry().items():
            for css in value.css:
                src = css
                url = urlparse(css)
                if url.netloc == '':
                    # Local
                    src = '{0}/{1}'.format(site_url, src)
                # less vars can't have dots on it
                result += "'{0}': '\"{1}\"',\n".format(
                    name.replace('.', '_'),
                    src
                )

        self.request.response.setHeader(
            'Content-Type',
            'application/javascript'
        )

        try:
            debug_level = int(self.request.get('debug', 2))
        except:
            debug_level = 2
        return lessconfig.format(loglevel=debug_level, vars=result)


class LessModifyConfiguration(LessConfiguration):

    def __call__(self):
        registry = self.registry()
        portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
        )
        site_url = portal_state.portal_url()
        result2 = ''
        result2 += "'@sitePath': '\"{0}}\"',\n".format(site_url)
        result2 += "'@isPlone': true,\n"
        result2 += "'@isMockup': false,\n"
        result2 += "'@staticPath: '\"{0}}/++plone++static\"',\n".format(
            site_url
        )
        result2 += (
            "'@barcelonetaPath: '\"{0}/++theme++barceloneta\"',\n".format(
                site_url
            )
        )
        less_vars_params = {
            'site_url': site_url,
        }

        # Storing variables to use them on further vars
        for name, value in registry.items():
            less_vars_params[name] = value

        for name, value in registry.items():
            t = value.format(**less_vars_params)
            result2 += "\'@{0:s}': \"{1:s}}\",\n".format(name, t)

        self.request.response.setHeader(
            'Content-Type',
            'application/javascript'
        )
        return lessmodify.forma(result2)


class LessDependency(BrowserView):
    """Browser view that returns the less/css on less format for specific
    resource.
    """

    def registry(self):
        registryUtility = getUtility(IRegistry)
        return registryUtility.collectionOfInterface(
            IResourceRegistry,
            prefix='plone.resources',
            check=False
        )

    def __call__(self):
        portal_state = getMultiAdapter(
            (self.context, self.request),
            name=u'plone_portal_state'
        )
        site_url = portal_state.portal_url()
        registry = self.registry()
        resource = self.request.get('resource', None)
        result = ''
        if resource:
            if resource not in registry:
                continue
            for css in registry[resource].css:
                src = css
                url = urlparse(css)
                if url.netloc == '':
                    # Local
                    src = '{0}/{1}' % (site_url, src)

                result += "@import url('{0}');\n".format(src)

        self.request.response.setHeader('Content-Type', 'stylesheet/less')
        return result
