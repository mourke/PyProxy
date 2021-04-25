import signal
import socket
import sys
import threading
from threading import Thread
from typing import Optional
from urllib.parse import urlparse, ParseResult
from time import time
import blocklist
import cache

HOST_NAME = ""  # listen to all
PORT = 4012
ENCODING = 'Latin-1'
HEADER_SIZE = 8192  # 8KiB is the HTTP header size
verbose = False
timing = False

blocked_urls = blocklist.read_blocklist() # will never change throughout the lifetime of the application


def log(values: object):
    if verbose:
        print(values, flush=True)


def recvall(s: socket):
    reply = s.recv(HEADER_SIZE) # header size must be at most 8 KiB or this logic breaks.
    http_header = reply.decode(ENCODING).split('\r\n')
    body = http_header[-1]
    if body == '': # there is no body to be sent as http header was terminated by empty string https://www.w3.org/Protocols/rfc2616/rfc2616-sec4.html#sec4.4
        return reply

    content_length = 0
    for element in http_header:
        if "Transfer-Encoding: " in element and "chunked" in element:
            raise NotImplementedError("Chunked Transfer encoding is not supported as I don't have time")
        if "Content-Length: " in element:
            content_length = int(element.removeprefix("Content-Length: "))
            break

    while len(body) < content_length:  # we need to fetch more
        temp = s.recv(HEADER_SIZE)
        body += temp.decode(ENCODING)  # yes this is garbled but we only need the length
        reply += temp

    return reply


class ProxyRequestHandler(Thread):
    data_sent = 0 # in bytes. This is only for HTTP connections as caching is disabled on HTTPS
    data_received = 0 # in bytes. This is only for HTTP connections as caching is disabled on HTTPS
    _forwarding_socket: socket
    _request_socket: socket
    _wants_stop = False # call cancel to set this to true and stop all requests

    def cancel(self):
        self._wants_stop = True

    def run(self):
        self.setup()
        try:
            self.handle()
        finally:  # if an exception is thrown inside handle make sure we still close the sockets
            self.finish()

    def __init__(self, request_socket):
        Thread.__init__(self)
        self._request_socket = request_socket

    @staticmethod
    def header_from_data(data: bytes) -> tuple[str, ParseResult, str]:
        request_string = data.decode(ENCODING)
        header_info = request_string.split("\r\n")[0].split(" ")  # get only first line of HTTP header and split into:

        method = header_info[0]
        url_string = header_info[1]
        http_version = header_info[2]

        first = url_string.split(":")[0]
        if (not first == "http") and (not first == "https"):  # we need to add // before the url otherwise the bad parsing library breaks
            url_string = "//" + url_string
        url = urlparse(url_string)
        if not url.port:
            if url.scheme == "http":
                url = ParseResult(url.scheme, f'{url.hostname}:80', '', url.params, url.query, url.fragment)
            elif url.scheme == "https":
                url = ParseResult(url.scheme, f'{url.hostname}:443', '', url.params, url.query, url.fragment)
            else:
                raise NameError(f"Unable to extract port from scheme: {url.scheme}")
        return method, url, http_version

    def setup(self):
        log("\n[+] Creating forwarding socket...")
        self._forwarding_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def handleHTTP(self, host: str, port: int, data: bytes):
        log(f"[+] Checking if {host} exists in cache...")
        reply = cache.data_for_url(f'{host}:{port}')
        if reply:  # exists in cache and hasn't expired
            log(f"[+] Response from {host} cached and not expired")
        else:  # fetch from server
            log("[+] Response not cached or has expired")
            log("[+] Connecting to remote server...")
            self._forwarding_socket.connect((host, port))
            log("[+] Forwarding client's request to remote server...")
            self._forwarding_socket.sendall(data)
            self.data_sent = len(data)  # only add if data was actually sent to the internet
            log("[+] Receiving response from remote server...")

            reply = recvall(self._forwarding_socket)
            http_header = reply.decode(ENCODING).split('\r\n')
            date_str: Optional[str] = None
            expiration_str: Optional[str] = None
            for element in http_header:
                if "Date: " in element:
                    date_str = element.removeprefix("Date: ")
                elif "Expires: " in element:
                    expiration_str = element.removeprefix("Expires: ")

            if date_str and expiration_str:
                log("[+] Caching response...")
                cache.cache_url(f'{host}:{port}', reply, date_str, expiration_str)
            else:
                log("[-] Header had no cache policy. Not caching just to be safe.")

        log("[+] Forwarding response to client...")
        self._request_socket.sendall(reply)
        self.data_received = len(reply)

    def handleHTTPS(self, host: str, port: int, http_version: str):
        # HTTPS connections cannot be cached as the data is encrypted
        log("[+] Creating HTTPS tunnel...")
        self._forwarding_socket.connect((host, port))
        log("[+] Success")
        reply = f"{http_version} 200 Connection established\r\n\r\n"
        log("[+] Sending connection established to client...")
        self._request_socket.sendall(reply.encode(ENCODING))
        log("[+] HTTPS tunnel established. Data between client and server is now being securely forwarded")

        # stop blocking. recv will now throw an exception when there is no data to be received.
        # when data is sent, request will be populated and the try will continue executing.
        # when the connection is closed, 0 bytes will be returned and the while loop will be exited.
        self._forwarding_socket.setblocking(False)
        self._request_socket.setblocking(False)

        while not self._wants_stop:
            # this is broken into two separate statements because if client has nothing to send, an error
            # will be thrown and the try statement will exit and the loop will restart. this means that the server
            # data will never be queried until the client has data to receive as the try statement will never move on.
            # breaking it into two ensures that they are both queried equally
            try:
                request = self._request_socket.recv(HEADER_SIZE)
                length = len(request)
                if length == 0:
                    log(f"[-] Client closed the connection")
                    break
                log(f"[+] Client sent {length} bytes")
                self._forwarding_socket.sendall(request)
            except socket.error: # error saying there is no data being sent by the client. continue the loop
                pass
            try:
                reply = self._forwarding_socket.recv(HEADER_SIZE)
                length = len(reply)
                if length == 0:
                    log(f"[-] Server closed the connection")
                    break
                log(f"[+] Server sent {length} bytes")
                self._request_socket.sendall(reply)
            except socket.error: # error saying there is no data being sent by the server. continue the loop
                pass

    def handle(self):
        log("[+] Receive request from client...")

        request_data = recvall(self._request_socket)
        request_header = self.header_from_data(request_data)

        method = request_header[0]
        url = request_header[1]
        host = url.hostname
        port = url.port
        http_version = request_header[2]

        log(f"[+] Client attempting to connect to {host}:{port}")

        if f"{url.scheme}{url.hostname}" in blocked_urls:  # if example.com is blocked, block all sub paths too
            sys.stderr.write(f"[-] Connections to and from '{host}:{port}' are blocked. Cancelling...\n")
            sys.stderr.flush()
            return

        message = f"{method} {host}:{port} {http_version}"

        if port == 80:
            t1 = time()
            self.handleHTTP(host, port, request_data)
            t2 = time()

            if timing:
                message += f" took {t2 - t1:.5f} ms"
            print(message)
        elif port == 443:
            if method != "CONNECT":
                raise NotImplementedError("This proxy only supports HTTP tunneling for HTTPS connections.")
            print(message)
            self.handleHTTPS(host, port, http_version) # no need to pass request data as we know it's a CONNECT message
        else:
            raise NotImplementedError("Only http and https connections are supported with this proxy")

    def finish(self):
        log("[+] Closing forwarding socket...")
        self._forwarding_socket.close()
        log("[+] Closing request socket...\n")
        self._request_socket.close()


