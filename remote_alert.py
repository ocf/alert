#!/usr/bin/env python

import SocketServer, SimpleHTTPServer, urllib, threading, itertools, sys, ldap
from ircbot import SingleServerIRCBot as Bot

httpPort = 27000

ircChannel = "#rebuild"
ircNick = "nattominions"
ircServer = "irc.ocf.berkeley.edu"
ircPort = 6667

receivers = []

class RemoteAlertIRCClient(Bot):
  def __init__(self, channel, nickname, server, port=6667):
    Bot.__init__(self, [(server, port)], nickname, nickname)
    self.channel = channel
    
  def on_welcome(self, c, e):
    c.join(self.channel)
  
  def message(self, text):
    self.connection.privmsg(self.channel, text)

  def terminate(self):
     self.connection.disconnect("Farewell")

class WithInitTCPServer(SocketServer.TCPServer):
  allow_reuse_address = True # -__-

  def __init__(self, server_address, RequestHandlerClass, receivers):
    SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
    self.receivers = receivers
    
  def finish_request(self, request, client_address):
    self.RequestHandlerClass(request, client_address, self, self.receivers)

class RemoteAlert(SimpleHTTPServer.SimpleHTTPRequestHandler):
  nickRepeat = 3
  
  def __init__(self, request, client_address, server, receivers):
    self.receivers = receivers
    SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, request, client_address, server)
    
  def log_message(self, format, *args):
    pass
    
  def do_GET(self):
    target = urllib.unquote(self.path[1:]).split("/")
    print target
    if len(target) != 3:
      self.bureaucracy("Parameters incorrect: /TARGET/MESSAGE")
      return
    # Still broken
    if target[1] == "admin" and target[2] == "shutdown":
      for r in self.receivers:
        r.terminate()
      self.server.socket.close()
      self.server.shutdown()
    senderUid = target[0]
    # This is bad -- the ldap will be rebound each time the method is called. It's useless anyway as the entire class is re-instantiated (!) each time a request is performed.
    l = ldap.initialize("ldap://ldap.berkeley.edu")
    l.simple_bind_s("", "")
    
    search_filter = "(uid={0})".format(target[0])
    attrs = ["displayName"]

    ldap_entries = l.search_st("ou=People,dc=Berkeley,dc=EDU", ldap.SCOPE_SUBTREE, search_filter, attrs)

    name = [entry[1]["displayName"][0] for entry in ldap_entries][0] # More than one name? Too bad!

    message = "{0}, message from {1}: {2}".format(" ".join(itertools.repeat(target[1], self.nickRepeat)), name, target[2])
    for r in self.receivers:
      r.message(message)
    self.bureaucracy("Message delivered")
    
  def bureaucracy(self, text, response = 200, contentType = "text/plain"):
    self.send_response(response)
    self.send_header("Content-type", contentType)
    self.send_header("Content-length", len(text))
    self.end_headers()
    self.wfile.write(text)

bot = RemoteAlertIRCClient(ircChannel, ircNick, ircServer, ircPort)
receivers.append(bot)
bot_thread = threading.Thread(target = bot.start)
bot_thread.start()
    
httpd = WithInitTCPServer(('', httpPort), RemoteAlert, receivers = receivers)
httpd.serve_forever()
