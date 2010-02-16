#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author: Tomasz 'Fluxid' Kowalczyk
# e-mail: fluxid@o2.pl
# jid: fluxid@jabster.pl

import os
import sys
import urllib
import httplib
from urlparse import urlparse
import time
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
import re
import time
from threading import Thread
from ConfigParser import ConfigParser
import pickle
import logging
import getopt
import signal
import subprocess
import locale

_SCROB_FRAC = 0.9

class BannedException(Exception): pass
class BadAuthException(Exception): pass
class BadTimeException(Exception): pass
class FailedException(Exception): pass
class BadSessionException(Exception): pass
class HardErrorException(Exception): pass

INFO_RE = re.compile(r'^([a-zA-Z]+):\s*(.+)$')

class NullHandler(logging.Handler):
    def emit(record):
        pass

# I'm tired, hungry and pissed off now, so i'm writing this little piece
# of crap because i can't think of anything better at this moment

class StupidStreamHandler(logging.Handler):
    def __init__(self, stream, level=logging.NOTSET):
        self.s = stream
        logging.Handler.__init__(self, level)
        self.encoding = locale.getpreferredencoding()
    
    def emit(self, record):
        msg = self.format(record)
        if isinstance(msg, unicode):
            msg = msg.encode(self.encoding, 'replace')
        self.s.write(msg)
        self.s.write('\n')
        self.flush()

class StupidFileHandler(StupidStreamHandler):
    def __init__(self, fname, fwrite, level=logging.NOTSET):
        f = open(fname, fwrite)
        logging.Handler.__init__(self, f, level)
        self.encoding = 'utf-8'
    
    def close(self):
        logging.Handler.close(self)
        self.f.close()

# /crap

class Track(object):
    def __init__(self, artist, title, album, position=0, length=0):
        self.artist = artist.strip() if artist else ''
        self.title = title.strip() if title else ''
        self.album = album.strip() if album else ''
        self.length = int(length)
        self.position = int(position)

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.artist.lower() == other.artist.lower() and
                self.title.lower() == other.title.lower())

    def __ne__(self, other):
        return not self.__eq__(other)

    def __nonzero__(self):
        if self.artist and self.title: # and self.length:
            return True
        return False

    def __unicode__(self):
        if self.artist and self.title:
            if self.album:
                return u'%s - %s (%s)' % (self.artist, self.title, self.album)
            else:
                return u'%s - %s' % (self.title, self.artist)
        else:
            return u'None'

    def __str__(self):
        return self.__unicode__().encode(locale.getpreferredencoding())

    def __repr__(self):
        # It seems repr must be str not unicode...
        return '<Track: %s>' % self

