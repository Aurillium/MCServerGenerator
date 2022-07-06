#!/usr/bin/python3
from enum import Enum
import argparse
import requests
import hashlib
import shutil
import shlex
import sys
import os
import re

LATEST = None
VERSIONS = []
WRITTEN_FILES = []
DIRS_CREATED = []

def warn(message):
  print("Warning: " + message)
  
def fatal(message):
  print("Fatal: " + message + "\nRolling back changes...")
  for file in WRITTEN_FILES:
    try:
      os.remove(file)
    except:
      print(f"Error: Could not delete file '{file}'.")
  for directory in reversed(DIRS_CREATED):
    try:
      os.rmdir(directory)
    except:
      print(f"Error: Could not delete directory '{directory}'.")
  print("Done! Exitting now...")
  sys.exit(1)

def info(message):
  print("Info: " + message)

class ErrorLevel(Enum):
  INFO = info
  WARN = warn
  WARNING = warn
  FATAL = fatal

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

def get_url(url, resource=None, error_level=ErrorLevel.FATAL):
  try:
    r = requests.get(url)
    if r.status_code == 200:
      return r
    else:
      error_level(f"Error {r.status_code}: {r.reason} when getting {resource if resource else url}.")
  except requests.exceptions.ConnectionError:
    error_level("There appears to be no internet connection.")

def ram_size(ram):
  format_error = "Invalid RAM format (use the Java format, eg: 512M, 2G, 1536M)"
  try:
    num = int(ram[:-1])
  except ValueError:
    fatal(format_error)
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
    fatal(format_error)

def yn_prompt(prompt):
  while True:
    answer = input(prompt + " [y/N] ").strip().lower()
    if answer == "n" or not answer:
      return False
    elif answer == "y":
      return True

def save_file(path, content, error_level=ErrorLevel.FATAL):
  content_type = type(content)
  try:
    with open(path, "w+" if content_type == str else "wb+") as f:
      f.write(content)
    WRITTEN_FILES.append(path)
  except PermissionError:
    error_level(f"You do not have permission to save files at '{path}'.")

def makedirs(path, error_level=ErrorLevel.FATAL):
  parts = [part for part in path.split(os.path.sep) if part]
  new_path = "/" if path[0] == "/" else ""
  for part in parts:
    new_path += part + "/"
    if not os.path.exists(new_path):
      try:
        os.mkdir(new_path)
        DIRS_CREATED.append(new_path)
      except PermissionError:
        error_level(f"You do not have permission to create a directory at '{new_path}'.")

def get_spigot_geyser(directory):
  info("Downloading Geyser for Spigot...")
  makedirs(os.path.join(directory, "plugins"))
  r = get_url("https://ci.opencollab.dev//job/GeyserMC/job/Geyser/job/master/lastSuccessfulBuild/artifact/bootstrap/spigot/target/Geyser-Spigot.jar")
  save_file(os.path.join(directory, "plugins", "Geyser-Spigot.jar"), r.content)
  info("Installed Geyser for Spigot!")
def get_spigot_floodgate(directory):
  info("Downloading Floodgate for Spigot...")
  makedirs(os.path.join(directory, "plugins"))
  r = get_url("https://ci.opencollab.dev/job/GeyserMC/job/Floodgate/job/master/lastSuccessfulBuild/artifact/spigot/build/libs/floodgate-spigot.jar")
  save_file(os.path.join(directory, "plugins", "Floodgate-Spigot.jar"), r.content)
  info("Installed Floodgate for Spigot!")

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
  fatal("Maximum RAM size is less than the minimum.")
if mx > mn:
  warn("If the minimum and maximum RAM do not match, there will be unused memory, which is wasted.")
if mx < 536870912: # 512MB
  warn("Minecraft will not run well with less than 512MB RAM.")
if mx > 34359738368: # 32GB
  warn("Minecraft will not benefit from more than 32GB RAM.")

print("Downloading versions...")
r = get_url("https://launchermeta.mojang.com/mc/game/version_manifest.json", "version manifest")
manifest = r.json()
LATEST = manifest["latest"]["release"]
for version in manifest["versions"]:
  if version["type"] == "release":
    VERSIONS.append(version["id"])

software = get_software(args.software if args.software else "")
version = get_version(args.version if args.version else "")
directory = args.directory if args.directory else "."
build = None

if args.floodgate:
  args.geyser = True
if args.geyser and version != LATEST:
  warn("Geyser can only run on the latest Minecraft versions, so it will not be installed. Set the version to 'latest' to ensure you have the latest version.")
  args.geyser = False
if args.geyser and software not in ("paper", "spigot", "fabric"):
  warn("Geyser is only supported on Paper, Spigot, and Fabric servers, so it will not be installed here.")
  args.geyser = False

if os.path.exists(directory):
  if os.listdir(directory):
    if not yn_prompt("This directory is not empty, install anyway?"):
      sys.exit(0)
else:
  try:
    makedirs(directory)
  except PermissionError:
    fatal("You do not have permission to make a server here!")

