# =======================================================================
# RoCore - Peer-to-Peer File Sharing System
# College Project - 2nd Year Computer Science
# Description: This backend uses FastAPI to serve the web UI, handle
# chunked file uploads, and manage WebSockets for live progress updates.
# =======================================================================

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
import aiofiles
import logging
from backend.discovery import DiscoveryService
from backend.utils import get_local_ip, generate_qr_base64
import uuid
import json

# Setup basic logging to see server output in terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RoCore Backend")

# Allow CORS so the frontend can make API requests to this backend easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generate a random device name if not provided in environment variables
DEVICE_NAME = os.environ.get("DEVICE_NAME", f"Host-{uuid.uuid4().hex[:4]}")
PORT = int(os.environ.get("PORT", 8080))
IP_ADDRESS = get_local_ip()

# Create the uploads folder if it doesn't exist yet
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Setup Jinja templates for serving the index.html page
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
templates = Jinja2Templates(directory=frontend_dir)

# =======================================================================
# WebSocket Manager
# Keeps track of all connected browsers (like phones scanning the QR)
# =======================================================================
class ConnectionManager:
    def __init__(self):
        # Maps a websocket connection to its client info (name, id, etc)
        self.active_connections = {}
        # Maps a string client_id to its websocket for direct messaging
        self.client_id_to_ws = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = {}

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            info = self.active_connections.pop(websocket)
            if "client_id" in info and info["client_id"] in self.client_id_to_ws:
                del self.client_id_to_ws[info["client_id"]]

    async def register_client(self, websocket: WebSocket, client_id: str, device_name: str, is_host: bool):
        # Save client details when they first connect
        self.active_connections[websocket] = {
            "client_id": client_id,
            "device_name": device_name,
            "is_host": is_host
        }
        self.client_id_to_ws[client_id] = websocket

    async def broadcast(self, message: dict):
        # Send a JSON message to everyone connected
        dead_conns = []
        for connection in self.active_connections.keys():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"WS broadcast error: {e}")
                dead_conns.append(connection)
        
        # Clean up any dead connections
        for c in dead_conns:
            self.disconnect(c)
            
    async def send_to_client(self, client_id: str, message: dict):
        # Send a JSON message to one specific client
        if client_id in self.client_id_to_ws:
            try:
                await self.client_id_to_ws[client_id].send_json(message)
            except Exception as e:
                logger.error(f"WS send error: {e}")

# Global variables
manager = ConnectionManager()
discovery_service = None
main_loop = None

def get_all_peers():
    """
    Returns a combined list of:
    1. This server itself
    2. Other laptops found on the network via mDNS (zeroconf)
    3. Mobile phones connected to us via WebSockets
    """
    # 1. The Server Itself (Host)
    peers = [{
        "client_id": "SERVER",
        "name": DEVICE_NAME,
        "is_host": True,
        "is_web_client": True,  # meaning it accepts direct WS/HTTP relay
        "addresses": [IP_ADDRESS],
        "port": PORT
    }]

    # 2. mDNS peers (other laptops running RoCore)
    if discovery_service:
        peers.extend(discovery_service.get_peers())
    
    # 3. WebSocket clients (mobile devices connected to our IP)
    for ws, info in manager.active_connections.items():
        if "client_id" in info:
            peers.append({
                "client_id": info["client_id"],
                "name": info["device_name"],
                "is_host": info["is_host"],
                "is_web_client": True,
                "addresses": [],
                "port": 0
            })
    return peers

def broadcast_peers_update():
    # Tell all connected clients about the new peers list
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({"type": "peers_update", "peers": get_all_peers()}),
            main_loop
        )

def on_mdns_peers_changed():
    # Callback triggered by discovery.py when a new device is found
    broadcast_peers_update()

@app.on_event("startup")
async def startup_event():
    global discovery_service, main_loop
    main_loop = asyncio.get_running_loop()
    # Start broadcasting our presence on the local network
    discovery_service = DiscoveryService(DEVICE_NAME, IP_ADDRESS, PORT, on_mdns_peers_changed)
    discovery_service.start()

@app.on_event("shutdown")
async def shutdown_event():
    # Stop the network broadcast when server stops
    if discovery_service:
        discovery_service.stop()

