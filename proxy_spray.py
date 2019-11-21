#!/usr/bin/env python3

import argparse
import requests
import ipaddress
import re
import pdb
from sys import stderr
from multiprocessing.pool import Pool
from pathlib import Path
from time import sleep

# Disable Warnings
import warnings
warnings.filterwarnings('ignore')

# =========
# INTERFACE
# =========

parser = argparse.ArgumentParser(description='''Determine if an upstream
HTTP/S proxy will send requests to an upstream target.''')

misc_group = parser.add_argument_group('Miscellaneous Configurations',
    description='Available miscellaneous options.')
misc_group.add_argument('--display-failures','-df',
    action='store_true',
    help='Display invalid proxies')
misc_group.add_argument('--http-headers','-he',
    nargs='+',
    default=[],
    help='''Any additional HTTP headers that will be passed for each
    HTTP request. These can be supplied in the form of space delimited
    values, like 'X-FORWARDED-FOR: 192.168.1.2', or a file names containing
    lines of the same structure.
    ''')
misc_group.add_argument('--process-count','-pc',
    default=4,
    type=int,
    help='Count of processes to use during execution.')

input_group = parser.add_argument_group('Input Configurations',
    description='''Pass inputs to the script.
    ''')
input_group.add_argument('--proxy-urls','-pus',
    required=True,
    nargs='+',
    help='''Space delimited proxies to attempt in URI format. These
    values can be individual URLs or file names.
    ''')
input_group.add_argument('--targets','-ts',
    required=True,
    nargs='+',
    help='''Upstream HTTP servers to try and hit via proxies
    specified in --proxy-urls. These can be in the form of file names,
    URLs, individual IP addresses, or CIDR ranges.
    ''')

assumption_group = parser.add_argument_group('Assumption Group',
    description='''Control whether targets without a scheme should be
    modified with http, https, or both.''')
assumption_group.add_argument('--no-assume-https','-nahttps',
    action='store_true',
    help='''Assume that any target without a scheme, i.e. http(s),
    is an https service.
    ''')
assumption_group.add_argument('--no-assume-http','-nahttp',
    action='store_true',
    help='''Assume that any target without a scheme, i.e. http(s),
    is an http service.
    ''')


# == END INTERFACE ==

# =================
# CLASS DEFINITIONS
# =================

class ProxyDict(dict):
    '''Simple `dict`-like object with an `appendProxy` method
    that simplifies the process of adding new proxies.
    '''

    def appendProxy(self,scheme,proxy):

        if scheme in self:
            proxies[scheme].append(proxy)
        else:
            proxies[scheme] = [proxy]

# == END CLASS DEFINITIONS ==

# ====================
# FUNCTION DEFINITIONS
# ====================

def parseProxy(s):
    '''Parse a proxy string in URL format and return a tuple
    in the form of `(scheme,url)`.
    '''

    match = re.search('^(https?://)(.+)',s,re.I)
    assert match, f'Invalid proxy/proxy file supplied: {s}'
    return match.groups()[0].split(':')[0],s

def assumeIPTarget(t):
    '''Generate IP target assumptions. Returns a list of URL strings
    with http(s):// prefixed where necessary.
    '''

    output = []
    if not args.no_assume_http: output.append(f'http://{t}')
    if not args.no_assume_https: output.append(f'https://{t}')
    return output

def assumeURLTarget(t):
    '''Generate URL target assumptions. Returns a list of URL strings
    with http(s):// prefixed where necessary.
    '''

    output = []

    if not args.no_assume_http:
        if not t.startswith('http') and not t.startswith('https'):
            output.append(f'http://{t}')

    if not args.no_assume_https:
        if not t.startswith('https') and not t.startswith('http'):
            output.append(f'https://{t}')

    return output

def parseHeader(h):
    '''Parse an HTTP header string and return a tuple in the
    following form: (header_key,header_value)
    '''

    split = [v for v in re.split('^(.+):\s{1,}(.+)$',h) if v]
    assert split.__len__() == 2, f'Invalid header supplied: {h}'
    return split[0],split[1]
    

def parseTarget(t):
    '''Parse the target, make URL assumptions, and then return
    a list of the final output values.
    '''

    # Use an RE to determine if this is a CIDR string
    if re.search('/[0-9]{,2}$',t):
        t = ipaddress.IPv4Network(t,strict=False)
    # Treat as an individual IP address otherwise
    else:
        # Catch any assertions and then assume the
        # input is simply a URL
        try:
            t = ipaddress.IPv4Address(t)
        except:
            pass

    # Expand and assume for any IPv4 network
    if t.__class__ == ipaddress.IPv4Network:
        output = []
        for ip in t:
            output += assumeIPTarget(ip)
        return output

    # Handle an individual IP address
    elif t.__class__ == ipaddress.IPv4Address:
        return assumeIPTarget(t)

    # Handle an individual URL target
    else:
        nt = assumeURLTarget(t)
        if not nt:
            return [t]
        else:
            return nt

