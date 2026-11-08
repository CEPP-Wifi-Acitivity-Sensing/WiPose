# Flash RuView 0.8.8 on an ESP32-S3 with 8 MB flash

Use this bundle only with an ESP32-S3 whose physical flash is 8 MB.
Never write it to an ESP32-C6 or a 4 MB S3.

## Before you start

1. Install esptool: `python3 -m pip install esptool`.
2. Connect the node by USB and identify its exact serial port.
3. Back up the current flash or application partition.
4. Stop any serial monitor or RuView process using the port.
5. Do not erase flash if you want to retain the node's WiFi and RuView settings.

## Write the complete bundle

Replace `/dev/cu.usbmodemXXXX` with the confirmed port:

```bash
python3 -m esptool --chip esp32s3 --port /dev/cu.usbmodemXXXX --baud 460800 write_flash \
  0x0000 bootloader.bin \
  0x8000 partition-table.bin \
  0xf000 ota_data_initial.bin \
  0x20000 esp32-csi-node.bin
```

These four files do not include an NVS image, so this command preserves the
existing NVS region. Keep a backup anyway.

## Validate

Reboot the node. Confirm firmware `0.8.8`, the expected node ID, WiFi channel,
and sensing-server address. Then require a five-minute live burn-in with no
parser or transport errors before using the node for calibration.
