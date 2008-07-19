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

def send_data(url, datax):
	url2 = urlparse(url)
	host = url2[1]
	request = (url2[2] or '/') + (url2[4] and '?' + url2[4])
	
	boundary = '--31337_36669_MIME_Boundary_Shit'
	
	data = []
	for (key, val) in datax.iteritems():
		data.append('--' + boundary)
		data.append('Content-Disposition: form-data; name="%s";' % key)
		data.append('Content-Type: text/plain')
		data.append('')
		data.append(val)
		data.append('')
	
	data.append('--' + boundary + '--')
	data2 = '\r\n'.join(data)
	print data2
	
	http = httplib.HTTPConnection(host)
	http.putrequest('POST', request)
	http.putheader('Content-Type', 'multipart/form-data; boundary=' + boundary)
	http.putheader('User-Agent', 'Fluxid MOC Scrobbler 0.1 Alpha')
	http.putheader('Content-Length', str(len(data2)))
	http.endheaders()
	http.send(data2)
	return http.getresponse().read()

def send_encoded(url, data):
	url2 = urlparse(url)
	host = url2[1]
	request = (url2[2] or '/') + (url2[4] and '?' + url2[4])
	
	data2 = urllib.urlencode(data)
	
	http = httplib.HTTPConnection(host)
	http.putrequest('POST', request)
	http.putheader('Content-Type', 'application/x-www-form-urlencoded')
	http.putheader('User-Agent', 'Fluxid MOC Scrobbler 0.1 Alpha')
	http.putheader('Content-Length', str(len(data2)))
	http.endheaders()
	http.send(data2)
	return http.getresponse().read()

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

def now_playing(track):
	print send_encoded(np_link, {'s': session, 'a': track['Artist'], 't': track['SongTitle'], 'b': track['Album'], 'l': track['TotalSec'], 'n': '', 'm': ''})

def scrobble(track):
	print 'Scrobbled!'
	print send_encoded(sub_link, {'s': session, 'a[0]': track['Artist'], 't[0]': track['SongTitle'], 'i[0]': int(time.time()), 'o[0]': 'P', 'r[0]': '', 'l[0]': track['TotalSec'], 'b[0]': track['Album'], 'n[0]': '', 'm[0]': ''})


def diff(track1, track2):
	return not (track1['Artist'].lower() == track2['Artist'].lower() and track1['SongTitle'].lower() == track2['SongTitle'].lower())

def can_scrobble(track):
	return ((int(track['TotalSec']) >= 240) and (int(track['CurrentSec']) > (float(track['TotalSec']) * _SCROB_FRAC)))

def can_scrobble2(track):
	return ((int(track['TotalSec']) >= 240) and (int(track['CurrentSec']) > (float(track['TotalSec']) * 0.5)))

def main():
	authorize()
	oldtrack = None
	newtrack = None
	unscrobbled = True
	counter = 0
	while True:
		newtrack = get_mocp()
		if newtrack['State'] == 'PLAY':
			if oldtrack:
				if diff(oldtrack, newtrack):
					if unscrobbled and can_scrobble2(oldtrack):
						scrobble(oldtrack)
					oldtrack = newtrack
					unscrobbled = True
					counter = 0
				
				if unscrobbled and can_scrobble(newtrack):
					scrobble(newtrack)
					unscrobbled = False
						
				if unscrobbled:
					if counter == 0:
						now_playing(newtrack)
					counter += 1
					counter %= 4
			else:
				oldtrack = newtrack
				continue
		time.sleep(5)
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
