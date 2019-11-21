# Proxy Spray

Basic utility to spray HTTP requests at HTTP proxies to determine
if it's possible to use that proxy to access upstream resources.

# Requirements

`proxy_spray` requires Python3.7 and the requests library.

# Key Capabilities

## Target Scanning

It enables you to easily scan for a range of target IP addresses
in an effort to identify ACL flaws that may allow access to private
HTTP resources.

Values supplied to the `--targets` parameter can be individual IP
addresses, URLs, CIDR values, or file names containing newline
delimited values of the aforementioned types.

If IP address or CIDR values are supplied, take note of the 
`--no-assume-http` and `--no-assume-https` arguments, which
allow you to disable suffixing of the `https://` and `http://`
schemes. If disregarded, `proxy_spray` will attempt to try
each scheme relative to the proxies supplied.

## Multiprocessing

It uses multiprocessing to make scanning efficient. Use the
`--process-count` parameter to specify the number of processes
to use during execution.

# Example

```bash
./proxy_spray.py --proxy-urls https://192.168.86.1:8080 https://192.168.86.2:8080 \
  --targets https://www.google.com https://www.linkedin.com 8.8.8.8/24 \
  --display-failures
```

The example above would attempt to access `google.com` and `linkedin.com`
via each specified proxy `(192.168.86.1,192.168.86.2)`, whild writing the
outcome of each test to `stdout`:

```
  _ \                      __|
  __/ _| _ \ \ \ /  |  | \__ \  _ \   _| _` |  |  |
_|  _| \___/  _\_\ \_, | ____/ .__/ _| \__,_| \_, |
                    ___/       _|              ___/

[+] Loading proxies...done!
[+] Loading targets...done!
[+] Loading http headers...done!
[+] Beginning to send HTTP requests

FAILURE: https://www.google.com >--[VIA]--> https://192.168.86.1:8080
SUCCESS: https://www.google.com >--[VIA]--> https://192.168.86.2:8080
FAILURE: https://www.linkedin.com >--[VIA]--> https://192.168.86.1:8080
SUCCESS: https://www.linkedin.com >--[VIA]--> https://192.168.86.2:8080
FAILURE: https://8.8.8.0 >--[VIA]--> https://192.168.86.1:8080
FAILURE: https://8.8.8.0 >--[VIA]--> https://192.168.86.1:8080
FAILURE: https://8.8.8.1 >--[VIA]--> https://192.168.86.1:8080
FAILURE: https://8.8.8.1 >--[VIA]--> https://192.168.86.2:8080

# ...and so forth...
```

