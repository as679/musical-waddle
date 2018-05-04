#!/usr/bin/env python
__version__ = '0.2'
import json
import time
import os
import subprocess
from avi.infrastructure.datastore import Datastore

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

    with open(out_file, 'a') as fh:
        json.dump(output, fh)
    print out_file
