#!/usr/bin/env python
__version__ = '0.4'
import json
import time
import os
import re
import subprocess
from avi.infrastructure.datastore import Datastore
from datetime import datetime

shell = [('ps -aux', True),
         ('top -b -o +%MEM | head -n 22', True),
         ('/opt/avi/scripts/taskqueue.py -s', True),
         ('grep "pending changes" /opt/avi/log/cc_agent_Default-Cloud.log', False),
         ]
out_file = '/tmp/report/report.' + time.strftime("%Y%m%d-%H%M%S") + '.json'

def format(command, message):
    data = {}
    data['command'] = command
    data['message'] = message
    return data

def shell_runner(cmd, check):
    try:
        output = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        if check:
            output = 'FAILED'
        else:
            output = None
    return format(cmd, output)

def nginx_logs():
    with open('./var/log/nginx/portal.access.log') as fh:
        data = fh.readlines()

    now = datetime.now()
    result = {'time': now.strftime('%d/%b/%Y:%H:%M:%S'), 'method': {}}
    conf = '$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent" $request_time $upstream_response_time $pipe'
    regex = ''.join(
        '(?P<' + g + '>.*?)' if g else re.escape(c)
        for g, c in re.findall(r'\$(\w+)|(.)', conf))

    for line in data:
        m = re.match(regex, line)
        if m is not None:
            m = m.groupdict()
            then = datetime.strptime(m['time_local'], '%d/%b/%Y:%H:%M:%S +0000')
            delta = (now - then).total_seconds() // 3600
            if delta < 1:
                (method, uri, protocol) = m['request'].split()
                try:
                    result['method'][method].append({'RCODE': m['status'], 'TIME': m['request_time']})
                except:
                    result['method'][method] = [{'RCODE': m['status'], 'TIME': m['request_time']}]
    return result

def aviportal_logs():
    with open('/var/log/upstart/aviportal.log') as fh:
        data = fh.readlines()

    now = datetime.now()
    uri_list = ['/api/virtualservice/', '/api/pool/', 'api/macro/', '/api/httppolicyset/',
                '/api/networksecuritypolicy/', '/api/sslkeyandcertificate/']
    method_list = ['POST', 'PUT', 'DELETE', 'GET']
    conf = '[$premable] $remote_addr () {$size} [$timestamp] $method $uri => $postamble'
    regex = ''.join(
        '(?P<' + g + '>.*?)' if g else re.escape(c)
        for g, c in re.findall(r'\$(\w+)|(.)', conf))

    result = {}
    output = {'time': now.strftime('%d/%b/%Y:%H:%M:%S'), 'method': result}
    for line in data:
        m = re.match(regex, line)
        if m is not None:
            m = m.groupdict()
            then = datetime.strptime(m['timestamp'], '%a %b %d %H:%M:%S %Y')
            delta = (now - then).total_seconds() // 900
            if delta < 1:
                if m['method'] in method_list and m['uri'].startswith(tuple(uri_list)):
                    for uri in uri_list:
                        if m['uri'].startswith(uri):
                            break
                    try:
                        result[m['method']][uri] += 1
                    except:
                        if not result.has_key(m['method']):
                            result[m['method']] = {}
                        result[m['method']][uri] = 1
    return output

if __name__ == '__main__':
    if not os.path.exists(os.path.dirname(out_file)):
        os.makedirs(os.path.dirname(out_file))
    ds = Datastore()

    output = []
    for cmd in shell:
        output.append(shell_runner(cmd[0], cmd[1]))

    for se in ds.get_all('serviceengine'):
        output.append(format('serviceengine:%s' % se['uuid'], str(se['runtime'])))

    for cluster in ds.get_all('cluster'):
        output.append(format('cluster:%s' % cluster['uuid'], str(cluster['runtime'])))

    output.append(format('VS_COUNT', len(ds.get_all('virtualservice'))))

    output.append(format('NGINX', nginx_logs()))
    output.append(format('AVIPORTAL', aviportal_logs()))

    with open(out_file, 'a') as fh:
        json.dump(output, fh)

    print out_file
