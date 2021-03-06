### This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from sos.plugins import Plugin, RedHatPlugin
import os, re
from glob import glob

class cluster(Plugin, RedHatPlugin):
    """cluster suite and GFS related information
    """

    optionList = [("gfslockdump",
                    'gather output of gfs lockdumps', 'slow', False),
                    ('lockdump', 'gather dlm lockdumps', 'slow', False)]

    def checkenabled(self):
        rhelver = self.policy().rhelVersion()
        if rhelver == 4:
            self.packages = [ "ccs", "cman", "cman-kernel", "magma",
                              "magma-plugins", "rgmanager", "fence", "dlm",
                              "dlm-kernel", "gulm", "GFS", "GFS-kernel",
                              "lvm2-cluster" ]
        elif rhelver == 5:
            self.packages = [ "rgmanager", "luci", "ricci",
                              "system-config-cluster", "gfs-utils", "gnbd",
                              "kmod-gfs", "kmod-gnbd", "lvm2-cluster",
                              "gfs2-utils" ]

        elif rhelver == 6:
            self.packages = [ "ricci", "corosync", "openais",
                              "cman", "clusterlib", "fence-agents" ]

        self.files = [ "/etc/cluster/cluster.conf" ]
        return Plugin.checkenabled(self)

    def setup(self):
        rhelver = self.policy().rhelVersion()

        self.addCopySpec("/etc/cluster.conf")
        self.addCopySpec("/etc/cluster.xml")
        self.addCopySpec("/etc/cluster")
        self.addCopySpec("/etc/sysconfig/cluster")
        self.addCopySpec("/etc/sysconfig/cman")
        self.addCopySpec("/etc/fence_virt.conf")
        self.addCopySpec("/var/lib/ricci")
        self.addCopySpec("/var/lib/luci")
        self.addCopySpec("/var/log/cluster")
        self.addCopySpec("/var/log/luci/luci.log")
        self.addCopySpec("/etc/fence_virt.conf")

        if self.getOption('gfslockdump'):
          self.do_gfslockdump()

        if self.getOption('lockdump'):
          self.do_lockdump()

        self.addCmdOutput("/usr/sbin/rg_test test "
                        + "/etc/cluster/cluster.conf" )
        self.addCmdOutput("fence_tool ls -n")
        self.addCmdOutput("gfs_control ls -n")
        self.addCmdOutput("dlm_tool log_plock")

        self.addCmdOutput("/sbin/fdisk -l")
        self.getCmdOutputNow("clustat")
        self.getCmdOutputNow("group_tool dump")
        self.addCmdOutput("cman_tool services")
        self.addCmdOutput("cman_tool nodes")
        self.addCmdOutput("cman_tool status")
        self.addCmdOutput("ccs_tool lsnode")
        self.addCmdOutput("/sbin/ipvsadm -L")

        if rhelver is 4:
            self.addCopySpec("/proc/cluster/*")
            self.addCmdOutput("cman_tool nodes")

        if rhelver is not 4: # 5+
            self.addCmdOutput("cman_tool -a nodes")

        if rhelver is 5:
            self.addCmdOutput("group_tool -v")
            self.addCmdOutput("group_tool dump fence")
            self.addCmdOutput("group_tool dump gfs")

        if rhelver not in (4,5): # 6+
            self.addCmdOutput("corosync-quorumtool -l")
            self.addCmdOutput("corosync-quorumtool -s")
            self.addCmdOutput("corosync-cpgtool")
            self.addCmdOutput("corosync-objctl")
            self.addCmdOutput("group_tool ls -g1")
            self.addCmdOutput("gfs_control ls -n")
            self.addCmdOutput("gfs_control dump")
            self.addCmdOutput("fence_tool dump")
            self.addCmdOutput("dlm_tool dump")
            self.addCmdOutput("dlm_tool ls -n")
            self.addCmdOutput("mkqdisk -L")

    def do_lockdump(self):
        rhelver = self.policy().rhelVersion()

        if rhelver is 4:
            status, output, time = self.callExtProg("cman_tool services")
            for lockspace in re.compile(r'^DLM Lock Space:\s*"([^"]*)".*$',
                    re.MULTILINE).findall(output):
                self.callExtProg("echo %s > /proc/cluster/dlm_locks" 
                        % lockspace)
                self.getCmdOutputNow("cat /proc/cluster/dlm_locks",
                        suggest_filename = "dlm_locks_%s" % lockspace)

        if rhelver is 5:
            status, output, time = self.callExtProg("group_tool")
            for lockspace in re.compile(r'^dlm\s+[^\s]+\s+([^\s]+)$',
                    re.MULTILINE).findall(output):
                self.addCmdOutput("dlm_tool lockdebug '%s'" % lockspace,
                        suggest_filename = "dlm_locks_%s" % lockspace)

        else: # RHEL6 or recent Fedora
            status, output, time = self.callExtProg("dlm_tool ls")
            for lockspace in re.compile(r'^name\s+([^\s]+)$',
                    re.MULTILINE).findall(output):
                self.addCmdOutput("dlm_tool lockdebug -svw '%s'"
                        % lockspace,
                        suggest_filename = "dlm_locks_%s" % lockspace)

    def do_gfslockdump(self):
        for mntpoint in self.doRegexFindAll(r'^\S+\s+([^\s]+)\s+gfs\s+.*$',
                    "/proc/mounts"):
            self.addCmdOutput("/sbin/gfs_tool lockdump %s" % mntpoint,
                        suggest_filename = "gfs_lockdump_"
                        + self.mangleCommand(mntpoint))

    def postproc(self):
        for cluster_conf in glob("/etc/cluster/cluster.conf*"):
            self.doFileSub(cluster_conf,
                        r"(\s*\<fencedevice\s*.*\s*passwd\s*=\s*)\S+(\")",
                        r"\1%s" %('"***"'))
        self.doCmdOutputSub("corosync-objctl",
                        r"(.*fence.*\.passwd=)(.*)",
                        r"\1******")
        return