class Scrobbler(Thread):
    def __init__(self, host, login, password):
        Thread.__init__(self)

        self.host = host
        self.login = login
        self.password = password
        self.session = None
        self.np_link = None
        self.sub_link = None
        self.cache = []
        self.playing = None
        self.notify_sent = False
        self.logger = None
        self._running = False
        self._authorized = False

    def send_encoded(self, url, data):
        url2 = urlparse(url)
        host = url2[1]
        request = (url2[2] or '/') + (url2[4] and '?' + url2[4])
        
        data = data.copy()
        data = dict([ (k.encode('utf-8'), v.encode('utf-8') if isinstance(v, unicode) else str(v)) for k, v in data.iteritems()])
        data2 = urllib.urlencode(data)
        
        try:
            http = httplib.HTTPConnection(host)
            http.putrequest('POST', request)
            http.putheader('Content-Type', 'application/x-www-form-urlencoded')
            http.putheader('User-Agent', 'Fluxid MOC Scrobbler 0.2')
            http.putheader('Content-Length', str(len(data2)))
            http.endheaders()
            http.send(data2)
            response = http.getresponse().read().upper().strip()
        except Exception, e:
            raise HardErrorException, str(e)
        if response == 'BADSESSION':
            raise BadSessionException
        elif response.startswith('FAILED'):
            raise FailedException, response.split(' ', 1)[1].strip() + (' POST = [%s]' % data2)

    def authorize(self):
        global token
        timestamp = time.time()
        token = md5(md5(self.password).hexdigest() + str(int(timestamp))).hexdigest()
        link = 'http://%s/?hs=true&p=1.2.1&c=mcl&v=1.0&u=%s&t=%d&a=%s' % (self.host, self.login, timestamp, token)
        try:
            f = urllib.urlopen(link)
        except Exception, e:
            raise HardErrorException, str(e)
        if f:
            f = f.readlines()
            first = f[0].upper().strip()
            if first == 'OK':
                self.session = f[1].strip()
                self.np_link = f[2].strip()
                self.sub_link = f[3].strip()
            elif first == 'BANNED':
                raise BannedException
            elif first == 'BADAUTH':
                raise BadAuthException
            elif first == 'BADTIME':
                raise BadTimeException
            elif first.startswith('FAILED'):
                raise FailedException, f[0].split(' ', 1)[1].strip()
            else:
                raise HardErrorException, u'Received unknown response from server: [%s]' % t
        else:
            raise HardErrorException, u'Empty response'
        self._authorized = True

    def scrobble(self, track, stream = False):
        if track:
            if stream:
                source = 'R'
            else:
                source = 'P'
            self.cache.append(( track, source, int(time.time()) ))

    def notify(self, track):
        if track:
            self.playing = track
            self.notify_sent = False
    
    def submit_scrobble(self, tracks):
        data = { 's': self.session }
        for i in range(len(tracks)):
            track, source, time = tracks[i]
            data.update({
                'a[%d]'%i: track.artist,
                't[%d]'%i: track.title,
                'i[%d]'%i: time,
                'o[%d]'%i: source,
                'r[%d]'%i: '',
                'l[%d]'%i: track.length or '',
                'b[%d]'%i: track.album,
                'n[%d]'%i: '',
                'm[%d]'%i: '',
            })
        self.send_encoded(self.sub_link, data)

    def submit_notify(self, track):
        self.send_encoded(self.np_link, {
            's': self.session,
            'a': track.artist,
            't': track.title,
            'b': track.album,
            'l': track.length or '',
            'n': '',
            'm': '',
        })
    
    def format_scrobbles(self, scrobbles):
        x = u', '.join([
            unicode(s[0])
            for s in scrobbles
        ])
        return u'[%s]' % x

    def run(self):
        if not self._authorized: return
        self._running = True
        while self._running:
            try:
                if self.cache:
                    slice = self.cache[:10]
                    if len(slice) == 1:
                        self.logger.debug(u'Submitting track: %s' % slice[0][0])
                    else:
                        self.logger.debug(u'Submitting %d tracks: %s' % (len(slice), self.format_scrobbles(slice)))
                    self.submit_scrobble(slice)
                    self.logger.debug(u'Submitted')
                    del self.cache[0:len(slice)]

                if self.playing and not self.notify_sent:
                    self.logger.debug(u'Sending notify')
                    self.submit_notify(self.playing)
                    self.logger.debug(u'Notify sent')
                    self.notify_sent = True

                time.sleep(1)
            except BadSessionException:
                self.logger.warning(u'Session timed out, authorizing')
                self.authorize() # Exceptions later
            except FailedException, e:
                self.logger.error(u'Error while submission: general failure. Trying again after 5 seconds. Reason: "%s".' % e.message)
                time.sleep(5)
            except HardErrorException, e:
                self.logger.error(u'Critical error while submission. Check your internet connection. Trying again after 5 seconds. Exception was: "%s"' % e.message)
                time.sleep(5)

    def stop(self):
        self._running = False

