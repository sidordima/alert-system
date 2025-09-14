import re
import logging
import requests
import ssl
import socket
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class Status:
    VALID_HTTP_CODES = (200, 201, 202, 203, 204, 205, 206, 207, 208, 226)
    def __init__(self, url, status=VALID_HTTP_CODES, timeout=5):
        if not isinstance(status, (list, tuple)):
            self.code = [str(status)]
        self.url = url
        self.code = status
        self.timeout = timeout
        self.last_status = True
        self.succ_check = False

    def check(self):
        try:
            response = requests.get(self.url, timeout=self.timeout)
        except Exception as e:
            self.succ_check = False
            logger.error(f"URL:{self.url} did not work: error - {e}")
            return False

        self.succ_check = True
        self.last_status = True if response.status_code in self.code else False
        return self.last_status

class Compare:
    """
    mask - example of string, where you need to extract target value
    sign - "<","<=","=",">=',">"
    value - pivot value
    """
    regexp_dig = r"\s*(-?\d+(?:\.\d+)?)\s*"

    def __init__(self, url, mask, sign, value, timeout = 5):
        self.url = url
        self.sign = sign
        self.value = value
        self.timeout = timeout
        self.last_status = True
        self.succ_check = False

        match = re.search(self.regexp_dig, mask)
        if match:
            value = match.group(1)
        else:
            raise Exception(f"Value(digits) do not find in {mask}")
        split_mask = mask.split(value, 1)
        self.mask = "".join([split_mask[0].rstrip(), self.regexp_dig, split_mask[1].lstrip()])

    def check(self):
        try:
            response = requests.get(self.url, timeout=self.timeout)
        except Exception as e:
            self.succ_check = False
            logger.error(f"URL:{self.url} did not work: error - {e}")
            return False

        if response.ok:
            if match := re.search(self.mask, response.text):
                extracted_value = match.group(1)
                self.last_status = eval(f'{extracted_value}{self.sign}{self.value}')
                self.succ_check = True
            else:
                logger.info(f"Did not find value by mask: {response.text[:60]}")
                self.succ_check = False
        else:
            logger.error(f"...{self.url[-20:]} have status {response.status_code}. I can't check value")
        return self.last_status

class SSLcheck:
    def __init__(self,url,day_before,timeout=5):
        self.url = url
        self.timeout = timeout
        self.day_before = day_before
        self.last_status = True
        self.succ_check = False

    def check(self):
        try:
            response = requests.get(self.url, timeout=self.timeout)
        except Exception as e:
            self.succ_check = False
            logger.error(f"URL:{self.url} did not work: error - {e}")
            return False

        parsed = urlparse(self.url)
        target_url = parsed.hostname
        target_port = parsed.port or 443  # если не указан, берём 443

        context = ssl.create_default_context()
        with socket.create_connection((target_url, target_port)) as sock:
            with context.wrap_socket(sock, server_hostname=target_url) as ssock:
                cert = ssock.getpeercert()
                expiry = datetime.strptime(cert['notAfter'], "%b %d %H:%M:%S %Y %Z")

        days_left = (expiry - datetime.now(timezone.utc)).days
        return True if self.day_before<days_left else False

