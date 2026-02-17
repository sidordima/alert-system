import httpx
import asyncio
import logging
import re
import operator
import ssl
from urllib.parse import urlparse
from datetime import datetime, timezone
from cryptography import x509

logger = logging.getLogger(__name__)


class Status:
    VALID_HTTP_CODES = (200, 201, 202, 203, 204, 205, 206, 207, 208, 226)

    def __init__(self, url, status=VALID_HTTP_CODES, timeout=5, **kwargs):
        self.url = url
        self.codes = status if isinstance(status, (list, tuple)) else [status]
        self.timeout = timeout
        self.last_status = True
        self.succ_check = True

    async def check(self, client: httpx.AsyncClient):
        try:
            # Теперь мы принимаем client извне
            resp = await client.get(self.url, timeout=self.timeout)
            self.succ_check = True
            self.last_status = resp.status_code in self.codes
        except Exception as e:
            self.succ_check = False
            self.last_status = False
            logger.error(f"Status check failed for {self.url}: {e}")
        return self.last_status


class Compare:
    regexp_dig = r"\s*(-?\d+(?:\.\d+)?)\s*"
    OPERATORS = {"<": operator.lt, "<=": operator.le, "=": operator.eq,
                 "==": operator.eq, ">=": operator.ge, ">": operator.gt}

    def __init__(self, url, mask, sign, value, timeout=5, **kwargs):
        self.url = url
        self.sign = sign
        self.value = float(value)
        self.timeout = timeout
        self.last_status = True
        self.succ_check = True

        match = re.search(self.regexp_dig, mask)
        if not match: raise ValueError(f"No digits in mask: {mask}")
        found_val = match.group(1)
        split_mask = mask.split(found_val, 1)
        self.mask = "".join([split_mask[0].rstrip(), self.regexp_dig, split_mask[1].lstrip()])

    async def check(self, client: httpx.AsyncClient):
        try:
            resp = await client.get(self.url, timeout=self.timeout)
            print("Код",resp.status_code)
            self.succ_check = True
            self.last_status = True
            if resp.is_success:

                if m := re.search(self.mask, resp.text):
                    val = float(m.group(1))
                    self.last_status = self.OPERATORS[self.sign](val, self.value)
                    print("Статус по оператору",self.last_status)
                    self.succ_check = True
                else:
                    self.succ_check = False
                    self.last_status = False
            else:
                self.succ_check = False
                self.last_status = False
        except Exception as e:
            self.succ_check = False
            self.last_status = False
        return self.last_status


class SSLcheck:
    def __init__(self, url, day_before, timeout=5, **kwargs):
        self.url = url
        self.day_before = day_before
        self.timeout = timeout
        self.last_status = True
        self.succ_check = True

    async def check(self, client=None):  # client теперь не обязателен для этой логики
        parsed = urlparse(self.url)
        target_url = parsed.hostname
        target_port = parsed.port or 443

        # 1. Настраиваем контекст так, чтобы он не обрывал соединение на просроченном сертификате
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        try:
            # 2. Устанавливаем соединение (сразу переходим к "магии SSL")
            connect_coro = asyncio.open_connection(
                target_url, target_port, ssl=context, server_hostname=target_url
            )
            _, writer = await asyncio.wait_for(connect_coro, timeout=self.timeout)

            # 3. Извлекаем данные сертификата
            # 1. Получаем сертификат в бинарном виде (binary_form=True)
            cert_binary = writer.transport.get_extra_info('ssl_object').getpeercert(binary_form=True)

            # 2. Декодируем байты в объект сертификата
            cert = x509.load_der_x509_certificate(cert_binary)

            # 3. Достаем дату (в новых версиях cryptography используйте not_valid_after_utc)
            expiry = cert.not_valid_after_utc
            print(expiry)
            writer.close()
            await writer.wait_closed()


            # 4. Парсим дату (формат в сертификатах стандартный)


            days_left = (expiry - datetime.now(timezone.utc)).days
            print(f"Для {target_url} осталось дней: {days_left}")

            self.last_status = days_left > self.day_before
            self.succ_check = True

        except Exception as e:
            print(f"ОШИБКА при проверке {target_url}: {e}")
            self.last_status = False
            self.succ_check = False

        return self.last_status