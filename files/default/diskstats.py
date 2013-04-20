# 
# This file is generated by Chef
# Do not edit, changes will be overwritten 
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; only version 2 of the License is applicable.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# Authors:
#   David Crane <davidc at donorschoose.org>
#
# About this plugin:
#   This plugin reads data from /sys/block/[device]/stat, and is probably
#   only correct for Linux 2.6 kernels. (The motivation for this plugin
#   was https://github.com/indygreg/collectd-diskstats by Gregory Szorc.)
#
# collectd:
#   http://collectd.org
# collectd-python:
#   http://collectd.org/documentation/manpages/collectd-python.5.shtml
#
# The /proc/diskstats fields are documented in Documentation/iostats.txt
# in the Linux kernel source tree.

########################################################################
# To configure the plugin, you must specify the devices to monitor.
# The plugin takes a param 'Disk' whose string value is the exact
# device name. This param can be defined multiple times. E.g.,
#
#   <Plugin python>
#      ModulePath "/path/to/modules"
#      Import "diskstats"
#
#      <Module diskstats>
#          BlockDevice sda
#      </Module>
#   </Plugin>
#
# The recipe[collectd::attribute_driven] will build conf.d/python.conf
# for you with the configuration above if you define these attributes
# in a roles/*.json file:
#
#   default_attributes ({
#     "collectd" => {
#       "plugins" => {
#         "python" => {
#           "template" => "python.conf.erb",
#           "config" => {
#             # One for each custom module script:
#             "diskstats" => {
#               "BlockDevice" => "sda"
#             }
#           }
#         }
#       }
#     }
#   })

########################################################################
import collectd

# Plugin configuration: from <Module diskstats> BlockDevice list.
devices = []

def configure_callback(conf):
    """Receive configuration block"""
    global devices

    if conf.values[0] != 'diskstats':
        return

    for child in conf.children:
        if child.key == 'BlockDevice':
            for v in child.values:
                if v not in devices:
                    devices.append(v)
        else:
            collectd.warning('diskstats plugin: Unknown config key: %s.'
                             % child.key)

def read_callback():
    # if no disks to monitor, do nothing
    if not len(devices):
        return

    # Object for dispatching to graphite, reused for each device/metric.
    val = collectd.Values(plugin='diskstats')

    for device in devices:

        val.plugin_instance = device

        # The /sys/block/%s/stat read gives 1 line with 11 fields.
        # See /proc/diskstats documentation about field meanings.
        fh = open('/sys/block/%s/stat' % (device), 'r')
        for line in fh:
            fields = line.split()

            if len(fields) != 11:
                collectd.warning('format of /proc/diskstats not recognized: %s' % line)
                continue

            # /proc/diskstats field 1 and 5:
            # Reads/Writes (in IOPs) completed by underlying block device.
            rd_value = int(fields[0])
            wr_value = int(fields[4])
            val.type = 'disk_ops' # A 2-value derive field
            val.values = [rd_value, wr_value]
            val.dispatch()

            # /proc/diskstats field 2 and 6:
            # Reads (in IOPs) merged by kernel's queue scheduler into disk_ops field above.
            rd_value = int(fields[1])
            wr_value = int(fields[5])
            val.type = 'disk_merged' # A 2-value derive field
            val.values = [rd_value, wr_value]
            val.dispatch()

            # /proc/diskstats field 3 and 7:
            # Sectors read by the completed block device reads.
            rd_value = 512*int(fields[2])
            wr_value = 512*int(fields[6])
            val.type = 'disk_octets' # A 2-value derive field
            val.values = [rd_value, wr_value]
            val.dispatch()

            # /proc/diskstats field 4 and 8:
            # While at least one read queued to underlying block device.
            rd_value = int(fields[3])
            wr_value = int(fields[7])
            val.type = 'disk_time' # A 2-value derive field
            val.values = [rd_value, wr_value]
            val.dispatch()

            # /proc/diskstats field 9:
            # The number of I/Os currently in progress, that is, they've
            # been scheduled by the queue scheduler and issued to the
            # disk (submitted to the underlying disk's queue), but not
            # yet completed.
            value = int(fields[8])
            val.type = 'disk_ops_complex'
            val.type_instance = 'in_progress'
            val.values = [value]
            val.dispatch()

            # /proc/diskstats field 10:
            # The total number of milliseconds spent doing I/Os. This is
            # not the total response time seen by the applications; it
            # is the total amount of time during which at least one I/O
            # was in progress.
            # Can be used to estimate overall service time.
            value = int(fields[9])
            val.type = 'total_time_in_ms'
            val.type_instance = 'serving_io'
            val.values = [value]
            val.dispatch()

            # /proc/diskstats field 11:
            # This field counts the total response time of all I/Os. In
            # contrast to serving_io field above, it counts double when
            # two I/Os overlap.
            # Can be used to estimate overall response time.
            value = int(fields[10])
            val.type = 'total_time_in_ms'
            val.type_instance = 'weighted_io'
            val.values = [value]
            val.dispatch()

        fh.close()

########################################################################
# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(read_callback)