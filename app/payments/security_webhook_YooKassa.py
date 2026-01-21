import ipaddress
from aiohttp import web




YOOKASSA_IP_RANGES = [
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.154.128/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "2a02:5180::/32",
]

def is_yookassa_ip(ip: str) -> bool:
    ip_obj = ipaddress.ip_address(ip)
    return any(ip_obj in ipaddress.ip_network(net) for net in YOOKASSA_IP_RANGES)


def get_peer_ip(request: web.Request) -> str | None:
    """
    Возвращает реальный IP клиента, учитывая X-Forwarded-For
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # первый IP в списке — оригинальный
        return x_forwarded_for.split(",")[0].strip()
    return request.remote