def get_mocp():
    info = {}
    try:
        p = subprocess.Popen('mocp -i', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    except:
        return (None, 'stop')
    pstdout, pstderr = p.communicate()
    for line in pstdout.splitlines():
        m = INFO_RE.match(line)
        if m:
            key, value = m.groups()
            if value:
                info[key.lower()] = value.strip().decode('utf8', 'replace') # mocp -i output isn't depended on locale

    artist = info.get('artist', '')
    title = info.get('songtitle', '')
    album = info.get('album', '')
    position = info.get('currentsec', 0)
    length = info.get('totalsec', 0)
    
    state = 'stop'
    if 'state' in info:
        state = info['state'].lower()
    return (Track(artist, title, album, position, length), state)

def main():
    try:
        locale.setlocale(locale.LC_ALL)
    except:
        pass

    path = os.path.expanduser('~/.mocpscrob/')
    configpath = path + 'config'
    cachepath = path + 'cache'
    pidfile = path + 'pid'
    logfile = path + 'scrobbler.log'

    if not os.path.isdir(path):
        os.mkdir(path)

    shortargs = 'dc:ovqhk'
    longargs = 'daemon config= offline verbose quiet help kill'
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortargs, longargs.split())
    except getopt.error, e:
        print >>sys.stderr, str(e)
        print >>sys.stderr, 'Use --help parameter to get more info'
        return
    
    daemon = False
    verbose = False
    quiet = False
    offline = False
    kill = False

    for o, v in opts:
        if o in ('-h', '--help'):
            print """mocp-scrobbler.py 0.2-rc1"""
            """Usage: mocp-scrobbler.py [--daemon] [--offline] [--verbose | --quiet] [--kill] [--config=FILE]"""
            """  -d, --daemon       Run in background, messages will be written to log file"""
            """  -o, --offline      Don't connect to service, put everything in cache"""
            """  -v, --verbose      Write more messages to console/log"""
            """  -q, --quiet        Write only errors to console/log"""
            """  -k, --kill         Kill existing scrobbler instance and exit"""
            """  -c, --config=FILE  Use this file instead of default config"""
            return
        daemon = o in ('-d', '--daemon')
        offline = o in ('-o', '--offline')
        if o in ('-v', '--verbose'):
            verbose = True
            quiet = False
        if o in ('-q', '--quiet'):
            quiet = True
            verbose = False
        kill = o in ('-k', '--kill')
        if o in ('-c', '--config'):
            configfile = v
    
    if os.path.isfile(pidfile):
        if kill:
            if not quiet: print 'Attempting to kill existing scrobbler process...'
        else:
            print >>sys.stderr, 'Pidfile found! Attempting to kill existing scrobbler process...'
        try:
            f = open(pidfile)
            pid = int(f.read().strip())
            f.close()
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
        except OSError, e:
            os.remove(pidfile)
        except IOError, e:
            print >>sys.stderr, 'Error occured while reading pidfile. Check if process is really running, delete pidfile ("%s") and try again. Error was: "%s"' % (pidfile, str(e))
            return
    elif kill:
        if not quiet: print 'Pidfile not found.'

    if os.path.isfile(pidfile):
        print 'Waiting for existing process to end...'
        while os.path.isfile(pidfile):
            time.sleep(1)
    
    if kill: return

    config = ConfigParser()
    try:
        config.read(configpath)
        login = config.get('scrobbler', 'login')
        password = config.get('scrobbler', 'password')
        streams = config.get('scrobbler', 'password')
    except:
        print >>sys.stderr, 'Not configured. Edit file: %s' % configpath
        return

    forked = False
    if daemon:
        try:
            pid = os.fork()
            if pid:
                if not quiet:
                    print 'Scrobbler daemon started with pid %d' % pid
                sys.exit(0)
            forked = True
        except Exception, e:
            print >>sys.stderr, 'Could not start daemonize, scrobbler will run in foreground. Error was: "%s"' % str(e)

    logger = logging.getLogger('mocp.pyscrobbler')
    logger.setLevel(logging.INFO)
    if verbose:
        logger.setLevel(logging.DEBUG)
    elif quiet:
        logger.setLevel(logging.WARNING)

    try:
        f = open(pidfile, 'w')
        print >>f, os.getpid()
        f.close()
    except Exception, e:
        print logger.error(u'Can\'t write to pidfile, exiting')
        return

    if forked:
        try:
            lout = logging.FileHandler(logfile, 'w')
        except:
            try:
                logfile = os.getenv('TEMP', '/tmp/') + 'mocp-pyscrobbler.log'
                lout = StupidFileHandler(logfile, 'w')
            except:
                lout = NullHandler()
        formatter = logging.Formatter(u'%(levelname)s %(asctime)s %(message)s')
        lout.setFormatter(formatter)
        logger.addHandler(lout)
    else:
        lout = StupidStreamHandler(sys.stdout)
        logger.addHandler(lout)

    lastfm = Scrobbler('post.audioscrobbler.com', login, password)
    lastfm.logger = logger
    
    if not offline:
        errord = False
        try:
            logger.info(u'Authorizing')
            lastfm.authorize()
            lastfm.start()
        except BannedException:
            logger.error(u'Error while authorizing: your account is banned.')
            errord = True
        except BadAuthException:
            logger.error(u'Error while authorizing: incorrect username or password. Please check your login settings and try again.')
            errord = True
        except BadTimeException:
            logger.error(u'Error while authorizing: incorrect time setting. Please check your clock settings and try again.')
            errord = True
        except FailedException, e:
            logger.error(u'Error while authorizing: general failure. Reason: "%s"' % e.message)
            errord = True
        except HardErrorException, e:
            logger.error(u'Critical error while authorizing. Check your internet connection and try again. Maybe servers are dead? Reason: "%s"' % e.message)
            errord = True
        if errord:
            logger.info(u'Scrobbler will work in offline mode')

    try:
        cachefile = file(cachepath, 'r')
        cache = pickle.load(cachefile)
        if cache and isinstance(cache, list):
            lastfm.cache = cache
        cachefile.close()
        os.remove(cachepath)
    except:
        pass
   
    unscrobbled = True
    unnotified = True

    newtrack = None
    oldtrack = None

    maxsec = 0
    lasttime = 0
    
    # the code below sucks a little...
    global running
    running = True
    def handler(i, j):
        global running
        logger.info(u'Got signal, shutting down...')
        running = False
        signal.signal(signal.SIGQUIT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    
    #signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGQUIT, handler)
    signal.signal(signal.SIGTERM, handler)

    try:
        while running:
            newtrack, state = get_mocp()
            if (state == 'play' and newtrack) or (state == 'stop' and oldtrack):
                if newtrack and (not lasttime) and (not newtrack.length):
                    lasttime = newtrack.position

                a = (newtrack != oldtrack) or state == 'stop'
                b = (not a) and newtrack.length and (newtrack.length - 15 < maxsec) and (newtrack.position < 15)
                if a or b:
                    if oldtrack:
                        oldtrack.position = maxsec

                        toscrobble = False
                        if oldtrack.length:
                            toscrobble = (oldtrack.position > 240) or (oldtrack.position > oldtrack.length * 0.5)
                        else:
                            toscrobble = (oldtrack.position - lasttime > 60)
                        
                        if unscrobbled and toscrobble:
                            if state == 'stop':
                                logger.info(u'Scrobbling [on stop]')
                            else:
                                logger.info(u'Scrobbling [on change]')
                            lastfm.scrobble(oldtrack, not oldtrack.length)

                    if newtrack:
                        if not newtrack.length:
                            logger.info(u'Now playing (stream): %s' % newtrack)
                        elif b:
                            logger.info(u'Now playing (repeated): %s' % newtrack)
                        else:
                            logger.info(u'Now playing: %s' % newtrack)
                    
                    if state != 'stop':
                        oldtrack = newtrack
                    else:
                        oldtrack = None
                    unscrobbled = True
                    unnotified = True
                    maxsec = 0
                    if not newtrack.length:
                        lasttime = newtrack.position
                    else:
                        lasttime= 0
                
                maxsec = max(maxsec, newtrack.position)
                
                if newtrack and unnotified:
                    lastfm.notify(newtrack)
                    unnotified = False
                
                if newtrack and unscrobbled and newtrack.length >= 30 and (newtrack.position > newtrack.length * _SCROB_FRAC):
                    logger.info(u'Scrobbling [on %d%%]' % int(_SCROB_FRAC * 100))
                    lastfm.scrobble(newtrack)
                    unscrobbled = False
                
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stdout)
    
    if not offline:
        lastfm.stop()
        if lastfm.isAlive():
            lastfm.join()

    if lastfm.cache:
        try:
            cachefile = file(cachepath, 'wb')
            pickle.dump(lastfm.cache, cachefile, 2)
            cachefile.close()
        except:
            pass

    os.remove(pidfile)

if __name__ == '__main__':
    main()
