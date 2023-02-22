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

def show_md(data):
    console = Console()
    md = Markdown(data)
    console.print(md)


class SecondBrain():

    def __init__(self):
        self.config = Config()
        check_dir(self.config.location)

        self._target = None

        self.daily()

    def target(self):
        return self._target

    def _daily_path(self, offset=0):
        now = datetime.now()
        if offset:
            now = now - timedelta(days=offset)

        local = now.strftime(self.config.daily + ".md")
        fullpath = os.path.join(
                    self.config.location,
                    local
                )
        # Make sure inner exists
        d = os.path.dirname(fullpath)
        check_dir(d)
        return fullpath, local

    def daily(self, offset=0):
        self._target, _ = self._daily_path()

    def _load_task(self, path, inner, pending=True):
        ret = []
        with open(path, "r") as f:
            data = f.read()
            lines = data.split("\n")
            if pending:
                query = re.compile("^[\*-] \[\s\].*$")
            else:
                query = re.compile("^[\*-] \[x\].*$")
            for l in lines:
                if query.search(l):
                    ret.append([path, inner, l])
        return ret

    def list_tasks(self, max_range=360, pending=True):
        ptask = []
        for i in range(0, max_range):
            path, inner = self._daily_path(offset=i)
            if os.path.isfile(path):
                r = self._load_task(path, inner, pending)
                if r:
                    ptask = ptask + r
        return ptask

    def pending_tasks(self):
        pending = set( [x[2][6:].strip() for x in  br.list_tasks() ] )
        done = set( [x[2][6:].strip() for x in  br.list_tasks(pending=False) ] )
        left = pending - done
        return left

    def prevdaily(self):
        for i in range(1,64):
            daily, _ = self._daily_path(offset=i)
            if os.path.isfile(daily):
                self._target = daily
                return
        log.error("No previous daily in the last 64 days")
        sys.exit(1)

    def nextdaily(self):
        self._target, _ = self._daily_path(offset=-1)

    def view_md(self):
        if not os.path.isfile(self._target):
            log.error("No such file {}, cannot display it".format(self._target))
            sys.exit(1)
        with open(self._target, 'r') as f:
            data = f.read()
            show_md(data)

    def __gather_by_tag_in_list(self, entry_list, skip=None):
        tags = {}
        groups = {}

        for e in entry_list:
            m = re.findall("#([^\s]+)", e)
            if m:
                for g in m:
                    if g == skip:
                        continue
                    if g in tags:
                        tags[g] = tags[g] + 1
                        groups[g].append(e)
                    else:
                        tags[g] = 1
                        groups[g] = [e]

        return [ x[0] for x in sorted(tags.items(), key=lambda x: x[1], reverse=True) ], groups

    def _gather_tasks_by_dominating_tag(self, tasks, skip=None):
        task_set = set(tasks)

        ret = {}
        did_group = 0

        while(True):

            tsk, groups = self.__gather_by_tag_in_list(list(task_set), skip)

            if len(tsk) == 0:
                break

            if tsk:
                e = tsk[0]
                group_task_set = set(groups[e])
                task_set = task_set - group_task_set
                ret[e] = groups[e]
                did_group = 1


        if len(task_set) or not did_group:
            ret["_"] = list(task_set)

        return ret

    def _gen_task_nesting(self):
        pdt = self.pending_tasks()

        grp1 = self._gather_tasks_by_dominating_tag(pdt)

        if isinstance(grp1, list):
            return grp1

        print(grp1)

        for k in [ x for x in grp1.keys() if x != "_"]:
            grp1[k] = self._gather_tasks_by_dominating_tag(grp1[k], skip=k)

        # If the first level contains only one element merge up
        for l1_key in grp1.keys():
            if not isinstance(grp1[l1_key], list):
                l2_keys = list(grp1[l1_key].keys())
                if len(l2_keys) == 1:
                    grp1[l1_key] = grp1[l1_key][l2_keys[0]]

        return grp1


    def _task_nesting_md(self):
        task_nesting = self._gen_task_nesting()


        ret = ""

        if "_" in task_nesting:
            ret += "\n".join([ "* [ ] {}".format(x) for x in task_nesting["_"]])

        for k in [ x for x in task_nesting.keys() if x != "_" ]:

            ret += "\n\n## {}".format(k) + "\n\n"

            if isinstance(task_nesting[k], list):
                ret += "\n".join([ "* [ ] {}".format(x) for x in task_nesting[k]])
                continue


            if "_" in task_nesting[k]:
                ret += "\n".join([ "* [ ] {}".format(x) for x in task_nesting[k]["_"]])

            for kk in [ x for x in task_nesting[k].keys() if x != "_" ]:
                ret += "\n\n### {}".format(kk) + "\n\n"
                ret += "\n".join([ "* [ ] {}".format(x) for x in task_nesting[k][kk]])

        return ret

    def _cpy_with_task_list(self, path_to_template, target):
        pending_list = self._task_nesting_md()
        with open(path_to_template, "r") as f:
            content = f.read()
            content = content.replace("%tasks%", pending_list)
            with open(target, "w") as d:
                d.write(content)


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
                self._cpy_with_task_list(t, target)
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

        matches = []

        did_match = False
        for e in l:
            if query.search(e):
                if not did_match:
                    # We keep the first as target
                    self._target = self.config.location + "/" + e
                    did_match = True
                # Save others in ret for grep
                matches.append(e)
        if did_match:
            return matches
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

