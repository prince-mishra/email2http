import webapp2
import json
import logging
import urllib
from google.appengine.ext import db
from google.appengine.ext.webapp.mail_handlers import InboundMailHandler
from google.appengine.ext import ndb
from google.appengine.api import urlfetch


_DEBUG = True
class IncomingEmail(ndb.Model):
    subject  = ndb.StringProperty()
    sender   = ndb.StringProperty()
    to       = ndb.StringProperty()
    date     = ndb.StringProperty()
    body     = ndb.TextProperty()
    original = ndb.TextProperty()
    created  = ndb.DateTimeProperty(auto_now_add = True)

class WebHook(ndb.Model):
    email    = ndb.StringProperty()
    config   = ndb.TextProperty()
    created  = ndb.DateTimeProperty(auto_now_add = True)

class IncomingEmailHandler(InboundMailHandler):
    def receive(self, mail_message):
        email = IncomingEmail(
            subject     = mail_message.subject,
            sender      = mail_message.sender,
            to          = mail_message.to,
            date        = mail_message.date,
            body        = str([body.decode() for type, body in mail_message.bodies('text/plain') ]),
            original    = mail_message.original.as_string())
        email.put()
        logging.info("Received an email. " + str(mail_message.original))
        email_obj = {
                'sender'    : email.sender,
                'subject'   : email.subject,
                'to'        : email.to,
                'date'      : email.to,
                'body'      : email.body,
                'created'   : email.created.strftime('%Y-%m-%d %H:%M:%S.%f'),
        }
        self.execute_hooks(email_obj)

    def execute_hooks(self, email_obj):
        to = email_obj['to']
        cfgs = WebHook.query(WebHook.email == to)
        for c in cfgs:
            cdata = c.config
            rendered_cdata = cdata % {'body' : urllib.quote(json.dumps(email_obj))}
            config_obj = json.loads(rendered_cdata)
            url = config_obj['url'].strip()
            payload = json.dumps(config_obj['payload'])
            logging.info("Outgoing request for %s. Details %s" % (url, payload))
            result = urlfetch.fetch(url=url,
                payload=payload,
                method=urlfetch.POST)


class EmailStore(webapp2.RequestHandler):
    def get(self):
    	to = self.request.get('to').strip()
    	emails = IncomingEmail.query(IncomingEmail.to == to).order(-IncomingEmail.created)
    	logging.info("fetching email records for %s" % to)
    	response = {'data' : []}
    	for email in emails:
    		email_obj = {
    			'sender' 	: email.sender,
    			'subject'	: email.subject,
    			'to'		: email.to,
    			'date'		: email.to,
    			'body'		: email.body,
    			'created'	: email.created.strftime('%Y-%m-%d %H:%M:%S.%f')
    		}
    		response['data'].append(email_obj)
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(response))

class WebHookHandler(webapp2.RequestHandler):
    def get(self):
        configs = WebHook.query()
        response = {'data' : []}
        for cfg in configs:
            cfg_obj = {
                'email'     : cfg.email,
                'cfg'       : cfg.config,
                'created'   : cfg.created.strftime('%Y-%m-%d %H:%M:%S.%f'),


            }
            response['data'].append(cfg_obj)
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(response))

class WebHookCreateHandler(webapp2.RequestHandler):
    def post(self):
        emailid = self.request.POST['email']
        configtxt = self.request.POST['config']
        logging.info("ARGS %s %s" % (emailid, configtxt))
        wh = WebHook(
            email     = emailid,
            config      = configtxt)
        wh.put()
        logging.info("added webhook %s %s" % (emailid, configtxt))
        ret = {
            'success' : True,
            'msg'   : 'webhook added sucessfully for %s' % emailid
        }
        self.response.headers['Content-Type'] = 'application/json'
        self.response.write(json.dumps(ret))


app = webapp2.WSGIApplication([
    ('/emailstore/', EmailStore),IncomingEmailHandler.mapping(), ('/listwebhooks', WebHookHandler), ('/createwebhook', WebHookCreateHandler)
], debug=True)