# =======================================================================
# API Endpoints
# =======================================================================

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Serve the main frontend UI
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/me")
async def get_me(request: Request):
    # Get server info and generate a QR code for mobile connection
    url = f"http://{IP_ADDRESS}:{PORT}/"
    qr_b64 = generate_qr_base64(url)
    
    client_ip = request.client.host
    # Check if the person loading the page is on the laptop itself
    is_host = client_ip in ["127.0.0.1", "::1", "localhost", IP_ADDRESS]
    
    return {
        "name": DEVICE_NAME,
        "ip": IP_ADDRESS,
        "port": PORT,
        "qr": qr_b64,
        "url": url,
        "is_host_browser": is_host
    }

@app.get("/api/download/{file_id}")
async def download_file(file_id: str, filename: str):
    # Endpoint used by browsers to download the received file
    filepath = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(path=filepath, filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/upload/status")
async def get_upload_status(file_id: str):
    # Check how much of a file is already uploaded (for resuming broken transfers)
    filepath = os.path.join(UPLOAD_DIR, f"{file_id}.part")
    if os.path.exists(filepath):
        return {"uploaded_bytes": os.path.getsize(filepath)}
    return {"uploaded_bytes": 0}

@app.post("/api/upload")
async def upload_file(
    request: Request,
    file_id: str = Form(...),
    filename: str = Form(...),
    sender_name: str = Form("Unknown"),
    total_size: int = Form(...),
    offset: int = Form(0),
    target_client_id: str = Form(""),
    file: UploadFile = File(...)
):
    """
    Handles incoming file chunks. Files are sent in 5MB pieces to prevent
    crashing the server on large files like videos.
    """
    filepath = os.path.join(UPLOAD_DIR, f"{file_id}.part")
    final_filepath = os.path.join(UPLOAD_DIR, filename)

    # If it's the first chunk, notify everyone the transfer started
    if offset == 0:
        await manager.broadcast({
            "type": "transfer_start",
            "transfer_id": file_id,
            "filename": filename,
            "sender": sender_name,
            "direction": "incoming",
            "total_size": total_size
        })

    # 'ab' mode appends to the file, 'wb' overwrites
    mode = 'ab' if offset > 0 else 'wb'
    
    try:
        # Save the chunk using async file IO
        async with aiofiles.open(filepath, mode) as out_file:
            if offset > 0:
                await out_file.seek(offset)
            
            downloaded = offset
            # Read in 1MB blocks
            while content := await file.read(1024 * 1024):
                await out_file.write(content)
                downloaded += len(content)
                
                # Update UI progress bars
                await manager.broadcast({
                    "type": "transfer_progress",
                    "transfer_id": file_id,
                    "downloaded": downloaded,
                    "total_size": total_size
                })
        
        # Check if the entire file is received
        if downloaded >= total_size:
            os.rename(filepath, final_filepath)
            
            await manager.broadcast({
                "type": "transfer_complete",
                "transfer_id": file_id,
                "filepath": final_filepath
            })
            
            # Trigger a download prompt in the target's browser
            if target_client_id:
                download_url = f"/api/download/{file_id}?filename={filename}"
                offer_msg = {
                    "type": "file_offer",
                    "filename": filename,
                    "url": download_url,
                    "sender": sender_name
                }
                
                if target_client_id == "SERVER":
                    # The file was sent to the laptop server. Find the laptop's browser and prompt it.
                    for ws, info in manager.active_connections.items():
                        if info.get("is_host") and "client_id" in info:
                            await manager.send_to_client(info["client_id"], offer_msg)
                else:
                    # File was sent to a specific phone/web client
                    await manager.send_to_client(target_client_id, offer_msg)

            return {"status": "success", "filename": filename, "completed": True}
        else:
            return {"status": "success", "filename": filename, "completed": False, "downloaded": downloaded}
            
    except Exception as e:
        logger.error(f"Transfer failed: {e}")
        await manager.broadcast({
            "type": "transfer_error",
            "transfer_id": file_id,
            "error": str(e)
        })
        return JSONResponse(status_code=500, content={"error": str(e)})

# =======================================================================
# WebSocket Endpoint
# =======================================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial peers list to the new connection
        await websocket.send_json({"type": "peers_update", "peers": get_all_peers()})
        
        # Listen for messages from the browser
        while True:
            data_str = await websocket.receive_text()
            try:
                data = json.loads(data_str)
                if data.get("type") == "register":
                    # Browser is telling us its name and ID
                    await manager.register_client(
                        websocket, 
                        data["client_id"], 
                        data["device_name"],
                        data.get("is_host", False)
                    )
                    # Notify everyone that a new device connected
                    broadcast_peers_update()
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        # User closed the browser tab
        manager.disconnect(websocket)
        broadcast_peers_update()
