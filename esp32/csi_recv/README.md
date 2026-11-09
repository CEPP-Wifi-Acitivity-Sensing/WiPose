# csi_recv
This code is used for a ESP32s3 board

## Uploading Code onto the board
- Locate ESP-IDF extension on VScode
- Select csi_recv workspace
- Select ESP-IDF version
- Select Flash Method : `UART`
- Select Port and Monitor Port
    - If undetected
         - Port is fucked
         - The current USB-C cable doesn't support data transfer
- Set Espressif Device Target (IDF Target) : `ESP32` > `ESP32s3 chip (via ESP-PROG)`
- Build and Flash

## Exporting Data
- Run
`python .\csi_data_read_parse.py -p <PORT> -s <PATH>/<FILE_NAME>.csv -b 1500000 --headless`

- GUI mode with reduced refresh load:
`python .\csi_data_read_parse.py -p <PORT> -b 1500000 --plot-interval-ms 250 --plot-stride 4`

- The parser prints periodic capture stats (`host_fps` and `device_fps`) to help identify whether the bottleneck is host-side parsing/rendering or on-device generation.