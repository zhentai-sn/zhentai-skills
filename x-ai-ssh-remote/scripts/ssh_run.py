#!/usr/bin/env python3
"""paramiko 驱动的 SSH 执行器 —— 密码/密钥登录，非交互跑命令。

当环境里没有 sshpass、又没 root 装不上时的兜底：用 python3 + paramiko
非交互传密码，稳定复用。凭据一律从环境变量读，脚本内不留任何 secret。

环境变量：
  SSH_HOST  必填，目标 IP / 域名
  SSH_USER  登录用户，默认 root
  SSH_PORT  端口，默认 22
  SSH_PASS  密码登录时填（含特殊字符也没事，走 env 不过 shell）
  SSH_KEY   密钥登录时填私钥路径（与 SSH_PASS 二选一，优先密钥）
  SSH_KEY_PASS  私钥口令（加密私钥才需要）

用法：
  # 连通性自检（只测握手 + 认证，不跑命令）
  SSH_HOST=1.2.3.4 SSH_PASS='...' python3 ssh_run.py --test

  # 跑单条命令
  SSH_HOST=1.2.3.4 SSH_PASS='...' python3 ssh_run.py 'uptime'

  # 跑多条（各自独立执行，输出分段）
  SSH_HOST=1.2.3.4 SSH_KEY=~/.ssh/id_ed25519 python3 ssh_run.py 'hostname' 'df -h' 'docker ps'
"""
import os
import sys

try:
    import paramiko
except ImportError:
    sys.exit("缺 paramiko：pip install --user paramiko（本仓环境通常自带 2.12）")


def connect():
    host = os.environ.get("SSH_HOST")
    if not host:
        sys.exit("缺 SSH_HOST")
    user = os.environ.get("SSH_USER", "root")
    port = int(os.environ.get("SSH_PORT", "22"))
    key = os.environ.get("SSH_KEY")
    password = os.environ.get("SSH_PASS")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = dict(hostname=host, port=port, username=user,
              timeout=15, banner_timeout=15, auth_timeout=15)
    if key:
        kw["key_filename"] = os.path.expanduser(key)
        if os.environ.get("SSH_KEY_PASS"):
            kw["passphrase"] = os.environ["SSH_KEY_PASS"]
    elif password:
        kw["password"] = password
        kw["look_for_keys"] = False
        kw["allow_agent"] = False
    else:
        sys.exit("缺认证：SSH_PASS 或 SSH_KEY 至少给一个")
    c.connect(**kw)
    return c, f"{user}@{host}:{port}"


def main():
    args = sys.argv[1:]
    test_only = "--test" in args
    cmds = [a for a in args if a != "--test"]

    try:
        c, target = connect()
    except Exception as e:
        print(f"=== CONNECT FAILED ({type(e).__name__}) ===\n{e}")
        sys.exit(1)

    print(f"=== CONNECT OK: {target} ===")
    if test_only and not cmds:
        cmds = ["hostname", "whoami", "uname -sr", "uptime"]

    rc_final = 0
    for cmd in cmds:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
        rc = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace").rstrip()
        err = stderr.read().decode(errors="replace").rstrip()
        print(f"\n$ {cmd}")
        if out:
            print(out)
        if err:
            print(err, file=sys.stderr)
        if rc != 0:
            print(f"[exit {rc}]")
            rc_final = rc
    c.close()
    sys.exit(rc_final)


if __name__ == "__main__":
    main()
