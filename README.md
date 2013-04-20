# collectd [![Build Status](https://secure.travis-ci.org/hectcastro/chef-collectd.png?branch=master)](http://travis-ci.org/hectcastro/chef-collectd)

## Description

Installs and configures collectd.  Much of the work in this cookbook reflects
work done by [coderanger](https://github.com/coderanger/chef-collectd)
and [realityforge](https://github.com/realityforge-cookbooks/collectd).

This DonorsChoose/chef-collectd forked repo has been modified to support
postgresql and python customizable plugins. In particular, the source build
needed to --enable-postgresql and --enable-python, in an environment that has
a PGDG install of postgresql-devel package, not the CentOS package.

## Requirements

### Platforms

* Amazon 2012.09
* RedHat 6.3 (Santiago)
* Ubuntu 12.04 (Precise)

### Cookbooks

* build-essential
* yum

## Attributes

* `node["collectd"]["version"]` - Version of collectd to install.
* `node["collectd"]["dir"]` - Base directory for collectd.
* `node["collectd"]["url"]` - URL to the collectd archive.
* `node["collectd"]["checksum"]` - Checksum for the collectd archive.
* `node["collectd"]["interval"]` - Number of seconds to wait between data reads.
* `node["collectd"]["read_threads"]` - Number of threads performing data reads.
* `node["collectd"]["name"]` - Name of the node reporting statstics.
* `node["collectd"]["plugins"]` - Mash of plugins for installation.
* `node["collectd"]["graphite_role"]` – Role assigned to Graphite server for search.
* `node["collectd"]["graphite_ipaddress"]` – IP address to Graphite server if you're
  trying to target one that isn't searchable.

* `node["collectd"]["packages"]` – List of collectd packages.

## Recipes

* `recipe[collectd]` will install collectd from source.
* `recipe[collectd::attribute_driven]` will install collectd via node attributes.
* `recipe[collectd::packages]` will install collectd (and other plugins) from
  packages.
* `recipe[collectd::recompile]` will attempt to recompile collectd.

## Usage

In order to configure collectd via attributes, setup your roles like the following:

    default_attributes(
      "collectd" => {
        "plugins" => {
          "syslog" => {
            "config" => { "LogLevel" => "Info" }
          },
          "disk"      => { },
          "swap"      => { },
          "memory"    => { },
          "cpu"       => { },
          "interface" => {
            "config" => { "Interface" => "lo", "IgnoreSelected" => true }
          },
          "df"        => {
            "config" => {
              "ReportReserved" => false,
              "FSType" => [ "proc", "sysfs", "fusectl", "debugfs", "devtmpfs", "devpts", "tmpfs" ],
              "IgnoreSelected" => true
            }
          },
          "write_graphite" => {
            "config" => {
              "Prefix" => "servers."
            }
          }
        }
      }
    )

### Postgresql Plugin

DonorsChoose.org has added a number of customized <Query> blocks to collect
metrics directly from the running database cluster. 

Cluster-level metrics should probably only be applied to the "postgres"
maintenance database, since these would gather identical metrics from
all other database instances in the cluster. This should be done in the
`/var/chef-solo/roles/PGSQL.rb` file:

    default_attributes({
      "collectd" => {
        "plugins" => {
          "postgresql" => {
            "template" => "postgresql.conf.erb",
            "config" => {
              "postgres" => {
                "Host" => "localhost",
                "Port" => "5432",
                "User" => "postgres",
                "Query" => [
                # Home-grown cookbooks/collectd/templates/default/postgresql.conf.erb queries:

                  # PostgreSQL configuration settings.
                  # (current-setting-* for 48 interesting postgresql.conf settings)
                  "config_settings",

                  # PostgreSQL transaction log: Log segments.
                  # Copied from the munin monitoring tool:
                  # http://munin-monitoring.org/browser/munin/plugins/node.d/postgres_xlog.in
                  # (files-* for log-segments)
                  "xlog",

                  # PostgreSQL bgwriter and checkpoints buffer statistics.
                  # Copied from a couple munin monitoring tools:
                  # http://munin-monitoring.org/browser/munin/plugins/node.d/postgres_bgwriter.in
                  # http://munin-monitoring.org/browser/munin/plugins/node.d/postgres_checkpoints.in
                  # (total_time_in_ms-* for checkpoint_write and checkpoint_sync,
                  #  operations-* for checkpoints_timed, checkpoints_req and maxwritten_clean,
                  #  pg_blks-* for bgwriter_checkpoint, bgwriter_clean, bgwriter_backend,
                  #                bgwriter_backend_fsync and bgwriter_alloc)
                  "bgwriter"
                ]
              }
            }
          }
        }
      }
    })

Database-level metrics should probably be applied to every application
specific database instance in the cluster. This should be done in the
`/var/chef-solo/nodes/*.json` file for each server node, since each has
a specific set of schemas in the cluster:

    {
      "collectd": {
        "plugins": {
          "postgresql": {
            "config": {
              "dc_prod": { // One of these for each schema
                "Host": "localhost",
                "Port": "5432",
                "User": "postgres",
                "Query": [
                // Home-grown cookbooks/collectd/templates/default/postgresql.conf.erb queries:

                  // number of backends, with counts of various states and longest duration
                  // (current-count-* for active, blocked, idleinxact and notinuse,
                  //  current-longest-* for active, blocked, idleinxact and notinuse,
                  //  current-oldest-* for connection and notinuse)
                  "activity",

                  // PostgreSQL lock contention
                  // (gauge-locks-* for granted and waiting)
                  "locks",

                // Built-in /opt/collectd/share/collectd/postgresql_default.conf queries:

                  // numbers of committed and rolled-back transactions of the user tables
                  // (pg_xact-* for commit and rollback)
                  "transactions",

                  // numbers of various table modifications (i. e. insertions, updates, deletions) of the user tables
                  // (pg_n_tup_c-* for ins, upd, del and hot_upd)
                  "queries",

                  // numbers of various table scans and returned tuples of the user tables
                  // (pg_scan-* for seq, seq_tup_read, idx and idx_tup_fetch)
                  "query_plans",

                  // numbers of live and dead rows in the user tables
                  // (pg_n_tup_g-* for live and dead)
                  "table_states",

                  // disk block access counts for user tables
                  // (pg_blks-* for heap_read, heap_hit, idx_read, idx_hit,
                  //                toast_read, toast_hit, tidx_read and tidx_hit)
                  "disk_io",

                  // on-disk size of the database in bytes
                  // (pg_db_size)
                  "disk_usage"
                ]
              }
            }
          }
        }
      }
    }
