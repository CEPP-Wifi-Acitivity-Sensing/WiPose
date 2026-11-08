import socket
import struct
import math
import csv
import time
from datetime import datetime

HOST = "0.0.0.0"
PORT = 5005

CSV_FILE = "./csi_data/test.csv"

MAGIC = 0xC5110001
HEADER_SIZE = 20


def parse_csi(data):

    if len(data) < HEADER_SIZE:
        return None

    # Check RuView ADR-018 magic
    magic = struct.unpack_from("<I", data, 0)[0]

    if magic != MAGIC:
        return None

    node_id = data[4]

    n_antennas = data[5]

    n_subcarriers = struct.unpack_from("<H", data, 6)[0]

    frequency_mhz = struct.unpack_from("<I", data, 8)[0]

    sequence = struct.unpack_from("<I", data, 12)[0]

    rssi = struct.unpack_from("<b", data, 16)[0]

    noise_floor = struct.unpack_from("<b", data, 17)[0]

    expected_length = (
        HEADER_SIZE
        + n_antennas * n_subcarriers * 2
    )

    if len(data) < expected_length:
        return None

    amplitudes = []
    phases = []

    offset = HEADER_SIZE

    # Read CSI I/Q data
    for antenna in range(n_antennas):

        antenna_amplitudes = []
        antenna_phases = []

        for subcarrier in range(n_subcarriers):

            i = struct.unpack_from("<b", data, offset)[0]
            q = struct.unpack_from("<b", data, offset + 1)[0]

            offset += 2

            amplitude = math.sqrt(i * i + q * q)

            phase = math.atan2(q, i)

            antenna_amplitudes.append(amplitude)
            antenna_phases.append(phase)

        amplitudes.append(antenna_amplitudes)
        phases.append(antenna_phases)

    return {
        "node_id": node_id,
        "amplitudes": amplitudes,
        "phases": phases,
        "n_antennas": n_antennas,
        "n_subcarriers": n_subcarriers,
    }


# --------------------------------------------------
# Start UDP listener
# --------------------------------------------------

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print(f"Listening on UDP port {PORT}...")

# Runtime starts here
start_time = time.perf_counter()


# --------------------------------------------------
# Open CSV
# --------------------------------------------------

with open(CSV_FILE, "w", newline="") as csvfile:

    writer = csv.writer(csvfile)

    # Four columns
    writer.writerow([
        "time",
        "runtime",
        "node_id",
        "amplitudes",
        "phases"
    ])

    while True:

        data, addr = sock.recvfrom(65535)

        frame = parse_csi(data)

        if frame is None:
            continue

        # Current clock time
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Time since program started
        runtime = time.perf_counter() - start_time

        # Use first antenna
        amplitudes = frame["amplitudes"][0]
        phases = frame["phases"][0]

        # Convert arrays into CSV-friendly strings
        amplitude_string = ",".join(
            f"{x:.3f}" for x in amplitudes
        )

        phase_string = ",".join(
            f"{x:.5f}" for x in phases
        )

        # Write one row
        writer.writerow([
            timestamp,
            f"{runtime:.3f}",
            frame["node_id"],
            amplitude_string,
            phase_string
        ])

        # Make sure data is written immediately
        csvfile.flush()

        print(
            f"{timestamp} | "
            f"Node: {frame['node_id']} | "
            f"Runtime: {runtime:.3f}s | "
            f"Subcarriers: {len(amplitudes)} \n"
            f"Amplitudes: {amplitude_string} \n"
            f"Phases: {phase_string} \n"
        )