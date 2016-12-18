#!/usr/bin/env python
import os
import json
import subprocess
import Logging as log
import argparse

def go(argv=None):
    parser = argparse.ArgumentParser(description="Filter the catalog for deployment")
    parser.add_argument("--deploy", action='store_true', help="install rather than link")
    parser.add_argument("--target", default='deploy/python_libs', help="where to install")
    parser.add_argument("-n", dest="dry_run", default=False, action='store_true',  help="Don't do anything, just talk about it.")
    log.add_logging_args(parser)
    args = parser.parse_args()
    
    #log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
    
    json_file = "python_dependencies_local.json"
    pip_dependencies = "python_dependencies.txt"
    dest = args.target
    if dest[-1] != "/":
        dest = dest + "/"

    libs = json.load( open(json_file) )
    #libs = []
    def status_msg(*args):
        w = ""
        for msg in args:
            w += str(msg) + " "
        d = int((80 - len(w)-4)/2) * "-"
        s = "  "
        log.info(d + s + w + s + d + "\n")

    # Check if the python libs directory exists
    if not os.path.exists( dest ):
        status_msg("No python libraries folder detected")
        status_msg("Making", dest)
        os.makedirs(dest)

    # Open pip dependencies file
    dependencies = open( pip_dependencies ).read()

    status_msg("Checking for missing pip packages")
    # Install any missing pip packages
    for package in dependencies.split('\n'):
        if package is not "":
            path = dest + package
            cmdargs = ["pip", "install", "-U", "--use-wheel", "--target", dest, package]
            log.info("Running: {}".format(" ".join(cmdargs)))
            if not args.dry_run:
                subprocess.call(cmdargs)
                
    if args.deploy:
        for lib in libs:
            path = os.path.abspath(lib["package_home"])
            log.info ("pip install --target {} --use-wheel {}".format(dest, path))
            if not args.dry_run:
                os.system("pip install --target {} --use-wheel {}".format(dest, path))
    else:        
        # Create symbolic links for local packages
        #status_msg("Checking for missing local modules")
        for lib in libs:
            path = os.path.abspath(lib["link_path"])
            name = lib["name"]
            dest_path = dest+name
            if os.path.exists( path ):
                #log.info ("(cd {}; pip install -e  .)".format(path))
                #os.system("(cd {}; pip install -e  .)".format(path))
                #log.info ("(cd {}; pip install --use-wheel --target {}   .)".format(path, os.path.abspath(dest)))
                #os.system("(cd {}; pip install --use-wheel --target {}   .)".format(path, os.path.abspath(dest)))
                status_msg("Found:", name)
                status_msg("Checking if symbolic link exists for", name)
                if os.path.exists( dest_path ): 
                     status_msg("Symbolic link exists for", name)
                else:
                     status_msg("No symbolic link found for",name)
                     status_msg("Creating symbolic link at", dest_path)
                     if not args.dry_run:
                         os.symlink(path, dest_path )
            else:
                status_msg("Error: Could not find the library", name, "at", path)
                status_msg("Have you cloned all the dependencies?")

if __name__ == "__main__":
    go();
