import socket
import logging
from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf, ServiceListener
import threading
import time

logger = logging.getLogger(__name__)

class RoCoreListener(ServiceListener):
    def __init__(self, callback):
        self.peers = {} # name -> info
        self.callback = callback # Function to call when peers change

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        logger.info(f"Service {name} removed")
        if name in self.peers:
            del self.peers[name]
            self.callback()

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
            if addresses:
                peer_info = {
                    "name": name.split(".")[0],
                    "addresses": addresses,
                    "port": info.port,
                    "server": info.server,
                    "properties": {k.decode(): v.decode() for k, v in info.properties.items()}
                }
                logger.info(f"Service {name} added: {peer_info}")
                self.peers[name] = peer_info
                self.callback()

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

class DiscoveryService:
    def __init__(self, device_name: str, ip_address: str, port: int, callback):
        self.device_name = device_name
        self.ip_address = ip_address
        self.port = port
        self.type = "_rocore._tcp.local."
        self.name = f"{self.device_name}.{self.type}"
        self.zeroconf = Zeroconf()
        self.listener = RoCoreListener(callback)
        self.browser = ServiceBrowser(self.zeroconf, self.type, self.listener)
        self.info = None

    def start(self):
        desc = {'version': '1.0', 'device_name': self.device_name}
        try:
            self.info = ServiceInfo(
                self.type,
                self.name,
                addresses=[socket.inet_aton(self.ip_address)],
                port=self.port,
                properties=desc,
                server=f"{self.device_name}.local.",
            )
            self.zeroconf.register_service(self.info)
            logger.info(f"Registered mDNS service: {self.name} at {self.ip_address}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to register service: {e}")

    def stop(self):
        if self.info:
            self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()

    def get_peers(self):
        return list(self.listener.peers.values())
