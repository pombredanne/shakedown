import os
import paramiko
import select
import subprocess

import shakedown


def run_command(
    host,
    command,
    username='core',
    key_path=None
):
    """ Run a command via SSH, proxyied through the mesos master

        host (str): host or IP of the machine to execute the command on
        command (str): the command to execute
        username (str): SSH username
        key_path (str): path to the SSH private key to use for SSH authentication
    """
    if not key_path:
        key_path = shakedown.cli.ssh_key_file

    key_path = os.path.expanduser(key_path)

    if not os.path.isfile(key_path):
        print('error: key not found: ' + key_path)
        return False

    key = paramiko.RSAKey.from_private_key_file(key_path)

    transport = None

    if host == shakedown.master_ip():
        transport = paramiko.Transport(host)
    else:
        transport_master = paramiko.Transport(shakedown.master_ip())
        _start_transport(transport_master, username, key)

        if not transport_master.is_authenticated():
           print('error: unable to authentication ' + username + '@' + shakedown.master_ip() + ' with key ' + key_path)
           return False

        channel = transport_master.open_channel('direct-tcpip', (host, 22), ('127.0.0.1', 0))
        transport = paramiko.Transport(channel)

    _start_transport(transport, username, key)

    if transport.is_authenticated():
        print("\n{}{} $ {}\n".format(shakedown.cli.helpers.fchr('>>'), host, command))

        channel = transport.open_session()
        channel.exec_command(command)
        channel.recv_exit_status()

        while channel.recv_ready():
            rl, wl, xl = select.select([channel], [], [], 0.0)
            if len(rl) > 0:
                recv = str(channel.recv(1024), "utf-8")
                print(recv, end='', flush=True)

        channel.close()
        transport.close()

        if host != shakedown.master_ip():
            transport_master.close()

        return True
    else:
        print('error: unable to authentication ' + username + '@' + host + ' with key ' + key_path)
        return False


def run_command_on_master(
    command,
    username='core',
    key_path=None
):
    return run_command(shakedown.master_ip(), command, username, key_path)


def run_command_on_agent(
    host,
    command,
    username='core',
    key_path=None
):
    return run_command(host, command, username, key_path)


def run_dcos_command(command):
    """ Run a command via DCOS CLI

        command (str): command to run
    """

    call = command.split()
    call.insert(0, 'dcos')

    print("\n{}{}\n".format(shakedown.cli.helpers.fchr('>>'), ' '.join(call)))

    output, error = subprocess.Popen(call, stdout = subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    output = output.decode('utf-8')
    error = error.decode('utf-8')

    print(output, error)

    return output, error


def _start_transport(transport, username, key):
    transport.start_client()
    transport.auth_publickey(username, key)

    return transport