def isFile(s):
    '''Determine if the input value (s) is a file name and
    return the `Path` object associated with that file if
    so.
    '''

    p = Path(s)
    if p.is_file(): return p
    else: return False

def printResult(out):

    s =  out[2] + ' >--[VIA]--> ' + list(out[1].values())[0]
    if out[0]:
        print('SUCCESS: '+s)
    elif args.display_failures:
        print(f'FAILURE: '+s)

def compareSchemes(v0,v1):

    r = '^(https?)'
    rv0, rv1 = re.search(r,v0), re.search(r,v1)
    if rv0 and rv1 and rv0.groups()[0] == rv1.groups()[0]:
        return True
    else:
        return False

def genericRequestsCallback(proxy,target,verify=False,
        allow_redirects=False,headers=None):
    '''Generic HTTP request callback that returns a simple tuple
    communicating if the request completed successfully. The output
    tuple is structured as:

    (True/False,proxy_argument_received,target_argument_received)

    '''

    headers = headers or {}

    try:
        resp = requests.get(target,
                    proxies=proxy,
                    verify=verify,
                    allow_redirects=allow_redirects,
                    headers=headers)

        if resp.status_code == 403:
            raise Exception('403 Forbidden Response')

        return (True,proxy,target,resp,None)

    except Exception as e:
        return (False,proxy,target,None,e)

if __name__ == '__main__':
    
    # == END FUNCTION DEFINITIONS ==
    
    # ================
    # BEGIN MAIN LOGIC
    # ================
    
    args = parser.parse_args()
    
    print(
    '\n  _ \                      __|\n' \
    '  __/ _| _ \ \ \ /  |  | \__ \  _ \   _| _` |  |  |\n' \
    '_|  _| \___/  _\_\ \_, | ____/ .__/ _| \__,_| \_, |\n' \
    '                    ___/       _|              ___/\n',file=stderr)
    
    # == Handle proxies ==
    
    print('[+] Loading proxies...',end='',file=stderr)
    proxies = []
    for p in args.proxy_urls:
        
        # Handle a file of proxies
        pth = isFile(p)
        if pth:
            with open(pth) as infile:
                for proxy in infile:
                    scheme,proxy = parseProxy(proxy.strip())
                    proxy = {scheme:proxy}
                    if proxy in proxies: continue
                    proxies.append(proxy)
    
        # Handle an individual proxy
        else:
            scheme,proxy = parseProxy(p)
            proxy = {scheme:proxy}
            if proxy in proxies: continue
            proxies.append({scheme:proxy})
    
    print('done!',file=stderr)
    # == END handle proxies ==
    # == Handle targets ==
    print('[+] Loading targets...',end='',file=stderr)
    targets = []
    for t in args.targets:
    
        # Handle a file of targets
        pth = isFile(t)
        if pth:
            with open(pth) as infile:
                for target in infile:
                    targets += parseTarget(target.strip())
    
        # Handle an individual target
        else:
            targets += parseTarget(t)
    print('done!',file=stderr)
    # == END handle targets ==
    # == Handle headers ==
    
    print('[+] Loading http headers...',end='',file=stderr)
    headers = {}
    for h in args.http_headers:
    
        pth = isFile(h)
        if pth:
            with open(pth) as infile:
                for header in infile:
                    key,value = parseHeader(header)
                    headers[key] = value
    
        else:
            key,value = parseHeader(h)
            headers[key] = value
    print('done!',file=stderr)
    
    # == END handle headers ==
    
    # ======================
    # BEGIN SENDING REQUESTS
    # ======================
    
    print('[+] Beginning to send HTTP requests',file=stderr)
    if not args.display_failures:
        print('[+] Failed requests will not be displayed',file=stderr)
    
    # Initialize variables for multiprocessing
    pool, results = Pool(args.process_count), []
    tcount = targets.__len__()
    
    # Send the requests
    for proxy in proxies:
    
        for target in targets:
    
            # Assure protocols are matching, skip otherwise
            if not compareSchemes(list(proxy.values())[0],target):
                continue
    
            # Handle maximum parallel execution
            while results.__len__() == args.process_count:
    
                # Detect and display completed requests
                to_del = []
                for res in results:
                    if res.ready():
                        printResult(res.get())
                        to_del.append(res)
    
                # Delete complete results
                if to_del:
                    for res in to_del:
                        del(results[results.index(res)])
                    to_del.clear()
    
                # Depending on if requests or ongoing, break or sleep
                if results.__len__() < args.process_count:
                    break
                else:
                    sleep(.5)
    
            # Perform the next request
            results.append(
                    pool.apply_async(
                        genericRequestsCallback,(),{'proxy':proxy,
                            'target':target,'headers':headers})
                )
    
            sleep(.25)
    
    # Wait and report on pending results
    print('[+] Final requests sent, awaiting responses',file=stderr)
    while results:
    
        result = results[0]
    
        if result.ready():
            printResult(result.get())
            del(results[results.index(result)])
    
        if results: sleep(.5)
    print('[+] Execution complete',file=stderr)
    
    # Close up the pool
    pool.close()
    pool.join()
    
    # == END MAIN LOGIC ==
