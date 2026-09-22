#!/usr/bin/env python3
"""把一台密码登录的服务器迁移到密钥登录。

流程：本地备好密钥对 → 用密码会话把公钥幂等写进服务器 authorized_keys →
立刻用密钥回连验证。全程幂等，重复跑不会写重复公钥。

⚠️ 本脚本**不**替你禁用密码登录——那是不可逆动作，验证密钥可用后由人工确认再改
   sshd（步骤见 SKILL.md「② 关掉密码登录」）。

环境变量：
  SSH_HOST  必填
  SSH_USER  默认 root
  SSH_PORT  默认 22
  SSH_PASS  必填（迁移当次仍靠密码登进去植入公钥）
  SSH_KEY   本地私钥路径，默认 ~/.ssh/id_ed25519（不存在则自动生成 ed25519）
  SSH_ALIAS 可选，验证通过后打印的 ~/.ssh/config Host 别名建议用这个名字
"""
import os
import subprocess
import sys

try:
    import paramiko
except ImportError:
    sys.exit("缺 paramiko")


def ensure_local_key(key_path):
    key_path = os.path.expanduser(key_path)
    pub_path = key_path + ".pub"
    if not os.path.exists(key_path):
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        print(f"[*] 本地无密钥，生成 ed25519: {key_path}")
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-C", "x-ai-ssh-remote"],
            check=True,
        )
    with open(pub_path) as f:
        return key_path, f.read().strip()


def main():
    host = os.environ.get("SSH_HOST") or sys.exit("缺 SSH_HOST")
    user = os.environ.get("SSH_USER", "root")
    port = int(os.environ.get("SSH_PORT", "22"))
    password = os.environ.get("SSH_PASS") or sys.exit("缺 SSH_PASS（迁移当次仍需密码）")
    key_path = os.environ.get("SSH_KEY", "~/.ssh/id_ed25519")

    key_path, pubkey = ensure_local_key(key_path)

    # 1) 密码登录，幂等植入公钥
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=host, port=port, username=user, password=password,
              look_for_keys=False, allow_agent=False, timeout=15)
    marker = pubkey.split()[1][:20]  # 公钥主体片段做幂等判重
    install = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys && "
        f"grep -qF '{marker}' ~/.ssh/authorized_keys || echo '{pubkey}' >> ~/.ssh/authorized_keys"
    )
    _, out, err = c.exec_command(install)
    out.channel.recv_exit_status()
    e = err.read().decode().strip()
    if e:
        print(f"[!] 植入报错: {e}")
    c.close()
    print("[✓] 公钥已幂等写入服务器 authorized_keys")

    # 2) 密钥回连验证
    c2 = paramiko.SSHClient()
    c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c2.connect(hostname=host, port=port, username=user,
                   key_filename=os.path.expanduser(key_path),
                   look_for_keys=False, allow_agent=False, timeout=15)
        _, o, _ = c2.exec_command("whoami")
        o.channel.recv_exit_status()
        who = o.read().decode().strip()
        c2.close()
        print(f"[✓] 密钥登录验证通过（whoami={who}，用私钥 {key_path}）")
    except Exception as ex:
        sys.exit(f"[✗] 密钥登录验证失败，先别动密码登录: {type(ex).__name__} {ex}")

    alias = os.environ.get("SSH_ALIAS", "<起个别名>")
    print("\n[建议] 追加到 ~/.ssh/config，以后 `ssh %s` 一步直连：" % alias)
    print(f"""
Host {alias}
    HostName {host}
    User {user}
    Port {port}
    IdentityFile {key_path}
    IdentitiesOnly yes
""")

    print("下一步（人工确认后执行，可逆前先保留一个密码会话别断）:")
    print("  1. 换用密钥登：ssh -i %s %s@%s -p %d（或配好上面别名后 ssh %s）" % (key_path, user, host, port, alias))
    print("  2. 关密码登录：改 /etc/ssh/sshd_config → PasswordAuthentication no，再 systemctl reload sshd")


if __name__ == "__main__":
    main()
