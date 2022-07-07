#!/usr/bin/python3
import datetime
import argparse
import platform
import requests
import hashlib
import tarfile
import zipfile
import shutil
import shlex
import enum
import time
import sys
import os
import io
import re

LATEST = None
VERSIONS = []
WRITTEN_FILES = []
DIRS_CREATED = []
PROPERTIES = {}
GEYSER_CONFIG = {}
JAVA_PATH = ""

def info(message):
  print("Info: " + message)

def warn(message):
  print("Warning: " + message)
  
def fatal(message):
  print("Fatal: " + message)
  rollback()
  print("Exitting now...")
  sys.exit(1)

class ErrorLevel(enum.Enum):
  INFO = info
  WARN = warn
  WARNING = warn
  FATAL = fatal

def rollback():
  print("Rolling back changes...")
  if JAVA_PATH:
    try:
      shutil.rmtree(JAVA_PATH)
    except:
      print(f"Error: Could not delete Java.")
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
  print("Done!")

def get_mojang_timestamp():
  return datetime.datetime.now().strftime("%a %b %d %H:%M:%S " + time.tzname[time.daylight] + " %Y")

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

def get_part_startup_linux(directory, rmn, rmx):
  startup = (
    f'#!/bin/bash\n'
    f'cd {shlex.quote(os.path.abspath(directory))}\n'
    f'export RAM_MIN="{rmn}"\n'
    f'export RAM_MAX="{rmx}"\n'
  )
  if JAVA_PATH:
    startup += f"export PATH={shlex.quote(os.path.abspath(os.path.join(JAVA_PATH, 'bin')))}:$PATH\nexport JAVA_HOME={shlex.quote(os.path.abspath(JAVA_PATH))}\n"
  return startup

def get_spigot_geyser(directory):
  info("Downloading Geyser for Spigot...")
  makedirs(os.path.join(directory, "plugins"))
  r = get_url("https://ci.opencollab.dev//job/GeyserMC/job/Geyser/job/master/lastSuccessfulBuild/artifact/bootstrap/spigot/target/Geyser-Spigot.jar")
  geyser_jar = os.path.join(directory, "plugins", "Geyser-Spigot.jar")
  save_file(geyser_jar, r.content)
  info("Setting up configuration...")
  config_file = os.path.join(directory, "plugins", "Geyser-Spigot", "config.yml")
  with zipfile.ZipFile(geyser_jar) as f:
    f.extract("config.yml", os.path.join(directory, "plugins", "Geyser-Spigot"))
    WRITTEN_FILES.append(config_file)
  lines = []
  with open(config_file) as f:
    level = ""
    prev_indent = 0
    for line in f:
      if "#" in line:
        active_line, comment = line.split("#", 1)
      else:
        active_line = line
        comment = None
      if not active_line.strip():
        lines.append(line)
        continue
      indent = len(line) - len(line.lstrip())
      if indent > prev_indent:
        level = level + "." + key
      if indent < prev_indent:
        level = ".".join(level.split(".")[:-1])
      prev_indent = indent
      if ":" in active_line:
        key, value = active_line.strip().split(":", 1)
        true_key = level + "." + key
        if true_key[1:] in GEYSER_CONFIG:
          lines.append(" " * indent + key + ": " + GEYSER_CONFIG[true_key[1:]] + (" #" + comment if comment else "\n"))
        else:
          lines.append(line)
      else:
        lines.append(line)
  save_file(config_file, "".join(lines))
  info("Installed Geyser for Spigot!")
def get_spigot_floodgate(directory):
  info("Downloading Floodgate for Spigot...")
  makedirs(os.path.join(directory, "plugins"))
  r = get_url("https://ci.opencollab.dev/job/GeyserMC/job/Floodgate/job/master/lastSuccessfulBuild/artifact/spigot/build/libs/floodgate-spigot.jar")
  save_file(os.path.join(directory, "plugins", "Floodgate-Spigot.jar"), r.content)
  info("Installed Floodgate for Spigot!")