class ProxyServer:
    socket: socket.socket
    request_queue_size = 5
    server_address: tuple[str, int]
    _threads: list[ProxyRequestHandler] = []
    _user_wants_to_exit = False # have to create this as accept is blocking and there's no way of getting Keyboard Interrupts otherwise
    data_sent = 0  # in bytes
    data_received = 0  # in bytes

    def cleanup_finished_requests(self):
        assert threading.current_thread() is threading.main_thread() # must be main to join
        for thread in self._threads:
            if not thread.is_alive():
                self._threads.remove(thread)
                thread.join() # won't block as work is done
                self.data_sent += thread.data_sent
                self.data_received += thread.data_received

    def handle_request(self):
        request, client_address = self.socket.accept()
        thread = ProxyRequestHandler(request)
        self._threads.append(thread)
        thread.start()

    def signal_handler(self, signal, frame):
        self._user_wants_to_exit = True

    def serve_forever(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        while True:
            try:
                self.cleanup_finished_requests() # cleanup threads so that we aren't keeping a massive array of tasks every time
                self.handle_request()
            except socket.timeout:
                if self._user_wants_to_exit: # check if user has pressed Ctrl+C while we were listening for connections
                    self.shutdown()
                    raise KeyboardInterrupt
                continue # do nothing
            except:
                self.shutdown()
                raise

    def shutdown(self):
        print("[-] Stopping web server...")
        self.socket.close()
        for thread in self._threads: # join any threads. this will block
            thread.cancel() # stop from blocking
            thread.join()
            self.data_sent += thread.data_sent
            self.data_received += thread.data_received

    def __init__(self, server_address):
        self.server_address = server_address
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(1.0) # will timeout from accept every 1s so it doesn't block and we can interrupt with a Keyboard exception
        try:
            self.socket.bind(self.server_address)
            self.socket.listen(self.request_queue_size)
        except:
            self.socket.close()
            raise


def start_proxy(args):
    global verbose
    global timing

    if "-t" in args:
        timing = True
    if "-v" in args:
        verbose = True

    print("[+] Loading blocklist...")
    urls = blocklist.read_blocklist()
    if len(urls):
        print("[+] Blocking the following URLs:")
    for url in urls:
        print(f"\t{url}")
    print("[+] Starting proxy server...")
    server = ProxyServer((HOST_NAME, PORT))
    print(f"[+] Server listening on port {PORT}", end='\n\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[-] Server successfully stopped.")
        print(f"[-] Total HTTP data sent: {server.data_sent} bytes.")
        print(f"[-] Total HTTP data received: {server.data_received} bytes.")
