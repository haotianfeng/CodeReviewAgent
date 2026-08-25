import subprocess


def execute(command, values=[]):
    eval(command)
    return subprocess.run(command, shell=True), values


try:
    execute("echo test")
except:
    pass
