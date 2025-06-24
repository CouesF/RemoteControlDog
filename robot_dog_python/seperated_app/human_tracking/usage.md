use docker to run this code:

```bash
docker run --runtime nvidia --env NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics -it --rm --network host --shm-size=8g \
--volume /tmp/argus_socket:/tmp/argus_socket \
--volume /etc/enctune.conf:/etc/enctune.conf \
--volume /etc/nv_tegra_release:/etc/nv_tegra_release \
--volume /tmp/nv_jetson_model:/tmp/nv_jetson_model \
--volume /var/run/dbus:/var/run/dbus \
--volume /var/run/avahi-daemon/socket:/var/run/avahi-daemon/socket \
--volume /var/run/docker.sock:/var/run/docker.sock \
--volume /home/d3lab/Projects/jetson-containers/data:/data \
-v /etc/localtime:/etc/localtime:ro \
-v /etc/timezone:/etc/timezone:ro \
--device /dev/snd \
-e PULSE_SERVER=unix:/run/user/1000/pulse/native \
-v /run/user/1000/pulse:/run/user/1000/pulse \
--device /dev/bus/usb \
--device /dev/video0 \
--device /dev/video1 \
--device /dev/i2c-0 \
--device /dev/i2c-1 \
--device /dev/i2c-2 \
--device /dev/i2c-4 \
--device /dev/i2c-5 \
--device /dev/i2c-7 \
--device /dev/i2c-9 \
-v /run/jtop.sock:/run/jtop.sock \
--name jetson_container_human_tracking \
-v /home/d3lab/Projects/RemoteControlDog/robot_dog_python/seperated_app/human_tracking:/app \
dustynv/l4t-pytorch:r36.4.0
```

`cd app`