server_file = None
print(f"Searching for {software.title()} {version}...")
if software == "paper":
  builds_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds/"
  r = get_url(builds_url, f"Paper builds for {version}")
  j = r.json()
  if "error" in j:
    if j["error"] == "Version not found.":
      fatal("This version of Paper has not been released yet.")
    else:
      fatal("Unexpected error: " + j["error"])
  builds = j["builds"]
  if len(builds) == 0:
    fatal("This version of Paper has not been released yet.")
  if build:
    for b in builds:
      selected = b
      if b["build"] == build:
        break
    else:
      fatal("The selected build could not be found.")
  else:
    selected = builds[-1]
  download_info = selected["downloads"]["application"]
  r = get_url(builds_url + str(selected["build"]) + "/downloads/" + download_info["name"], "Paper jar")
  if hashlib.sha256(r.content).digest().hex() != download_info["sha256"]:
    fatal("Hashes do not match for downloaded jarfile.")
  save_file(os.path.join(directory, download_info["name"]), r.content)
  info("Saved jarfile!")
  if args.geyser: get_spigot_geyser(directory)
  if args.floodgate: get_spigot_floodgate(directory)
  info("Writing startup script...")
  save_file(os.path.join(directory, "start.sh"), '#!/bin/bash\n'
                                                f'cd {shlex.quote(os.path.abspath(directory))}\n'
                                                f'export RAM_MIN="{args.ram_min}"\n'
                                                f'export RAM_MAX="{args.ram_max}"\n'
                                                f'java -Xms$RAM_MIN -Xmx$RAM_MAX -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 -Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true -jar {download_info["name"]} --nogui\n')

elif software == "spigot":
  try:
    r = requests.get(f"https://download.getbukkit.org/spigot/spigot-{version}.jar")
  except requests.exceptions.ConnectionError:
    fatal("There appears to be no internet connection.")
  if r.status_code == 404:
    fatal("This version of Spigot has not been released yet.")
  if r.status_code != 200:
    fatal(f"Error {r.status_code}: {r.reason} when getting Spigot jarfile.")
  jarfile = f"spigot-{version}.jar"
  save_file(os.path.join(directory, jarfile), r.content)
  info("Saved jarfile!")
  if args.geyser: get_spigot_geyser(directory)
  if args.floodgate: get_spigot_floodgate(directory)
  info("Writing startup script...")
  save_file(os.path.join(directory, "start.sh"), f'#!/bin/bash\n'
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
  download_info = r.json()["downloads"]["server"]
  r = get_url(download_info["url"])
  if len(r.content) != download_info["size"]:
    fatal("Jarfile size does not match the Mojang-specified size.")
  elif hashlib.sha1(r.content).digest().hex() != download_info["sha1"]:
    fatal("Hashes do not match for downloaded jarfile.")

  if software == "vanilla":
    jarfile = f"vanilla-{version}.jar"
    save_file(os.path.join(directory, jarfile), r.content)
    info("Saved jarfile!")

  elif software == "fabric":
    save_file(os.path.join(directory, "server.jar"), r.content)
    info("Saved vanilla jarfile! Downloading Fabric...")
    r = get_url("https://meta.fabricmc.net/v2/versions/installer")
    installer_version = r.json()[0]["version"]
    r = get_url("https://meta.fabricmc.net/v2/versions/loader")
    loader_version = r.json()[0]["version"]
    r = get_url(f"https://meta.fabricmc.net/v2/versions/loader/{version}/{loader_version}/{installer_version}/server/jar")
    jarfile = f"fabric-{version}.jar"
    save_file(os.path.join(directory, jarfile), r.content)

    info("Saved Fabric jarfile!")
    
    if args.geyser:
      info("Installing Geyser now...")
      r = get_url("https://github.com/FabricMC/fabric/releases/")
      if not r:
        fatal("Could not get Fabric API releases.")
      escaped_version = version.replace(".", "\\.")
      pattern = "\\/FabricMC\\/fabric\\/releases\\/download\\/[0-9.]+%2B" + escaped_version + "/fabric-api-[0-9.]+\\+" + escaped_version + "\\.jar"
      
      makedirs(os.path.join(directory, "mods"))
      match = re.search(pattern, r.content.decode("utf8")).group()
      r = get_url("https://github.com" + match)
      if not r:
        fatal("Could not download Fabric API.")
      save_file(os.path.join(directory, "mods", match.split("/")[-1]), r.content)
      info("Installed Fabric API!")
      
      version_split = version.split(".")
      try:
        r = requests.get("https://ci.opencollab.dev/job/GeyserMC/job/Geyser-Fabric/job/java-" + version_split[0] + "." + version_split[1] + "/lastSuccessfulBuild/artifact/build/libs/Geyser-Fabric.jar")
      except requests.exceptions.ConnectionError:
        fatal("There appears to be no internet connection.")
      if r.status_code == 404:
        fatal("This version of Geyser for Fabric has not been released yet.")
      if r.status_code != 200:
        fatal(f"Error {r.status_code}: {r.reason} when getting Geyser for Fabric jarfile.")  
      save_file(os.path.join(directory, "mods", "Geyser-Fabric.jar"), r.content)
      info("Installed Geyser!")
      
      if args.floodgate:
        info("Installing Floodgate now...")
        r = get_url("https://ci.opencollab.dev/job/GeyserMC/job/Floodgate-Fabric/job/master/lastSuccessfulBuild/artifact/build/libs/floodgate-fabric.jar")
        if not r:
          fatal("Could not download Floodgate for Fabric jarfile.")
        save_file(os.path.join(directory, "mods", "Floodgate-Fabric.jar"), r.content)
        info("Installed Floodgate!")

  info("Writing startup script...")
  save_file(os.path.join(directory, "start.sh"), f'#!/bin/bash\n'
                                                 f'cd {shlex.quote(os.path.abspath(directory))}\n'
                                                 f'export RAM_MIN="{args.ram_min}"\n'
                                                 f'export RAM_MAX="{args.ram_max}"\n'
                                                 f'java -Xms$RAM_MIN -Xmx$RAM_MAX -jar {jarfile} -nogui\n')

os.chmod(os.path.join(directory, "start.sh"), 0o774)
if yn_prompt("Do you agree to the Minecraft EULA? (https://aka.ms/MinecraftEULA)"):
  save_file(os.path.join(directory, "eula.txt"), "eula=true")
print("Installation successful!")
