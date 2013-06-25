include_recipe "build-essential"

if node["platform_family"] == "rhel" && node["platform_version"].to_i > 5
  %w{ perl-ExtUtils-Embed perl-ExtUtils-MakeMaker }.each do |pkg|
    package pkg
  end
end

if node["collectd"]["plugins"]
  plugins = node["collectd"]["plugins"]
  plugin_support_packages = []
  plugin_enable_features = []

  case node["platform_family"]
  when "rhel"
    # include_recipe "yum::epel"

    plugin_support_packages << "ganglia-devel" if plugins.include?("ganglia")
    plugin_support_packages << "libcurl-devel" if plugins.include?("apache") ||
      plugins.include?("ascent") ||
      plugins.include?("curl") ||
      plugins.include?("nginx") ||
      plugins.include?("write_http")
    plugin_support_packages << "libesmtp-devel" if plugins.include?("notify_email")
    plugin_support_packages << "libgcrypt-devel" if plugins.include?("network")
    plugin_support_packages << "libmemcached-devel" if plugins.include?("memcached")
    plugin_support_packages << "liboping-devel" if plugins.include?("ping")
    plugin_support_packages << "libpcap-devel" if plugins.include?("dns")
    plugin_support_packages << "libvirt-devel" if plugins.include?("virt")
    plugin_support_packages << "libxml2-devel" if plugins.include?("ascent") ||
      plugins.include?("virt")
    plugin_support_packages << "mysql-devel" if plugins.include?("mysql")
    plugin_support_packages << "perl-devel" if plugins.include?("perl")
    #plugin_support_packages << "postgresql-devel" if plugins.include?("postgresql")
    plugin_enable_features << "--enable-postgresql" if plugins.include?("postgresql")
    plugin_support_packages << "python-devel" if plugins.include?("python")
    plugin_enable_features << "--enable-python" if plugins.include?("python")
    plugin_support_packages << "rrdtool-devel" if plugins.include?("rrdcached") ||
      plugins.include?("rrdtool")
    plugin_support_packages << "varnish-libs-devel" if plugins.include?("varnish")
    plugin_support_packages << "yajl-devel" if plugins.include?("curl_json")
  when "debian"
    plugin_support_packages << "libcurl4-openssl-dev" if plugins.include?("apache") ||
      plugins.include?("ascent") ||
      plugins.include?("curl") ||
      plugins.include?("nginx") ||
      plugins.include?("write_http")
    plugin_support_packages << "libesmtp-dev" if plugins.include?("notify_email")
    plugin_support_packages << "libganglia1" if plugins.include?("ganglia")
    plugin_support_packages << "libgcrypt11-dev" if plugins.include?("network")
    plugin_support_packages << "libmemcached-dev" if plugins.include?("memcached")
    plugin_support_packages << "libmysqlclient-dev" if plugins.include?("mysql")
    plugin_support_packages << "liboping-dev" if plugins.include?("ping")
    plugin_support_packages << "libpcap0.8-dev" if plugins.include?("dns")
    plugin_support_packages << "libperl-dev" if plugins.include?("perl")
    plugin_support_packages << "librrd-dev" if plugins.include?("rrdcached") ||
      plugins.include?("rrdtool")
    plugin_support_packages << "libvirt-dev" if plugins.include?("virt")
    plugin_support_packages << "libxml2-dev" if plugins.include?("ascent") ||
      plugins.include?("virt")
    plugin_support_packages << "libyajl-dev" if plugins.include?("curl_json")
  end

  plugin_support_packages.each do |pkg|
    package pkg
  end
end

bash "install-collectd" do
  #cwd Chef::Config[:file_cache_path]
  cwd "/usr/local/src"
  # We must build in support for some plugins, determined above and stored in
  # the plugin_enable_features array.
  code <<-EOH
    # See the remote_file resource below for collectd-*.tar.gz and
    # a comment about how to pre-download and data_bags/collectd.install.json
    #tar -xzf collectd-#{node["collectd"]["version"]}.tar.gz
    tar -zxf #{Chef::Config[:file_cache_path]}/collectd-#{node["collectd"]["version"]}.tar.gz
    # Note the CPPFLAGS and LDFLAGS are needed to --enable-postgresql in the build.
    (cd collectd-#{node["collectd"]["version"]} && CPPFLAGS=-I/usr/pgsql-9.2/include LDFLAGS=-L/usr/pgsql-9.2/lib ./configure --prefix=#{node["collectd"]["dir"]} #{plugin_enable_features.join(' ')} && make && make install)
  EOH
  #action :nothing
  notifies :restart, "service[collectd]"
  action :run
  # This will build a new version, or you can force a rebuild by removing
  # the /opt/collectd/sbin/collectd executable.
  not_if "#{node["collectd"]["dir"]}/sbin/collectd -h 2>&1 | grep #{node["collectd"]["version"]}"
end

# Note this compares the checksum of the /var/chef-solo/collectd-*.tar.gz
# with the data_bags/collectd.json attribute, and will only attempt a
# download if the checksum is incorrect. Since www.collectd.org is
# refusing chef downloads because it was being overloaded, we must
# pre-download the tarball. For example,
#   curl --url http://www.collectd.org/files/collectd-5.3.0.tar.gz \
#        --output /var/chef-solo/collectd-5.3.0.tar.gz
remote_file "#{Chef::Config[:file_cache_path]}/collectd-#{node["collectd"]["version"]}.tar.gz" do
  source node["collectd"]["url"]
  checksum node["collectd"]["checksum"]
  notifies :run, "bash[install-collectd]", :immediately
  action :create_if_missing
end

template "/etc/init.d/collectd" do
  mode "0766"
  case node["platform_family"]
  when "rhel"
    source "collectd.init-rhel.erb"
  else
    source "collectd.init.erb"
  end
  variables(
    :dir => node["collectd"]["dir"]
  )
  notifies :restart, "service[collectd]"
end

template "#{node["collectd"]["dir"]}/etc/collectd.conf" do
  mode "0644"
  source "collectd.conf.erb"
  variables(
    :name         => node["collectd"]["name"],
    :dir          => node["collectd"]["dir"],
    :interval     => node["collectd"]["interval"],
    :read_threads => node["collectd"]["read_threads"],
    :plugins      => node["collectd"]["plugins"]
  )
  notifies :restart, "service[collectd]"
end

directory "#{node["collectd"]["dir"]}/etc/conf.d" do
  action :create
end

directory "#{node["collectd"]["dir"]}/lib/collectd/python" do
  action :create
end

cookbook_file "#{node["collectd"]["dir"]}/lib/collectd/python/raid.py" do
  source "raid.py"
  mode "0644"
  owner "root"
  group "root"
  notifies :restart, "service[collectd]"
end

cookbook_file "#{node["collectd"]["dir"]}/lib/collectd/python/smartctl.py" do
  source "smartctl.py"
  mode "0644"
  owner "root"
  group "root"
  notifies :restart, "service[collectd]"
end

cookbook_file "#{node["collectd"]["dir"]}/lib/collectd/python/diskstats.py" do
  source "diskstats.py"
  mode "0644"
  owner "root"
  group "root"
  notifies :restart, "service[collectd]"
end

service "collectd" do
  supports :status => true, :restart => true
  action [ :enable, :start ]
end