def get_adoptium(directory, version):
  info(f"Downloading Adoptium JRE (JDK{version})...")
  operating_system = {"Linux": "linux", "Darwin": "mac", "Windows": "windows"}.get(platform.system())
  if not operating_system:
    fatal("Your operating system is not supported.")
  architecture = None
  arch = platform.machine()
  if arch in ("x86_64", "AMD64"):
    architecture = "x64"
  elif arch in ("i386", "i686"):
    architecture = "x86-32"
  elif arch in ("arm",):
    architecture = "arm"
  elif arch in ("aarch64_be", "aarch64", "armv8b", "armv8l"):
    architecture = "aarch64"
  if not operating_system:
    fatal("Your architecture is not supported.")
  pattern = f"\\/adoptium\\/temurin{version}-binaries\\/releases\\/download\\/jdk-{version}\\.[0-9]+\\.[0-9]+%2B[0-9]+\\/OpenJDK{version}U-jre_{architecture}_{operating_system}_hotspot_{version}\\.[0-9]+\\.[0-9]+_[0-9]+\\.tar\\.gz"
  old_pattern = f"\\/adoptium\\/temurin{version}-binaries\\/releases\\/download\\/jdk{version}u[0-9]+-b[0-9]+\\/OpenJDK{version}U-jre_{architecture}_{operating_system}_hotspot_{version}u[0-9]+b[0-9]+\\.tar\\.gz"
  r = get_url(f"https://github.com/adoptium/temurin{version}-binaries/releases/")
  search_result = re.search(pattern, r.content.decode())
  if not search_result:
    search_result = re.search(old_pattern, r.content.decode())
  url = "https://github.com" + search_result.group()
  r = get_url(url)
  h = get_url(url + ".sha256.txt").content.decode().split()[0]
  if hashlib.sha256(r.content).digest().hex() != h:
    fatal("Downloaded Java environment hashes do not match.")
  with tarfile.open(fileobj=io.BytesIO(r.content)) as tar:
    root = [i for i in tar.getnames() if "/" not in i][0]
    tar.extractall(directory)
    adoptium = os.path.join(directory, root)
  info("Installed Adoptium!")
  return adoptium

parser = argparse.ArgumentParser(description="Set up a Minecraft server automatically")
parser.add_argument("-d", "--directory", "--dir", type=str, help="The directory for the server", default=".")
parser.add_argument("-v", "--version", type=str, help="The server Minecraft version (any version or 'latest')")
parser.add_argument("-s", "--software", type=str, help="The server software to use. Currently supported: [P]aper, [S]pigot, [V]anilla, [F]abric")
parser.add_argument("-rmn", "--ram-min", "--ram-minimum", type=str, help="The minimum amount of RAM the server should use (use Java format; 512M, 2G, etc.). This should match the maximum RAM and automatically does when left blank.")
parser.add_argument("-rmx", "--ram-max", "--ram-maximum", type=str, help="The maximum amount of RAM the server should use (use Java format; 512M, 2G, etc.)", default="4G")
parser.add_argument("-g", "--geyser", action="store_const", help="Install Geyser where compatible", const=True, default=False)
parser.add_argument("-f", "--floodgate", action="store_const", help="Install Floodgate and Geyser where compatible", const=True, default=False)
parser.add_argument("--build", "--paper-build", type=int, help="If you're using Paper, you can use this option to select a specifc build number")
parser.add_argument("-p", "--port", type=int, help="The port the server will run on", default=25565)
parser.add_argument("-m", "--motd", type=str, help="The server MOTD", default="A Minecraft Server")
parser.add_argument("--disable-online-mode", "--disable-online", action="store_const", help="Online mode (the most secure way of authenticating players) will be disabled if this flag is used", const=True, default=False)
parser.add_argument("-n", "--players", "--max-players", type=int, help="The maximum number of players who can join the server at once", default=20)
parser.add_argument("-x", "--spawn-protection", type=int, help="The number of blocks from spawn that players cannot modify the world", default=16)
parser.add_argument("-e", "--seed", type=str, help="The world seed", default="")
parser.add_argument("-a", "--gamemode", type=str, help="The default gamemode", default="survival")
parser.add_argument("-i", "--difficulty", type=str, help="The server difficulty", default="easy")
parser.add_argument("--hardcore", "--enable-hardcore", action="store_const", help="Hardcore mode will be enabled if this flag is used", const=True, default=False)
parser.add_argument("--disable-pvp", action="store_const", help="PVP will be disabled if this flag is used", const=True, default=False)
parser.add_argument("-b", "--bedrock-port", type=int, help="The port the server will run on for Bedrock players when Geyser is installed", default=19132)
parser.add_argument("-l1", "--bedrock-motd-1", type=str, help="The first MOTD line on Bedrock", default="A Minecraft Server")
parser.add_argument("-l2", "--bedrock-motd-2", type=str, help="The second MOTD line on Bedrock", default="Bottom text")
parser.add_argument("-N", "--bedrock-name", "--bedrock-server-name", type=str, help="The server name on Bedrock", default="My Geyser Server")
parser.add_argument("--agree-eula", action="store_const", help="Automatically agree to the Minecraft EULA (https://aka.ms/MinecraftEULA)", const=True, default=False)
parser.add_argument("-j", "--java", "--jre", action="store_const", help="Install the Adoptium JRE in the server directory", const=True, default=False)
parser.add_argument("-y", "--force-create", action="store_const", help="Use a directory even if it already has files in it", const=True, default=False)

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

