#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import urllib
import httplib
from urlparse import urlparse
import time
import md5
import re

_CLIENTNAME = 'tst'
_CLIENTVER = '1.0'

_USER = 'fluxid'
_PASS = 'wtmicros'

session = ''
np_link = ''
sub_link = ''

class BannedException(Exception): pass
class BadAuthException(Exception): pass
class BadTimeException(Exception): pass
class FailedException(Exception): pass
class BadSessionException(Exception): pass
class HardErrorException(Exception): pass

def send_data(url, data):
	url2 = urlparse(url)
	host = url2[1]
	request = (url2[2] or '/') + (url2[4] and '?' + url2[4])
	
	boundary = '--31337_36669_MIME_Boundary_Shit'
	
	for (key, val) in data.iteritems():
		data = []
		data.append('--' + boundary)
		data.append('Content-Disposition: form-data; name="%s"' % key)
		data.append('Content-Type: text/plain')
		data.append('')
		data.append(val)
		data.append('')
	
	data.append('--' + boundary + '--')
	data2 = '\r\n'.join(data)
	
	http = httplib.HTTPConnection(host)
	http.putrequest('POST', request)
	http.putheader('Content-Type', 'multipart/form-data; boundary=' + boundary)
	http.putheader('User-Agent', 'Fluxid MOC Scrobbler 0.1 Alpha')
	http.putheader('Content-Length', str(len(data2)))
	http.endheaders()
	http.send(data2)
	return http.getresponse().read()
	http.close()
	del data, data2

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
			info[x[0]] = x[1].strip()
	mocp.close()
	return info

def nowplaying(artist, title, album, length):
	print 'Wysłano nowplaying'
	print send_data(np_link, {'s': session, 'a': artist, 't': title, 'b': album, 'l': length, 'n': '', 'm': ''})

def scrobble():
	print 'Scrobbled!'

def main():
	authorize()
	oldtrack = None
	newtrack = None
	scrobbled = False
	while True:
		newtrack = get_mocp()
		if newtrack['State'] == 'PLAY':
			nowplaying(newtrack['Artist'], newtrack['SongTitle'], newtrack['Album'], newtrack['TotalSec'])
			if oldtrack:
				if not (oldtrack['Artist'].lower() == newtrack['Artist'].lower() and oldtrack['SongTitle'].lower() == newtrack['SongTitle'].lower()):
					if not scrobbled:
						pass
						# TODO
			else:
				oldtrack = newtrack
		time.sleep(10)
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
