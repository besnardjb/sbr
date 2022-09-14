#!/bin/env python3
from genericpath import isfile
import sys
import argparse
import os
import re
import yaml
from datetime import datetime
from datetime import timedelta
import glob
import logging
from rich.logging import RichHandler
import shutil

FORMAT = "%(message)s"
logging.basicConfig(
    level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler()]
)

log = logging.getLogger("rich")

from rich.console import Console
from rich.markdown import Markdown



def check_dir(dir):
    dir = os.path.expanduser(dir)
    if not os.path.isdir(dir):
        os.makedirs(dir)

class Config():

    def __init__(self):
        self.conf_file = os.path.expanduser("~/.config/sbr/config.yaml")
        self.default_conf = { "daily_format" : "Daily/%Y/%m/%d",
                              "brain_location" : "~/.sbr" }

        self.config = self.default_conf
        self._load_or_init()


    def _load_or_init(self):
        if os.path.isfile(self.conf_file):
            with open(self.conf_file, 'r') as f:
                try:
                    self.config = yaml.load(f, Loader=yaml.FullLoader)
                except Exception as e:
                    log.error("BAD YAML could not load configuration file in {}".format(self.conf_file))
                    print(e)
                    sys.exit(1)
        else:
            check_dir("~/.config/sbr/")

            with open(self.conf_file, 'w') as f:
                f.write(yaml.dump( self.config) )
            log.info("Created config file in {}".format(self.conf_file))

    @property
    def daily(self):
        return self.config["daily_format"]

    @property
    def location(self):
        return os.path.expanduser(self.config["brain_location"])




class SecondBrain():

    def __init__(self):
        self.config = Config()
        check_dir(self.config.location)

        self._target = None

        self.daily()

    def _daily_path(self, offset=0):
        now = datetime.now()
        if offset:
            now = now - timedelta(days=offset)

        inner = now.strftime(self.config.daily + ".md")
        # Make sure inner exists
        d = os.path.dirname(inner)
        check_dir(d)
        return self.config.location + "/" + inner

    def daily(self, offset=0):
        self._target = self._daily_path()


    def prevdaily(self):
        for i in range(1,64):
            daily = self._daily_path(offset=i)
            if os.path.isfile(daily):
                self._target = daily
                return
        log.error("No previous daily in the last 64 days")
        sys.exit(1)

    def nextdaily(self):
        self._target = self._daily_path(offset=-1)

    def view_md(self):
        if not os.path.isfile(self._target):
            log.error("No such file {}, cannot display it".format(self._target))
            sys.exit(1)
        with open(self._target, 'r') as f:
            data = f.read()
            console = Console()
            md = Markdown(data)
            console.print(md)

    def _get_template(self):
        target = self._target
        if os.path.isfile(target):
            # Nothing to do
            return
        startdir = os.path.dirname(target)
        p = startdir

        while p != "/" and p:
            t = p + "/Template.md"
            if os.path.isfile(t):
                check_dir(startdir)
                shutil.copyfile(t, target)
                return
            p = os.path.dirname(p)


    def edit(self):
        if not self._target:
            raise Exception("No target file selected")


        edit = os.getenv("EDITOR")
        if not edit:
            edit = "vim"

        self._get_template()

        os.system("{} \"{}\"".format(edit, self._target))

    def list(self):
        os.chdir(self.config.location)
        return glob.glob('./**/*.md'.format(), recursive=True)

    def find(self, pattern):
        l = self.list()
        query = re.compile(pattern)

        did_match = False
        for e in l:
            if query.search(e):
                if not did_match:
                    log.warning("Matched {}".format(e))
                    self._target = self.config.location + "/" + e
                    did_match = True
                else:
                    log.info("Could have matched {}".format(e))
        if did_match:
            return
        log.error("No file matches {}".format(pattern))
        sys.exit(1)


    def open(self, target):
        loc = self.config.location
        target = loc + "/" + target
        if not os.path.isfile(target):
            # Make sure storage dir is present
            check_dir(os.path.dirname(target))
        self._target = target



br = SecondBrain()

def complete_prefix(prefix, parsed_args, **kwargs):
    print(prefix)


def run():

    #
    # Argument parsing
    #


    parser = argparse.ArgumentParser(description='Second BRain.')


    parser.add_argument('-d', "--daily",  action='store_true', help="Target daily note")
    parser.add_argument('-p', "--prevdaily",  action='store_true', help="Target previous daily note")
    parser.add_argument('-n', "--nextdaily",  action='store_true', help="Target next daily note")

    parser.add_argument('-o', "--open", help="Target existing node")

    parser.add_argument('-l', "--list",  action='store_true', help="List notes")
    parser.add_argument('-f', "--find", type=str, help="Open file matching pattern")

    parser.add_argument('-e', "--edit",  action='store_true', help="Open target for eddition")
    parser.add_argument('-v', "--view",  action='store_true', default=True, help="View target content (default)")


    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args(sys.argv[1:])


    if args.list:
        console = Console()
        console.print(br.list())
        sys.exit(0)

    if args.find:
        br.find(args.find)
    elif args.open:
        br.open(args.open)
    elif args.daily:
        br.daily()
    elif args.prevdaily:
        br.prevdaily()
    elif args.nextdaily:
        br.nextdaily()


    if args.edit:
        br.edit()
        sys.exit(0)

    br.view_md()
