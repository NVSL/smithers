#!/usr/bin/env python

import argparse
import os
import subprocess
import sys
from gtron import check_up_to_date, get_branch,  has_uncommited_changes, theWorkspace

import Gadgetron.GtronLogging as log


class CmdFailure(Exception):
    def __init__(self, returncode, stdout, stderr):
        Exception.__init__(self)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def __str__(self):
        return "{}\n{}\nreturn code={}".format(self.stdout, self.stderr, self.returncode)
    

dry_run = False
def do_cmd(s,
           stdout=None,
           stderr=None,
           stdin=None,
           live_updates=False,
           raise_on_err=True,
           cwd=None,
           read_only=False,
           env=None,
           echo=False):
    if dry_run is True and not read_only:
        output = ""
        if env is not None:
            print "\n".join(["{}={}".format(k,v) for (k,v) in env.items()]) + " " + s;
        else:
            print s
        return (None,None,None)
    else:
        if dry_run or echo:
            print s

        if env is None:
            nenv = os.environ
        else:
            nenv = os.environ.copy()
            nenv.update(env)

        log.info("Executing: " + s);
        if live_updates:
            p = subprocess.Popen(s, shell=True, stdout=stdout, stderr=stderr, stdin=stdin, cwd=cwd, env=nenv);
            (out, err) = p.communicate()
        else:
            p = subprocess.Popen(s, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin, cwd=cwd, env=nenv);
            (out, err) = p.communicate()
            log.info("Stdout: \n" + str(out));
            log.info("stderr: \n" + str(err));
            
        if stdout is not None:
            if out is not None:
                stdout.write(out)
        if stderr is not None:
            if err is not None:
                stderr.write(err)

        if p.returncode is not 0:
            log.info("Command failed  ({})".format(s))
            if raise_on_err:
                raise CmdFailure(p.returncode, out, err)

        return (p.returncode, out, err)

def go(argv=None):
    parser = argparse.ArgumentParser(description="Deploy jet")
    parser.add_argument("--release", action='store_true', help="Do a deployment of the release branch")
    parser.add_argument("--relbranch", default=None, help="Release branch")
    parser.add_argument("--update", action='store_true',help="Update before install")
    parser.add_argument("--version", default=None, help="Version name to use in deployment")
    parser.add_argument("--dirs", default=[], nargs="*", help="repos to update and build")
    parser.add_argument("--nobuild", action='store_true', help="Just deploy, don't build")
    parser.add_argument("--nodeploy", action='store_true', help="Don't deploy, just build")
    parser.add_argument("-n", dest="dry_run", action='store_true', help="Don't actually do anything")
    log.add_logging_args(parser)
    args = parser.parse_args()

    if args.release:
        assert args.relbranch == None, "Can't specify different release branch for release deployment"
        assert args.dirs == [], "can't limit directories for release deployment"
        assert args.version == None, "cant set version name in release deployment"
        args.relbranch = "release"
        args.update = True;
    else:
        assert args.version is not None, "Must set version name for non-release deployment"
        
    global dry_run
    dry_run = args.dry_run

    old_branches = {}

    if not args.nobuild and args.relbranch is not None:
        try:
            for i in theWorkspace.get_repo_dirs():
                if has_uncommited_changes(i):
                    log.error("{} has uncommitted changes".format(i))
                    raise Exception
                b = get_branch(i);
                if b != args.relbranch:
                    old_branches[i] = b
                    do_cmd("cd {}; git checkout -b {}".format(i,args.relbranch))
            if args.update:
                log.info("Updating...")
                do_cmd('gtron update --failstop {}'.format(" ".join(args.dirs)), stdout=sys.stdout, stderr=sys.stderr, echo=True, live_updates=True)
        finally:
            for i in old_branches:
                try:
                    do_cmd('cd {}; git checkout {}'.format(i,old_branches[i]))
                except:
                    pass

#log.info("Building...")
    #do_cmd('gtron build --failstop {}'.format(" ".join(args.dirs)), stdout=sys.stdout, stderr=sys.stderr, echo=True, live_updates=True)

    try:
        if args.version:
            version_string = args.version
        else:
            version_string = "release-v" + open("VERSION.txt").read().strip().replace(".","-")
        deploy_dir = "deploy_{}".format(version_string)
        if not args.nobuild:
            #do_cmd("grunt clean", env={'GTRON_DEPLOY_DIRECTORY': deploy_dir}, echo=True, live_updates=True)
            do_cmd("grunt build_deploy", env={'GTRON_DEPLOY_DIRECTORY': deploy_dir}, echo=True, live_updates=True)
        if not args.nodeploy:
            do_cmd("appcfg.py -A ucsdgadgetron -V {} update {}/app.yaml".format(version_string, deploy_dir), echo=True, live_updates=True)
            do_cmd("appcfg.py -A ucsdgadgetron -V {} update_cron {}".format(version_string, deploy_dir), echo=True, live_updates=True)
            do_cmd("appcfg.py -A ucsdgadgetron -V {} update_indexes {}".format(version_string, deploy_dir), echo=True, live_updates=True)
    finally:
        pass;

if __name__ == "__main__":
    go()
