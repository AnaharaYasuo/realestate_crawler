# -*- coding: utf-8 -*-
import webapp2
from google.appengine.ext.webapp.util import run_wsgi_app
import getsumifu


class SumifuHandler(webapp2.RequestHandler):

    def get(self):
        getsumifu.main()

        
class MitsuiHandler(webapp2.RequestHandler):

    def get(self):
        getsumifu.main()


app = webapp2.WSGIApplication(routes=[('/api/scraper/sumifu', SumifuHandler),
                                      ('/api/scraper/mitsui', MitsuiHandler), ],
                                     debug=True)


def main():
    run_wsgi_app(app)


if __name__ == "__main__":
    main()
