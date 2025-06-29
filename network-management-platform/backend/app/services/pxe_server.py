"""
Modern PXE boot server implementation with iPXE support
"""

import asyncio
import socket
import struct
import logging
import os
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import ipaddress
import aiofiles
from enum import Enum

from app.core.redis_client import cache_manager
from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class BootMode(str, Enum):
    BIOS = "bios"
    UEFI = "uefi"
    BOTH = "both"


class DHCPServer:
    """DHCP server with PXE boot options"""
    
    def __init__(self, interface: str, subnet: str, tftp_server: str, 
                 http_server: str, boot_mode: BootMode = BootMode.BOTH):
        self.interface = interface
        self.subnet = ipaddress.ip_network(subnet)
        self.tftp_server = tftp_server
        self.http_server = http_server
        self.boot_mode = boot_mode
        
        # DHCP configuration
        self.lease_time = 86400  # 24 hours
        self.leases: Dict[str, Dict[str, Any]] = {}
        self.reservations: Dict[str, str] = {}  # MAC -> IP mapping
        
        # Socket for DHCP
        self.sock = None
        self.running = False
        
    async def start(self):
        """Start DHCP server"""
        try:
            # Create UDP socket for DHCP
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sock.bind(('', 67))  # DHCP server port
            
            self.running = True
            logger.info(f"DHCP server started on {self.interface}")
            
            # Start handling DHCP requests
            await self._handle_dhcp_requests()
            
        except Exception as e:
            logger.error(f"Failed to start DHCP server: {e}")
            self.running = False
            raise
    
    async def stop(self):
        """Stop DHCP server"""
        self.running = False
        if self.sock:
            self.sock.close()
        logger.info("DHCP server stopped")
    
    async def _handle_dhcp_requests(self):
        """Handle incoming DHCP requests"""
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                # Receive DHCP packet
                data, addr = await loop.sock_recvfrom(self.sock, 1024)
                
                # Parse DHCP packet
                dhcp_packet = self._parse_dhcp_packet(data)
                
                if dhcp_packet:
                    # Process based on message type
                    msg_type = dhcp_packet.get('message_type')
                    
                    if msg_type == 1:  # DHCPDISCOVER
                        await self._handle_dhcp_discover(dhcp_packet, addr)
                    elif msg_type == 3:  # DHCPREQUEST
                        await self._handle_dhcp_request(dhcp_packet, addr)
                    
            except Exception as e:
                logger.error(f"Error handling DHCP request: {e}")
    
    def _parse_dhcp_packet(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse DHCP packet"""
        try:
            if len(data) < 240:
                return None
            
            # Extract fields
            op = data[0]
            htype = data[1]
            hlen = data[2]
            xid = struct.unpack('!I', data[4:8])[0]
            client_ip = socket.inet_ntoa(data[12:16])
            your_ip = socket.inet_ntoa(data[16:20])
            server_ip = socket.inet_ntoa(data[20:24])
            gateway_ip = socket.inet_ntoa(data[24:28])
            client_mac = data[28:28+hlen].hex()
            
            # Parse options
            options = {}
            if len(data) > 240 and data[236:240] == b'\x63\x82\x53\x63':  # Magic cookie
                i = 240
                while i < len(data):
                    if data[i] == 255:  # End option
                        break
                    elif data[i] == 0:  # Pad option
                        i += 1
                        continue
                    
                    opt_code = data[i]
                    opt_len = data[i+1]
                    opt_data = data[i+2:i+2+opt_len]
                    options[opt_code] = opt_data
                    i += 2 + opt_len
            
            # Get message type
            message_type = None
            if 53 in options:
                message_type = options[53][0]
            
            return {
                'xid': xid,
                'client_mac': client_mac,
                'client_ip': client_ip,
                'message_type': message_type,
                'options': options
            }
            
        except Exception as e:
            logger.error(f"Failed to parse DHCP packet: {e}")
            return None
    
    async def _handle_dhcp_discover(self, packet: Dict[str, Any], addr: Tuple[str, int]):
        """Handle DHCP DISCOVER message"""
        try:
            client_mac = packet['client_mac']
            xid = packet['xid']
            
            # Allocate IP address
            offered_ip = self._allocate_ip(client_mac)
            if not offered_ip:
                logger.warning(f"No IP available for {client_mac}")
                return
            
            # Build DHCP OFFER
            response = self._build_dhcp_offer(xid, client_mac, offered_ip)
            
            # Send response
            await self._send_dhcp_response(response)
            
            logger.info(f"DHCP OFFER sent to {client_mac}: {offered_ip}")
            
        except Exception as e:
            logger.error(f"Failed to handle DHCP DISCOVER: {e}")
    
    async def _handle_dhcp_request(self, packet: Dict[str, Any], addr: Tuple[str, int]):
        """Handle DHCP REQUEST message"""
        try:
            client_mac = packet['client_mac']
            xid = packet['xid']
            
            # Get requested IP from options
            requested_ip = None
            if 50 in packet['options']:  # Requested IP option
                requested_ip = socket.inet_ntoa(packet['options'][50])
            
            # Validate and confirm lease
            if self._confirm_lease(client_mac, requested_ip):
                # Build DHCP ACK
                response = self._build_dhcp_ack(xid, client_mac, requested_ip)
                
                # Send response
                await self._send_dhcp_response(response)
                
                logger.info(f"DHCP ACK sent to {client_mac}: {requested_ip}")
                
                # Broadcast boot event
                await websocket_manager.connection_manager.broadcast_to_channel(
                    "pxe_boot",
                    {
                        "type": "dhcp_lease",
                        "mac_address": client_mac,
                        "ip_address": requested_ip,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            
        except Exception as e:
            logger.error(f"Failed to handle DHCP REQUEST: {e}")
    
    def _allocate_ip(self, mac_address: str) -> Optional[str]:
        """Allocate IP address for client"""
        # Check reservations first
        if mac_address in self.reservations:
            return self.reservations[mac_address]
        
        # Find available IP in subnet
        for ip in self.subnet.hosts():
            ip_str = str(ip)
            if ip_str not in [lease['ip'] for lease in self.leases.values()]:
                return ip_str
        
        return None
    
    def _confirm_lease(self, mac_address: str, ip_address: str) -> bool:
        """Confirm IP lease for client"""
        self.leases[mac_address] = {
            'ip': ip_address,
            'mac': mac_address,
            'timestamp': datetime.utcnow(),
            'lease_time': self.lease_time
        }
        return True
    
    def _build_dhcp_offer(self, xid: int, client_mac: str, offered_ip: str) -> bytes:
        """Build DHCP OFFER packet"""
        return self._build_dhcp_response(2, xid, client_mac, offered_ip)  # 2 = DHCPOFFER
    
    def _build_dhcp_ack(self, xid: int, client_mac: str, offered_ip: str) -> bytes:
        """Build DHCP ACK packet"""
        return self._build_dhcp_response(5, xid, client_mac, offered_ip)  # 5 = DHCPACK
    
    def _build_dhcp_response(self, msg_type: int, xid: int, client_mac: str, 
                            offered_ip: str) -> bytes:
        """Build DHCP response packet with PXE options"""
        # DHCP header
        packet = bytearray(240)
        packet[0] = 2  # Boot reply
        packet[1] = 1  # Ethernet
        packet[2] = 6  # Hardware address length
        packet[4:8] = struct.pack('!I', xid)
        packet[16:20] = socket.inet_aton(offered_ip)  # Your IP
        packet[20:24] = socket.inet_aton(self.tftp_server)  # Server IP
        
        # Client MAC address
        mac_bytes = bytes.fromhex(client_mac.replace(':', ''))
        packet[28:28+len(mac_bytes)] = mac_bytes
        
        # Boot filename (for legacy PXE)
        if self.boot_mode in [BootMode.BIOS, BootMode.BOTH]:
            boot_file = b'ipxe.pxe'
            packet[108:108+len(boot_file)] = boot_file
        
        # DHCP magic cookie
        packet[236:240] = b'\x63\x82\x53\x63'
        
        # DHCP options
        options = bytearray()
        
        # Message type
        options.extend([53, 1, msg_type])
        
        # Server identifier
        options.extend([54, 4] + list(socket.inet_aton(self.tftp_server)))
        
        # Lease time
        options.extend([51, 4] + list(struct.pack('!I', self.lease_time)))
        
        # Subnet mask
        subnet_mask = str(self.subnet.netmask)
        options.extend([1, 4] + list(socket.inet_aton(subnet_mask)))
        
        # Router
        gateway = str(list(self.subnet.hosts())[0])
        options.extend([3, 4] + list(socket.inet_aton(gateway)))
        
        # DNS servers
        dns_servers = ['8.8.8.8', '8.8.4.4']
        for dns in dns_servers:
            options.extend([6, 4] + list(socket.inet_aton(dns)))
        
        # PXE-specific options
        # Next server (TFTP)
        options.extend([66, len(self.tftp_server.encode())] + 
                      list(self.tftp_server.encode()))
        
        # Boot filename
        if self.boot_mode == BootMode.UEFI:
            boot_file = 'ipxe.efi'
        else:
            boot_file = 'ipxe.pxe'
        
        options.extend([67, len(boot_file.encode())] + list(boot_file.encode()))
        
        # Vendor class identifier
        vendor_class = b'PXEClient'
        options.extend([60, len(vendor_class)] + list(vendor_class))
        
        # PXE boot server type
        options.extend([43, 6, 6, 1, 0, 0, 0, 0])
        
        # End option
        options.append(255)
        
        # Add options to packet
        packet.extend(options)
        
        return bytes(packet)
    
    async def _send_dhcp_response(self, packet: bytes):
        """Send DHCP response packet"""
        try:
            # Broadcast response
            self.sock.sendto(packet, ('255.255.255.255', 68))
        except Exception as e:
            logger.error(f"Failed to send DHCP response: {e}")


class TFTPServer:
    """TFTP server for PXE boot files"""
    
    def __init__(self, root_dir: str, port: int = 69):
        self.root_dir = Path(root_dir)
        self.port = port
        self.clients: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.running = False
        self.sock = None
        
    async def start(self):
        """Start TFTP server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(('', self.port))
            self.running = True
            
            logger.info(f"TFTP server started on port {self.port}")
            
            # Start handling TFTP requests
            await self._handle_tftp_requests()
            
        except Exception as e:
            logger.error(f"Failed to start TFTP server: {e}")
            self.running = False
            raise
    
    async def stop(self):
        """Stop TFTP server"""
        self.running = False
        if self.sock:
            self.sock.close()
        logger.info("TFTP server stopped")
    
    async def _handle_tftp_requests(self):
        """Handle incoming TFTP requests"""
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self.sock, 1024)
                
                # Parse TFTP packet
                opcode = struct.unpack('!H', data[:2])[0]
                
                if opcode == 1:  # RRQ (Read Request)
                    await self._handle_read_request(data[2:], addr)
                elif opcode == 4:  # ACK
                    await self._handle_ack(data[2:], addr)
                elif opcode == 5:  # ERROR
                    await self._handle_error(data[2:], addr)
                    
            except Exception as e:
                logger.error(f"Error handling TFTP request: {e}")
    
    async def _handle_read_request(self, data: bytes, addr: Tuple[str, int]):
        """Handle TFTP read request"""
        try:
            # Parse filename and mode
            parts = data.split(b'\x00')
            if len(parts) >= 2:
                filename = parts[0].decode('utf-8')
                mode = parts[1].decode('utf-8')
                
                # Security check - prevent directory traversal
                safe_filename = os.path.basename(filename)
                file_path = self.root_dir / safe_filename
                
                if not file_path.exists():
                    await self._send_error(addr, 1, "File not found")
                    return
                
                # Initialize client session
                self.clients[addr] = {
                    'filename': safe_filename,
                    'file_path': file_path,
                    'block_num': 0,
                    'file_size': file_path.stat().st_size
                }
                
                # Send first data block
                await self._send_data_block(addr, 1)
                
                logger.info(f"TFTP RRQ from {addr[0]}: {safe_filename}")
                
        except Exception as e:
            logger.error(f"Failed to handle read request: {e}")
            await self._send_error(addr, 0, "Internal error")
    
    async def _handle_ack(self, data: bytes, addr: Tuple[str, int]):
        """Handle TFTP ACK"""
        try:
            if addr not in self.clients:
                return
            
            block_num = struct.unpack('!H', data[:2])[0]
            client = self.clients[addr]
            
            # Send next block
            next_block = block_num + 1
            await self._send_data_block(addr, next_block)
            
        except Exception as e:
            logger.error(f"Failed to handle ACK: {e}")
    
    async def _send_data_block(self, addr: Tuple[str, int], block_num: int):
        """Send TFTP data block"""
        try:
            if addr not in self.clients:
                return
            
            client = self.clients[addr]
            file_path = client['file_path']
            
            # Calculate offset
            offset = (block_num - 1) * 512
            
            # Read data block
            async with aiofiles.open(file_path, 'rb') as f:
                await f.seek(offset)
                data = await f.read(512)
            
            # Build DATA packet
            packet = struct.pack('!HH', 3, block_num) + data
            
            # Send packet
            self.sock.sendto(packet, addr)
            
            # Check if transfer complete
            if len(data) < 512:
                logger.info(f"TFTP transfer complete: {client['filename']} to {addr[0]}")
                del self.clients[addr]
                
        except Exception as e:
            logger.error(f"Failed to send data block: {e}")
            await self._send_error(addr, 0, "Read error")
    
    async def _send_error(self, addr: Tuple[str, int], error_code: int, 
                         error_msg: str):
        """Send TFTP error packet"""
        try:
            packet = struct.pack('!HH', 5, error_code)
            packet += error_msg.encode('utf-8') + b'\x00'
            self.sock.sendto(packet, addr)
        except Exception as e:
            logger.error(f"Failed to send error packet: {e}")
    
    async def _handle_error(self, data: bytes, addr: Tuple[str, int]):
        """Handle TFTP error"""
        if addr in self.clients:
            del self.clients[addr]


