# MOCp-Scrobbler

Last.fm scrobbler for MOC audio player with support for now-playing notifications, daemonization and cache.
Works with  internet streams (with properly set tags) and scrobbles on 90% of track. Supports scrobbling of looped track too.

    # mocp-scrobbler.py --help
    mocp-scrobbler.py 0.2-rc1
    Usage: mocp-scrobbler.py [--daemon] [--offline] [--verbose | --quiet] [--kill] [--config=FILE]
      -d, --daemon       Run in background, messages will be written to log file
      -o, --offline      Don't connect to service, put everything in cache
      -v, --verbose      Write more messages to console/log
      -q, --quiet        Write only errors to console/log
      -k, --kill         Kill existing scrobbler instance and exit
      -c, --config=FILE  Use this file instead of default config

Just put this python script in your $PATH.
Before running you must place configuration file in ``~/.mocpscrob/config`` which should look like below:

    [scrobbler]
    login=YOUR_LASTFM_LOGIN
    password=YOUR_PASSWORD

Cache, pid file and logs are placed in the same folder.

Instead of running in daemon mode, you can simply run it in GNU Screen:

    # screen -dR scrob mocp-scrobbler.py -v
