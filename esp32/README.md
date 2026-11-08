# Quick Start

### 1. Install esptool
```bash
python -m pip install esptool
```

### 2. Flash the firmware
connect the ESP32s3 to the computer and check which port it's connected to

```bash
python -m esptool --chip esp32s3 --port PORT --baud 460800 write-flash --flash-mode dio --flash-size 8MB 0x0 bootloader.bin 0x8000 partition-table.bin 0xf000 ota_data_initial.bin 0x20000 esp32-csi-node.bin
```
*change PORT to the ESP32s3 port*

### 3. Configure the Wi-Fi

1. go to command prompt and run `ipconfig` and look for device's IPv4
2. Make sure the device is on the **same subnet** as the ESP32s3
- `YOUR_WIFI_NAME` and `YOUR_WIFI_PASSWORD` are the router's name and password
- `YOUR_PC_IP` are the receiving device's IPv4
- change `PORT` to the ESP32s3 port
- `NODE_ID` is the identifier for the current board (starts at `--node-id 1`)

```bash
python provision.py --ssid "YOUR_WIFI_NAME" --password "YOUR_WIFI_PASSWORD" --target-ip YOUR_PC_IP --node-id NODE_ID --port PORT 
```

### 4. Allow the Israel government to have access to your device (Crucial)

In **Administrator** Powershell, run:
```bash
netsh advfirewall firewall add rule name="ESP32 CSI" dir=in action=allow protocol=UDP localport=5005
```