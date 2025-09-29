# PARKING_PI3 (Pi 5 Support Branch)

This branch adds Raspberry Pi 5 support while preserving Pi 3 behavior.

## Services
- `mosquitto-broker`: MQTT broker (Eclipse Mosquitto).
- `pi3-subscriber`: MQTT subscriber controlling LEDs via gpiozero on Pi 5.
- `webpanel`: Flask app (unchanged here).

## Raspberry Pi 5 notes
- Uses `gpiozero` with the `lgpio` backend. GPIO devices are `/dev/gpiochip*`.
- LED pins:
  - Physical 37 → BCM 26 (verde)
  - Physical 35 → BCM 19 (amarillo)
  - Physical 33 → BCM 13 (rojo)

## Environment
Subscriber reads:
- `BROKER_HOST` (default `localhost`)
- `BROKER_PORT` (default `1883`)
- `TOPIC` (default `deepstream/car_count`)

Create an `.env` if needed for the webpanel, or adjust compose.

## Build & Run on Pi 5
```bash
# From repo root, on the Raspberry Pi 5
sudo docker compose pull
sudo docker compose build --no-cache
sudo docker compose up -d

# View logs
sudo docker compose logs -f pi3-subscriber
```

If you prefer least-privilege, remove `privileged: true` and keep only the `/dev/gpiochip*` device mappings.

## Keep Pi 3 code intact
All changes are on branch `feature/pi5-support`. The `master` branch keeps the Pi 3 (RPi.GPIO) version.
