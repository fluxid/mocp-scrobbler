#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author: Tomasz 'Fluxid' Kowalczyk
# e-mail and xmpp/jabber: myself@fluxid.pl

from configparser import SafeConfigParser
import getopt
from hashlib import md5
from http.client import HTTPConnection
import locale
import logging
import os
import pickle
import re
import signal
import subprocess
import sys
import time
from threading import Thread
from urllib.request import urlopen
from urllib.parse import urlparse, quote_from_bytes, quote

log = logging.getLogger('mocp.pyscrobbler')
log.setLevel(logging.INFO)

_SCROB_FRAC = 0.9
INFO_RE = re.compile(r'^([a-zA-Z]+):\s*(.+)$')

class ScrobException(Exception):
    def __init__(self, message=''):
        self._message = message
    
    def __str__(self):
        return self._message

class BannedException(ScrobException):
    pass

class BadAuthException(ScrobException):
    pass

class BadTimeException(ScrobException):
    pass

class FailedException(ScrobException):
    pass

class BadSessionException(ScrobException):
    pass

class HardErrorException(ScrobException):
    pass

class NullHandler(logging.Handler):
    def emit(self, record):
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
        # Don't set encoding on stream we don't own
        msg = msg.encode(self.encoding, 'replace')
        self.s.buffer.write(msg)
        self.s.buffer.write(b'\n')
        self.s.buffer.flush()
        self.flush()

