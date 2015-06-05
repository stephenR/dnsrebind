# dnsrebind

Simple hacky dns rebinding server based on dnslib and cherrypy

```shell
./dnsrebind.py -d DOMAIN -i IP
cd www
#modify pwn.html to your needs
vim pwn.html
python -m SimpleHTTPServer 80
```

and then go to yourdomain/start.html?ip=TARGET&path=PATH

The dns server has a publicly accessible HTTP API to set new records. The idea is to have it as dumb as possible and let the attack payload do any work, see www/pwn.html.
The API listens on port 18081 by default and provides:

/add?domain=DOMAIN&ip=IP

/reset
