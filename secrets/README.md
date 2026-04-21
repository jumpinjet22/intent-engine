# Docker secrets

Copy the example files and put your real MQTT credentials in the `.txt` files:

```bash
cp secrets/mqtt_username.txt.example secrets/mqtt_username.txt
cp secrets/mqtt_password.txt.example secrets/mqtt_password.txt
```

These files are consumed by `docker-compose.secrets.yml` and mounted into the
`intent-engine` container as Docker secrets.
