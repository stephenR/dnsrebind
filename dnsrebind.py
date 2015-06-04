#!/usr/bin/env python

import dnslib.server as dnss
import cherrypy
import argparse

SOA_RECORD = """\
$ORIGIN {0}
@	IN SOA	{0}	root.{0} (
	2015060305	; serial
	3h	; refresh
	1h	; retry
	1h	; expiry
	1h )	; minimum\
"""

NS_RECORD = """\
$ORIGIN {}.
$TTL 2d
	IN NS		{}
	IN NS		{}
"""

def add_dot(s):
    if s[-1] == '.':
        return s
    return s + '.'

class RebindResolver(dnss.BaseResolver):
    def __init__(self, ip, domain, ns1, ns2):
        self.domain = add_dot(domain)
        self.ip = ip
        self.soa_record = dnss.RR.fromZone(SOA_RECORD.format(self.domain))
        if ns1 != '' and ns2 != '':
            self.ns_record = dnss.RR.fromZone(NS_RECORD.format(self.domain, add_dot(ns1), add_dot(ns2)))
        else:
            self.ns_record = None
        self.reset()

    def reset(self):
        self.db = {}
        self.db[self.domain] = self.ip

    def resolve(self,request,handler):
        reply = request.reply()
        qtype = dnss.QTYPE[request.q.qtype]
        qname = '.'.join(request.q.qname.label)+'.'

        if qtype == 'SOA':
            reply.add_answer(*self.soa_record)
            return reply

        if qtype == 'NS':
            if self.ns_record == None:
                reply.header.rcode = dnss.RCODE.NXDOMAIN
            else:
                reply.add_answer(*self.ns_record)
            return reply

        qname_substr = qname
        while True:
            if self.db.has_key(qname_substr):
                ip = self.db[qname_substr]
                reply.add_answer(*dnss.RR.fromZone("{} 60 A {}".format(qname, ip)))
                return reply
            if not '.' in qname_substr:
                break
            qname_substr = qname_substr[qname_substr.find('.')+1:]

        reply.header.rcode = dnss.RCODE.NXDOMAIN
        return reply


class DNSApi(object):
    def __init__(self, resolver):
        self.resolver = resolver

    def add(self, domain=None, ip=None):
        if domain==None or ip==None:
            return "FAIL"
        domain = add_dot(domain)
        resolver.db[domain] = ip
        return "OK"
    add.exposed = True

    def reset(self):
        self.resolver.reset()
    reset.exposed = True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simple DNS server with dumb HTTP API.')
    parser.add_argument('-d', '--domain', required=True)
    parser.add_argument('-i', '--ip', required=True)
    parser.add_argument('--ns1', default='')
    parser.add_argument('--ns2', default='')
    parser.add_argument('--dnsport', default='53', type=int)
    parser.add_argument('--apiport', default='18081', type=int)
    args = parser.parse_args()

    resolver = RebindResolver(args.ip, args.domain, args.ns1, args.ns2)
    server = dnss.DNSServer(resolver,port=args.dnsport,address='0.0.0.0')
    server.start_thread()

    cherrypy.config.update({'server.socket_host': '0.0.0.0',
                        'server.socket_port': args.apiport,
                       })
    cherrypy.quickstart(DNSApi(resolver))

