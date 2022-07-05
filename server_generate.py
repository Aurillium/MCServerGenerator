#!/usr/bin/python3
import argparse
import requests
import hashlib
import shutil
import shlex
import sys
import os

LATEST = None
VERSIONS = []

def get_software(software=""):
  software = software.strip().lower()
  while True:
    if software in ("paper", "spigot", "vanilla", "fabric"):
      return software
    else:
      if software:
        print("That isn't a valid type of server software.")
    software = input("Server softare ([P]aper, [S]pigot, [V]anilla, [F]abric): ").strip().lower()
    if software == "p": software = "paper"
    elif software == "s": software = "spigot"
    elif software == "v": software = "vanilla"
    elif software == "f": software = "fabric"

def get_version(version=""):
  version = version.strip().lower()
  while True:
    if version == "latest":
      return LATEST
    elif version in VERSIONS:
      return version
    else:
      if version:
        print("That isn't a valid version.")
    version = input("Server version (any release or 'latest'): ").strip().lower()

def get_url(url, resource=None):
  try:
    r = requests.get(url)
    if r.status_code == 200:
      return r
    else:
      print(f"Error {r.status_code}: {r.reason} when getting {resource if resource else url}.")
  except requests.exceptions.ConnectionError:
    print("There appears to be no internet connection.")

def ram_size(ram):
  format_error = "Invalid RAM format (use the Java format, eg: 512M, 2G, 1536M)"
  try:
    num = int(ram[:-1])
  except ValueError:
    print(format_error)
    sys.exit(1)
  suf = ram[-1].upper()
  if suf == "B":
    return num
  elif suf == "K":
    return num * 1024
  elif suf == "M":
    return num * 1024 * 1024
  elif suf == "G":
    return num * 1024 * 1024 * 1024
  elif suf == "T":
    return num * 1024 * 1024 * 1024 * 1024 # You might be using a *little* too much at this point just fyi
  else:
    print(format_error)
    sys.exit(1)

def yn_prompt(prompt):
  while True:
    answer = input(prompt + " [y/N] ").strip().lower()
    if answer == "n" or not answer:
      return False
    elif answer == "y":
      return True

parser = argparse.ArgumentParser(description="Set up a Minecraft server automatically")
parser.add_argument("-d", "--directory", "--dir", type=str, help="The directory for the server", default=".")
parser.add_argument("-v", "--version", type=str, help="The server Minecraft version (any version or 'latest')")
parser.add_argument("-s", "--software", type=str, help="The server software to use. Currently supported: [P]aper, [S]pigot, [V]anilla, [F]abric")
parser.add_argument("-rmn", "--ram-min", "--ram-minimum", type=str, help="The minimum amount of RAM the server should use (use Java format; 512M, 2G, etc.). This should match the maximum RAM and automatically does when left blank.")
parser.add_argument("-rmx", "--ram-max", "--ram-maximum", type=str, help="The maximum amount of RAM the server should use (use Java format; 512M, 2G, etc.)", default="4G")
parser.add_argument("-g", "--geyser", action="store_const", help="Install Geyser where compatible", const=True, default=False)
parser.add_argument("-f", "--floodgate", action="store_const", help="Install Floodgate and Geyser where compatible", const=True, default=False)
args = parser.parse_args()

if not args.ram_min:
  args.ram_min = args.ram_max
mn = ram_size(args.ram_min)
mx = ram_size(args.ram_max)
if mx < mn:
  print("Maximum RAM size is less than the minimum.")
  sys.exit(1)
if mx > mn:
  print("Warning: If the minimum and maximum RAM do not match, there will be unused memory, which is wasted.")
if mx < 536870912: # 512MB
  print("Warning: Minecraft will not run well with less than 512MB RAM.")
if mx > 34359738368: # 32GB
  print("Warning: Minecraft will not benefit from more than 32GB RAM.")

print("Downloading versions...")
r = get_url("https://launchermeta.mojang.com/mc/game/version_manifest.json", "version manifest")
if r:
  manifest = r.json()
  LATEST = manifest["latest"]["release"]
  for version in manifest["versions"]:
    if version["type"] == "release":
      VERSIONS.append(version["id"])
else:
  sys.exit(1)

software = get_software(args.software if args.software else "")
version = get_version(args.version if args.version else "")
directory = args.directory if args.directory else "."
build = None

if os.path.exists(directory):
  if os.listdir(directory):
    if not yn_prompt("This directory is not empty, install anyway?"):
      sys.exit(0)
else:
  try:
    os.makedirs(directory)
  except PermissionError:
    print("You do not have permission to make a server here!")
    sys.exit(1)

