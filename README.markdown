# mocp-scrobbler.py (For Python3)

Last.fm scrobbler for MOC audio player with support for now-playing notifications, daemonization and cache. It needs just Python 3 to run, nothing else.

Works with internet streams (only with properly set tags - usually Icecast streams). Scrobbles on 90% of track or on track change/stop if at least 50% or half minute was played. Supports scrobbling of looped track too.

    % python3 mocp-scrobbler.py --help
    mocp-scrobbler.py 0.2
    Usage:
      mocp-scrobbler.py [--daemon] [--offline] [--verbose | --quiet] [--config=FILE]
      mocp-scrobbler.py --kill [--verbose | --quiet]
      
      -c, --config=FILE  Use this file instead of default config
      -d, --daemon       Run in background, messages will be written to log file
      -k, --kill         Kill existing scrobbler instance and exit
      -o, --offline      Don't connect to service, put everything in cache
      -q, --quiet        Write only errors to console/log
      -v, --verbose      Write more messages to console/log

## Installation

Installation is manual. Just put this python script in your $PATH. It doesn't need to configure anything within MOC itself.
Before running you need to create configuration file ``~/.mocpscrob/config`` which should look like below:

    [scrobbler]
    login=YOUR_LASTFM_LOGIN
    password=YOUR_PASSWORD
    streams=true
    hostname=post.audioscrobbler.com

``password`` will be replaced with ``password_md5`` on the first run. Its value will be original value hashed using MD5 algorithm. If you want to change password, just add again ``password`` with you new password - ``password_md5`` will be replaced.

``streams`` and ``hostname`` are not required, and given values are default.

``streams`` turns on scrobbling when listening to internet streams. If it works incorrectly, set it to false.

``hostname`` may be useful if you want to use different scrobbling service, for example libre.fm (turtle.libre.fm).

Cache, pidfile and logs are placed in ``~/.mocpscrob/``.

Instead of running in daemon mode, you can run it in GNU Screen:

    % screen -dR scrob mocp-scrobbler.py -v

## Troubleshooting

Before issuing bugs, please check the following:

1.  Make sure you're using Python in at least version 3.1 (I didn't really test it with Python 3.0)
1.  Check if ``mocp -i`` prints what track is currently playing

## FAQ

### What about other players?

Maybe in future, but as different project.

### What about Python 2.x?

Not supported anymore, sorry. Old code can be found in ``master`` branch, but it will land in py2 branch soon.

### What about scrobbling API 2?

There is some interest in using this script as ``gobbler`` for libre.fm, which AFAIK doesn't support new API yet, so...
