这个是RJ45网口对应的网卡：`enP8p1s0`
以下命令把这个网卡修改成静态ipv4地址
`sudo nmcli connection modify "Wired connection 1" ipv4.method manual ipv4.addresses 192.168.123.222/24 ifname enP8p1s0`
重新激活该连接使其生效
```bash
sudo nmcli connection down "Wired connection 1"
sudo nmcli connection up "Wired connection 1"
```    
这会先断开连接，然后再以新的配置重新连接。

然后可以ping到机器狗
`ping 192.168.123.161`