class HTTPBootServer:
    """HTTP server for iPXE boot and large files"""
    
    def __init__(self, root_dir: str, port: int = 8080):
        self.root_dir = Path(root_dir)
        self.port = port
        self.app = None
        
    async def start(self):
        """Start HTTP boot server"""
        from aiohttp import web
        
        self.app = web.Application()
        self.app.router.add_get('/boot/{path:.*}', self._handle_boot_file)
        self.app.router.add_get('/ipxe/{path:.*}', self._handle_ipxe_script)
        self.app.router.add_get('/images/{path:.*}', self._handle_image_file)
        self.app.router.add_get('/preseed/{path:.*}', self._handle_preseed_file)
        self.app.router.add_get('/autoinstall/{path:.*}', self._handle_autoinstall_file)
        
        logger.info(f"HTTP boot server starting on port {self.port}")
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
    
    async def _handle_boot_file(self, request):
        """Handle boot file requests"""
        from aiohttp import web
        
        try:
            path = request.match_info['path']
            file_path = self.root_dir / 'boot' / path
            
            if not file_path.exists() or not file_path.is_file():
                return web.Response(status=404)
            
            # Log boot file access
            client_ip = request.remote
            logger.info(f"HTTP boot file request from {client_ip}: {path}")
            
            # Serve file
            return web.FileResponse(file_path)
            
        except Exception as e:
            logger.error(f"Failed to serve boot file: {e}")
            return web.Response(status=500)
    
    async def _handle_ipxe_script(self, request):
        """Handle iPXE script requests dynamically"""
        from aiohttp import web
        
        try:
            client_ip = request.remote
            mac = request.headers.get('X-Client-MAC', 'unknown')
            
            # Generate dynamic iPXE script based on client
            script = self._generate_ipxe_script(client_ip, mac)
            
            return web.Response(text=script, content_type='text/plain')
            
        except Exception as e:
            logger.error(f"Failed to generate iPXE script: {e}")
            return web.Response(status=500)
    
    def _generate_ipxe_script(self, client_ip: str, mac: str) -> str:
        """Generate dynamic iPXE boot script"""
        base_url = f"http://{self.port}"
        
        script = f"""#!ipxe
# iPXE boot script for {mac}
echo Booting from network...
echo Client IP: {client_ip}
echo MAC: {mac}

# Set variables
set base-url {base_url}
set menu-timeout 30000

# Boot menu
:start
menu Network Boot Menu
item --gap -- ------------------------- Operating Systems -------------------------
item ubuntu2204    Ubuntu 22.04 LTS Server
item ubuntu2404    Ubuntu 24.04 LTS Server
item debian12      Debian 12 (Bookworm)
item centos9       CentOS Stream 9
item --gap -- ------------------------- Tools -------------------------
item memtest       Memtest86+
item shell         iPXE Shell
item reboot        Reboot
choose --timeout ${{menu-timeout}} --default ubuntu2204 selected || goto cancel
goto ${{selected}}

:ubuntu2204
echo Booting Ubuntu 22.04 LTS Server...
kernel ${{base-url}}/images/ubuntu2204/vmlinuz initrd=initrd autoinstall ds=nocloud-net;s=${{base-url}}/autoinstall/ubuntu2204/
initrd ${{base-url}}/images/ubuntu2204/initrd
boot

:ubuntu2404
echo Booting Ubuntu 24.04 LTS Server...
kernel ${{base-url}}/images/ubuntu2404/vmlinuz initrd=initrd autoinstall ds=nocloud-net;s=${{base-url}}/autoinstall/ubuntu2404/
initrd ${{base-url}}/images/ubuntu2404/initrd
boot

:debian12
echo Booting Debian 12...
kernel ${{base-url}}/images/debian12/vmlinuz initrd=initrd auto=true priority=critical preseed/url=${{base-url}}/preseed/debian12.cfg
initrd ${{base-url}}/images/debian12/initrd
boot

:centos9
echo Booting CentOS Stream 9...
kernel ${{base-url}}/images/centos9/vmlinuz initrd=initrd inst.ks=${{base-url}}/kickstart/centos9.cfg
initrd ${{base-url}}/images/centos9/initrd
boot

:memtest
echo Booting Memtest86+...
kernel ${{base-url}}/tools/memtest86+
boot

:shell
echo Entering iPXE shell...
shell

:reboot
reboot

:cancel
echo Boot cancelled
exit
"""
        return script
    
    async def _handle_image_file(self, request):
        """Handle OS image file requests"""
        from aiohttp import web
        
        try:
            path = request.match_info['path']
            file_path = self.root_dir / 'images' / path
            
            if not file_path.exists() or not file_path.is_file():
                return web.Response(status=404)
            
            return web.FileResponse(file_path)
            
        except Exception as e:
            logger.error(f"Failed to serve image file: {e}")
            return web.Response(status=500)
    
    async def _handle_preseed_file(self, request):
        """Handle Debian/Ubuntu preseed files"""
        from aiohttp import web
        
        try:
            path = request.match_info['path']
            file_path = self.root_dir / 'preseed' / path
            
            if not file_path.exists():
                # Generate default preseed if not exists
                preseed_content = self._generate_default_preseed()
                return web.Response(text=preseed_content, content_type='text/plain')
            
            return web.FileResponse(file_path)
            
        except Exception as e:
            logger.error(f"Failed to serve preseed file: {e}")
            return web.Response(status=500)
    
    async def _handle_autoinstall_file(self, request):
        """Handle Ubuntu autoinstall files"""
        from aiohttp import web
        
        try:
            path = request.match_info['path']
            
            # Handle meta-data and user-data separately
            if path.endswith('meta-data'):
                return web.Response(text="", content_type='text/plain')
            
            if path.endswith('user-data'):
                # Generate autoinstall configuration
                autoinstall_content = self._generate_autoinstall_config()
                return web.Response(text=autoinstall_content, 
                                  content_type='text/cloud-config')
            
            # Serve other files
            file_path = self.root_dir / 'autoinstall' / path
            if file_path.exists():
                return web.FileResponse(file_path)
            
            return web.Response(status=404)
            
        except Exception as e:
            logger.error(f"Failed to serve autoinstall file: {e}")
            return web.Response(status=500)
    
    def _generate_default_preseed(self) -> str:
        """Generate default Debian/Ubuntu preseed configuration"""
        return """# Debian/Ubuntu Preseed Configuration
# Generated by Network Management Platform

# Localization
d-i debian-installer/locale string en_US.UTF-8
d-i keyboard-configuration/xkb-keymap select us

# Network configuration
d-i netcfg/choose_interface select auto
d-i netcfg/get_hostname string unassigned-hostname
d-i netcfg/get_domain string unassigned-domain

# Mirror settings
d-i mirror/country string manual
d-i mirror/http/hostname string archive.ubuntu.com
d-i mirror/http/directory string /ubuntu
d-i mirror/http/proxy string

# Account setup
d-i passwd/root-login boolean false
d-i passwd/user-fullname string Ubuntu User
d-i passwd/username string ubuntu
d-i passwd/user-password-crypted password $6$rounds=4096$SALT$HASH
d-i user-setup/allow-password-weak boolean true

# Clock and time zone setup
d-i clock-setup/utc boolean true
d-i time/zone string UTC

# Partitioning
d-i partman-auto/method string regular
d-i partman-auto/choose_recipe select atomic
d-i partman-partitioning/confirm_write_new_label boolean true
d-i partman/choose_partition select finish
d-i partman/confirm boolean true
d-i partman/confirm_nooverwrite boolean true

# Package selection
tasksel tasksel/first multiselect standard, server
d-i pkgsel/include string openssh-server curl wget git
d-i pkgsel/upgrade select full-upgrade
d-i pkgsel/update-policy select unattended-upgrades

# Boot loader installation
d-i grub-installer/only_debian boolean true
d-i grub-installer/with_other_os boolean true

# Finishing up
d-i finish-install/reboot_in_progress note
"""
    
    def _generate_autoinstall_config(self) -> str:
        """Generate Ubuntu autoinstall configuration"""
        return """#cloud-config
autoinstall:
  version: 1
  
  # Locale and keyboard
  locale: en_US.UTF-8
  keyboard:
    layout: us
    variant: ""
  
  # Network configuration
  network:
    version: 2
    ethernets:
      enp0s3:
        dhcp4: true
  
  # Storage configuration
  storage:
    layout:
      name: direct
  
  # Identity
  identity:
    hostname: ubuntu-server
    username: ubuntu
    # Password is 'ubuntu' - change in production!
    password: "$6$rounds=4096$SALT$HASH"
  
  # SSH
  ssh:
    install-server: true
    allow-pw: true
  
  # Package installation
  packages:
    - curl
    - wget
    - git
    - python3
    - python3-pip
    - docker.io
    - net-tools
  
  # Late commands
  late-commands:
    - echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/ubuntu
    - curtin in-target --target=/target -- systemctl enable ssh
    - curtin in-target --target=/target -- systemctl enable docker
"""