class StupidFileHandler(StupidStreamHandler):
    def __init__(self, fname, fwrite, level=logging.NOTSET):
        f = open(fname, fwrite)
        StupidStreamHandler.__init__(self, f, level)
        self.f = f
        self.encoding = locale.getpreferredencoding() or 'utf-8'
    
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
        return (
            isinstance(other, self.__class__) and
            self.artist.lower() == other.artist.lower() and
            self.title.lower() == other.title.lower()
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __bool__(self):
        if self.artist and self.title: # and self.length:
            return True
        return False

    def __str__(self):
        if self:
            if self.album:
                return '%s - %s (%s)' % (self.artist, self.title, self.album)
            else:
                return '%s - %s' % (self.title, self.artist)
        else:
            return 'None'

    def __repr__(self):
        return '<Track: %s>' % self

class Scrobbler(Thread):
    def __init__(self, host, login, password_md5):
        Thread.__init__(self)

        self.host = host
        self.login = login
        self.password_md5 = password_md5
        self.session = None
        self.np_link = None
        self.sub_link = None
        self.cache = []
        self.playing = None
        self.notify_sent = False
        self._running = False
        self._authorized = False

    def send_encoded(self, url, data):
        url2 = urlparse(url)
        host = url2.netloc
        path = url2.path or '/'
        query = '?' + url2.query if url2.query else ''
        request = path + query
        
        data2 = '&'.join((
            quote(k) + '=' + quote_from_bytes(str(v).encode('utf8'))
            for k, v in data.items()
        )).encode('ascii')
        
        try:
            http = HTTPConnection(host)
            http.putrequest('POST', request)
            http.putheader('Content-Type', 'application/x-www-form-urlencoded')
            http.putheader('User-Agent', 'Fluxid MOC Scrobbler 0.2')
            http.putheader('Content-Length', str(len(data2)))
            http.endheaders()
            http.send(data2)
            response = http.getresponse().read().decode('utf8').upper().strip()
        except Exception as e:
            raise HardErrorException(str(e))
        if response == 'BADSESSION':
            raise BadSessionException
        elif response.startswith('FAILED'):
            raise FailedException(response.split(' ', 1)[1].strip() + (' POST = [%r]' % data2))

    def authorize(self):
        log.debug('Authorizing...')
        timestamp = time.time()
        token = md5((self.password_md5 + str(int(timestamp))).encode('ascii')).hexdigest()
        link = 'http://%s/?hs=true&p=1.2.1&c=mcl&v=1.0&u=%s&t=%d&a=%s' % (self.host, self.login, timestamp, token)
        try:
            f = urlopen(link)
        except Exception as e:
            raise HardErrorException(str(e))
        if f:
            f = f.readlines()
            f0 = f[0].strip().decode('utf8', 'replace')
            first = f0.upper()
            if first == 'OK':
                self.session = f[1].strip().decode('ascii')
                self.np_link = f[2].strip().decode('ascii')
                self.sub_link = f[3].strip().decode('ascii')
            elif first == 'BANNED':
                raise BannedException
            elif first == 'BADAUTH':
                raise BadAuthException
            elif first == 'BADTIME':
                raise BadTimeException
            elif first.startswith('FAILED'):
                raise FailedException(f[0].split(' ', 1)[1].strip())
            else:
                raise HardErrorException('Received unknown response from server: [%r]' % b'\n'.join(f))
        else:
            raise HardErrorException('Empty response')
        log.debug('Authorized!')
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
        x = ', '.join((
            str(s[0])
            for s in scrobbles
        ))
        return '[%s]' % x

    def run(self):
        self._running = True
        while self._running:
            if not self._authorized:
                errord = 0
                try:
                    self.authorize()
                except BannedException:
                    log.error('Error while authorizing: your account is banned.')
                    errord = 1
                except BadAuthException:
                    log.error('Error while authorizing: incorrect username or password. Please check your login settings.')
                    errord = 1
                except BadTimeException:
                    log.error('Error while authorizing: incorrect time setting. Please check your clock settings.')
                    errord = 1
                except FailedException as e:
                    log.error('Error while authorizing: general failure. Will try again after one minute. Reason: "%s"' % str(e))
                    errord = 2
                except HardErrorException as e:
                    log.error('Critical error while authorizing. Check your internet connection. Or maybe servers are dead? Will try again after one minute. Reason: "%s"' % str(e))
                    errord = 2

                if errord == 1:
                    log.info('Scrobbler will work in offline mode')
                    self._running = False
                elif errord == 2:
                    self.nice_sleep(60)

                continue

            try:
                if self.cache:
                    slice = self.cache[:10]
                    if len(slice) == 1:
                        log.debug('Submitting track: %s' % slice[0][0])
                    else:
                        log.debug('Submitting %d tracks: %s' % (len(slice), self.format_scrobbles(slice)))
                    self.submit_scrobble(slice)
                    log.debug('Submitted')
                    del self.cache[0:len(slice)]

                if self.playing and not self.notify_sent:
                    log.debug('Sending notify')
                    self.submit_notify(self.playing)
                    log.debug('Notify sent')
                    self.notify_sent = True

                time.sleep(1)
            except BadSessionException:
                log.debug('Session timed out')
                self._authorized = False
            except FailedException as e:
                log.error('Error while submission: general failure. Trying again after 10 seconds. Reason: "%s".' % str(e))
                self.nice_sleep(10)
            except HardErrorException as e:
                log.error('Critical error while submission. Check your internet connection. Trying again after 10 seconds. Exception was: "%s"' % str(e))
                self.nice_sleep(10)

    def nice_sleep(self, seconds):
        # This way, so we can quit nicely while waiting
        counter = 0
        while self._running and counter < seconds:
            time.sleep(1)
            counter += 1

    def stop(self):
        self._running = False

def get_mocp():
    info = {}
    try:
        p = subprocess.Popen('mocp -i', shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    except:
        return (None, 'stop')
    pstdout, _ = p.communicate()
    pstdout = pstdout.decode('utf8', 'replace') # mocp -i output doesn't depend on locale
    for line in pstdout.splitlines():
        m = INFO_RE.match(line)
        if m:
            key, value = m.groups()
            if value:
                info[key.lower()] = value.strip()

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
    hostname = 'post.audioscrobbler.com'
    exit_code = 0

    if not os.path.isdir(path):
        os.mkdir(path)

    shortargs = 'dc:ovqhk'
    longargs = 'daemon config= offline verbose quiet help kill'
    try:
        opts, args = getopt.getopt(sys.argv[1:], shortargs, longargs.split())
    except getopt.error as e:
        print(str(e), file=sys.stderr)
        print('Use --help parameter to get more info', file=sys.stderr)
        return
    
    daemon = False
    verbose = False
    quiet = False
    offline = False
    kill = False

    for o, v in opts:
        if o in ('-h', '--help'):
            print(
                'mocp-scrobbler.py 0.2',
                'Usage:',
                '  mocp-scrobbler.py [--daemon] [--offline] [--verbose | --quiet] [--config=FILE]',
                '  mocp-scrobbler.py --kill [--verbose | --quiet]',
                '',
                '  -c, --config=FILE  Use this file instead of default config',
                '  -d, --daemon       Run in background, messages will be written to log file',
                '  -k, --kill         Kill existing scrobbler instance and exit',
                '  -o, --offline      Don\'t connect to service, put everything in cache',
                '  -q, --quiet        Write only errors to console/log',
                '  -v, --verbose      Write more messages to console/log',
                sep='\n'
            )
            return 1
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
            if not quiet:
                print('Attempting to kill existing scrobbler process...')
        else:
            print('Pidfile found! Attempting to kill existing scrobbler process...', file=sys.stderr)
        try:
            with open(pidfile) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
        except (OSError, ValueError) as e:
            os.remove(pidfile)
        except IOError as e:
            print('Error occured while reading pidfile. Check if process is really running, delete pidfile ("%s") and try again. Error was: "%s"' % (pidfile, str(e)), file=sys.stderr)
            return 1
    elif kill:
        if not quiet:
            print('Pidfile not found.')

    if os.path.isfile(pidfile):
        print('Waiting for existing process to end...')
        while os.path.isfile(pidfile):
            time.sleep(1)
    
    if kill: return

    config = SafeConfigParser()

    try:
        config.read(configpath)
    except:
        print('Not configured. Edit file: %s' % configpath, file=sys.stderr)
        return 1

    getter = lambda k, f: config.get('scrobbler', k) if config.has_option('scrobbler', k) else f

    login = getter('login', None)
    password = getter('password', None)
    password_md5 = getter('password_md5', None)
    streams = getter('streams', '1').lower in ('true', '1', 'yes')
    hostname = getter('hostname', hostname)

    if not login:
        print('Missing login. Edit file: %s' % configpath, file=sys.stderr)
        return 1

    if not (password or password_md5):
        print('Missing password. Edit file: %s' % configpath, file=sys.stderr)
        return 1

    if password:
        password_md5 = md5(password.encode('utf-8')).hexdigest()
        config.set('scrobbler', 'password_md5', password_md5)
        config.remove_option('scrobbler', 'password')
        with open(configpath, 'w') as f:
            config.write(f)
        print('Your password wasn\'t hashed - config file has been updated')

    del password

    forked = False
    if daemon:
        try:
            pid = os.fork()
            if pid:
                if not quiet:
                    print('Scrobbler daemon started with pid %d' % pid)
                sys.exit(0)
            forked = True
        except Exception as e:
            print('Could not daemonize, scrobbler will run in foreground. Error was: "%s"' % str(e), file=sys.stderr)

    if verbose:
        log.setLevel(logging.DEBUG)
    elif quiet:
        log.setLevel(logging.WARNING)

    try:
        with open(pidfile, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        print('Can\'t write to pidfile, exiting. Error was: "%s"' % str(e), file=sys.stderr)
        return 1

    if forked:
        try:
            lout = StupidFileHandler(logfile, 'w')
        except:
            try:
                logfile = os.getenv('TEMP', '/tmp/') + 'mocp-pyscrobbler.log'
                lout = StupidFileHandler(logfile, 'wa')
            except:
                lout = NullHandler()
        formatter = logging.Formatter('%(levelname)s %(asctime)s %(message)s')
        lout.setFormatter(formatter)
        log.addHandler(lout)
    else:
        lout = StupidStreamHandler(sys.stdout)
        log.addHandler(lout)

    lastfm = Scrobbler(hostname, login, password_md5)

    if os.path.isfile(cachepath):
        cache = None

        try:
            with open(cachepath, 'rb') as f:
                cache = pickle.load(f)
        except Exception as e:
            log.exception('Error while trying to read scrobbling cache:')

        if cache and isinstance(cache, list):
            lastfm.cache = cache

        try:
            os.remove(cachepath)
        except:
            pass
    
    if not offline:
        lastfm.start()
   
    unscrobbled = True
    unnotified = True

    newtrack = None
    oldtrack = None

    maxsec = 0
    lasttime = 0
    
    running = True
    def handler(i, j):
        nonlocal running
        log.info('Got signal, shutting down...')
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
                                log.info('Scrobbling [on stop]')
                            else:
                                log.info('Scrobbling [on change]')
                            lastfm.scrobble(oldtrack, not oldtrack.length)

                    if newtrack:
                        if not newtrack.length:
                            log.info('Now playing (stream): %s' % newtrack)
                        elif b:
                            log.info('Now playing (repeated): %s' % newtrack)
                        else:
                            log.info('Now playing: %s' % newtrack)
                    
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
                    log.info('Scrobbling [on %d%%]' % int(_SCROB_FRAC * 100))
                    lastfm.scrobble(newtrack)
                    unscrobbled = False
                
            time.sleep(5)
    except KeyboardInterrupt:
        log.info('Keyboard interrupt. Please wait until I shut down')
    except Exception:
        log.exception('An error occured:')
        exit_code = 1
    
    if not offline:
        lastfm.stop()
        if lastfm.isAlive():
            lastfm.join()

    if lastfm.cache:
        try:
            with open(cachepath, 'wb') as f:
                pickle.dump(lastfm.cache, f, pickle.HIGHEST_PROTOCOL)
        except:
            log.exception('Error while trying to save scrobbling cache:')

    try:
        os.remove(pidfile)
    except:
        pass

    return exit_code

if __name__ == '__main__':
    sys.exit(main() or 0)
