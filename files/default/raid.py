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
#   This plugin uses collectd's Python plugin to record Adaptec RAID Controller information.
#
# collectd:
#   http://collectd.org
# collectd-python:
#   http://collectd.org/documentation/manpages/collectd-python.5.shtml

########################################################################
# To configure the plugin, you must specify the full path to the
# arcconf utility. This assumes there is a single controller on the box.
#
#   <Plugin python>
#      ModulePath "/path/to/modules"
#      Import "raid"
#
#      <Module "raid">
#        ArcconfCmd "/usr/StorMan/arcconf"
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
#             "raid" => {
#               "ArcconfCmd" => "/usr/StorMan/arcconf"
#             }
#           }
#         }
#       }
#     }
#   })

######################################################################
import collectd, os, re, array

# Adaptec's arcconf executable. Override in config by specifying 'ArcconfCmd'.
ARCCONF_CMD = '/usr/StorMan/arcconf'

def configure_callback(conf):
    """Receive configuration block"""
    global ARCCONF_CMD
    for node in conf.children:
        if node.key == 'ArcconfCmd':
            ARCCONF_CMD = node.values[0]
        #elif node.key == 'Port':
        #    REDIS_PORT = int(node.values[0])
        else:
            collectd.warning('raid plugin: Unknown config key: %s.'
                             % node.key)

######################################################################
def dispatch_value(value, plugin_instance, type, type_instance):
    """Dispatch a value to write_graphite"""

    val = collectd.Values(plugin='raid')
    val.plugin_instance = plugin_instance
    val.type = type
    val.type_instance = type_instance
    val.values = [value]

    # send high-level values as ...plugin-plugin_instance.type-type_instance
    val.dispatch()

########################################################################
# Regex for matching and parsing lines of arcconf output

# /usr/StorMan/arcconf GETCONFIG 1 AL
# ----------------------------------------------------------------------
# Controller information
# ----------------------------------------------------------------------
#    Controller Status                        : Optimal
#    Temperature                              : 56 C/ 132 F (Normal)
#    Defunct disk drive count                 : 0
#    Logical devices/Failed/Degraded          : 1/0/0
#    --------------------------------------------------------
#    Controller Battery Information
#    --------------------------------------------------------
#    Status                                   : Optimal
#    Over temperature                         : No
#    Capacity remaining                       : 99 percent
#    Time remaining (at current draw)         : 1 days, 19 hours, 55 minutes
c_status_re = re.compile('^\s*Controller Status\s*:\s*(.*)$')
c_temp_re = re.compile('^\s*Temperature\s*:\s*([0-9]+) C/\s*[0-9]+ F (.*)\s*$')
c_defunct_re = re.compile('^\s*Defunct disk drive count\s*:\s*([0-9]+).*$')
c_degraded_re = re.compile('^\s*Logical devices/Failed/Degraded\s*:\s*([0-9]+)/([0-9]+)/([0-9]+).*$')

b_status_re = re.compile('^\s*Status\s*:\s*(.*)\s*$')
b_temp_re = re.compile('^\s*Over temperature\s*:\s*(.*)\s*$')
b_capacity_re = re.compile('\s*Capacity remaining\s*:\s*([0-9]+)\s*percent.*$')
b_time_re = re.compile('\s*Time remaining \(at current draw\)\s*:\s*([0-9]+) days, ([0-9]+) hours, ([0-9]+) minutes.*$')

# ----------------------------------------------------------------------
# Logical device information
# ----------------------------------------------------------------------
# Logical device number 0
#    Write-cache mode                         : Enabled (write-back)
#    Failed stripes                           : No
l_writecache_re = re.compile('^\s*Write-cache mode\s*:\s*(.*)\s*$')
l_failedstripes_re = re.compile('^\s*Failed stripes\s*:\s*(.*)\s*$')

# ----------------------------------------------------------------------
# Physical Device information
# ----------------------------------------------------------------------
#       Device #0
#          Device is a Hard drive
#          State                              : Online
#          Write Cache                        : Disabled (write-through)
p_harddrive_re = re.compile('^\s*Device is a Hard drive\s*$')
p_state_re = re.compile('^\s*State\s*:\s*(.*)\s*$')
p_writecache_re = re.compile('^\s*Write Cache\s*:\s*(.*)\s*$')