class PXEBootManager:
    """Manages PXE boot services and deployment"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.dhcp_server = None
        self.tftp_server = None
        self.http_server = None
        self.deployment_jobs: Dict[str, Dict[str, Any]] = {}
        
    async def start_services(self):
        """Start all PXE boot services"""
        try:
            # Initialize services
            self.dhcp_server = DHCPServer(
                interface=self.config['interface'],
                subnet=self.config['subnet'],
                tftp_server=self.config['tftp_server'],
                http_server=self.config['http_server'],
                boot_mode=BootMode(self.config.get('boot_mode', 'both'))
            )
            
            self.tftp_server = TFTPServer(
                root_dir=self.config['tftp_root'],
                port=self.config.get('tftp_port', 69)
            )
            
            self.http_server = HTTPBootServer(
                root_dir=self.config['http_root'],
                port=self.config.get('http_port', 8080)
            )
            
            # Start services
            await asyncio.gather(
                self.dhcp_server.start(),
                self.tftp_server.start(),
                self.http_server.start()
            )
            
            logger.info("PXE boot services started successfully")
            
            # Store status in cache
            await cache_manager.set("pxe_boot_status", {
                "status": "running",
                "services": {
                    "dhcp": "running",
                    "tftp": "running",
                    "http": "running"
                },
                "config": self.config,
                "started_at": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to start PXE boot services: {e}")
            raise
    
    async def stop_services(self):
        """Stop all PXE boot services"""
        try:
            tasks = []
            
            if self.dhcp_server:
                tasks.append(self.dhcp_server.stop())
            if self.tftp_server:
                tasks.append(self.tftp_server.stop())
            # HTTP server stop would be handled differently
            
            await asyncio.gather(*tasks)
            
            logger.info("PXE boot services stopped")
            
            # Update status
            await cache_manager.set("pxe_boot_status", {
                "status": "stopped",
                "stopped_at": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to stop PXE boot services: {e}")
    
    async def create_deployment_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create OS deployment job"""
        try:
            job_id = f"deploy-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            
            # Validate configuration
            required_fields = ["target_mac", "os_type", "hostname"]
            for field in required_fields:
                if field not in job_config:
                    return {
                        "success": False,
                        "error": f"Missing required field: {field}"
                    }
            
            # Create deployment job
            deployment_job = {
                "id": job_id,
                "config": job_config,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "target_mac": job_config["target_mac"],
                "os_type": job_config["os_type"],
                "hostname": job_config["hostname"]
            }
            
            self.deployment_jobs[job_id] = deployment_job
            
            # Store in cache
            await cache_manager.set(f"deployment_job:{job_id}", deployment_job, ttl=86400)
            
            # Create custom configuration files
            await self._create_deployment_config(job_id, job_config)
            
            return {
                "success": True,
                "job_id": job_id,
                "message": "Deployment job created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create deployment job: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_deployment_config(self, job_id: str, config: Dict[str, Any]):
        """Create custom deployment configuration files"""
        try:
            os_type = config["os_type"]
            
            if os_type.startswith("ubuntu"):
                # Create autoinstall configuration
                await self._create_ubuntu_autoinstall(job_id, config)
            elif os_type.startswith("debian"):
                # Create preseed configuration
                await self._create_debian_preseed(job_id, config)
            elif os_type.startswith("centos") or os_type.startswith("rhel"):
                # Create kickstart configuration
                await self._create_redhat_kickstart(job_id, config)
                
        except Exception as e:
            logger.error(f"Failed to create deployment config: {e}")
    
    async def _create_ubuntu_autoinstall(self, job_id: str, config: Dict[str, Any]):
        """Create Ubuntu autoinstall configuration"""
        try:
            # Generate custom autoinstall configuration
            autoinstall_config = {
                "autoinstall": {
                    "version": 1,
                    "locale": config.get("locale", "en_US.UTF-8"),
                    "keyboard": {
                        "layout": config.get("keyboard_layout", "us"),
                        "variant": ""
                    },
                    "network": {
                        "version": 2,
                        "ethernets": {
                            "enp0s3": {
                                "dhcp4": config.get("use_dhcp", True)
                            }
                        }
                    },
                    "storage": {
                        "layout": {
                            "name": config.get("storage_layout", "direct")
                        }
                    },
                    "identity": {
                        "hostname": config["hostname"],
                        "username": config.get("username", "ubuntu"),
                        "password": config.get("password_hash", 
                                              "$6$rounds=4096$salt$hash")  # Default hash
                    },
                    "ssh": {
                        "install-server": True,
                        "allow-pw": config.get("allow_password_auth", True),
                        "authorized-keys": config.get("ssh_keys", [])
                    },
                    "packages": config.get("packages", [
                        "curl", "wget", "git", "python3", "python3-pip",
                        "docker.io", "net-tools", "htop", "vim"
                    ]),
                    "late-commands": config.get("late_commands", [
                        f"echo '{config.get('username', 'ubuntu')} ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/{config.get('username', 'ubuntu')}",
                        "curtin in-target --target=/target -- systemctl enable ssh",
                        "curtin in-target --target=/target -- systemctl enable docker"
                    ])
                }
            }
            
            # Add user data if provided
            if "user_data" in config:
                autoinstall_config["autoinstall"]["user-data"] = config["user_data"]
            
            # Save configuration
            config_dir = Path(self.config['http_root']) / "autoinstall" / job_id
            config_dir.mkdir(parents=True, exist_ok=True)
            
            user_data_path = config_dir / "user-data"
            async with aiofiles.open(user_data_path, 'w') as f:
                await f.write("#cloud-config\n")
                await f.write(json.dumps(autoinstall_config, indent=2))
            
            # Create empty meta-data file
            meta_data_path = config_dir / "meta-data"
            async with aiofiles.open(meta_data_path, 'w') as f:
                await f.write("")
            
            # Store configuration reference
            await cache_manager.set(
                f"pxe_config:{job_id}",
                {
                    "type": "ubuntu_autoinstall",
                    "path": str(config_dir),
                    "url": f"{self.config['http_server']}/autoinstall/{job_id}/"
                },
                ttl=86400
            )
            
            logger.info(f"Created Ubuntu autoinstall configuration for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to create Ubuntu autoinstall config: {e}")
            raise
    
    async def _create_debian_preseed(self, job_id: str, config: Dict[str, Any]):
        """Create Debian preseed configuration"""
        try:
            # Generate preseed configuration
            preseed_lines = [
                "# Debian Preseed Configuration",
                f"# Generated for job: {job_id}",
                "",
                "# Localization",
                f"d-i debian-installer/locale string {config.get('locale', 'en_US.UTF-8')}",
                f"d-i keyboard-configuration/xkb-keymap select {config.get('keyboard_layout', 'us')}",
                "",
                "# Network configuration",
                "d-i netcfg/choose_interface select auto",
                f"d-i netcfg/get_hostname string {config['hostname']}",
                f"d-i netcfg/get_domain string {config.get('domain', 'local')}",
                "",
                "# Mirror settings",
                "d-i mirror/country string manual",
                f"d-i mirror/http/hostname string {config.get('mirror_hostname', 'deb.debian.org')}",
                f"d-i mirror/http/directory string {config.get('mirror_directory', '/debian')}",
                "d-i mirror/http/proxy string",
                "",
                "# Account setup",
                "d-i passwd/root-login boolean false",
                f"d-i passwd/user-fullname string {config.get('user_fullname', 'Debian User')}",
                f"d-i passwd/username string {config.get('username', 'debian')}",
                f"d-i passwd/user-password-crypted password {config.get('password_hash', '$6$rounds=4096$salt$hash')}",
                "d-i user-setup/allow-password-weak boolean true",
                "",
                "# Clock and time zone setup",
                "d-i clock-setup/utc boolean true",
                f"d-i time/zone string {config.get('timezone', 'UTC')}",
                "",
                "# Partitioning",
                f"d-i partman-auto/method string {config.get('partition_method', 'regular')}",
                "d-i partman-auto/choose_recipe select atomic",
                "d-i partman-partitioning/confirm_write_new_label boolean true",
                "d-i partman/choose_partition select finish",
                "d-i partman/confirm boolean true",
                "d-i partman/confirm_nooverwrite boolean true",
                "",
                "# Package selection",
                f"tasksel tasksel/first multiselect {', '.join(config.get('tasksel', ['standard', 'server']))}",
                f"d-i pkgsel/include string {' '.join(config.get('packages', ['openssh-server', 'curl', 'wget', 'git']))}",
                "d-i pkgsel/upgrade select full-upgrade",
                "d-i pkgsel/update-policy select unattended-upgrades",
                "",
                "# Boot loader installation",
                "d-i grub-installer/only_debian boolean true",
                "d-i grub-installer/with_other_os boolean true",
                "",
                "# Finishing up",
                "d-i finish-install/reboot_in_progress note",
            ]
            
            # Add late commands if provided
            if "late_commands" in config:
                preseed_lines.extend([
                    "",
                    "# Late commands",
                ])
                for cmd in config["late_commands"]:
                    preseed_lines.append(f"d-i preseed/late_command string {cmd}")
            
            # Save configuration
            config_dir = Path(self.config['http_root']) / "preseed"
            config_dir.mkdir(parents=True, exist_ok=True)
            
            preseed_path = config_dir / f"{job_id}.cfg"
            async with aiofiles.open(preseed_path, 'w') as f:
                await f.write('\n'.join(preseed_lines))
            
            # Store configuration reference
            await cache_manager.set(
                f"pxe_config:{job_id}",
                {
                    "type": "debian_preseed",
                    "path": str(preseed_path),
                    "url": f"{self.config['http_server']}/preseed/{job_id}.cfg"
                },
                ttl=86400
            )
            
            logger.info(f"Created Debian preseed configuration for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to create Debian preseed config: {e}")
            raise
    
    async def _create_redhat_kickstart(self, job_id: str, config: Dict[str, Any]):
        """Create RedHat/CentOS kickstart configuration"""
        try:
            # Generate kickstart configuration
            kickstart_lines = [
                "# RedHat/CentOS Kickstart Configuration",
                f"# Generated for job: {job_id}",
                "",
                "# System language",
                f"lang {config.get('lang', 'en_US.UTF-8')}",
                "",
                "# Keyboard layouts",
                f"keyboard --vckeymap={config.get('keyboard', 'us')} --xlayouts='{config.get('keyboard', 'us')}'",
                "",
                "# Network information",
                f"network --bootproto=dhcp --device=link --activate --hostname={config['hostname']}",
                "",
                "# Root password",
                f"rootpw --iscrypted {config.get('root_password_hash', '$6$rounds=4096$salt$hash')}",
                "",
                "# System timezone",
                f"timezone {config.get('timezone', 'UTC')} --utc",
                "",
                "# System bootloader configuration",
                "bootloader --location=mbr --boot-drive=sda",
                "",
                "# Partition clearing information",
                "clearpart --all --initlabel",
                "",
                "# Disk partitioning information",
                "autopart --type=lvm",
                "",
                "# System authorization information",
                "auth --enableshadow --passalgo=sha512",
                "",
                "# SELinux configuration",
                f"selinux --{config.get('selinux', 'enforcing')}",
                "",
                "# Firewall configuration",
                f"firewall --{config.get('firewall', 'enabled')} --ssh",
                "",
                "# Reboot after installation",
                "reboot",
                "",
                "# Packages",
                "%packages",
                "@^minimal",
                "@core",
            ]
            
            # Add custom packages
            for package in config.get('packages', ['openssh-server', 'curl', 'wget', 'git']):
                kickstart_lines.append(package)
            
            kickstart_lines.extend([
                "%end",
                "",
            ])
            
            # Add user creation if specified
            if "username" in config:
                kickstart_lines.extend([
                    "# User creation",
                    f"user --name={config['username']} --password={config.get('password_hash', '$6$rounds=4096$salt$hash')} --iscrypted --gecos=\"{config.get('user_fullname', 'User')}\" --groups=wheel",
                    "",
                ])
            
            # Add post-installation script
            kickstart_lines.extend([
                "%post --log=/root/post-install.log",
                "# Post-installation script",
                "echo 'Post-installation configuration starting...'",
                "",
                "# Enable SSH",
                "systemctl enable sshd",
                "",
                "# Configure sudoers for wheel group",
                "echo '%wheel ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers",
                "",
            ])
            
            # Add custom post commands
            for cmd in config.get('post_commands', []):
                kickstart_lines.append(cmd)
            
            kickstart_lines.extend([
                "",
                "echo 'Post-installation configuration completed'",
                "%end",
            ])
            
            # Save configuration
            config_dir = Path(self.config['http_root']) / "kickstart"
            config_dir.mkdir(parents=True, exist_ok=True)
            
            kickstart_path = config_dir / f"{job_id}.cfg"
            async with aiofiles.open(kickstart_path, 'w') as f:
                await f.write('\n'.join(kickstart_lines))
            
            # Store configuration reference
            await cache_manager.set(
                f"pxe_config:{job_id}",
                {
                    "type": "redhat_kickstart",
                    "path": str(kickstart_path),
                    "url": f"{self.config['http_server']}/kickstart/{job_id}.cfg"
                },
                ttl=86400
            )
            
            logger.info(f"Created RedHat/CentOS kickstart configuration for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to create RedHat kickstart config: {e}")
            raise
    
    async def get_deployment_status(self, job_id: str) -> Dict[str, Any]:
        """Get deployment job status"""
        try:
            job_data = await cache_manager.get(f"deployment_job:{job_id}")
            if job_data:
                return job_data
            else:
                return {
                    "success": False,
                    "error": "Job not found"
                }
                
        except Exception as e:
            logger.error(f"Failed to get deployment status: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Global PXE boot manager instance
pxe_boot_manager = None