CHAY ISAAC SIM QUA STREAM (TAILSCALE)
=====================================

1. CAI TAILSCALE (chi lam 1 lan)
-------------------------------------
Tren VM:
  curl -fsSL https://tailscale.com/install.sh | sh
  tailscale up                 # mo link no in ra de dang nhap
  tailscale ip -4              # ra 100.x.y.z -> ghi lai

Tren may cua ban:
  Cai Tailscale (https://tailscale.com/download), dang nhap CUNG tai khoan.
  Kiem tra: tailscale ping 100.x.y.z   -> phai ra "pong"


2. CHAY
-------------------------------------
Tren VM:
```
  cd /home/PhyRC_2027_Challenge
  docker stop $(docker ps -q --filter label=phyrc.project=PhyRC_2027)
  ISAACSIM_HOST=$(tailscale ip -4) ./run.sh gui --stream 2>&1 | tee stream_run.log
```

  Dong dau phai la:  Livestream: host 100.x.y.z, signaling 49100/TCP, media 47998/UDP.
  Cho log hien cac dong friction (Gripper/cloth, Table/cloth) = scene da load.
  Lan dau mat 5-10 phut.


3. KET NOI
-------------------------------------
Tren may cua ban:
  1) Tai "Isaac Sim WebRTC Streaming Client" (trang download Isaac Sim,
     muc Latest Release), cai dat va mo len.
  2) O o Server, nhap: 100.x.y.z   (IP Tailscale cua VM)
  3) Bam Connect.
  4) Bam chuot vao cua so stream 1 lan cho no nhan ban phim, roi dieu khien
     (W/S, A/D, Q/E, ..., ESC de thoat).

  Chi 1 client ket noi cung luc.

Kiem tra khi dang ket noi (terminal SSH thu 2 tren VM):
  ss -lntup | grep -E "49100|47998"
  -> 1 dong tcp 49100 va 1 dong udp ...:47998


4. DUNG
-------------------------------------
  ESC trong cua so stream, hoac:
  docker stop $(docker ps -q --filter label=phyrc.project=PhyRC_2027)
