# RoCore

**Remote Core Communication**  
A local-first, peer-to-peer communication system that enables devices on the same network to discover, connect, and exchange files natively through the browser—without relying on cloud storage, internet connectivity, or native apps.

## 🚀 Features

- **True Cross-Platform**: Works instantly on iOS, Android, macOS, Windows, and Linux. No apps to install.
- **Local-First Speed**: Transfers happen entirely over your local Wi-Fi or hotspot. No internet required, meaning no data limits and full-speed local bandwidth.
- **Zero Configuration**: Uses mDNS (Zeroconf) for automatic discovery of other laptops on the network.
- **Seamless Mobile Pairing**: Simply scan the QR code from the host laptop to instantly connect a mobile device.
- **Resumable Chunked Uploads**: Files are chunked and streamed. If the connection drops, transfers can resume right where they left off.
- **Modern Minimal UI**: Built with a sleek, spacious, and intuitive interface designed for clarity and ease of use.

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, WebSockets (for real-time peer state and progress)
- **Networking**: `zeroconf` (mDNS network broadcast), `aiofiles` (async file streaming)
- **Frontend**: HTML5, Vanilla JavaScript, Tailwind CSS (via CDN)

## 📦 Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/debdattamandalin/RoCore.git
   cd RoCore
   ```

2. **Run the server**
   The project includes a convenient startup script that automatically creates a virtual environment, installs dependencies, and launches the server.
   
   ```bash
   chmod +x run.sh
   ./run.sh
   ```

3. **Access the Application**
   - On your Host machine (where the server is running), open your browser and go to: `http://localhost:8080`
   - To connect a mobile device, just point your phone's camera at the QR code displayed on the host's screen.

## 📱 How to Use

1. Start `RoCore` on your laptop.
2. Open the UI. You'll see your network name (e.g., `Host-6678`) and a QR code.
3. If another laptop on the same Wi-Fi runs `RoCore`, it will automatically appear in the **Nearby Devices** list.
4. Scan the QR code with your phone. Your phone will immediately appear in the **Nearby Devices** list on the laptop, and the laptop will appear on the phone.
5. Click **Send** next to any device to transfer files seamlessly!

## 🎓 Academic Note
This project was developed as a 2nd Year Computer Science project, demonstrating applied concepts in local networking, async web servers, websockets, and modern web UI/UX design.

## 📄 License
This project is open-source and available under the MIT License.