if 1 <= args.port <= 65535:
  PROPERTIES["server-port"] = str(args.port)
  PROPERTIES["query.port"] = str(args.port)
else:
  fatal("The port number must be between 1 and 65535.")
PROPERTIES["motd"] = args.motd
if args.players > 0:
  PROPERTIES["max-players"] = str(args.players)
  GEYSER_CONFIG["max-players"] = str(args.players)
else:
  fatal("The maximum number of players must be more than 0.")
PROPERTIES["spawn-protection"] = str(args.spawn_protection)
PROPERTIES["seed"] = args.seed
modes = ("creative", "survival", "adventure", "spectator")
if args.gamemode in modes:
  PROPERTIES["gamemode"] = args.gamemode
else:
  fatal("The gamemode must be one of " + ", ".join(["'" + mode + "'" for mode in modes[:-1]]) + ", or '" + modes[-1] + "'")
modes = ("easy", "normal", "hard", "peaceful")
if args.difficulty in modes:
  PROPERTIES["difficulty"] = args.difficulty
else:
  fatal("The difficulty must be one of " + ", ".join(["'" + mode + "'" for mode in modes[:-1]]) + ", or '" + modes[-1] + "'")
if args.hardcore and args.difficulty != "hard":
  info("Hardcore mode overrides the difficulty of the server to be hard.")
PROPERTIES["hardcore"] = "true" if args.hardcore else "false"
PROPERTIES["pvp"] = "false" if args.disable_pvp else "true"

if 1 <= args.port <= 65535:
  GEYSER_CONFIG["bedrock.port"] = str(args.bedrock_port)
else:
  fatal("The Bedrock port number must be between 1 and 65535.")
GEYSER_CONFIG["bedrock.motd1"] = args.bedrock_motd_1
GEYSER_CONFIG["bedrock.motd2"] = args.bedrock_motd_2
GEYSER_CONFIG["bedrock.server-name"] = args.bedrock_name

info("Downloading versions...")
r = get_url("https://launchermeta.mojang.com/mc/game/version_manifest.json", "version manifest")
manifest = r.json()
LATEST = manifest["latest"]["release"]
for version in manifest["versions"]:
  if version["type"] == "release":
    VERSIONS.append(version["id"])

software = get_software(args.software if args.software else "")
version = get_version(args.version if args.version else "")
directory = args.directory if args.directory else "."
build = args.build

if args.floodgate:
  args.geyser = True
if args.geyser and version != LATEST:
  warn("Geyser can only run on the latest Minecraft versions, so it will not be installed. Set the version to 'latest' to ensure you have the latest version.")
  args.geyser = False
  args.floodgate = False
if args.geyser and software not in ("paper", "spigot", "fabric"):
  warn("Geyser is only supported on Paper, Spigot, and Fabric servers, so it will not be installed here.")
  args.geyser = False
  args.floodgate = False
if args.disable_online_mode:
  if args.floodgate:
    PROPERTIES["online-mode"] = "true"
    warn("Online mode cannot be disabled while Floodgate is enabled because Floodgate overrides online mode.")
  else:
    PROPERTIES["online-mode"] = "false"
else:
  PROPERTIES["online-mode"] = "true"

if os.path.exists(directory):
  if os.listdir(directory):
    if not args.force_create:
      if not yn_prompt("This directory is not empty, install anyway?"):
        sys.exit(0)
else:
  try:
    makedirs(directory)
  except PermissionError:
    fatal("You do not have permission to make a server here!")

