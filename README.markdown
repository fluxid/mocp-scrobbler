# mocp-scrobbler.py (For Python3)

Last.fm scrobbler for MOC audio player with support for now-playing notifications, daemonization and cache.
Works with internet streams (only with properly set tags - usually Icecast streams) and scrobbles on 90% of track and on track change if at least 50% or half minute was played. Supports scrobbling of looped track too.

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

Just put this python script in your $PATH.
Before running you must place configuration file in ``~/.mocpscrob/config`` which should look like below:

    [scrobbler]
    login=YOUR_LASTFM_LOGIN
    password=YOUR_PASSWORD
    streams=true
    hostname=post.audioscrobbler.com

streams and hostname are not required, and given values are default.
streams turns on scrobbling when listening to internet streams. If it works incorrectly, set it to false.
hostname may be useful if you want to use different scrobbling service, for example libre.fm (turtle.libre.fm).

Cache, pidfile and logs are placed in ``~/.mocpscrob/config``.

Instead of running in daemon mode, you can run it in GNU Screen:

    % screen -dR scrob mocp-scrobbler.py -v