########################################################################
# /usr/StorMan/arcconf GETLOGS 1 DEVICE TABULAR
#       driveErrorEntry                            
#           deviceID ....................................... 3
#           hwErrors ....................................... 0
#           mediumErrors ................................... 1
#           smartWarning ................................... 0
p_deviceid_re = re.compile('^\s*deviceID \.*\s*([0-9]+).*$')
p_hwerrors_re = re.compile('^\s*hwErrors \.*\s*([0-9]+).*$')
p_mediumerrors_re = re.compile('^\s*mediumErrors \.*\s*([0-9]+).*$')
p_smartwarning_re = re.compile('^\s*smartWarning \.*\s*([0-9]+).*$')


########################################################################
def read_callback():

# ----------------------------------------------------------------------
# Controller information
# ----------------------------------------------------------------------
#    Controller Status                        : Optimal
#    Temperature                              : 56 C/ 132 F (Normal)
#    Defunct disk drive count                 : 0
#    Logical devices/Failed/Degraded          : 1/0/0
#    --------------------------------------------------------
#    Controller Battery Information
#    --------------------------------------------------------
#    Status                                   : Optimal
#    Over temperature                         : No
#    Capacity remaining                       : 99 percent
#    Time remaining (at current draw)         : 1 days, 19 hours, 55 minutes

    non_optimal_status = 1   # Assume non-optimal until seen
    card_overheating = 0
    centigrade = 0
    defunct_drives = 0

    battery_problems = 0
    battery_percent = 0
    battery_minutes = 0

    num_logical_groups = 0
    in_degraded_state = 0
    in_failed_state = 0

# ----------------------------------------------------------------------
# Logical device information
# ----------------------------------------------------------------------
# Logical device number 0
#    Write-cache mode                         : Enabled (write-back)
#    Failed stripes                           : No

    in_write_through_mode = 0
    containing_bad_stripes = 0

# ----------------------------------------------------------------------
# Physical Device information
# ----------------------------------------------------------------------
#       Device #0
#          Device is a Hard drive
#          State                              : Online
#          Write Cache                        : Disabled (write-through)

    num_physical_drives = 0
    in_abnormal_state = 0
    in_write_back_mode = 0

    for line in os.popen4('%s GETCONFIG 1 AL' % (ARCCONF_CMD))[1].readlines():
        # Match the regexs
        cstatus = c_status_re.match(line)
        if cstatus:
            non_optimal_status = 1 if (cstatus.group(1) != "Optimal") else 0
            continue
        ctemp = c_temp_re.match(line)
        if ctemp:
            card_overheating = 1 if (ctemp.group(2) != "(Normal)") else 0
            centigrade = int(ctemp.group(1))
        cdefunct = c_defunct_re.match(line)
        if cdefunct:
            defunct_drives = int(cdefunct.group(1))
            continue
        cdegraded = c_degraded_re.match(line)
        if cdegraded:
            num_logical_groups = int(cdegraded.group(1))
            in_degraded_state = int(cdegraded.group(2))
            in_failed_state = int(cdegraded.group(3))
            continue
        bstatus = b_status_re.match(line)
        if bstatus:
            if (bstatus.group(1) != "Optimal"
            and bstatus.group(1) != "Charging"
            and bstatus.group(1) != "ZMM Optimal"):
                battery_problems = 1
            continue
        btemp = b_temp_re.match(line)
        if btemp:
            if (btemp.group(1) != "No"):
                battery_problems = 1
            continue
        bcapacity = b_capacity_re.match(line)
        if bcapacity:
            battery_percent = int(bcapacity.group(1))
            continue
        btime = b_time_re.match(line)
        if btime:
            battery_minutes = int(btime.group(1)) * 1440 + int(btime.group(2)) * 60 + int(btime.group(3))
            if (battery_minutes < 1500): # Below 1 day time remaining, reverts to write-through.
                battery_problems = 1
            continue

        lwritecache = l_writecache_re.match(line)
        if lwritecache:
            in_write_through_mode += 1 if (lwritecache.group(1) != "Enabled (write-back)") else 0
            continue
        lfailedstripes = l_failedstripes_re.match(line)
        if lfailedstripes:
            containing_bad_stripes += 1 if (lfailedstripes.group(1) != "No") else 0
            continue

        pharddrive = p_harddrive_re.match(line)
        if pharddrive:
            num_physical_drives += 1
            continue
        pstate = p_state_re.match(line)
        if pstate:
            in_abnormal_state += 1 if (pstate.group(1) != "Online" and pstate.group(1) != "Hot Spare") else 0
            continue
        pwritecache = p_writecache_re.match(line)
        if pwritecache:
            in_write_back_mode += 1 if (pwritecache.group(1) != "Disabled (write-through)") else 0
            continue