if args.java:
  middle_num = int(version.split(".")[:2][1])
  if middle_num < 17:
    JAVA_PATH = get_adoptium(directory, 8)
  elif middle_num == 17:
    JAVA_PATH = get_adoptium(directory, 16)
  else:
    JAVA_PATH = get_adoptium(directory, 17)

server_file = None
info(f"Searching for {software.title()} {version}...")
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
  save_file(os.path.join(directory, "start.sh"), get_part_startup_linux(directory, args.ram_min, args.ram_max) + f'java -Xms$RAM_MIN -Xmx$RAM_MAX -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 -Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true -jar {download_info["name"]} --nogui\n')

elif software == "spigot":
  try:
    r = requests.get(f"https://download.getbukkit.org/spigot/spigot-{version}.jar")
  except requests.exceptions.ConnectionError:
    fatal("There appears to be no internet connection.")
  if r.status_code == 404:
    try:
      r = requests.get(f"https://cdn.getbukkit.org/spigot/spigot-{version}.jar")
    except requests.exceptions.ConnectionError:
      fatal("There appears to be no internet connection.")
    if r.status_code == 404:
      fatal("This version of Spigot has not been released yet.")
    elif r.status_code != 200:
      fatal(f"Error {r.status_code}: {r.reason} when getting Spigot jarfile.")
  elif r.status_code != 200:
    fatal(f"Error {r.status_code}: {r.reason} when getting Spigot jarfile.")
  jarfile = f"spigot-{version}.jar"
  save_file(os.path.join(directory, jarfile), r.content)
  info("Saved jarfile!")
  if args.geyser: get_spigot_geyser(directory)
  if args.floodgate: get_spigot_floodgate(directory)
  info("Writing startup script...")
  save_file(os.path.join(directory, "start.sh"), get_part_startup_linux(directory, args.ram_min, args.ram_max) + f'java -Xms$RAM_MIN -Xmx$RAM_MAX -XX:+UseG1GC -jar {jarfile} -nogui\n')

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
      match = re.search(pattern, r.content.decode()).group()
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
      warn("Geyser-specific commandline options are not currently available with Fabric.")
      
      if args.floodgate:
        info("Installing Floodgate now...")
        r = get_url("https://ci.opencollab.dev/job/GeyserMC/job/Floodgate-Fabric/job/master/lastSuccessfulBuild/artifact/build/libs/floodgate-fabric.jar")
        if not r:
          fatal("Could not download Floodgate for Fabric jarfile.")
        save_file(os.path.join(directory, "mods", "Floodgate-Fabric.jar"), r.content)
        info("Installed Floodgate!")

  info("Writing startup script...")
  save_file(os.path.join(directory, "start.sh"), get_part_startup_linux(directory, args.ram_min, args.ram_max) + f'java -Xms$RAM_MIN -Xmx$RAM_MAX -jar {jarfile} -nogui\n')

os.chmod(os.path.join(directory, "start.sh"), 0o774)
info("Finished startup script!")
info("Setting server properties...")
r = get_url("https://server.properties/")
lines = r.content.decode().split("\n")[:-4]
lines[1] = "#" + get_mojang_timestamp()
new_lines = []
for line in lines:
  if "#" in line:
    active_line, comment = line.split("#", 1)
  else:
    active_line = line
    comment = None
  if active_line.strip():
    key, value = active_line.split("=", 1)
    if key in PROPERTIES:
      new_lines.append(key + "=" + PROPERTIES.get(key, value) + (" #" + comment if comment else ""))
    else:
      new_lines.append(line)
  else:
    new_lines.append(line)
save_file(os.path.join(directory, "server.properties"), "\n".join(new_lines) + "\n\n# Server generated by https://github.com/Aurillium/MCServerGenerator\n")
eula_file = "#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/MinecraftEULA).\n#" + get_mojang_timestamp() + "\n"
if args.agree_eula:
  save_file(os.path.join(directory, "eula.txt"), eula_file + "eula=true\n")
elif yn_prompt("Do you agree to the Minecraft EULA? (https://aka.ms/MinecraftEULA)"):
  save_file(os.path.join(directory, "eula.txt"), eula_file + "eula=true\n")
else:
  save_file(os.path.join(directory, "eula.txt"), eula_file + "eula=false\n")
print("Installation successful!")
