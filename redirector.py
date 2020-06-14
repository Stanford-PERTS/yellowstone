"""Defines specific links that should be immediately redirected elsewhere.

N.B. None of these work unless they're also specified in app.yaml.
"""

import webapp2

# Reminder: 302's are temporary, 301's are permanent.

redirection_map = {
    '/go': ('https://neptune.perts.net/participate', 302),
    # Old home page links.
    '/login': ('https://neptune.perts.net/login', 302),
    '/logout': ('https://neptune.perts.net/logout', 302),
    '/perts': ('/', 301),
    '/PERTS': ('/', 301),
    # Old-style program abbreviations
    '/orientation/cb17': ('/orientation/cb', 301),
    '/orientation/cg17': ('/orientation/cg', 301),
    '/orientation/hg17': ('/orientation/hg', 301),
    # Orientation pages that have more direct URLs
    '/orientation/ep': ('/engage', 301),
    # Old program landing pages, which used to the hubspot inquiry form.
    '/orientation/highschool': ('/404', 302),
    # Alias for careers
    '/jobs': ('/careers', 301),
    # Alias for team section of about page.
    '/team': ('/about#team', 302),
    # CTC
    '/ctc': ('http://collegetransitioncollaborative.org', 301),
    '/cloud-security': ('/security#cloud-services', 301),
}


class RedirectionHandler(webapp2.RequestHandler):
    def get(self):
        url, code = redirection_map[self.request.path]
        if self.request.query_string:
            url = '{}?{}'.format(url, self.request.query_string)
        self.redirect(url, code=code)


app = webapp2.WSGIApplication(
    [(k, RedirectionHandler) for k, v in redirection_map.items()])