def list_md(title, l):
    add = "\n".join([ "- {}".format(x) for x in l])
    out = "# {}\n{}".format(title, add)
    show_md(out)

def run():

    #
    # Argument parsing
    #


    parser = argparse.ArgumentParser(description='Second BRain.')


    parser.add_argument('-d', "--daily",  action='store_true', help="Target daily note")
    parser.add_argument('-e', "--edit",  action='store_true', help="Open target for eddition")
    parser.add_argument('-f', "--find", type=str, help="Open file matching pattern")
    parser.add_argument('-g', "--grep", type=str, help="List files matching a pattern")
    parser.add_argument('-l', "--list",  action='store_true', help="List notes")
    parser.add_argument('-n', "--nextdaily",  action='store_true', help="Target next daily note")
    parser.add_argument('-o', "--open", help="Target existing node")
    parser.add_argument('-p', "--prevdaily",  action='store_true', help="Target previous daily note")
    parser.add_argument('-t', "--tasks", action='store_true', help="List unchecked items in daily notes (last 360 days)")
    parser.add_argument('-T', "--alltasks", action='store_true', help="List all items in daily notes with their locations (last 360 days)")
    parser.add_argument('-v', "--view",  action='store_true', default=True, help="View target content (default)")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args(sys.argv[1:])

    if args.list:
        console = Console()
        list_md("List of Notes", br.list())
        sys.exit(0)
    if args.grep:
        l = br.find(args.grep)
        list_md("Matches '{}'".format(args.grep), l)
        sys.exit(0)
    if args.find:
        br.find(args.find)
        log.info("Matched {}".format(br.target()))
    elif args.open:
        br.open(args.open)
    elif args.daily:
        br.daily()
    elif args.prevdaily:
        br.prevdaily()
    elif args.nextdaily:
        br.nextdaily()
    elif args.alltasks:
        allt = br.list_tasks(pending=False) + br.list_tasks()
        ll = [ "{} in **{}**".format(x[2], x[1]) for x in allt]
        ll = ["# All tasks"] + ll
        show_md("\n".join(ll))
        sys.exit(0)
    elif args.tasks:
        show_md("# Pending Tasks\n" + br._task_nesting_md())
        sys.exit(0)


    if args.edit:
        br.edit()
        sys.exit(0)

    br.view_md()