server_file = None
print(f"Searching for {software.title()} {version}...")
if software == "paper":
  builds_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds/"
  r = get_url(builds_url, f"Paper builds for {version}")
  if not r:
    sys.exit(1)
  j = r.json()
  if "error" in j:
    if j["error"] == "Version not found.":
      print("This version of Paper has not been released yet.")
    else:
      print("Unexpected error: " + j["error"])
    sys.exit(1)
  builds = j["builds"]
  if len(builds) == 0:
    print("This version of Paper has not been released yet.")
    sys.exit(1)
  if build:
    for b in builds:
      selected = b
      if b["build"] == build:
        break
    else:
      print("The selected build could not be found.")
      sys.exit(1)
  else:
    selected = builds[-1]
  download_info = selected["downloads"]["application"]
  r = get_url(builds_url + str(selected["build"]) + "/downloads/" + download_info["name"], "Paper jar")
  if not r:
    sys.exit(1)
  elif hashlib.sha256(r.content).digest().hex() != download_info["sha256"]:
    print("Hashes do not match for downloaded jarfile.")
    sys.exit(1)
  with open(os.path.join(directory, download_info["name"]), "wb+") as f:
    f.write(r.content)
  print("Saved jarfile! Writing startup script...")
  with open(os.path.join(directory, "start.sh"), "w+") as f:
    f.write('#!/bin/bash\n'
            f'cd {shlex.quote(os.path.abspath(directory))}\n'
            f'export RAM_MIN="{args.ram_min}"\n'
            f'export RAM_MAX="{args.ram_max}"\n'
            f'java -Xms$RAM_MIN -Xmx$RAM_MAX -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 -Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true -jar {download_info["name"]} --nogui\n')

elif software == "spigot":
  try:
    r = requests.get(f"https://download.getbukkit.org/spigot/spigot-{version}.jar")
  except requests.exceptions.ConnectionError:
    print("There appears to be no internet connection.")
  if r.status_code == 404:
    print("This version of Spigot has not been released yet.")
    sys.exit(1)
  if r.status_code != 200:
    print(f"Error {r.status_code}: {r.reason} when getting {resource if resource else url}.")
  jarfile = f"spigot-{version}.jar"
  with open(os.path.join(directory, jarfile), "wb+") as f:
    f.write(r.content)
  print("Saved jarfile! Writing startup script...")
  with open(os.path.join(directory, "start.sh"), "w+") as f:
    f.write(f'#!/bin/bash\n'
            f'cd {shlex.quote(os.path.abspath(directory))}\n'
            f'export RAM_MIN="{args.ram_min}"\n'
            f'export RAM_MAX="{args.ram_max}"\n'
            f'java -Xms$RAM_MIN -Xmx$RAM_MAX -XX:+UseG1GC -jar {jarfile} -nogui\n')

elif software == "vanilla" or software == "fabric":
  for mc_version in manifest["versions"]:
    if mc_version["id"] == version:
      launcher_url = mc_version["url"]
      break
  r = get_url(launcher_url)
  if not r:
    sys.exit(1)
  download_info = r.json()["downloads"]["server"]
  r = get_url(download_info["url"])
  if not r:
    sys.exit(1)
  elif len(r.content) != download_info["size"]:
    print("Jarfile size does not match the Mojang-specified size.")
    sys.exit(1)
  elif hashlib.sha1(r.content).digest().hex() != download_info["sha1"]:
    print("Hashes do not match for downloaded jarfile.")
    sys.exit(1)

  if software == "vanilla":
    jarfile = f"vanilla-{version}.jar"
    with open(os.path.join(directory, jarfile), "wb+") as f:
      f.write(r.content)
    print("Saved jarfile! Writing startup script...")

  elif software == "fabric":
    with open(os.path.join(directory, "server.jar"), "wb+") as f:
      f.write(r.content)
    print("Saved vanilla jarfile! Downloading Fabric...")
    r = get_url("https://meta.fabricmc.net/v2/versions/installer")
    if not r:
      sys.exit(1)
    installer_version = r.json()[0]["version"]
    r = get_url("https://meta.fabricmc.net/v2/versions/loader")
    if not r:
      sys.exit(1)
    loader_version = r.json()[0]["version"]
    r = get_url(f"https://meta.fabricmc.net/v2/versions/loader/{version}/{loader_version}/{installer_version}/server/jar")
    if not r:
      sys.exit(1)
    jarfile = f"fabric-{version}.jar"
    with open(os.path.join(directory, jarfile), "wb+") as f:
      f.write(r.content)

    print("Saved Fabric jarfile! Writing startup script...")

  with open(os.path.join(directory, "start.sh"), "w+") as f:
    f.write(f'#!/bin/bash\n'
            f'cd {shlex.quote(os.path.abspath(directory))}\n'
            f'export RAM_MIN="{args.ram_min}"\n'
            f'export RAM_MAX="{args.ram_max}"\n'
            f'java -Xms$RAM_MIN -Xmx$RAM_MAX -jar {jarfile} -nogui\n')

os.chmod(os.path.join(directory, "start.sh"), 0o774)
if yn_prompt("Do you agree to the Minecraft EULA? (https://aka.ms/MinecraftEULA)"):
  with open(os.path.join(directory, "eula.txt"), "w+") as f:
    f.write("eula=true")
print("Installation successful!")