# /usr/StorMan/arcconf GETLOGS 1 DEVICE TABULAR
#       driveErrorEntry                            
#           deviceID ....................................... 3
#           hwErrors ....................................... 0
#           mediumErrors ................................... 1
#           smartWarning ................................... 0

    # Initialize arrays because an empty driveErrorEntry won't appear
    hardware_errors = array.array('i',(0,)*num_physical_drives)
    medium_errors = array.array('i',(0,)*num_physical_drives)
    smart_warnings = array.array('i',(0,)*num_physical_drives)

    device_id = None

    for line in os.popen4('%s GETLOGS 1 DEVICE TABULAR' % (ARCCONF_CMD))[1].readlines():
        # Match the regexs
        pdeviceid = p_deviceid_re.match(line)
        if pdeviceid:
            device_id = int(pdeviceid.group(1))
            continue
        phwerrors = p_hwerrors_re.match(line)
        if phwerrors:
            hardware_errors[device_id] = int(phwerrors.group(1))
            continue
        pmediumerrors = p_mediumerrors_re.match(line)
        if pmediumerrors:
            medium_errors[device_id] = int(pmediumerrors.group(1))
            continue
        psmartwarning = p_smartwarning_re.match(line)
        if psmartwarning:
            smart_warnings[device_id] = int(psmartwarning.group(1))
            continue

    # send high-level values as ...raid-controller.gauge-status_not_optimal
    dispatch_value(non_optimal_status, 'controller', 'gauge', 'non_optimal_status')
    dispatch_value(card_overheating, 'controller', 'gauge', 'card_overheating')
    dispatch_value(defunct_drives, 'controller', 'gauge', 'defunct_drives')
    dispatch_value(battery_problems, 'controller', 'gauge', 'battery_problems')

    dispatch_value(centigrade, 'controller', 'temperature', 'centigrade')
    dispatch_value(battery_percent, 'controller', 'charge', 'battery_percent')
    dispatch_value(battery_minutes, 'controller', 'charge', 'battery_minutes')

    dispatch_value(num_logical_groups, 'arrays', 'current', 'num_logical_groups')
    dispatch_value(in_degraded_state, 'arrays', 'gauge', 'in_degraded_state')
    dispatch_value(in_failed_state, 'arrays', 'gauge', 'in_failed_state')
    dispatch_value(in_write_through_mode, 'arrays', 'gauge', 'in_write_through_mode')
    dispatch_value(containing_bad_stripes, 'arrays', 'gauge', 'containing_bad_stripes')

    dispatch_value(num_physical_drives, 'drives', 'current', 'num_physical_drives')
    dispatch_value(in_abnormal_state, 'drives', 'gauge', 'in_abnormal_state')
    dispatch_value(in_write_back_mode, 'drives', 'gauge', 'in_write_back_mode')

    for index, item in enumerate(hardware_errors):
        dispatch_value(item, 'hd%d' % (index), 'current', 'hardware_errors')
    for index, item in enumerate(medium_errors):
        dispatch_value(item, 'hd%d' % (index), 'current', 'medium_errors')
    for index, item in enumerate(smart_warnings):
        dispatch_value(item, 'hd%d' % (index), 'current', 'smart_warnings')

# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(read_callback)
