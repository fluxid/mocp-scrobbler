#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import urllib
import httplib
from urlparse import urlparse
import time
import md5
import re

_CLIENTNAME = 'tst' # Oficjalny, testowy
#_CLIENTNAME = 'mcl' # Mój własny, oficjalny
_CLIENTVER = '1.0'

_USER = 'fluxid'
_PASS = 'wtmicros'

_SCROB_FRAC = 0.9

session = ''
np_link = ''
sub_link = ''

class BannedException(Exception): pass
class BadAuthException(Exception): pass
class BadTimeException(Exception): pass
class FailedException(Exception): pass
class BadSessionException(Exception): pass
class HardErrorException(Exception): pass

def send_encoded(url, data):
	url2 = urlparse(url)
	host = url2[1]
	request = (url2[2] or '/') + (url2[4] and '?' + url2[4])
	
	data2 = urllib.urlencode(data)
	
	try:
		http = httplib.HTTPConnection(host)
		http.putrequest('POST', request)
		http.putheader('Content-Type', 'application/x-www-form-urlencoded')
		http.putheader('User-Agent', 'Fluxid MOC Scrobbler 0.1 Alpha')
		http.putheader('Content-Length', str(len(data2)))
		http.endheaders()
		http.send(data2)
		response = http.getresponse().read().upper().strip()
	except:
		raise HardErrorException
	if response == 'BADSESSION':
		raise BadSessionException
	elif response.startswith('FAILED'):
		raise FailedException, f[0].split(' ', 1)[1].strip()

def authorize():
	global token
	timestamp = time.time()
	token = md5.new(md5.new(_PASS).hexdigest() + str(int(timestamp))).hexdigest()
	link = 'http://post.audioscrobbler.com/?hs=true&p=1.2.1&c=%s&v=%s&u=%s&t=%d&a=%s'% (_CLIENTNAME, _CLIENTVER, _USER, timestamp, token)
	f = urllib.urlopen(link)
	if f:
		f = f.readlines()
		first = f[0].upper().strip()
		if first == 'OK':
			global session, np_link, sub_link
			session = f[1].strip()
			np_link = f[2].strip()
			sub_link = f[3].strip()
		elif first == 'BANNED':
			raise BannedException
		elif first == 'BADAUTH':
			raise BadAuthException
		elif first == 'BADTIME':
			raise BadTimeException
		elif first.startswith('FAILED'):
			raise FailedException, f[0].split(' ', 1)[1].strip()
		else:
			raise HardErrorException
	else:
		raise HardErrorException

def get_mocp():
	mocp = os.popen("mocp -i")
	info = {}
	test = re.compile(r'^[a-zA-Z]+: .*')
	for line in mocp:
		if test.match(line):
			x = line.split(': ', 1)
			info[x[0].lower()] = x[1].strip()
	mocp.close()
	return info

def now_playing(track):
	send_encoded(np_link, {'s': session, 'a': track['artist'], 't': track['songtitle'], 'b': track['album'], 'l': track['totalsec'], 'n': '', 'm': ''})

def scrobble(track):
	send_encoded(sub_link, {'s': session, 'a[0]': track['artist'], 't[0]': track['songtitle'], 'i[0]': int(time.time()), 'o[0]': 'P', 'r[0]': '', 'l[0]': track['totalsec'], 'b[0]': track['album'], 'n[0]': '', 'm[0]': ''})

def diff(oldtrack, newtrack):
	if newtrack and not oldtrack:
		return True
	if not ('artist' in oldtrack and 'artist' in newtrack and 'songtitle' in oldtrack and 'songtitle' in newtrack):
		return False
	return not ( (oldtrack['artist'].lower() == newtrack['artist'].lower()) and (oldtrack['songtitle'].lower() == newtrack['songtitle'].lower()) )

def can_scrobble(track, frac):
	if not track:
		return False
	if 'totalsec' in track:
		total = float(track['totalsec'])
	else:
		total = 0;
	if total <= 30: return False
	if 'currentsec' in track:
		current = int(track['currentsec'])
	else:
		current = 0;
	
	return (current > total * frac)

def can_scrobble_min(track):
	if not track:
		return False
	if 'totalsec' in track:
		total = float(track['totalsec'])
	else:
		total = 0;
	if total <= 30: return False
	if 'currentsec' in track:
		current = int(track['currentsec'])
	else:
		current = 0;
	return (current > 240) or (current > total * 0.5)

def main():
	try:
		authorize()
	except BannedException:
		print 'Error while authorizing: your account is banned.'
		return
	except BadAuthException:
		print 'Error while authorizing: incorrect username or password. Please check your login settings and try again.'
		return
	except BadTimeException:
		print 'Error while authorizing: incorrect time setting. Please check your clock settings and try again.'
		return
	except FailedException, e:
		print 'Error while authorizing: general failure. Reason: "%s"' % e.message
		return
	except HardErrorException:
		print 'Critical error while authorizing. Check your internet connection and try again. Maybe servers are dead?'
		return
	
	print 'Authorized'
	
	unscrobbled = True
	unnotified = True
	
	newtrack = None
	oldtrack = None
	
	maxsec = 0
	
	while True:
		try:
			while True:
				newtrack = get_mocp()
				if 'state' in newtrack and newtrack['state'].lower() == 'play':
					a = diff(oldtrack, newtrack)
					b = not a and (int(newtrack['totalsec']) - 15 < maxsec) and (int(newtrack['currentsec']) < 15)
					if a or b:
						if oldtrack: oldtrack['currentsec'] = maxsec
						if unscrobbled and can_scrobble_min(oldtrack):
							print 'Scrobbled [on change]'
							scrobble(oldtrack)
						
						if b:
							print 'Now playing (repeated): %s - %s (%s)' % (newtrack['songtitle'], newtrack['artist'], newtrack['album'])
						else:
							print 'Now playing: %s - %s (%s)' % (newtrack['songtitle'], newtrack['artist'], newtrack['album'])
						
						oldtrack = newtrack
						unscrobbled = True
						unnotified = True
						maxsec = 0
					
					maxsec = max(maxsec, int(newtrack['currentsec']))
					
					if unnotified:
						now_playing(newtrack)
						print 'Notify sent.'
						unnotified = False
					
					if unscrobbled and can_scrobble(newtrack, _SCROB_FRAC):
						print 'Scrobbled [on %d%%]' % int(_SCROB_FRAC * 100)
						scrobble(newtrack)
						unscrobbled = False
					
				time.sleep(2)
		except BadSessionException:
			authorize()
		except FailedException, e:
			print 'Error while submission: general failure. Reason: "%s". Continuing after 5 seconds (scrobbling cache is unimplemented yet)' % e.message
			time.sleep(5)
		except HardErrorException:
			print 'Critical error while submission. Check your internet connection. Trying again after 10 seconds (scrobbling cache is unimplemented yet)'
			time.sleep(10)
		except KeyboardInterrupt:
			break
#		except Exception, e:
#			print e
#		time.sleep(5)
#		print 'Continuing'

#	print session, np_link, sub_link
#	try:
#		pid = os.fork()
#		if pid:
#			print 'Scrobbler daemonized with PID %d' % pid
#			sys.exit(0)
#		forked = True
#	except Exception, e:
#		forked = False
#		logger.critical('Could not daemonize. Scrobbler will run in foreground. ("%s")' % e)
#	
#	while True:

main()
